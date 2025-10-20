import random
from enum import Enum
from typing import Optional

from loguru._logger import Logger
from sc2.bot_ai import BotAI
from sc2.constants import IS_STRUCTURE
from sc2.game_data import Cost
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.ability_id import AbilityId

from sc2bot.core.commander import Commander
from sc2bot.core.debug import Debug
from sc2bot.core.history import History
from sc2bot.core.mapdata import MapData


class BotBase(BotAI):
    name: str
    seed: int
    logger: Logger
    debug: Debug
    commander: dict[str, Commander]
    history: History
    map: Optional[MapData]
    debug_enabled: bool

    def __init__(self, name: str, *, seed: int = 0, debug_enabled: bool = True) -> None:
        super().__init__()
        self.name = name
        self.seed = seed
        random.seed(seed)
        self.debug = Debug(self)
        self.history = History(self)
        self.commander = {}
        self.logger.debug("Initialized {}", self)
        self.map = None
        self.debug_enabled = debug_enabled

    def __repr__(self) -> str:
        return f"{self.name}(seed={self.seed})"

    @property
    def logger(self) -> Logger:
        return self.debug.logger

    async def on_start(self) -> None:
        self.client.game_step = 1
        self.map = await MapData.analyze_map(self)
        self.load_strategy()

    def load_strategy(self) -> None:
        pass

    async def on_step(self, step: int):
        if self.debug_enabled:
            self.debug.on_step_start(step)

        self.history.on_step(step)
        # Update commander
        for commander in self.commander.values():
            await commander.on_step(step)

        if self.debug_enabled:
            self.debug.on_step_end(step)

    # --- Commanders

    def add_commander(self, name, **kwargs) -> Commander:
        commander = Commander(self, name, **kwargs)
        self.commander[name] = commander
        self.logger.debug("Adding {}", commander)
        return commander

    def remove_commander(self, name: str) -> Commander:
        commander = self.commander.pop(name)
        self.logger.debug("Removing {}", commander)
        return commander

    def get_controlling_commander(self, unit: Unit | int) -> Optional[Commander]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        for commander in self.commander.values():
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
        self.logger.trace("Unit {} created", unit)
        # TODO fix
        self.commander['ProxyMarine'].add_units(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        commander = self.get_controlling_commander(unit_tag)
        self.logger.trace("Unit {} destroyed (commander= {})", unit_tag, commander)
        if commander is not None:
            commander.remove_units(unit_tag)

    async def on_building_construction_started(self, unit: Unit) -> None:
        self.logger.trace("Building {} construction started", unit)
        # TODO fix
        self.commander['ProxyMarine'].add_units(unit)
