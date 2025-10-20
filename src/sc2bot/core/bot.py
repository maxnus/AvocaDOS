import random
from enum import Enum
from typing import Optional

from loguru import logger
from loguru._logger import Logger
from sc2.bot_ai import BotAI
from sc2.constants import IS_STRUCTURE
from sc2.game_data import Cost
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
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

    def __init__(self, name: str, *, seed: int = 0) -> None:
        super().__init__()
        self.name = name
        self.seed = seed
        random.seed(seed)
        self.debug = Debug(self)
        #self.logger = self.debug.logger
        self.history = History(self)
        self.commander = {}
        self.logger.debug("Initialized {}", self)
        self.map = None

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
        #if step == 20:
        #    self.map = await self.analyze_map()
        #    self.load_strategy()

        self.debug.on_step_start(step)

        self.history.on_step(step)
        await self.update_commanders(step)

        self.debug.on_step_end(step)

    # --- Commanders

    def add_commander(self, name, **kwargs) -> Commander:
        commander = Commander(self, name, **kwargs)
        self.commander[name] = commander
        logger.debug("Adding {}", commander)
        return commander

    async def update_commanders(self, iteration: int) -> None:
        for commander in self.commander.values():
            await commander.on_step(iteration)

    def get_controlling_commander(self, unit: Unit) -> Optional[Commander]:
        for commander in self.commander.values():
            if unit.tag in commander.tags:
                return commander
        return None

    # --- Macro utility

    async def expand(self) -> int:
        if not self.can_afford(UnitTypeId.COMMANDCENTER):
            return 0

        target = self.time / 60
        have = self.townhalls(UnitTypeId.COMMANDCENTER).amount
        pending = self.already_pending(UnitTypeId.COMMANDCENTER)
        to_build = int(target - have - pending)
        queued = 0
        for _ in range(to_build):
            await self.expand_now()
            queued += 1
        return queued

    async def build_supply(self):
        ccs = self.townhalls(UnitTypeId.COMMANDCENTER).ready
        if ccs.exists:
            cc = ccs.first
            if self.supply_left < 4 and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
                if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                    await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 5))

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
            return 0.0
        return self.get_cost(building.type_id).time * (1 - building.build_progress)

    async def get_travel_distances(self, start: Units | list[Point2], destination: Point2) -> list[float]:
        if isinstance(start, Units):
            flying_units = start.flying
            if flying_units:
                raise NotImplementedError
            ground_units = start.not_flying
            query = [[unit, destination] for unit in ground_units]
        else:
            query = [[position, destination] for position in start]
        #self.logger.warning("query={}", query)
        distances = await self.client.query_pathings(query)
        #self.logger.warning("distances={}", distances)

        #distances = [d if d >= 0 else None for d in distances]
        return distances

    async def get_travel_time(self, unit: Unit, destination: Point2, *,
                              target_distance: float = 0.0) -> float:
        if unit.is_flying:
            distance = unit.distance_to(destination)
        else:
            distance = await self.client.query_pathing(unit.position, destination)
            if distance is None:
                # unreachable
                return float('inf')
        distance = max(distance - target_distance, 0)
        speed = 1.4 * unit.real_speed
        return distance / speed

    async def get_travel_times(self, units: Units, destination: Point2, *,
                               target_distance: float = 0.0) -> list[float]:
        #distances = [d if d is not None else float('inf') for d in await self.get_travel_distances(units, destination)]
        distances = await self.get_travel_distances(units, destination)
        times = [max(d - target_distance, 0) / (1.4 * unit.real_speed) for (unit, d) in zip(units, distances)]
        return times

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:
        match utype:
            case UnitTypeId.REFINERY:
                geysers = self.vespene_geyser.closer_than(10.0, self.map.base_center)
                if geysers:
                    return geysers.random

            case UnitTypeId.SUPPLYDEPOT:
                positions = [p for p in self.main_base_ramp.corner_depots if await self.can_place_single(utype, p)]
                if positions:
                    return self.map.base_center.closest(positions)
                return await self.find_placement(utype, near=self.map.base_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    position = self.main_base_ramp.barracks_correct_placement
                    if await self.can_place_single(utype, position):
                        return position
                    return await self.find_placement(utype, near=self.map.base_center, addon_place=True)
                else:
                    return await self.find_placement(utype, near=near, max_distance=max_distance,
                                                     random_alternative=False, addon_place=True)
            case UnitTypeId.COMMANDCENTER:
                if near is None:
                    self.logger.error("NotImplemented")
                else:
                    return await self.find_placement(utype, near=near)
            case _:
                self.logger.error("Not implemented: {}", utype)
        return None

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
        self.commander['ProxyMarine'].take_control(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        self.logger.trace("Building {} construction started", unit)
        # TODO fix
        self.commander['ProxyMarine'].take_control(unit)
