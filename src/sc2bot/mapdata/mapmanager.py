from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.botobject import BotObject
from sc2bot.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class MapManager(BotObject):
    center: Point2
    start_base: ExpansionLocation
    expansions: list[ExpansionLocation]
    expansion_order: list[tuple[int, float]]
    enemy_start_locations: list[ExpansionLocation]
    enemy_expansion_order: list[list[tuple[int, float]]]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)

    async def on_start(self) -> None:
        self.center = self.api.game_info.map_center
        self.start_base = ExpansionLocation(self.bot, self.api.start_location)

        self.expansions = [ExpansionLocation(self.bot, location) for location in self._get_expansion_list()]
        self.expansion_order = sorted(
            [(idx, self.start_base.center.distance_to(exp.center)) for idx, exp in enumerate(self.expansions)],
            key=lambda x: x[1]
        )

        # Enemy
        self.enemy_start_locations = [ExpansionLocation(self.bot, loc) for loc in self.api.enemy_start_locations]
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
            return self.api.expansion_locations_list
        except AssertionError:
            return []

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:
        match utype:
            case UnitTypeId.REFINERY:
                if near is None:
                    near = self.map.start_base.center
                geysers = self.api.vespene_geyser.closer_than(10.0, near)
                if geysers:
                    return geysers.random

            case UnitTypeId.SUPPLYDEPOT:
                positions = [p for p in self.api.main_base_ramp.corner_depots if await self.api.can_place_single(utype, p)]
                if positions:
                    return self.bot.map.start_base.center.closest(positions)
                if await self.api.can_place_single(utype, self.api.main_base_ramp.depot_in_middle):
                    return self.api.main_base_ramp.depot_in_middle
                return await self.api.find_placement(utype, near=self.map.start_base.base_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    position = self.api.main_base_ramp.barracks_correct_placement
                    if await self.api.can_place_single(utype, position):
                        return position
                    return await self.api.find_placement(utype, near=self.map.start_base.base_center,
                                                         addon_place=True)
                else:
                    return await self.api.find_placement(utype, near=near, max_distance=max_distance,
                                                         random_alternative=False, addon_place=True)
            case UnitTypeId.COMMANDCENTER:
                if near is None:
                    self.logger.error("NotImplemented")
                else:
                    return await self.api.find_placement(utype, near=near)
            case _:
                self.logger.error("Not implemented: {}", utype)
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
        distances = await self.api.client.query_pathings(query)
        #self.logger.warning("distances={}", distances)

        #distances = [d if d >= 0 else None for d in distances]
        return distances

    async def get_travel_time(self, unit: Unit, destination: Point2, *,
                              target_distance: float = 0.0) -> float:
        if unit.is_flying:
            distance = unit.distance_to(destination)
        else:
            distance = await self.api.client.query_pathing(unit.position, destination)
            if distance is None:
                # unreachable
                return float('inf')
        distance = max(distance - target_distance, 0)
        speed = 1.4 * unit.real_speed
        return distance / speed
