import itertools
from collections.abc import Iterator
from time import perf_counter
from typing import Optional, TYPE_CHECKING

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2

from .constants import ALTERNATIVES, TRAINERS
from .manager import Manager
from .tasks import (Task, TaskStatus, TaskRequirementType, TaskRequirements, TaskDependencies, BuildingCountTask,
                    UnitCountTask,
                    ResearchTask, MoveTask, AttackTask, HandoverUnitsTask, MiningTask)
from .util import LineSegment

if TYPE_CHECKING:
    from .commander import Commander


class TaskManager(Manager):
    completed: dict[int, Task]
    current: dict[int, Task]
    future: dict[int, Task]

    def __init__(self, commander: 'Commander', tasks: Optional[dict[int, Task]]) -> None:
        super().__init__(commander)
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
                value = self.commander.forces(req_type).ready.amount
            elif isinstance(req_type, UpgradeId):
                value = req_type in self.bot.state.upgrades
            elif req_type == TaskRequirementType.TIME:
                value = self.bot.time
            elif req_type == TaskRequirementType.SUPPLY:
                value = self.bot.supply_used
            elif req_type == TaskRequirementType.MINERALS:
                value = self.bot.minerals
            elif req_type == TaskRequirementType.VESPENE:
                value = self.bot.vespene
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
        elif isinstance(task, MoveTask):
            completed = self._on_move_task(task)
        elif isinstance(task, AttackTask):
            completed = self._on_attack_task(task)
        elif isinstance(task, HandoverUnitsTask):
            completed = self._on_handover_units_task(task)
        else:
            completed = False
            self.logger.warning("Not implemented: {}", task)
        #if (time_ms := 1000 * (perf_counter() - t0)) > 5:
        #    self.logger.warning("{} took {:.3f} ms", task, time_ms)
        if completed:
            task.mark_complete()
        return completed

    async def _on_build_task(self, task: BuildingCountTask) -> bool:
        assigned = self.commander.units.tags_in(task.assigned)
        if assigned:
            return False

        target = await self.bot.map.get_building_location(task.utype, near=task.position,
                                                          max_distance=int(task.max_distance))
        if target is None:
            return False
        position = target if isinstance(target, Point2) else target.position

        # SCV can start constructing from a distance of 2.5 away
        worker, travel_time = await self.commander.pick_worker(position, target_distance=2.5)
        if not worker:
            return False

        if self.commander.resources.can_afford(task.utype) and worker.distance_to(target) <= 2.5:
            self.commander.order.build(worker, task.utype, target)
            self.commander.mining.remove_worker(worker)  # TODO
        else:
            resource_time = self.commander.resources.can_afford_in(task.utype, excluded_workers=worker)
            if resource_time <= travel_time:
                self.commander.order.move(worker, position)
                self.commander.mining.remove_worker(worker)  # TODO
                self.commander.resources.reserve(task.utype)
        task.assigned.add(worker.tag)
        return False

    async def _on_unit_count_task(self, task: UnitCountTask) -> bool:
        utype = ALTERNATIVES.get(task.utype, task.utype)
        units = self.commander.forces(utype).ready
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
        pending = int(self.bot.already_pending(task.utype))
        to_build = task.number - units.amount - pending

        trainer_utype = TRAINERS.get(task.utype)
        if trainer_utype is None:
            self.commander.logger.error("No trainer for {}", task.utype)

        if trainer_utype == UnitTypeId.SCV:
            if self.bot.tech_requirement_progress(task.utype) < 1:
                #self.logger.debug("Tech requirements for {} not fulfilled", task.utype)
                return False

            for _ in range(to_build):
                target = await self.bot.map.get_building_location(task.utype, near=task.position,
                                                                  max_distance=task.max_distance)
                #position = task.position
                if target is None:
                    break
                position = target if isinstance(target, Point2) else target.position
                # SCV can start constructing from a distance of 2.5 away
                worker, travel_time = await self.commander.pick_worker(position, target_distance=2.5)
                if not worker:
                    break
                #worker = self.commander.workers.random
                #self.logger.trace("Found free worker: {} {}", worker, worker.orders[0])
                if self.commander.resources.can_afford(task.utype) and worker.distance_to(target) <= 2.5:
                    #self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                    self.commander.order.build(worker, task.utype, target)
                    self.commander.mining.remove_worker(worker)     # TODO
                else:
                    resource_time = self.commander.resources.can_afford_in(task.utype, excluded_workers=worker)
                    #self.logger.trace("{}: resource_time={:.2f}, travel_time={:.2f}", task, resource_time, travel_time)
                    if resource_time <= travel_time:
                        #self.logger.trace("{}: send it", task)
                        self.commander.order.move(worker, position)
                        self.commander.mining.remove_worker(worker)  # TODO
                        self.commander.resources.reserve(task.utype)

        else:
            for _ in range(to_build):
                trainer = self.commander.pick_trainer(task.utype)
                if trainer is None:
                    break
                if self.commander.resources.can_afford(task.utype):
                    self.commander.order.train(trainer, task.utype)
                else:
                    self.commander.resources.reserve(task.utype)
        return False

    def _on_research_task(self, task: ResearchTask) -> bool:
        if task.upgrade in self.bot.state.upgrades:
            self.logger.trace("Upgrade {} complete", task.upgrade)
            return True
        try:
            if self.bot.already_pending_upgrade(task.upgrade) > 0:
                #self.logger.trace("Upgrade {} already pending", task.upgrade)
                return False
        except Exception as exc:
            self.logger.error("EXCEPTION {}", str(exc))
        if not self.commander.resources.can_afford(task.upgrade):
            #self.logger.trace("Cannot afford {}", task.upgrade)
            return False
        researcher = self.commander.pick_researcher(task.upgrade)
        if researcher is not None:
            self.commander.order.research(researcher, task.upgrade)
            self.logger.info("Starting {} at {}", task.upgrade.name, researcher)
        #else:
        #    self.logger.trace("No researcher for {}", task.upgrade)
        return False

    def _on_move_task(self, task: MoveTask) -> bool:
        if task.units is None:
            units = self.commander.units
        else:
            #units = []
            #for utype, number in task.units.items():
            units = sum((self.commander.units(utype).closest_n_units(task.target, number) for utype, number in task.units.items()),
                        start=[])
        for unit in units:
            self.commander.order.move(unit, task.target)
        return True

    def _on_attack_task(self, task: AttackTask) -> bool:
        #self.combat.marine_micro(task)
        for unit in self.commander.units.idle:
            #unit.attack(task.target)
            self.commander.order.attack(unit, task.target)
        return False

    def _on_handover_units_task(self, task: HandoverUnitsTask) -> bool:
        commander = self.bot.commanders.get(task.commander)
        if commander is None:
            return False
        units = self.commander.units(task.utype)
        self.commander.remove_units(units)
        commander.add_units(units)
        return True
