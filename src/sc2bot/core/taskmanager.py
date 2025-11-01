import math
from collections.abc import Iterator
from time import perf_counter
from typing import Optional, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2

from .constants import ALTERNATIVES, TRAINERS
from .botobject import BotObject
from .tasks import (Task, TaskStatus, TaskRequirementType, TaskRequirements, TaskDependencies, BuildingCountTask,
                    UnitCountTask, ResearchTask, AttackTask, DefenseTask)
from ..micro.squad import SquadDefendTask, SquadAttackTask, Squad

if TYPE_CHECKING:
    from .avocados import AvocaDOS


class TaskManager(BotObject):
    completed: dict[int, Task]
    current: dict[int, Task]
    future: dict[int, Task]

    def __init__(self, bot: 'AvocaDOS', tasks: Optional[dict[int, Task]] = None) -> None:
        super().__init__(bot)
        self.completed = {}
        self.current = {}
        self.future = tasks or {}

    def add(self, task: Task) -> int:
        self.future[task.id] = task
        return task.id

    def __bool__(self) -> bool:
        return bool(self.current)

    def __iter__(self) -> Iterator[Task]:
        yield from sorted(self.current.values(), key=lambda task: task.priority, reverse=True)

    async def on_step(self, step: int) -> None:
        for task in self:
            await self._dispatch_task(task)

        for task in self.current.copy().values():
            if task.status == TaskStatus.COMPLETED:
                self.current.pop(task.id)
                self.completed[task.id] = task
                self.logger.debug("Completed {}", task)
                if task.repeat:
                    self.add(task.copy(status=TaskStatus.NOT_STARTED))

        for task in self.future.copy().values():
            if self._task_ready(task):
                task = self.future.pop(task.id)
                task.status = TaskStatus.STARTED
                self.current[task.id] = task
                self.logger.debug("Started {}", task)

    def get_status(self, task_id: int) -> Optional[TaskStatus]:
        if task_id in self.current:
            return self.current[task_id].status
        if task_id in self.future:
            return self.future[task_id].status
        if task_id in self.completed:
            return self.completed[task_id].status
        self.logger.warning(f"Unknown task id: {task_id}")
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

    def _dependencies_fulfilled(self, dependencies: TaskDependencies) -> bool:
        return all(self.get_status(dep) in {status, None} for dep, status in dependencies.items())

    def _task_ready(self, task: Task) -> bool:
        return self._dependencies_fulfilled(task.deps) and self._requirements_fulfilled(task.reqs)

    async def _dispatch_task(self, task: Task) -> bool:
        t0 = perf_counter()
        if isinstance(task, UnitCountTask):
            completed = await self._on_unit_count_task(task)
        elif isinstance(task, ResearchTask):
            completed = self._on_research_task(task)
        elif isinstance(task, (AttackTask, DefenseTask)):
            completed = self._on_squad_task(task)
        else:
            self.logger.error("Not implemented: {}", task)
            completed = False
        #if (time_ms := 1000 * (perf_counter() - t0)) > 5:
        #    self.logger.warning("{} took {:.3f} ms", task, time_ms)
        if completed:
            task.mark_complete()
        return completed

    async def _on_build_task(self, task: BuildingCountTask) -> bool:
        assigned = self.bot.units.tags_in(task.assigned)
        if assigned:
            return False

        target = await self.map.get_building_location(task.utype, near=task.position,
                                                      max_distance=int(task.max_distance))
        if target is None:
            return False
        position = target if isinstance(target, Point2) else target.position

        # SCV can start constructing from a distance of 2.5 away
        worker, travel_time = await self.bot.pick_worker(position, target_distance=2.5)
        if not worker:
            return False

        if self.bot.resources.can_afford(task.utype) and worker.distance_to(target) <= 2.5:
            self.order.build(worker, task.utype, target)
            self.mining.unassign_worker(worker)  # TODO
        else:
            resource_time = self.bot.resources.can_afford_in(task.utype, excluded_workers=worker)
            if resource_time <= travel_time:
                self.order.move(worker, position)
                self.mining.unassign_worker(worker)  # TODO
                self.resources.reserve(task.utype)
        task.assigned.add(worker.tag)
        return False

    async def _on_unit_count_task(self, task: UnitCountTask) -> bool:
        utype = ALTERNATIVES.get(task.utype, task.utype)
        units = self.bot.forces(utype).ready
        #self.logger.trace("Have {} units of type {}", units.amount, task.utype.name)
        #self.logger.trace("units for {}: {}", task, units)
        if task.position is not None:
            units = units.closer_than(task.max_distance, task.position)
            #self.logger.trace("Have {} units of type {} within range of {}",
            #                  units.amount, task.utype.name, task.max_distance)
        #self.logger.trace("units for {} within {}: {}", task, task.position, units)
        if units.amount >= task.number:
            return True

        # TODO: only pending for commander
        pending = int(self.api.already_pending(task.utype))
        to_build = task.number - units.amount - pending

        trainer_utype = TRAINERS.get(task.utype)
        if trainer_utype is None:
            self.logger.error("No trainer for {}", task.utype)

        if trainer_utype == UnitTypeId.SCV:
            if self.api.tech_requirement_progress(task.utype) < 1:
                #self.logger.debug("Tech requirements for {} not fulfilled", task.utype)
                return False

            for _ in range(to_build):
                target = await self.map.get_building_location(task.utype, near=task.position,
                                                              max_distance=task.max_distance)
                #position = task.position
                if target is None:
                    break
                position = target if isinstance(target, Point2) else target.position
                # SCV can start constructing from a distance of 2.5 away
                worker, travel_time = await self.bot.pick_worker(position, target_distance=2.5)
                if not worker:
                    break
                #worker = self.commander.workers.random
                #self.logger.trace("Found free worker: {} {}", worker, worker.orders[0])
                if self.resources.can_afford(task.utype) and worker.distance_to(target) <= 2.5:
                    #self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                    self.order.build(worker, task.utype, target)
                    self.mining.unassign_worker(worker)     # TODO
                else:
                    resource_time = self.resources.can_afford_in(task.utype, excluded_workers=worker)
                    #self.logger.trace("{}: resource_time={:.2f}, travel_time={:.2f}", task, resource_time, travel_time)
                    if resource_time <= travel_time:
                        #self.logger.trace("{}: send it", task)
                        self.order.move(worker, position)
                        self.mining.unassign_worker(worker)  # TODO
                        self.resources.reserve(task.utype)

        else:
            for _ in range(to_build):
                trainer = self.bot.pick_trainer(task.utype)
                if trainer is None:
                    break
                if self.resources.can_afford(task.utype):
                    self.order.train(trainer, task.utype)
                else:
                    self.resources.reserve(task.utype)
        return False

    def _on_research_task(self, task: ResearchTask) -> bool:
        if task.upgrade in self.api.state.upgrades:
            self.logger.trace("Upgrade {} complete", task.upgrade)
            return True
        try:
            if self.api.already_pending_upgrade(task.upgrade) > 0:
                #self.logger.trace("Upgrade {} already pending", task.upgrade)
                return False
        except Exception as exc:
            self.logger.error("EXCEPTION {}", str(exc))
        if not self.resources.can_afford(task.upgrade):
            #self.logger.trace("Cannot afford {}", task.upgrade)
            return False
        researcher = self.bot.pick_researcher(task.upgrade)
        if researcher is not None:
            self.order.upgrade(researcher, task.upgrade)
            self.logger.info("Starting {} at {}", task.upgrade.name, researcher)
        #else:
        #    self.logger.trace("No researcher for {}", task.upgrade)
        return False

    def _on_squad_task(self, task: AttackTask | DefenseTask) -> bool:
        if isinstance(task, AttackTask):
            squads_with_task = self.squads.with_task(SquadAttackTask(task.target))
        else:
            squads_with_task = self.squads.with_task(SquadDefendTask(task.target))

        total_strength = sum(s.strength for s in squads_with_task)
        if task.strength is not None and total_strength >= task.strength:
            return False

        units = self.bot.army.idle.filter(lambda u: self.squads.get_squad_of_unit(u) is None)

        if task.strength is not None and units:
            units_to_add = int(math.ceil(task.strength - total_strength))
            units = units.closest_n_units(task.target, units_to_add)

        if task.strength is None:
            for squad in self.squads:
                if squad in squads_with_task:
                    continue
                units += squad.units

        if not units:
            return False

        # Find suitable existing squad
        squad = None
        if squads_with_task:
            # TODO
            closest_squad, distance = min([(s, s.center.distance_to(units.center)) for s in squads_with_task],
                                  key=lambda x: x[1])
            if distance <= 10:
                squad = closest_squad

        if squad is None:
            if len(units) < task.minimum_size:
                #self.logger.info("Squad size of {} is required but only {} units found", task.minimum_size, len(units))
                return False
            self.squads.remove_from_squads(units)
            squad = self.squads.create(units)
        else:
            self.squads.remove_from_squads(units)
            squad.add(units)

        if isinstance(task, AttackTask):
            squad.attack(task.target)
        else:
            squad.defend(task.target)
        return False
