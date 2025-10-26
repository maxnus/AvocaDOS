from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import Optional, TYPE_CHECKING

from loguru._logger import Logger
import numpy
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.system import System
from sc2bot.micro.combat import MicroManager
from sc2bot.core.constants import TRAINERS, ALTERNATIVES, RESEARCHERS
from sc2bot.core.mapdata import MapData
from sc2bot.core.orders import Order, MoveOrder, AttackOrder, BuildOrder, TrainOrder, GatherOrder, ResearchOrder, \
    AbilityOrder, OrderManager
from sc2bot.core.resourcemanager import ResourceManager
from sc2bot.core.tasks import Task, UnitCountTask, UnitPendingTask, AttackTask, MoveTask, \
    ResearchTask, HandoverUnitsTask, BuildTask
from sc2bot.core.taskmanager import TaskManager

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


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



class Commander(System):
    name: str
    #
    tags: set[int]
    orders: dict[int, Optional[Order]]
    previous_orders: dict[int, Optional[Order]]
    #assigned: dict[int, list[int]]
    # Systems
    order: OrderManager
    resource_priority: float
    resources: ResourceManager
    tasks: TaskManager
    combat: MicroManager

    def __init__(self, bot: 'AvocaDOS', name: str, *,
                 tags: Optional[set[int]] = None,
                 tasks: Optional[list[Task]] = None,
                 resource_priority: float = 0.5,
                 ) -> None:
        super().__init__(bot)
        self.name = name
        self.tags = tags or set()
        self.orders = {}
        self.previous_orders = {}
        #self.assigned = {}
        # Manager
        self.order = OrderManager(self)
        self.resource_priority = resource_priority
        self.resources = ResourceManager(self)
        self.tasks = TaskManager(self, tasks)
        self.combat = MicroManager(self)

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
        return super().logger.bind(prefix=self.name)

    @property
    def map(self) -> MapData:
        return self.bot.map

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

    # --- Control

    # def remove_dead_tags(self) -> int:
    #     size_before = len(self.tags)
    #     alive = self.bot.units | self.bot.structures
    #     self.tags.intersection_update(alive.tags)
    #     number_dead = size_before - len(self.tags)
    #     if number_dead:
    #         self.logger.trace("Removed {} dead tags", number_dead)
    #     return number_dead

    def add_units(self, units: Units | Unit | set[int]) -> None:
        if isinstance(units, Unit):
            tags = {units.tag}
        elif isinstance(units, Units):
            tags = units.tags
        else:
            tags = units
        self.logger.trace("Adding {}", units)
        self.tags.update(tags)

    def remove_units(self, units: int | Iterable[int]) -> None:
        units = units if isinstance(units, Units) else {units}
        self.logger.trace("Removing {}", units)
        self.tags.difference_update(units)

    def has_units(self, units: Unit | Units) -> bool:
        if isinstance(units, Unit):
            return units.tag in self.tags
        return all(u.tag in self.tags for u in units)

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

    # --- Pick unit

    async def pick_worker(self, position: Point2, *,
                          target_distance: float = 0.0,
                          include_constructing: bool = True,
                          construction_time_discount: float = 0.7) -> tuple[Optional[Unit], Optional[float]]:
        #workers = self.workers.idle + self.workers.collecting
        workers = self.workers.idle + self.workers.collecting + self.workers.filter(lambda x: x.is_moving)
        if include_constructing:
            workers += self.workers.filter(lambda unit: unit.is_constructing_scv)
        workers = workers.filter(lambda w: not self.order.has_order(w))
        if not workers:
            return None, None
        # Prefilter for performance
        if len(workers) > 10:
            workers = workers.closest_n_units(position=position, n=10)
        travel_times = await self.map.get_travel_times(workers, position, target_distance=target_distance)
        total_times = {unit: travel_time + construction_time_discount * self.bot.get_remaining_construction_time(unit)
                       for unit, travel_time in zip(workers, travel_times)}
        #self.logger.trace("worker travel times: {}", list(total_times.values())[:8])
        best = min(total_times, key=total_times.get)
        return best, total_times[best]

    def pick_trainer(self, utype: UnitTypeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        trainer_utype = TRAINERS[utype]

        free_trainers = self.structures(trainer_utype).idle.filter(lambda x: not self.order.has_order(x))
        #self.logger.trace("free trainers for {}: {}", utype.name, free_trainers)
        if not free_trainers:
            return None

        # Additional logic
        match utype:
            case UnitTypeId.ORBITALCOMMAND:
                trainers = free_trainers
            case UnitTypeId.SCV:
                trainers = free_trainers
            case UnitTypeId.MARINE | UnitTypeId.REAPER:
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
            case UnitTypeId.MARAUDER:
                trainers = free_trainers.filter(lambda x: x.has_techlab)
            case UnitTypeId.BARRACKSTECHLAB | UnitTypeId.BARRACKSREACTOR:
                trainers = free_trainers.filter(lambda x: not x.has_add_on)
            case _:
                self.logger.warning("Trainer for {} not implemented", utype)
                return None
        if not trainers:
            return None
        if position is None:
            return trainers.random
        return trainers.closest_to(position)

    def pick_researcher(self, upgrade: UpgradeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        researcher_utype = RESEARCHERS[upgrade]
        researchers = self.structures(researcher_utype).idle.filter(lambda x: not self.order.has_order(x))
        if not researchers:
            return None
        if position is None:
            return researchers.random
        return researchers.closest_to(position)

    # --- Tasks

    def add_task(self, task: Task) -> int:
        return self.tasks.add(task)

    # --- Callbacks

    async def on_step(self, step: int):
        # if (number_dead := self.remove_dead_tags()) != 0:
        #     self.logger.debug("{} units died", number_dead)

        await self.order.on_step(step)

        if step % 4 == 0:
            await self.tasks.on_step(step)

        await self._micro(step)

    async def _micro(self, iteration: int) -> None:

        units = self.units - self.workers
        await self.combat.micro_units(units)

        if iteration % 8 == 0:
            for unit in self.structures(UnitTypeId.SUPPLYDEPOT).ready.idle:
                raise_depot = self.bot.enemy_units.closer_than(2.5, unit)
                unit(AbilityId.MORPH_SUPPLYDEPOT_RAISE if raise_depot else AbilityId.MORPH_SUPPLYDEPOT_LOWER)

        if iteration % 8 == 0:
            for orbital in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
                if orbital.energy >= 50:
                    mineral_field = self.bot.mineral_field.in_distance_between(orbital.position, 0, 8)
                    if mineral_field:
                        orbital(AbilityId.CALLDOWNMULE_CALLDOWNMULE, mineral_field.random)

        if iteration % 8 == 0:
            minerals = self.bot.mineral_field.filter(
                lambda x:  any(x.distance_to(base) <= 8 for base in self.townhalls.ready))
            if minerals:
                workers = self.workers.filter(lambda w: (w.is_idle or w.is_moving) and not self.order.has_order(w))
                for worker in workers:
                    self.order.gather(worker, minerals.closest_to(worker))
