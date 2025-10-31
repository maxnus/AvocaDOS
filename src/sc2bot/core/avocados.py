import heapq
from collections import Counter
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

from sc2bot.core.buildordermanager import BuildOrderManager
from sc2bot.core.constants import TRAINERS, RESEARCHERS
from sc2bot.core.historymanager import HistoryManager
from sc2bot.core.miningmanager import MiningManager
from sc2bot.debug.debugmanager import DebugManager
from sc2bot.debug.micro_scenario_manager import MicroScenarioManager
from sc2bot.mapdata.mapmanager import MapManager
from sc2bot.core.orders import Order, OrderManager
from sc2bot.core.resourcemanager import ResourceManager
from sc2bot.core.taskmanager import TaskManager
from sc2bot.core.tasks import Task
from sc2bot.core.util import squared_distance, LineSegment
from sc2bot.micro.combat import MicroManager

if TYPE_CHECKING:
    from sc2bot.core.botapi import BotApi


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



class AvocaDOS:
    api: 'BotApi'
    name: str
    # Manager
    map: Optional[MapManager]
    build: BuildOrderManager
    order: OrderManager
    resources: ResourceManager
    tasks: TaskManager
    combat: MicroManager
    mining: MiningManager
    history: HistoryManager
    debug: DebugManager
    micro_scenario: Optional[MicroScenarioManager]
    # Other
    previous_orders: dict[int, Optional[Order]]

    def __init__(self, api: 'BotApi', *,
                 name: str = 'AvocaDOS',
                 build: Optional[str] = None,
                 log_level: str = "DEBUG",
                 micro_scenario: Optional[dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]] = None,
                 ) -> None:
        super().__init__()
        self.api = api
        self.name = name
        # Manager
        self.build = BuildOrderManager(self, build=build)
        self.order = OrderManager(self)
        self.resources = ResourceManager(self)
        self.tasks = TaskManager(self)
        self.combat = MicroManager(self)
        self.mining = MiningManager(self)
        self.history = HistoryManager(self)
        self.map = MapManager(self)
        self.debug = DebugManager(self, log_level=log_level)
        if micro_scenario is not None:
            self.micro_scenario = MicroScenarioManager(self, units=micro_scenario)
        else:
            self.micro_scenario = None
        self.logger.debug("Initialized {}", self)

    def __repr__(self) -> str:
        unit_info = [f'{count} {utype.name}' for utype, count in sorted(
            sorted(self.get_unit_type_counts().items(), key=lambda item: item[0].name),
            key=lambda item: item[1], reverse=True)]
        return f"{type(self).__name__}({', '.join(unit_info)})"

    async def on_start(self) -> None:
        await self.map.on_start()
        await self.build.on_start()

        if self.micro_scenario is not None:
            await self.micro_scenario.on_start()

        await self.mining.add_expansion(self.map.start_base)

    async def on_step(self, step: int):
        await self.debug.on_step_start(step)
        if self.micro_scenario is not None and self.micro_scenario.running:
            await self.micro_scenario.on_step()

        self.resources.reset(self.api.minerals, self.api.vespene)

        # if self.time >= 180:
        #    self.logger.info("Minerals at 3 min = {}", self.minerals)

        # Update other systems
        await self.history.on_step(step)
        await self.order.on_step(step)
        await self.micro(step)
        await self.tasks.on_step(step)
        await self.mining.on_step(step)

        await self.debug.on_step_end(step)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await self.debug.on_unit_took_damage(unit, amount_damage_taken)

    # --- Properties

    @property
    def time(self) -> float:
        return self.api.time

    @property
    def logger(self) -> Logger:
        return self.debug.logger

    # --- Units

    @property
    def units(self) -> Units:
        return self.api.units

    @property
    def workers(self) -> Units:
        return self.api.workers

    @property
    def army(self) -> Units:
        return self.units - self.workers

    @property
    def structures(self) -> Units:
        return self.api.structures

    @property
    def townhalls(self) -> Units:
        return self.api.townhalls

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
            return self.api.game_data.units[utype.value].creation_ability.exact_id
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
            #if self.mining.has_worker(worker):
            #    return include_collecting
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
                                      * self.api.get_remaining_construction_time(unit)
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

    async def micro(self, iteration: int) -> None:

        units = self.units - self.workers
        await self.combat.micro_units(units)

        if iteration % 8 == 0:
            for unit in self.structures(UnitTypeId.SUPPLYDEPOT).ready.idle:
                raise_depot = self.api.enemy_units.closer_than(2.5, unit)
                unit(AbilityId.MORPH_SUPPLYDEPOT_RAISE if raise_depot else AbilityId.MORPH_SUPPLYDEPOT_LOWER)

        if iteration % 8 == 0:
            for orbital in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
                if orbital.energy >= 50:
                    mineral_fields = self.api.mineral_field.in_distance_between(orbital.position, 0, 8)
                    if mineral_fields:
                        mineral_field = mineral_fields.closest_to(orbital.position)
                        self.order.ability(orbital, AbilityId.CALLDOWNMULE_CALLDOWNMULE, mineral_field)
