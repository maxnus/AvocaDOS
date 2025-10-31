from dataclasses import dataclass
from typing import Self, TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.system import System
from sc2bot.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class MapData(System):
    center: Point2
    start_base: ExpansionLocation
    expansions: list[ExpansionLocation]
    expansion_order: list[tuple[int, float]]
    enemy_start_locations: list[ExpansionLocation]
    enemy_expansion_order: list[list[tuple[int, float]]]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)

        self.center = bot.game_info.map_center
        self.start_base = ExpansionLocation(self.bot, self.bot.start_location)

        self.expansions = [ExpansionLocation(self.bot, location) for location in self._get_expansion_list()]
        self.expansion_order = sorted(
            [(idx, self.start_base.center.distance_to(exp.center)) for idx, exp in enumerate(self.expansions)],
            key=lambda x: x[1]
        )

        # Enemy
        self.enemy_start_locations = [ExpansionLocation(self.bot, loc) for loc in self.bot.enemy_start_locations]
        self.enemy_expansion_order = []
        for enemy_start_location in self.enemy_start_locations:
            self.enemy_expansion_order.append(sorted(
                [(idx, enemy_start_location.center.distance_to(exp.center)) for idx, exp in enumerate(self.expansions)],
                key=lambda x: x[1]
            ))

    def get_proxy_location(self) -> Point2:
        idx = self.enemy_expansion_order[0][2][0]
        return self.expansions[idx].center

    def _get_expansion_list(self) -> list[Point2]:
        try:
            return self.bot.expansion_locations_list
        except AssertionError:
            return []

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:
        match utype:
            case UnitTypeId.REFINERY:
                if near is None:
                    near = self.bot.map.start_base.center
                geysers = self.bot.vespene_geyser.closer_than(10.0, near)
                if geysers:
                    return geysers.random

            case UnitTypeId.SUPPLYDEPOT:
                positions = [p for p in self.bot.main_base_ramp.corner_depots if await self.bot.can_place_single(utype, p)]
                if positions:
                    return self.bot.map.start_base.center.closest(positions)
                if await self.bot.can_place_single(utype, self.bot.main_base_ramp.depot_in_middle):
                    return self.bot.main_base_ramp.depot_in_middle
                return await self.bot.find_placement(utype, near=self.bot.map.start_base.base_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    position = self.bot.main_base_ramp.barracks_correct_placement
                    if await self.bot.can_place_single(utype, position):
                        return position
                    return await self.bot.find_placement(utype, near=self.bot.map.start_base.base_center,
                                                         addon_place=True)
                else:
                    return await self.bot.find_placement(utype, near=near, max_distance=max_distance,
                                                    random_alternative=False, addon_place=True)
            case UnitTypeId.COMMANDCENTER:
                if near is None:
                    self.bot.logger.error("NotImplemented")
                else:
                    return await self.bot.find_placement(utype, near=near)
            case _:
                self.bot.logger.error("Not implemented: {}", utype)
        return None

    async def get_travel_times(self, units: Units, destination: Point2, *,
                               target_distance: float = 0.0) -> list[float]:
        #distances = [d if d is not None else float('inf') for d in await self.get_travel_distances(units, destination)]
        #distances = await self.get_travel_distances(units, destination)
        # Too expensive at the moment, use euclidean distance instead
        distances = [1.2 * unit.distance_to(destination) for unit in units]
        times = [max(d - target_distance, 0) / (1.4 * unit.real_speed) for (unit, d) in zip(units, distances)]
        return times

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
        distances = await self.bot.client.query_pathings(query)
        #self.logger.warning("distances={}", distances)

        #distances = [d if d >= 0 else None for d in distances]
        return distances

    async def get_travel_time(self, unit: Unit, destination: Point2, *,
                              target_distance: float = 0.0) -> float:
        if unit.is_flying:
            distance = unit.distance_to(destination)
        else:
            distance = await self.bot.client.query_pathing(unit.position, destination)
            if distance is None:
                # unreachable
                return float('inf')
        distance = max(distance - target_distance, 0)
        speed = 1.4 * unit.real_speed
        return distance / speed
