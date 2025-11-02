import heapq
from collections import Counter
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
import sys

from loguru import logger as _logger
from loguru._logger import Logger
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.buildordermanager import BuildOrderManager
from avocados.core.constants import TRAINERS, RESEARCHERS
from avocados.core.historymanager import HistoryManager
from avocados.core.miningmanager import MiningManager
from avocados.core.unitutil import get_unit_type_counts
from avocados.debug.debugmanager import DebugManager
from avocados.debug.micro_scenario_manager import MicroScenarioManager
from avocados.mapdata.mapmanager import MapManager
from avocados.core.orders import Order, OrderManager
from avocados.core.resourcemanager import ResourceManager
from avocados.core.objectivemanager import ObjectiveManager
from avocados.core.geomutil import LineSegment
from avocados.micro.combat import CombatManager
from avocados.micro.squadmanager import SquadManager

if TYPE_CHECKING:
    from avocados.core.botapi import BotApi


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


LOG_FORMAT = "<green>[{extra[step]}|{extra[time]:.3f}|{extra[prefix]}]</green> <level>{message}</level>"


class AvocaDOS:
    api: 'BotApi'
    name: str
    logger: Logger
    # Manager
    map: Optional[MapManager]
    build: BuildOrderManager
    order: OrderManager
    resources: ResourceManager
    objectives: ObjectiveManager
    squads: SquadManager
    combat: CombatManager
    mining: MiningManager
    history: HistoryManager
    debug: Optional[DebugManager]
    micro_scenario: Optional[MicroScenarioManager]
    # Other
    previous_orders: dict[int, Optional[Order]]

    def __init__(self, api: 'BotApi', *,
                 name: str = 'AvocaDOS',
                 build: Optional[str] = None,
                 debug: bool = True,
                 log_level: str = "DEBUG",
                 log_file: Optional[str] = 'AvocaDOS_{time:YYYY-MM-DD_HH-mm-ss}.log',
                 micro_scenario: Optional[dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]] = None,
                 ) -> None:
        super().__init__()
        self.api = api
        self.name = name

        # Logging
        self.logger = _logger.bind(bot=name, prefix=name, step=0, time=0)
        self.logger.remove()
        self.logger.add(
            sys.stdout,
            level=log_level,
            filter=lambda record: record['extra'].get('bot') == self.name,
            format=LOG_FORMAT,
        )
        if log_file:
            self.logger.add(
                f'data/{log_file}',
                level=log_level,
                filter=lambda record: record['extra'].get('bot') == self.name,
                format=LOG_FORMAT,
                rotation='1 day',
                retention='14 days',
            )

        # Manager
        self.build = BuildOrderManager(self, build=build)
        self.order = OrderManager(self)
        self.resources = ResourceManager(self)
        self.objectives = ObjectiveManager(self)
        self.squads = SquadManager(self)
        self.combat = CombatManager(self)
        self.mining = MiningManager(self)
        self.history = HistoryManager(self)
        self.map = MapManager(self)
        self.debug = DebugManager(self) if debug else None
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
        self.logger = self.logger.bind(step=self.api.state.game_loop, time=self.api.time)
        if self.micro_scenario is not None and self.micro_scenario.running:
            await self.micro_scenario.on_step(step)

        # if self.time >= 180:
        #    self.logger.info("Minerals at 3 min = {}", self.minerals)

        await self.map.on_step(step)
        await self.resources.on_step(step)
        await self.history.on_step(step)
        await self.order.on_step(step)
        await self.objectives.on_step(step)
        await self.mining.on_step(step)
        await self.squads.on_step(step)
        await self.combat.on_step(step)

        # TODO
        await self.other(step)
        if self.debug:
            await self.debug.on_step(step)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await self.debug.on_unit_took_damage(unit, amount_damage_taken)

    async def on_unit_created(self, unit: Unit) -> None:
        pass

    async def on_building_construction_started(self, unit: Unit) -> None:
        pass

    async def on_building_construction_finished(self, unit: Unit) -> None:
        pass

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        pass

    # --- Properties

    @property
    def time(self) -> float:
        return self.api.time

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
        return get_unit_type_counts(self.forces)

    # --- Pick unit

    async def pick_workers(self, location: Point2 | LineSegment, *,
                           number: int,
                           target_distance: float = 0.0,
                           include_moving: bool = True,
                           include_collecting: bool = True,
                           include_constructing: bool = True,
                           construction_time_discount: float = 0.7,
                           carrying_resource_penalty: float = 1.5,
                           ) -> list[tuple[Unit, float]]:

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
            workers_and_dist = {
                unit: travel_time
                      + carrying_resource_penalty if unit.is_carrying_resource else 0
                      + construction_time_discount * self.api.get_remaining_construction_time(unit)
                for unit, travel_time in zip(workers, travel_times)
            }
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
        trainer_utype = TRAINERS.get(utype)
        if trainer_utype is None:
            self.logger.error("No trainer for {}", utype)
            return None

        free_trainers = self.structures(trainer_utype).ready.idle.filter(lambda x: not self.order.has_order(x))
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

    # --- Callbacks

    async def other(self, iteration: int) -> None:

        if iteration % 8 == 0:
            for unit in self.structures((UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED)).ready.idle:
                raise_depot = self.api.enemy_units.closer_than(2, unit)
                self.order.ability(unit, AbilityId.MORPH_SUPPLYDEPOT_RAISE
                                         if raise_depot else AbilityId.MORPH_SUPPLYDEPOT_LOWER)

        if iteration % 8 == 0:
            for orbital in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
                if orbital.energy >= 50:
                    mineral_fields = self.api.mineral_field.in_distance_between(orbital.position, 0, 8)
                    if mineral_fields:
                        mineral_field = mineral_fields.closest_to(orbital.position)
                        self.order.ability(orbital, AbilityId.CALLDOWNMULE_CALLDOWNMULE, mineral_field)
