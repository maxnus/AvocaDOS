import asyncio
import random
from enum import Enum
from time import perf_counter
from typing import Optional

from loguru._logger import Logger
from sc2.bot_ai import BotAI
from sc2.constants import IS_STRUCTURE
from sc2.game_data import Cost
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.ability_id import AbilityId

from sc2bot.build import BuildOrder, get_build_order
from sc2bot.core.commander import Commander
from sc2bot.debug.debugsystem import DebugSystem
from sc2bot.core.history import History
from sc2bot.mapdata.mapdata import MapData
from sc2bot.core.util import UnitCost
from sc2bot.debug.micro_scenario_manager import MicroScenarioManager


class AvocaDOS(BotAI):
    name: str
    # Systems
    build: Optional[BuildOrder]
    commanders: dict[str, Commander]
    history: History
    map: Optional[MapData]
    # Debug
    debug: DebugSystem
    micro_scenario: Optional[MicroScenarioManager]

    def __init__(self, name: Optional[str] = None, *,
                 build: Optional[str] = None,
                 seed: int = 0,
                 slowdown: float = 0,
                 log_level: str = "DEBUG",
                 micro_scenario: Optional[dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]] = None,
                 ) -> None:
        super().__init__()
        self.name = name or self.__class__.__name__
        random.seed(seed)
        # Systems
        if build:
            self.build = get_build_order(build)(self)
        else:
            self.build = None
        self.history = History(self)
        self.commanders = {}
        self.map = None
        # Debug
        self.debug = DebugSystem(self, slowdown=slowdown, log_level=log_level)
        if micro_scenario is not None:
            self.micro_scenario = MicroScenarioManager(self, units=micro_scenario)
        else:
            self.micro_scenario = None
        self.logger.debug("Initialized {}", self)

    def __repr__(self) -> str:
        return self.name

    @property
    def logger(self) -> Logger:
        return self.debug.logger

    async def on_start(self) -> None:
        self.client.game_step = 1
        self.map = MapData(self)

        if self.build is not None:
            self.logger.debug("Loading build order {}", self.build)
            self.build.load()

        commander = self.commanders.get('Main')
        if commander:
            #commander.add_units(self.units | self.structures)
            commander.add_units(self.structures)
            commander.add_units(self.workers.random)
        else:
            self.logger.warning("No main commander found")

        if self.micro_scenario is not None:
            await self.micro_scenario.start()

    async def on_step(self, step: int):
        await self.debug.on_step_start(step)
        if self.micro_scenario is not None and self.micro_scenario.running:
            await self.micro_scenario.step()
        # Distribute resources
        if self.commanders:
            commander = max(self.commanders.values(), key=lambda cmd: cmd.resource_priority)
            commander.resources.reset(self.minerals, self.vespene)
        # Update commander
        for commander in self.commanders.values():
            await commander.on_step(step)
        # Update other systems
        await self.history.on_step(step)
        await self.debug.on_step_end(step)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await self.debug.on_unit_took_damage(unit, amount_damage_taken)

    # --- Commanders

    def add_commander(self, name, **kwargs) -> Commander:
        commander = Commander(self, name, **kwargs)
        self.logger.debug("Adding {}", commander)
        self.commanders[name] = commander
        return commander

    def remove_commander(self, name: str) -> Commander:
        commander = self.commanders.pop(name)
        self.logger.debug("Removing {}", commander)
        return commander

    def get_commander_of(self, unit: Unit | int) -> Optional[Commander]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        for commander in self.commanders.values():
            if tag in commander.tags:
                return commander
        return None

    # --- Base utility

    def get_attributes(self, utype: UnitTypeId) -> list[Enum]:
        return self.game_data.units[utype.value].attributes

    def is_structure(self, utype: UnitTypeId) -> bool:
        return IS_STRUCTURE in self.get_attributes(utype)

    def get_scv_build_target(self, scv: Unit) -> Optional[Unit]:
        """Return the building unit that this SCV is constructing, or None."""
        if not scv.is_constructing_scv:
            return None
        # Try to match via nearby incomplete structure
        buildings_being_constructed = self.structures.filter(lambda s: s.build_progress < 1)
        if not buildings_being_constructed:
            return None
        target = buildings_being_constructed.closest_to(scv)
        if target and scv.distance_to(target) < 3:
            return target
        return None

    def get_cost(self, utype: UnitTypeId) -> Cost:
        return self.game_data.units[utype.value].cost

    def get_unit_value(self, unit: UnitTypeId | Unit | Units) -> UnitCost:
        """Return 450 for orbital"""
        if isinstance(unit, Unit):
            unit = unit.type_id
        if isinstance(unit, Units):
            return sum((self.get_unit_value(u) for u in unit), start=UnitCost(0, 0, 0))

        cost = self.get_cost(unit)
        supply = self.game_data.units[unit.value]._proto.food_required
        return UnitCost(cost.minerals, cost.vespene, supply)

    def get_remaining_construction_time(self, scv: Unit) -> float:
        if not scv.is_constructing_scv:
            return 0
        building = self.get_scv_build_target(scv)
        if not building:
            return 0
        return self.get_cost(building.type_id).time * (1 - building.build_progress)

    def estimate_resource_collection_rates(self, *,
                                           excluded_workers: Optional[Unit | Units] = None,
                                           worker_mineral_rate: float = 1.0) -> tuple[float, float]:
        # TODO only correctly placed townhalls
        mineral_workers = 0
        for townhall in self.townhalls:
            mineral_workers += len(self.workers_mining_at(townhall, excluded_workers=excluded_workers))
        mineral_rate = max(worker_mineral_rate * mineral_workers, 0)
        return mineral_rate, 0

    def workers_mining_at(self, townhall: Unit, *,
                          excluded_workers: Optional[Unit | Units] = None,
                          radius: float = 10.0) -> Units:
        """Return number of workers currently mining minerals around a specific base."""
        nearby_minerals = self.mineral_field.closer_than(radius, townhall)
        if not nearby_minerals:
            return Units([], self)
        allowed_orders = {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}
        allowed_tags = {0, townhall.tag, *(m.tag for m in nearby_minerals)}
        workers = self.workers.closer_than(radius, townhall)
        if excluded_workers:
            excluded_workers_tags = (excluded_workers.tags if isinstance(excluded_workers, Units)
                                     else {excluded_workers.tag})
            workers = workers.tags_not_in(excluded_workers_tags)
        workers = workers.filter(lambda w: (w.orders and w.orders[0].ability.id in allowed_orders) and w.order_target in allowed_tags)
        return Units(workers, self)

    async def on_unit_created(self, unit: Unit) -> None:
        await self._assign_new_unit(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        await self._assign_new_unit(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        commander = self.get_commander_of(unit_tag)
        if commander is not None:
            commander.remove_units(unit_tag)

    async def _assign_new_unit(self, unit: Unit) -> None:
        for commander in self.commanders.values():
            if await commander.is_expected_unit(unit):
                break
        else:
            self.logger.debug("Unexpected new unit: {} at {}", unit, unit.position)
            commander = self.commanders.get('Main')
            if commander:
                commander.add_units(unit)
