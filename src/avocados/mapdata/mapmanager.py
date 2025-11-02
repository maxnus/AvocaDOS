from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.pixel_map import PixelMap
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.geomutil import Area, Circle, Rect
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class MapManager(BotObject):
    center: Point2
    start_base: ExpansionLocation
    expansions: list[ExpansionLocation]
    expansion_order: list[tuple[int, float]]
    enemy_start_locations: list[ExpansionLocation]
    enemy_start_location: Optional[ExpansionLocation] # Only set once known
    enemy_expansion_order: list[list[tuple[int, float]]]
    ramp_defense_location: Point2
    placement_grid: PixelMap

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
        for loc in self.enemy_start_locations:
            self.enemy_expansion_order.append(sorted(
                [(idx, loc.center.distance_to(exp.center)) for idx, exp in enumerate(self.expansions)],
                key=lambda x: x[1]
            ))
        self.enemy_start_location = self.enemy_start_locations[0] if len(self.enemy_start_locations) == 1 else None

        self.ramp_defense_location = self.api.main_base_ramp.top_center
        self.placement_grid = self.api.game_info.placement_grid.copy()

    async def on_step(self, step: int) -> None:
        # check for enemy start location
        # TODO: consider buildings on ramp or natural, if before ~3 min mark
        if self.enemy_start_location is None and step % 16 == 0:
            for loc in self.enemy_start_locations.copy():
                if self.api.enemy_structures.closer_than(10, loc.center):
                    self.logger.info("Found enemy start location at {}", loc)
                    self.enemy_start_locations = [loc]
                    break
                if self.any_part_of_area_is_visible(Rect.from_center(loc.center, 5, 5)):
                    self.logger.info("Enemy start location not at {}", loc)
                    self.enemy_start_locations.remove(loc)
            if len(self.enemy_start_locations) == 1:
                self.enemy_start_location = self.enemy_start_locations[0]
                self.logger.info("Enemy start location must be at {}", self.enemy_start_location)

    # async def can_place_building(self, utype: UnitTypeId, position: Point2) -> bool:
    #     footprint_size = int(2 * self.api.game_data.units[utype.value].footprint_radius)
    #
    #     point = position
    #     if not self.placement_grid[point]:
    #         return False
    #
    #     return await self.api.can_place_single(utype, point)

    def any_part_of_area_is_visible(self, area: Area) -> bool:
        bounds = area.bounding_rect(integral=True)
        for x in range(int(bounds.x), int(bounds.x + bounds.width)):
            for y in range(int(bounds.y), int(bounds.y + bounds.width)):
                if (point := Point2((x, y))) not in area:
                    continue
                if self.state.visibility[point] > 0:    # 0: Hidden, 1: Fog, 2: Visible
                    return True
        return False

    def get_expansions(self, sort_by: Optional[Callable[[ExpansionLocation], float]] = None) -> list[ExpansionLocation]:
        raise NotImplementedError

    def get_enemy_expansions(self, start_location_idx: int) -> list[ExpansionLocation]:
        return [self.expansions[idx] for idx, _ in self.enemy_expansion_order[start_location_idx]]

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
                geysers = self.api.vespene_geyser.closer_than(10.0, near).filter(lambda g: g.has_vespene)
                if not geysers:
                    return None
                if len(geysers) == 1:
                    return geysers.first
                geysers_contents = sorted([(geyser, geyser.vespene_contents) for geyser in geysers],
                                          key=lambda x: x[1], reverse=True)
                if geysers_contents[0][1] > geysers_contents[1][1]:
                    return geysers_contents[0][0]
                return geysers.closest_to(near)

            case UnitTypeId.SUPPLYDEPOT:
                ramp_positions = [p for p in self.api.main_base_ramp.corner_depots
                             if await self.api.can_place_single(utype, p)]
                if ramp_positions:
                    return self.bot.map.start_base.center.closest(ramp_positions)
                if await self.api.can_place_single(utype, self.api.main_base_ramp.depot_in_middle):
                    return self.api.main_base_ramp.depot_in_middle
                return await self.api.find_placement(utype, near=self.map.start_base.region_center,
                                                     random_alternative=False)

            case UnitTypeId.BARRACKS:
                if near is None:
                    ramp_position = self.api.main_base_ramp.barracks_correct_placement
                    if await self.api.can_place_single(utype, ramp_position):
                        return ramp_position
                    return await self.api.find_placement(utype, near=self.map.start_base.region_center,
                                                         addon_place=True, random_alternative=False)
                else:
                    return await self.api.find_placement(utype, near=near, max_distance=max_distance,
                                                         random_alternative=False, addon_place=True)

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
