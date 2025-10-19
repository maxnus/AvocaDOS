from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

from loguru._logger import Logger
import numpy
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.constants import TRAINERS, ALTERNATIVES
from sc2bot.core.orders import Order, MoveOrder, AttackOrder, BuildOrder, TrainOrder, GatherOrder
from sc2bot.core.task import Task, TaskManager, UnitCountTask, UnitPendingTask, TaskStatus, AttackTask, MoveTask

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


@dataclass
class Command:
    pass


@dataclass
class IdleCommand(Command):
    pass


@dataclass
class MoveCommand(Command):
    target: Point2


@dataclass
class AttackCommand(Command):
    target: Point2


@dataclass
class RetreatCommand(Command):
    target: Point2


#class UnitFlags(IntEnum):
#    HAS_ORDER = 1



class Commander:
    bot: 'BotBase'
    name: str
    tags: set[int]
    command: Command
    tasks: TaskManager
    #flags: dict[int, UnitFlags]
    orders: dict[int, Optional[Order]]

    def __init__(self, bot: 'BotBase', name: str,
                 tags: Optional[set[int]] = None,
                 tasks: Optional[list[Task]] = None) -> None:
        super().__init__()
        self.bot = bot
        self.name = name
        self.tags = tags or set()
        self.command = IdleCommand()
        self.tasks = TaskManager(self, tasks)
        #self.flags = {}
        self.orders = {}

    def __repr__(self) -> str:
        unit_info = [f'{count} {utype.name}' for utype, count in sorted(
            sorted(self.get_unit_type_counts().items(), key=lambda item: item[0].name),
            key=lambda item: item[1], reverse=True)]
        return f"{self.name}({', '.join(unit_info)})"

    def get_unit_type_counts(self) -> Counter[UnitTypeId]:
        counter = Counter()
        for unit in self.forces:
            counter[unit.type_id] += 1
        return counter

    @property
    def time(self) -> float:
        return self.bot.time

    @property
    def logger(self) -> Logger:
        return self.bot.logger.bind(prefix=self.name)

    @property
    def units(self) -> Units:
        return self.bot.units.tags_in(self.tags)

    @property
    def workers(self) -> Units:
        return self.bot.workers.tags_in(self.tags)

    @property
    def structures(self) -> Units:
        return self.bot.structures.tags_in(self.tags)

    @property
    def townhalls(self) -> Units:
        return self.bot.townhalls.tags_in(self.tags)

    @property
    def forces(self) -> Units:
        return self.units + self.structures

    # @property
    # def number_units(self) -> int:
    #     return len(self.units)

    @property
    def center(self) -> Optional[Point2]:
        if self.forces.empty:
            return None
        return self.forces.center

    # Units

    # def control_all(self) -> None:
    #     self.tags = AllTags()

    def remove_dead_tags(self) -> int:
        size_before = len(self.tags)
        alive = self.bot.units | self.bot.structures
        self.tags.intersection_update(alive.tags)
        number_dead = size_before - len(self.tags)
        if number_dead:
            self.logger.trace("Removed {} dead tags", number_dead)
        return number_dead

    def take_control(self, units: Units | Unit) -> None:
        tags = units.tags if isinstance(units, Units) else {units.tag}
        self.logger.trace("Taking control of {} / {}", units, tags)
        self.tags.update(tags)

    def has_control(self, units: Unit | Units) -> bool:
        if isinstance(units, Unit):
            return units.tag in self.tags
        return all(u.tag in self.tags for u in units)

    def surrender_control(self, units: Units, *, to: Optional['Commander'] = None) -> None:
        size_before = len(self.tags)
        tags = {unit.tag for unit in units if unit.tag in self.tags}
        self.tags.difference_update(tags)
        surrendered = size_before - len(self.tags)
        if surrendered == 0:
            return
        if to is not None:
            to.tags.update(tags)

    # def add_tags(self, tag: int | set[int]) -> None:
    #     if isinstance(tag, int):
    #         self.tags.add(tag)
    #     self.tags.update(tag)

    # def add_units(self, units: Unit | Units) -> None:
    #     if isinstance(units, Unit):
    #         units = Units([units], self.bot)
    #     self.units += units
    #
    # def remove_units(self, units: Unit | Units) -> None:
    #     if isinstance(units, Unit):
    #         units = Units([units], self.bot)
    #     self.units -= units
    #
    # def transfer_units(self, other: 'Commander', units: Units) -> None:
    #     self.remove_units(units)
    #     other.add_units(units)

    def move(self, target: Point2) -> None:
        self.command = MoveCommand(target)

    def attack(self, target: Point2) -> None:
        self.command = AttackCommand(target)

    def retreat(self, target: Point2) -> None:
        self.command = RetreatCommand(target)

    def get_position_covariance(self) -> Optional[numpy.ndarray]:
        if self.forces.empty:
            return None
        center = self.units.center
        deltas = [unit.position - center for unit in self.forces]
        dx = sum(d[0] for d in deltas)
        dy = sum(d[1] for d in deltas)
        return numpy.asarray([[dx*dx, dx*dy], [dy*dx, dy*dy]])

    async def get_best_training_unit(self, utype: UnitTypeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        match utype:
            case UnitTypeId.ORBITALCOMMAND:
                trainers = self.townhalls(UnitTypeId.COMMANDCENTER).idle
            case UnitTypeId.SCV:
                trainers = self.townhalls(UnitTypeId.COMMANDCENTER).idle
            case UnitTypeId.MARINE:
                rax = self.structures(UnitTypeId.BARRACKS).idle
                # Prefer reactors, unless position is given
                # TODO: prioritize reactors even if position is passed, in close calls
                if position is None:
                    reactored_rax = rax.filter(lambda x: x.has_reactor)
                    trainers = reactored_rax or rax
                else:
                    trainers = rax
            case UnitTypeId.MARAUDER | UnitTypeId.REAPER:
                trainers = self.structures(UnitTypeId.BARRACKS).filter(lambda x: x.has_tech_lab).idle
            case _:
                raise NotImplementedError(f"unit type {utype}")
        if not trainers:
            return None
        if position is None:
            return trainers.random
        return trainers.closest_to(position)

    # Orders

    def order_move(self, unit: Unit, target: Point2) -> None:
        if self.has_control(unit):
            unit.move(target)
            self.orders[unit.tag] = MoveOrder(target)
        else:
            self.logger.error("{} does not control {}", self, unit)

    def order_attack(self, unit: Unit, target: Point2) -> None:
        if self.has_control(unit):
            unit.attack(target)
            self.orders[unit.tag] = AttackOrder(target)
        else:
            self.logger.error("{} does not control {}", self, unit)

    def order_gather(self, unit: Unit, target: Unit) -> None:
        if self.has_control(unit):
            unit.gather(target)
            self.orders[unit.tag] = GatherOrder(target)
        else:
            self.logger.error("{} does not control {}", self, unit)

    def order_build(self, unit: Unit, utype: UnitTypeId, position: Point2) -> None:
        if self.has_control(unit):
            unit.build(utype)
            self.orders[unit.tag] = BuildOrder(utype, position)
        else:
            self.logger.error("{} does not control {}", self, unit)

    def order_train(self, unit: Unit, utype: UnitTypeId) -> None:
        if self.has_control(unit):
            unit.train(utype)
            self.orders[unit.tag] = TrainOrder(utype)
        else:
            self.logger.error("{} does not control {}", self, unit)

    def get_order(self, unit: Unit) -> Optional[Order]:
        return self.orders.get(unit.tag)

    def has_order(self, unit: Unit) -> bool:
        return unit.tag in self.orders

    def clear_orders(self) -> None:
        self.orders.clear()

    async def get_free_worker(self, position: Point2, *, include_constructing: bool = False) -> Optional[Unit]:
        #workers = self.workers.idle + self.workers.collecting
        workers = self.workers.idle + self.workers.collecting + self.workers.filter(lambda x: x.is_moving)
        if include_constructing:
            workers += self.workers.filter(lambda unit: unit.is_constructing_scv)
        workers = workers.filter(lambda w: not self.has_order(w))
        if not workers:
            return None
        # Prefilter for performance
        if len(workers) > 10:
            workers = workers.closest_n_units(position=position, n=10)
        total_times = {unit: await self.bot.get_travel_time(unit, position)
                       + await self.bot.get_remaining_construction_time(unit) for unit in workers}
        self.logger.trace("worker travel times: {}", list(total_times.values())[:8])
        return min(total_times, key=total_times.get)

    async def on_unit_count_task(self, task: UnitCountTask) -> bool:

        utype = ALTERNATIVES.get(task.utype, task.utype)
        units = self.forces(utype).ready
        self.logger.trace("Have {} units of type {}", units.amount, task.utype.name)
        if task.position is not None:
            units = units.closer_than(task.max_distance, task.position)
            self.logger.trace("Have {} units of type {} within range of {}",
                              units.amount, task.utype.name, task.max_distance)
        if units.amount >= task.number:
            return True

        # TODO: only pending for commander
        pending = int(self.bot.already_pending(task.utype))
        to_build = task.number - units.amount - pending
        self.logger.trace('task={}, have={}, pending={}, to_build={}', task, units.amount, pending, to_build)

        trainer = TRAINERS.get(task.utype)
        if trainer is None:
            self.logger.error("No trainer for {}", task.utype)

        if trainer == UnitTypeId.SCV:
            for _ in range(to_build):
                position = await self.bot.get_best_building_location(task.utype, near=task.position,
                                                                     max_distance=task.max_distance)
                if position is None:
                    break
                worker = await self.get_free_worker(position)
                if worker is None:
                    break
                if self.bot.can_afford(task.utype):
                    self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                    worker.build(task.utype, position)
                else:
                    resource_time = self.bot.history.time_for_cost(self.bot.get_cost(task.utype))
                    # Avoid pathing calculation for trivial cases:
                    if resource_time < 2:
                        travel_time = -1
                    elif resource_time > 30:
                        travel_time = float('inf')
                    else:
                        travel_time = await self.bot.get_travel_time(worker, position)
                    self.logger.trace("{}: resource_time={}, travel_time={}", task, resource_time, travel_time)
                    if travel_time <= resource_time:
                        self.order_move(worker, position)
        else:
            for _ in range(to_build):
                if not self.bot.can_afford(task.utype):
                    #self.logger.trace('cannot afford {}', task)
                    break
                trainer = await self.get_best_training_unit(task.utype)
                if trainer is not None:
                    self.order_train(trainer, task.utype)
                #else:
                #    self.logger.trace('No trainer for {}', task)
        return False

    async def on_unit_pending_task(self, task: UnitPendingTask) -> bool:
        pending = int(self.bot.already_pending(task.utype))
        if pending:
            self.logger.trace('already pending {}', task)
            return False
        if not self.bot.can_afford(task.utype):
            self.logger.trace('cannot afford {}', task)
            return False

        if self.bot.is_structure(task.utype):
            position = task.position or await self.bot.get_best_building_location(task.utype)
            worker = await self.get_free_worker(position)
            if worker is None:
                self.logger.trace('No worker for {}', task)
                return False
            else:
                self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                self.order_build(worker, task.utype, position)
                return True
        else:
            trainer = await self.get_best_training_unit(task.utype)
            if trainer is None:
                self.logger.trace('No trainer for {}', task)
                return False
            else:
                self.order_train(trainer, task.utype)
                return True

    def on_move_task(self, task: MoveTask) -> bool:
        if task.units is None:
            units = self.units
        else:
            #units = []
            #for utype, number in task.units.items():
            units = sum((self.units(utype).closest_n_units(task.target, number) for utype, number in task.units.items()),
                        start=[])
        for unit in units:
            self.order_move(unit, task.target)
        return True

    def on_attack_task(self, task: AttackTask) -> bool:
        # TODO: fix
        for marine in self.units(UnitTypeId.MARINE):
            self.order_attack(marine, task.target)
        return True

    async def work_on_tasks(self) -> None:
        for task in self.tasks:
            if isinstance(task, UnitCountTask):
                completed = await self.on_unit_count_task(task)
            elif isinstance(task, UnitPendingTask):
                completed = await self.on_unit_pending_task(task)
            elif isinstance(task, MoveTask):
                completed = self.on_move_task(task)
            elif isinstance(task, AttackTask):
                completed = self.on_attack_task(task)
            else:
                completed = False
                self.logger.warning("Not implemented: {}", task)
            if completed:
                task.mark_complete()

    async def on_step(self, iteration: int):

        if (number_dead := self.remove_dead_tags()) != 0:
            self.logger.debug("{} units died", number_dead)

        self.clear_orders()

        if not self.tasks:
            self.tasks.add(UnitPendingTask(UnitTypeId.MARINE))
            self.tasks.add(AttackTask(self.bot.get_enemy_base_location()))

        await self.work_on_tasks()
        await self.tasks.update_tasks(iteration)
        await self.micro(iteration)

    async def micro(self, iteration: int) -> None:
        if iteration % 20 == 0:
            for unit in self.structures(UnitTypeId.SUPPLYDEPOT).ready.idle:
                raise_ = False
                unit(AbilityId.MORPH_SUPPLYDEPOT_RAISE if raise_ else AbilityId.MORPH_SUPPLYDEPOT_LOWER)
            for orbital in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
                if orbital.energy >= 50:
                    mineral_field = self.bot.mineral_field.in_distance_between(orbital.position, 0, 8).random
                    orbital(AbilityId.CALLDOWNMULE_CALLDOWNMULE, mineral_field)

        if iteration % 10 == 0:
            minerals = self.bot.mineral_field.filter(
                lambda x:  any(x.distance_to(base) <= 8 for base in self.townhalls.ready))
            for worker in self.workers.idle.filter(lambda w: not self.has_order(w)):
                self.order_gather(worker, minerals.closest_to(worker))
