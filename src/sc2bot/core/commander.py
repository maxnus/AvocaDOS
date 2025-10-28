import heapq
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import numpy
from loguru._logger import Logger
from sc2.constants import CREATION_ABILITY_FIX
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.constants import TRAINERS, RESEARCHERS
from sc2bot.core.miningmanager import MiningManager
from sc2bot.mapdata.mapdata import MapData
from sc2bot.core.orders import Order, OrderManager
from sc2bot.core.resourcemanager import ResourceManager
from sc2bot.core.system import System
from sc2bot.core.taskmanager import TaskManager
from sc2bot.core.tasks import Task
from sc2bot.core.util import squared_distance, LineSegment
from sc2bot.micro.combat import MicroManager

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
    previous_orders: dict[int, Optional[Order]]
    # Systems
    order: OrderManager
    resource_priority: float
    resources: ResourceManager
    tasks: TaskManager
    combat: MicroManager
    mining: MiningManager
    # Other
    expected_units: dict[Order, tuple[UnitTypeId, Point2]]

    def __init__(self, bot: 'AvocaDOS', name: str, *,
                 tags: Optional[set[int]] = None,
                 tasks: Optional[list[Task]] = None,
                 resource_priority: float = 0.5,
                 ) -> None:
        super().__init__(bot)
        self.name = name
        self.tags = tags or set()
        # Manager
        self.order = OrderManager(self)
        self.resource_priority = resource_priority
        self.resources = ResourceManager(self)
        self.tasks = TaskManager(self, tasks)
        self.combat = MicroManager(self)
        self.mining = MiningManager(self)
        # Other
        self.expected_units = {}

    def __repr__(self) -> str:
        unit_info = [f'{count} {utype.name}' for utype, count in sorted(
            sorted(self.get_unit_type_counts().items(), key=lambda item: item[0].name),
            key=lambda item: item[1], reverse=True)]
        return f"{self.name}({', '.join(unit_info)})"

    async def on_step(self, step: int):
        # if (number_dead := self.remove_dead_tags()) != 0:
        #     self.logger.debug("{} units died", number_dead)

        await self.order.on_step(step)

        #if step % 4 == 0:
        await self.tasks.on_step(step)

        await self.mining.on_step(step)

        await self._micro(step)

    # --- Expected units

    def add_expected_unit(self, order: Order, utype: UnitTypeId, position: Point2) -> None:
        self.expected_units[order] = (utype, position)

    def remove_expected_unit(self, order: Order) -> None:
        self.expected_units.pop(order)

    async def is_expected_unit(self, unit: Unit) -> bool:
        # TODO improve
        if unit.is_structure and unit.type_id not in {UnitTypeId.BARRACKSREACTOR, UnitTypeId.BARRACKSTECHLAB}:
            expected_sq_distance = 0.01
        else:
            # TODO: [min, max] interval based on unit_range-eps, unit_range+eps
            expected_sq_distance = 12
        for order, (utype, location) in self.expected_units.items():
            if unit.type_id == utype and squared_distance(unit, location) <= expected_sq_distance:
                self.logger.trace("found expected unit {}", unit)
                self.remove_expected_unit(order)
                self.add_units(unit)
                return True
        return False

    # --- Properties

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

    def _get_creation_ability(self, utype: UnitTypeId) -> AbilityId:
        try:
            return self.bot.game_data.units[utype.value].creation_ability.exact_id
        except AttributeError:
            return CREATION_ABILITY_FIX.get(utype.value, 0)

    # TODO: FIX
    # def get_pending(self, utype: UnitTypeId) -> list[float]:
    #     # replicate: self.bot.already_pending(utype)
    #
    #     # tuple[Counter[AbilityId], dict[AbilityId, float]]
    #     abilities_amount: Counter[AbilityId] = Counter()
    #     build_progress: dict[AbilityId, list[float]] = defaultdict(list)
    #     unit: Unit
    #     for unit in self.units + self.structures:
    #         for order in unit.orders:
    #             abilities_amount[order.ability.exact_id] += 1
    #         if not unit.is_ready and (self.bot.race != Race.Terran or not unit.is_structure):
    #             # If an SCV is constructing a building, already_pending would count this structure twice
    #             # (once from the SCV order, and once from "not structure.is_ready")
    #             creation_ability = CREATION_ABILITY_FIX.get(
    #                 unit.type_id, self.bot.game_data.units[unit.type_id.value].creation_ability.exact_id)
    #             abilities_amount[creation_ability] += 2 if unit.type_id == UnitTypeId.ARCHON else 1
    #             build_progress[creation_ability].append(unit.build_progress)
    #
    #     return abilities_amount, max_build_progress

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

    async def pick_workers(self, location: Point2 | LineSegment, *,
                           number: int,
                           target_distance: float = 0.0,
                           include_moving: bool = True,
                           include_collecting: bool = True,
                           include_constructing: bool = True,
                           construction_time_discount: float = 0.7) -> list[tuple[Unit, float]]:

        def worker_filter(worker: Unit) -> bool:
            if self.order.has_order(worker):
                return False
            if worker.is_idle:
                return True
            if include_moving and worker.is_moving:
                return True
            if include_collecting and worker.is_collecting:
                return True
            if include_constructing and worker.is_constructing_scv:
                return True
            return False

        workers = self.workers.filter(worker_filter)
        if not workers:
            return []
        # Prefilter for performance
        if isinstance(location, Point2):
            if len(workers) > number + 10:
                workers = workers.closest_n_units(position=location, n=number + 10)
            travel_times = await self.map.get_travel_times(workers, location, target_distance=target_distance)
            workers_and_dist = {unit: travel_time + construction_time_discount
                                      * self.bot.get_remaining_construction_time(unit)
                                for unit, travel_time in zip(workers, travel_times)}
        elif isinstance(location, LineSegment):
            workers_and_dist = {unit: location.distance_to(unit) for unit in workers}
        else:
            raise TypeError(f"unknown location type: {type(location)}")

        result = heapq.nsmallest(number, workers_and_dist.items(), key=lambda item: item[1])
        return result

    async def pick_worker(self, position: Point2, *,
                          target_distance: float = 0.0,
                          include_moving: bool = True,
                          include_collecting: bool = True,
                          include_constructing: bool = True,
                          construction_time_discount: float = 0.7) -> tuple[Optional[Unit], Optional[float]]:
        workers = await self.pick_workers(location=position, number=1,
                                          target_distance=target_distance,
                                          include_moving=include_moving,
                                          include_collecting=include_collecting,
                                          include_constructing=include_constructing,
                                          construction_time_discount=construction_time_discount)
        if not workers:
            return None, None
        return workers[0]

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

        # if iteration % 8 == 0:
        #     minerals = self.bot.mineral_field.filter(
        #         lambda x:  any(x.distance_to(base) <= 8 for base in self.townhalls.ready))
        #     if minerals:
        #         workers = self.workers.filter(lambda w: (w.is_idle or w.is_moving) and not self.order.has_order(w))
        #         for worker in workers:
        #             self.order.gather(worker, minerals.closest_to(worker))
