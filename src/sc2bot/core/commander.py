from collections import Counter
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from loguru._logger import Logger
import numpy
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.constants import TRAINERS, ALTERNATIVES, RESEARCHERS
from sc2bot.core.orders import Order, MoveOrder, AttackOrder, BuildOrder, TrainOrder, GatherOrder
from sc2bot.core.tasks import Task, TaskManager, UnitCountTask, UnitPendingTask, TaskStatus, AttackTask, MoveTask, \
    BuildTask, ResearchTask

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


class Commander:
    bot: 'BotBase'
    name: str
    tags: set[int]
    command: Command
    tasks: TaskManager
    orders: dict[int, Optional[Order]]
    previous_orders: dict[int, Optional[Order]]

    def __init__(self, bot: 'BotBase', name: str,
                 tags: Optional[set[int]] = None,
                 tasks: Optional[list[Task]] = None) -> None:
        super().__init__()
        self.bot = bot
        self.name = name
        self.tags = tags or set()
        self.command = IdleCommand()
        self.tasks = TaskManager(self, tasks)
        self.orders = {}
        self.previous_orders = {}

    def __repr__(self) -> str:
        unit_info = [f'{count} {utype.name}' for utype, count in sorted(
            sorted(self.get_unit_type_counts().items(), key=lambda item: item[0].name),
            key=lambda item: item[1], reverse=True)]
        return f"{self.name}({', '.join(unit_info)})"

    @property
    def time(self) -> float:
        return self.bot.time

    @property
    def logger(self) -> Logger:
        return self.bot.logger.bind(prefix=self.name)

    # --- Resources

    # TODO: per commander

    @property
    def minerals(self) -> int:
        return self.bot.minerals

    @property
    def vespene(self) -> int:
        return self.bot.vespene

    @property
    def supply_used(self) -> float:
        return self.bot.supply_used

    # --- Units

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

    def get_unit_type_counts(self) -> Counter[UnitTypeId]:
        counter = Counter()
        for unit in self.forces:
            counter[unit.type_id] += 1
        return counter

    def can_afford(self, item: UnitTypeId | UpgradeId | AbilityId) -> bool:
        # TODO
        return self.bot.can_afford(item, check_supply_cost=True)

    # --- Control

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

    # --- Commands

    # def move(self, target: Point2) -> None:
    #     self.command = MoveCommand(target)
    #
    # def attack(self, target: Point2) -> None:
    #     self.command = AttackCommand(target)
    #
    # def retreat(self, target: Point2) -> None:
    #     self.command = RetreatCommand(target)

    # --- Position

    @property
    def center(self) -> Optional[Point2]:
        if self.forces.empty:
            return None
        return self.forces.center

    def get_position_covariance(self) -> Optional[numpy.ndarray]:
        if self.forces.empty:
            return None
        center = self.units.center
        deltas = [unit.position - center for unit in self.forces]
        dx = sum(d[0] for d in deltas)
        dy = sum(d[1] for d in deltas)
        return numpy.asarray([[dx*dx, dx*dy], [dy*dx, dy*dy]])

    # --- Orders

    def order_move(self, unit: Unit, target: Point2) -> bool:
        if not self.has_control(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        unit.move(target)
        self.orders[unit.tag] = MoveOrder(target)
        return True

    def order_attack(self, unit: Unit, target: Point2) -> bool:
        if not self.has_control(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        unit.attack(target)
        self.orders[unit.tag] = AttackOrder(target)
        return True

    def order_gather(self, unit: Unit, target: Unit) -> bool:
        if not self.has_control(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        unit.gather(target)
        self.orders[unit.tag] = GatherOrder(target)
        return True

    def order_build(self, unit: Unit, utype: UnitTypeId, position: Point2) -> bool:
        if not self.has_control(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        unit.build(utype)
        self.orders[unit.tag] = BuildOrder(utype, position)
        return True

    def order_train(self, unit: Unit, utype: UnitTypeId) -> bool:
        # TODO: do not train if already training
        if not self.has_control(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        unit.train(utype)
        self.orders[unit.tag] = TrainOrder(utype)
        return True

    def get_order(self, unit: Unit) -> Optional[Order]:
        return self.orders.get(unit.tag)

    def has_order(self, unit: Unit) -> bool:
        return unit.tag in self.orders

    def clear_orders(self) -> None:
        self.previous_orders = self.orders
        self.orders = {}

    # --- Pick unit

    async def _get_worker(self, position: Point2, *,
                          target_distance: float = 0.0,
                          include_constructing: bool = True) -> tuple[Optional[Unit], Optional[float]]:
        #workers = self.workers.idle + self.workers.collecting
        workers = self.workers.idle + self.workers.collecting + self.workers.filter(lambda x: x.is_moving)
        if include_constructing:
            workers += self.workers.filter(lambda unit: unit.is_constructing_scv)
        workers = workers.filter(lambda w: not self.has_order(w))
        if not workers:
            return None, None
        # Prefilter for performance
        if len(workers) > 10:
            workers = workers.closest_n_units(position=position, n=10)
        travel_times = await self.bot.get_travel_times(workers, position, target_distance=target_distance)
        total_times = {unit: travel_time + self.bot.get_remaining_construction_time(unit)
                       for unit, travel_time in zip(workers, travel_times)}
        #self.logger.trace("worker travel times: {}", list(total_times.values())[:8])
        best = min(total_times, key=total_times.get)
        return best, total_times[best]

    def _get_trainer(self, utype: UnitTypeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        trainer_utype = TRAINERS[utype]

        free_trainers = self.structures(trainer_utype).idle.filter(lambda x: not self.has_order(x))
        #self.logger.trace("free trainers for {}: {}", utype.name, free_trainers)
        if not free_trainers:
            return None

        # Additional logic
        match utype:
            case UnitTypeId.ORBITALCOMMAND:
                trainers = free_trainers
            case UnitTypeId.SCV:
                trainers = free_trainers
            case UnitTypeId.MARINE:
                # Prefer reactors, unless position is given
                # TODO: prioritize reactors even if position is passed, in close calls
                if position is None:
                    trainers = free_trainers.filter(lambda x: x.has_reactor)
                    if not trainers:
                        trainers = free_trainers.filter(lambda x: not x.has_techlab)
                    if not trainers:
                        trainers = free_trainers
                else:
                    trainers = free_trainers
            case UnitTypeId.MARAUDER | UnitTypeId.REAPER:
                trainers = free_trainers.filter(lambda x: x.has_techlab)
            case UnitTypeId.TECHLAB | UnitTypeId.REACTOR:
                trainers = free_trainers.filter(lambda x: not x.has_add_on)
            case _:
                self.logger.warning("Trainer for {} not implemented", utype)
                return None
        if not trainers:
            return None
        if position is None:
            return trainers.random
        return trainers.closest_to(position)

    def _get_researcher(self, upgrade: UpgradeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        researcher_utype = RESEARCHERS[upgrade]
        researchers = self.structures(researcher_utype).idle.filter(lambda x: not self.has_order(x))
        if not researchers:
            return None
        if position is None:
            return researchers.random
        return researchers.closest_to(position)

    # --- Tasks

    # def _on_build_task(self, task: BuildTask) -> bool:
    #     # Check if task is worked
    #     if True:
    #         worker = self._get_worker(task.position, include_constructing=True)

    async def _on_unit_count_task(self, task: UnitCountTask) -> bool:
        utype = ALTERNATIVES.get(task.utype, task.utype)
        units = self.forces(utype).ready
        #self.logger.trace("Have {} units of type {}", units.amount, task.utype.name)
        if task.position is not None:
            units = units.closer_than(task.max_distance, task.position)
            #self.logger.trace("Have {} units of type {} within range of {}",
            #                  units.amount, task.utype.name, task.max_distance)
        if units.amount >= task.number:
            return True

        # TODO: only pending for commander
        pending = int(self.bot.already_pending(task.utype))
        to_build = task.number - units.amount - pending
        #self.logger.trace('task={}, have={}, pending={}, to_build={}', task, units.amount, pending, to_build)

        trainer = TRAINERS.get(task.utype)
        if trainer is None:
            self.logger.error("No trainer for {}", task.utype)

        if trainer == UnitTypeId.SCV:
            for _ in range(to_build):
                target = await self.bot.get_building_location(task.utype, near=task.position,
                                                                max_distance=task.max_distance)
                #position = task.position
                if target is None:
                    break
                position = target if isinstance(target, Point2) else target.position
                # SCV can start constructing from a distance of 2.5 away
                worker, travel_time = await self._get_worker(position, target_distance=2.5)
                #worker = self.workers.random
                #self.logger.trace("Found free worker: {} {}", worker, worker.orders[0])
                if self.can_afford(task.utype) and worker.distance_to(target) <= 2.5:
                    #self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                    worker.build(task.utype, target)
                else:
                    resource_time = self.bot.time_for_cost(self.bot.get_cost(task.utype), excluded_workers=worker)
                    self.logger.trace("{}: resource_time={:.2f}, travel_time={:.2f}", task, resource_time, travel_time)
                    if resource_time <= travel_time:
                        self.logger.trace("{}: send it", task)
                        self.order_move(worker, position)
        else:
            for _ in range(to_build):
                if not self.can_afford(task.utype):
                    #self.logger.trace('cannot afford {}', task)
                    break
                trainer = self._get_trainer(task.utype)
                if trainer is not None:
                    self.order_train(trainer, task.utype)
                #else:
                #    self.logger.trace('No trainer for {}', task)
        return False

    async def _on_unit_pending_task(self, task: UnitPendingTask) -> bool:
        pending = int(self.bot.already_pending(task.utype))
        if pending:
            #self.logger.trace('already pending {}', task)
            return False
        if not self.can_afford(task.utype):
            #self.logger.trace('cannot afford {}', task)
            return False

        if self.bot.is_structure(task.utype):
            position = task.position or await self.bot.get_building_location(task.utype)
            worker, travel_time = await self._get_worker(position)
            if worker is None:
                #self.logger.trace('No worker for {}', task)
                return False
            else:
                self.logger.trace("{}: ordering worker {} build {} at {}", task, worker, task.utype.name, position)
                self.order_build(worker, task.utype, position)
                return True
        else:
            trainer = self._get_trainer(task.utype)
            if trainer is None:
                #self.logger.trace('No trainer for {}', task)
                return False
            else:
                self.order_train(trainer, task.utype)
                return True

    def _on_research_task(self, task: ResearchTask) -> bool:
        if self.bot.already_pending_upgrade(task.upgrade) > 0:
            return True
        if not self.can_afford(task.upgrade):
            return False
        researcher = self._get_researcher(task.upgrade)
        researcher.research(task.upgrade)
        self.logger.info("Starting {} at {}", task.upgrade.name, researcher)
        return True

    def _on_move_task(self, task: MoveTask) -> bool:
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

    def _on_attack_task(self, task: AttackTask) -> bool:
        # TODO: fix
        for marine in self.units(UnitTypeId.MARINE):
            self.order_attack(marine, task.target)
        #return True
        return False

    # --- Callbacks

    async def on_step(self, step: int):

        if (number_dead := self.remove_dead_tags()) != 0:
            self.logger.debug("{} units died", number_dead)

        if step % 4 == 0:
            await self._work_on_tasks(step)
            await self.tasks.update_tasks(step)

        await self._micro(step)

    async def _work_on_tasks(self, step: int) -> None:
        self.clear_orders()
        for task in self.tasks:
            if isinstance(task, UnitCountTask):
                completed = await self._on_unit_count_task(task)
            elif isinstance(task, UnitPendingTask):
                completed = await self._on_unit_pending_task(task)
            elif isinstance(task, ResearchTask):
                completed = self._on_research_task(task)
            elif isinstance(task, MoveTask):
                completed = self._on_move_task(task)
            elif isinstance(task, AttackTask):
                completed = self._on_attack_task(task)
            else:
                completed = False
                self.logger.warning("Not implemented: {}", task)
            if completed:
                task.mark_complete()

    async def _micro(self, iteration: int) -> None:
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
            workers = self.workers.filter(lambda w: (w.is_idle or w.is_moving) and not self.has_order(w))
            for worker in workers:
                self.order_gather(worker, minerals.closest_to(worker))
