import math
from collections.abc import Iterator
from time import perf_counter
from typing import Optional, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.units import Units

from avocados.core.constants import ALTERNATIVES, TRAINERS
from avocados.core.manager import BotManager
from avocados.core.objective import (Objective, TaskStatus, TaskRequirementType, TaskRequirements, ObjectiveDependencies,
                                     BuildingCountObjective, UnitCountObjective, ResearchObjective, AttackObjective, DefenseObjective)
from avocados.core.geomutil import squared_distance, get_best_score
from avocados.micro.squad import SquadDefendTask, SquadAttackTask, SquadStatus

if TYPE_CHECKING:
    from .avocados import AvocaDOS


class ObjectiveManager(BotManager):
    completed: dict[int, Objective]
    current: dict[int, Objective]
    future: dict[int, Objective]

    def __init__(self, bot: 'AvocaDOS', objectives: Optional[dict[int, Objective]] = None) -> None:
        super().__init__(bot)
        self.completed = {}
        self.current = {}
        self.future = objectives or {}

    def add(self, objective: Objective) -> int:
        self.future[objective.id] = objective
        return objective.id

    def add_unit_count_objective(self, utype: UnitTypeId, number: int = 1, **kwargs) -> int:
        objective = UnitCountObjective(self.bot, utype, number, **kwargs)
        return self.add(objective)

    def add_attack_objective(self, target: Point2, strength: float = 100, **kwargs) -> int:
        objective = AttackObjective(self.bot, target, strength, **kwargs)
        return self.add(objective)

    def add_defense_objective(self, target: Point2, strength: float = 100, **kwargs) -> int:
        objective = DefenseObjective(self.bot, target, strength, **kwargs)
        return self.add(objective)

    def objectives_of_type(self, objective_type: type[Objective] | tuple[type[Objective], ...]) -> list[Objective]:
        return [obj for obj in self.current.values() if isinstance(obj, objective_type)]

    def __bool__(self) -> bool:
        return bool(self.current)

    def __iter__(self) -> Iterator[Objective]:
        yield from sorted(self.current.values(), key=lambda obj: obj.priority, reverse=True)

    async def on_step(self, step: int) -> None:
        for obj in self:
            await self._dispatch_objective(obj)

        # TODO: Move below to on_step_started?
        for obj in self.current.copy().values():
            if obj.status == TaskStatus.COMPLETED:
                self.current.pop(obj.id)
                self.completed[obj.id] = obj
                self.logger.debug("Completed {}", obj)
                if obj.repeat:
                    self.add(obj.copy(status=TaskStatus.NOT_STARTED))

        for obj in self.future.copy().values():
            if self._task_ready(obj):
                obj = self.future.pop(obj.id)
                obj.status = TaskStatus.STARTED
                self.current[obj.id] = obj
                self.logger.debug("Started {}", obj)

    def get_status(self, objective_id: int) -> Optional[TaskStatus]:
        if objective_id in self.current:
            return self.current[objective_id].status
        if objective_id in self.future:
            return self.future[objective_id].status
        if objective_id in self.completed:
            return self.completed[objective_id].status
        self.logger.warning(f"Unknown objective ID: {objective_id}")
        return None

    def _requirements_fulfilled(self, requirements: TaskRequirements) -> bool:
        fulfilled = True
        for req_type, req_value in requirements:
            if isinstance(req_type, UnitTypeId):
                value = self.bot.forces(req_type).ready.amount
            elif isinstance(req_type, UpgradeId):
                value = req_type in self.api.state.upgrades
            elif req_type == TaskRequirementType.TIME:
                value = self.api.time
            elif req_type == TaskRequirementType.SUPPLY:
                value = self.api.supply_used
            elif req_type == TaskRequirementType.MINERALS:
                value = self.api.minerals
            elif req_type == TaskRequirementType.VESPENE:
                value = self.api.vespene
            else:
                self.logger.warning(f"Unknown requirement: {req_type}")
                continue
            if isinstance(value, bool):
                fulfilled = value == req_value and fulfilled
            else:
                fulfilled = value >= req_value and fulfilled
        return fulfilled

    def _dependencies_fulfilled(self, dependencies: ObjectiveDependencies) -> bool:
        return all(self.get_status(dep) in {status, None} for dep, status in dependencies.items())

    def _task_ready(self, objective: Objective) -> bool:
        return self._dependencies_fulfilled(objective.deps) and self._requirements_fulfilled(objective.reqs)

    async def _dispatch_objective(self, objective: Objective) -> bool:
        t0 = perf_counter()
        if isinstance(objective, UnitCountObjective):
            completed = await self._on_unit_count_objective(objective)
        elif isinstance(objective, ResearchObjective):
            completed = self._on_research_objective(objective)
        elif isinstance(objective, (AttackObjective, DefenseObjective)):
            completed = self._on_squad_objective(objective)
        else:
            self.logger.error("Not implemented: {}", objective)
            completed = False
        #if (time_ms := 1000 * (perf_counter() - t0)) > 5:
        #    self.logger.warning("{} took {:.3f} ms", task, time_ms)
        if completed:
            objective.mark_complete()
        return completed

    async def _on_build_objective(self, objective: BuildingCountObjective) -> bool:
        assigned = self.bot.units.tags_in(objective.assigned)
        if assigned:
            return False

        target = await self.building.get_building_location(objective.utype, near=objective.position,
                                                           max_distance=int(objective.max_distance))
        if target is None:
            return False
        position = target if isinstance(target, Point2) else target.position

        # SCV can start constructing from a distance of 2.5 away
        worker, travel_time = await self.bot.pick_worker(position, target_distance=2.5)
        if not worker:
            return False

        if self.bot.resources.can_afford(objective.utype) and worker.distance_to(target) <= 2.5:
            self.order.build(worker, objective.utype, target)
            self.mining.remove_worker(worker)  # TODO
        else:
            resource_time = self.bot.resources.can_afford_in(objective.utype, excluded_workers=worker)
            if resource_time <= travel_time:
                self.order.move(worker, position)
                self.mining.remove_worker(worker)  # TODO
                self.resources.reserve(objective.utype)
        objective.assigned.add(worker.tag)
        return False

    async def _on_unit_count_objective(self, objective: UnitCountObjective) -> bool:
        utype = ALTERNATIVES.get(objective.utype, objective.utype)
        units = self.bot.forces(utype).ready
        #self.logger.trace("Have {} units of type {}", units.amount, task.utype.name)
        #self.logger.trace("units for {}: {}", task, units)
        if objective.position is not None:
            units = units.closer_than(objective.max_distance, objective.position)
            #self.logger.trace("Have {} units of type {} within range of {}",
            #                  units.amount, task.utype.name, task.max_distance)
        #self.logger.trace("units for {} within {}: {}", task, task.position, units)
        if units.amount >= objective.number:
            return True

        pending = int(self.api.already_pending(objective.utype))
        to_build = objective.number - units.amount - pending

        trainer_utype = TRAINERS.get(objective.utype)
        if trainer_utype is None:
            self.logger.error("No trainer for {}", objective.utype)

        if trainer_utype == UnitTypeId.SCV:
            if self.api.tech_requirement_progress(objective.utype) < 1:
                #self.logger.debug("Tech requirements for {} not fulfilled", task.utype)
                return False

            for _ in range(to_build):
                wrapped_target = await self.building.get_building_location(objective.utype, near=objective.position,
                                                                   max_distance=objective.max_distance)
                #position = task.position
                if wrapped_target is None:
                    break
                # SCV can start constructing from a distance of 2.5 away
                worker, travel_time = await self.bot.pick_worker(wrapped_target.value, target_distance=2.5)
                if not worker:
                    break
                #worker = self.commander.workers.random
                #self.logger.trace("Found free worker: {} {}", worker, worker.orders[0])
                if self.resources.can_afford(objective.utype) and worker.distance_to(wrapped_target.value) <= 2.5:
                    #self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                    self.order.build(worker, objective.utype, wrapped_target.access())
                    self.mining.remove_worker(worker)     # TODO
                else:
                    resource_time = self.resources.can_afford_in(objective.utype, excluded_workers=worker)
                    #self.logger.debug("{}: resource_time={:.2f}, travel_time={:.2f}", objective, resource_time, travel_time)
                    if resource_time <= travel_time:
                        #self.logger.trace("{}: send it", task)
                        self.order.move(worker, wrapped_target.access())
                        self.mining.remove_worker(worker)  # TODO
                        self.resources.reserve(objective.utype)

        else:
            for _ in range(to_build):
                trainer = self.bot.pick_trainer(objective.utype)
                if trainer is None:
                    break
                if self.resources.can_afford(objective.utype):
                    self.order.train(trainer, objective.utype)
                else:
                    self.resources.reserve(objective.utype)
        return False

    def _on_research_objective(self, objective: ResearchObjective) -> bool:
        if objective.upgrade in self.api.state.upgrades:
            self.logger.trace("Upgrade {} complete", objective.upgrade)
            return True
        try:
            if self.api.already_pending_upgrade(objective.upgrade) > 0:
                #self.logger.trace("Upgrade {} already pending", task.upgrade)
                return False
        except Exception as exc:
            self.logger.error("EXCEPTION {}", str(exc))
        if not self.resources.can_afford(objective.upgrade):
            #self.logger.trace("Cannot afford {}", task.upgrade)
            return False
        researcher = self.bot.pick_researcher(objective.upgrade)
        if researcher is not None:
            self.order.upgrade(researcher, objective.upgrade)
            self.logger.info("Starting {} at {}", objective.upgrade.name, researcher)
        #else:
        #    self.logger.trace("No researcher for {}", task.upgrade)
        return False

    def _on_squad_objective(self, objective: AttackObjective | DefenseObjective) -> bool:
        task_type = SquadAttackTask if isinstance(objective, AttackObjective) else SquadDefendTask
        squads_with_task = self.squads.with_task(
            task_type, filter_=lambda t: squared_distance(t.target.center, objective.target) <= 1)

        if (objective.duration is not None and any(s.status == SquadStatus.AT_TARGET
                                                   and self.time > s.status_changed + objective.duration
                                                   for s in squads_with_task)):
            # Objective complete
            for s in squads_with_task:
                s.remove_task()
            return True

        total_strength = sum(s.strength for s in squads_with_task)
        missing_strength = objective.strength - total_strength
        # Enough squad(s) working on it
        if missing_strength <= 0:
            return False

        # Find best squad or create new
        if squads_with_task:
            closest_squad = get_best_score(squads_with_task, lambda s: s.center.distance_to(objective.target),
                                           highest=False)[0]
            # Create new squad and order to join
            units = self.bot.pick_army(strength=missing_strength, position=closest_squad.center,
                                       max_priority=objective.priority)
            if len(units) < objective.minimum_size:
                return False
            squad = self.squads.create(units, remove_from_squads=True)
            squad.join(closest_squad, priority=objective.priority)
        else:
            # Create new squad
            units = self.bot.pick_army(strength=missing_strength, position=objective.target,
                                       max_priority=objective.priority)
            if len(units) < objective.minimum_size:
                return False
            squad = self.squads.create(units, remove_from_squads=True)
            if isinstance(objective, AttackObjective):
                squad.attack(objective.target, priority=objective.priority)
            elif isinstance(objective, DefenseObjective):
                squad.defend(objective.target, priority=objective.priority)
            else:
                self.log.error("Unknown objective type: {}", objective)
                return False

        return False
