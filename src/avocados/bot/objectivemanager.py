from collections.abc import Iterator
from time import perf_counter
from typing import Optional, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId

from avocados.core.constants import ALTERNATIVES, TRAINERS, WORKER_TYPE_IDS
from avocados.core.manager import BotManager
from avocados.bot.objective import (Objective, ObjectiveStatus, ObjectiveRequirementType, ObjectiveRequirements,
                                    ObjectiveDependencies,
                                    UnitObjective, ResearchObjective, AttackObjective,
                                    DefenseObjective, ConstructionObjective, WorkerObjective, SupplyObjective,
                                    ExpansionObjective)
from avocados.geometry.util import squared_distance, get_best_score, Area
from avocados.combat.squad import SquadDefendTask, SquadAttackTask, SquadStatus
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class ObjectiveManager(BotManager):
    completed: dict[int, Objective]
    current: dict[int, Objective]
    future: dict[int, Objective]
    # Persistent objectives
    worker_objective: Optional[WorkerObjective]
    supply_objective: Optional[SupplyObjective]
    expansion_objective: Optional[ExpansionObjective]

    def __init__(self, bot: 'AvocaDOS', objectives: Optional[dict[int, Objective]] = None) -> None:
        super().__init__(bot)
        self.completed = {}
        self.current = {}
        self.future = objectives or {}
        self.worker_objective = None
        self.supply_objective = None
        self.expansion_objective = None

    def add(self, objective: Objective) -> int:
        self.logger.info("Adding new objective: {}", objective)
        self.future[objective.id] = objective
        return objective.id

    def set_worker_objective(self, number: int = 1, **kwargs) -> int:
        self.worker_objective = WorkerObjective(self.bot, number, **kwargs)
        return self.add(self.worker_objective)

    def set_supply_objective(self, number: int = 1, **kwargs) -> int:
        self.supply_objective = SupplyObjective(self.bot, number, **kwargs)
        return self.add(self.supply_objective)

    def set_expansion_objective(self, number: int, position: Optional[ExpansionLocation] = None, **kwargs) -> int:
        self.expansion_objective = ExpansionObjective(self.bot, number=number, position=position, **kwargs)
        return self.add(self.expansion_objective)

    def add_construction_objective(self, utype: UnitTypeId, number: int = 1, **kwargs) -> int:
        objective = ConstructionObjective(self.bot, utype, number, **kwargs)
        return self.add(objective)

    def add_unit_objective(self, utype: UnitTypeId, number: int = 1, **kwargs) -> int:
        objective = UnitObjective(self.bot, utype, number, **kwargs)
        return self.add(objective)

    def add_attack_objective(self, target: Area, strength: float = 100, **kwargs) -> int:
        objective = AttackObjective(self.bot, target, strength, **kwargs)
        return self.add(objective)

    def add_defense_objective(self, target: Area, strength: float = 100, **kwargs) -> int:
        objective = DefenseObjective(self.bot, target, strength, **kwargs)
        return self.add(objective)

    def objectives_of_type[T: Objective](self, objective_type: type[T]) -> list[T]:
        return [obj for obj in self.current.values() if isinstance(obj, objective_type)]

    def __bool__(self) -> bool:
        return bool(self.current)

    def __iter__(self) -> Iterator[Objective]:
        yield from sorted(self.current.values(), key=lambda obj: obj.priority, reverse=True)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        for obj in self:
            await self._dispatch_objective(obj)

        # TODO: Move below to on_step_started?
        for obj in self.current.copy().values():
            if obj.status in {ObjectiveStatus.COMPLETED, ObjectiveStatus.FAILED}:
                self.current.pop(obj.id)
                self.completed[obj.id] = obj
                self.logger.debug("Finished {} with status {}", obj, obj.status)
                if obj.repeat:
                    self.add(obj.copy(status=ObjectiveStatus.NOT_STARTED))

        for obj in self.future.copy().values():
            if self._task_ready(obj):
                obj = self.future.pop(obj.id)
                obj.status = ObjectiveStatus.STARTED
                self.current[obj.id] = obj
                self.logger.debug("Started {}", obj)
        self.timings['step'].add(t0)

    def get_status(self, objective_id: int) -> Optional[ObjectiveStatus]:
        if objective_id in self.current:
            return self.current[objective_id].status
        if objective_id in self.future:
            return self.future[objective_id].status
        if objective_id in self.completed:
            return self.completed[objective_id].status
        self.logger.warning(f"Unknown objective ID: {objective_id}")
        return None

    def _requirements_fulfilled(self, requirements: ObjectiveRequirements) -> bool:
        fulfilled = True
        for req_type, req_value in requirements:
            if isinstance(req_type, UnitTypeId):
                value = self.bot.forces(req_type).ready.amount
            elif isinstance(req_type, UpgradeId):
                value = req_type in self.api.state.upgrades
            elif req_type == ObjectiveRequirementType.TIME:
                value = self.api.time
            elif req_type == ObjectiveRequirementType.SUPPLY:
                value = self.api.supply_used
            elif req_type == ObjectiveRequirementType.MINERALS:
                value = self.api.minerals
            elif req_type == ObjectiveRequirementType.VESPENE:
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
        completed = False
        if isinstance(objective, UnitObjective):
            if self.step % 2 == 0:
                completed = await self._unit_objective(objective)
        elif isinstance(objective, (ConstructionObjective, SupplyObjective)):
            #if self.step % 2 == 0:
            completed = await self._construction_objective(objective)
        elif isinstance(objective, ResearchObjective):
            #if self.step % 2 == 0:
            completed = self._research_objective(objective)
        elif isinstance(objective, (AttackObjective, DefenseObjective)):
            if self.step % 4 == 0:
                completed = self._squad_objective(objective)
        else:
            self.log.error("ObjectiveNotImplemented-{}", objective)
        if completed:
            objective.mark_complete()
        return completed

    async def _construction_objective(self, objective: ConstructionObjective | SupplyObjective) -> bool:
        utype = ALTERNATIVES.get(objective.utype, objective.utype)
        units = self.bot.forces(utype).ready

        if objective.position is not None:
            units = units.filter(lambda u: u.position in objective.position)
        if units.amount >= objective.number:
            return True

        pending = int(self.api.already_pending(objective.utype))
        to_build = objective.number - units.amount - pending

        trainer_utype = TRAINERS.get(objective.utype)
        if trainer_utype is None:
            self.log.error("MissingTrainer{}", objective.utype)
            return False

        if trainer_utype not in WORKER_TYPE_IDS:
            self.log.error("TrainerNotWorker{}", objective.utype)
            return False

        time_for_tech = self.ext.time_until_tech(objective.utype)
        #self.logger.debug("Time for tech: {}", time_for_tech)
        if time_for_tech >= 60.0:
            return False

        for _ in range(to_build):
            wrapped_target = await self.building.get_building_location(
                objective.utype, area=objective.position, include_addon=getattr(objective, 'include_addon', True))
            #position = task.position
            if wrapped_target is None:
                self.log.warning("NoLocFound_{}_{}", objective.utype, objective.position)
                break
            # SCV can start constructing from a distance of 2.5 away
            worker, travel_time = await self.bot.pick_worker(wrapped_target.value, target_distance=2.5)
            if not worker:
                break

            orphaned = (self.api.structures_without_construction_SCVs.of_type(objective.utype)
                        .filter(lambda unit: objective.position is None or unit.position in objective.position))
            if orphaned:
                self.order.smart(worker.access(), target=orphaned.random)

            elif (time_for_tech == 0
                    and self.resources.can_afford(objective.utype)
                    and worker.value.distance_to(wrapped_target.value) <= 2.5):
                self.logger.trace("{}: ordering worker {} build {} at {}", objective, worker, objective.utype.name, wrapped_target.value)
                self.order.build(worker.access(), objective.utype, wrapped_target.access())

            elif time_for_tech <= travel_time:
                resource_time = self.resources.can_afford_in(objective.utype, excluded_workers=worker.value)
                #self.logger.debug("{}: resource_time={:.2f}, travel_time={:.2f}", objective, resource_time, travel_time)
                if resource_time <= travel_time:
                    #self.logger.trace("{}: send it", task)
                    self.order.move(worker.access(), wrapped_target.access())
                    self.resources.reserve(objective.utype)

        return False

    async def _unit_objective(self, objective: UnitObjective) -> bool:
        utype = ALTERNATIVES.get(objective.utype, objective.utype)
        units = self.bot.forces(utype).ready
        #self.logger.trace("Have {} units of type {}", units.amount, task.utype.name)
        #self.logger.trace("units for {}: {}", task, units)
        if objective.position is not None:
            units = units.filter(lambda u: u.position in objective.position)
            #self.logger.trace("Have {} units of type {} within range of {}",
            #                  units.amount, task.utype.name, task.max_distance)
        #self.logger.trace("units for {} within {}: {}", task, task.position, units)
        if units.amount >= objective.number:
            return True

        pending = int(self.api.already_pending(objective.utype))
        to_build = objective.number - units.amount - pending

        # trainer_utype = TRAINERS.get(objective.utype)
        # if trainer_utype is None:
        #     self.logger.error("No trainer for {}", objective.utype)

        for _ in range(to_build):
            trainer = self.bot.pick_trainer(objective.utype)
            if trainer is None:
                break
            time_for_tech = self.ext.time_until_tech(objective.utype)
            time_for_resources = self.resources.can_afford_in(objective.utype)
            if time_for_tech == 0 and time_for_resources == 0:
                self.order.train(trainer, objective.utype)
                self.logger.debug("Training {} at {}", objective.utype, trainer)
            elif time_for_tech <= time_for_resources:
                self.resources.reserve(objective.utype)
        return False

    def _research_objective(self, objective: ResearchObjective) -> bool:
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

    def _squad_objective(self, objective: AttackObjective | DefenseObjective) -> bool:
        task_type = SquadAttackTask if isinstance(objective, AttackObjective) else SquadDefendTask
        squads_with_task = self.squads.with_task(
            task_type, filter_=lambda t: squared_distance(t.target.center, objective.target.center) <= 1)

        if (objective.duration is not None and any(s.status == SquadStatus.AT_TARGET
                                                   and self.time > s.status_changed + objective.duration
                                                   for s in squads_with_task)):
        # TODO
        # if (len(self.api.all_enemy_units.filter(lambda u: u in objective.target)) == 0
        #         and max(self.intel.last_visible[objective.target.to_region()].values()) < 20.0):

            # Objective complete
            for s in squads_with_task:
                s.remove_task()
            return True

        total_strength = round(sum(s.strength for s in squads_with_task), 2)
        missing_strength = round(objective.strength - total_strength, 2)
        # Enough squad(s) working on it
        if missing_strength <= 0:
            return False

        # Find best squad or create new
        if squads_with_task:
            closest_squad = get_best_score(squads_with_task, lambda s: s.center.distance_to(objective.target.center),
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
            units = self.bot.pick_army(strength=missing_strength, position=objective.target.center,
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
