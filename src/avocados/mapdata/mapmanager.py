import itertools
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import numpy
from numpy import ndarray
from sc2.game_info import Ramp
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
    base: ExpansionLocation
    expansions: list[ExpansionLocation]
    expansion_distance_matrix: ndarray
    expansion_path_distance_matrix: ndarray
    expansion_order: list[tuple[int, float]]
    enemy_start_locations: list[ExpansionLocation]
    enemy_start_location: Optional[ExpansionLocation] # Only set once known
    enemy_expansion_order: list[list[tuple[int, float]]]
    ramp_defense_location: Optional[Point2]
    placement_grid: PixelMap

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        # Initialization of variables happens in on_start

    @property
    def width(self) -> int:
        return self.api.game_info.playable_area.width

    @property
    def height(self) -> int:
        return self.api.game_info.playable_area.height

    @property
    def number_expansions(self) -> int:
        return len(self.expansions)

    async def on_start(self) -> None:
        self.logger.debug("on_start started")
        self.center = self.api.game_info.map_center
        self.start_base = ExpansionLocation(self.bot, self.api.start_location)
        self.base = self.start_base # TODO: use later in case we lose the start_base

        self.expansions = [ExpansionLocation(self.bot, location) for location in self._get_expansion_list()]

        self.expansion_distance_matrix, self.expansion_path_distance_matrix = \
            await self._calculate_expansion_distances()

        self.expansion_order = sorted(  # noqa
            [(idx, self.expansion_path_distance_matrix[self.start_base.index, exp.index])
             for idx, exp in enumerate(self.expansions)], key=lambda x: x[1]
        )

        # Enemy
        self.enemy_start_locations = [ExpansionLocation(self.bot, loc) for loc in self.api.enemy_start_locations]
        self.enemy_expansion_order = []
        for loc in self.enemy_start_locations:
            self.enemy_expansion_order.append(sorted(   # noqa
                #[(idx, loc.center.distance_to(exp.center)) for idx, exp in enumerate(self.expansions)],
                [(idx, self.expansion_path_distance_matrix[loc.index, exp.index])
                 for idx, exp in enumerate(self.expansions)], key=lambda x: x[1]
            ))
        self.enemy_start_location = self.enemy_start_locations[0] if len(self.enemy_start_locations) == 1 else None

        self.ramp_defense_location = self.main_base_ramp.top_center if self.main_base_ramp else None
        self.placement_grid = self.api.game_info.placement_grid.copy()
        self.logger.debug("on_start finished")

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

    @property
    def main_base_ramp(self) -> Optional[Ramp]:
        try:
            return self.api.main_base_ramp
        except ValueError:
            return None

    def nearest_pathable(self, point: Point2) -> Optional[Point2]:
        if self.api.in_pathing_grid(point):
            return point

        # TODO: This can be improved

        def cells_by_distance(center: Point2, width: int, height: int) -> list[Point2]:
            cells = [Point2((center.x + x, center.y + y))
                     for x, y in itertools.product(range(-width, width+1), range(-height, height+1))]
            cells.sort(key=lambda c: (c.x - 2*center.x) ** 2 + (c.y - 2*center.y) ** 2)
            return cells

        for size in range(3, 21, 2):
            for point in cells_by_distance(point, size, size):
                if self.api.in_pathing_grid(point):
                    return point
        else:
            return None

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
        return self.expansions[idx].center.towards(self.center, 2)

    def _get_expansion_list(self) -> list[Point2]:
        try:
            expansion_list = self.api.expansion_locations_list
        except AssertionError:
            return []
        # Sort bottom-left to top-right
        expansion_list.sort(key=lambda exp: 5*exp.y + exp.x)
        return expansion_list

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:
        match utype:
            case UnitTypeId.REFINERY:
                if near is None:
                    near = self.start_base.center
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
                if self.main_base_ramp:
                    ramp_positions = [p for p in self.main_base_ramp.corner_depots
                                 if await self.api.can_place_single(utype, p)]
                    if ramp_positions:
                        return self.start_base.center.closest(ramp_positions)
                    if await self.api.can_place_single(utype, self.main_base_ramp.depot_in_middle):
                        return self.main_base_ramp.depot_in_middle
                return await self.api.find_placement(utype, near=self.start_base.region_center,
                                                     random_alternative=False)

            case UnitTypeId.BARRACKS:
                if near is None:
                    if self.main_base_ramp:
                        ramp_position = self.main_base_ramp.barracks_correct_placement
                        if await self.api.can_place_single(utype, ramp_position):
                            return ramp_position
                    return await self.api.find_placement(utype, near=self.start_base.region_center,
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
        distances = [1.4 * unit.distance_to(destination) for unit in units]
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

    # --- Private

    async def _calculate_expansion_distances(self, *, pathing_query_radius: float = 3) -> tuple[ndarray, ndarray]:
        distance_matrix = numpy.zeros((self.number_expansions, self.number_expansions))
        path_distance_matrix = numpy.zeros((self.number_expansions, self.number_expansions))
        for idx1, exp1 in enumerate(self.expansions):
            for idx2, exp2 in enumerate(self.expansions[:idx1]):
                dist = exp1.center.distance_to(exp2.center)
                distance_matrix[idx1, idx2] = dist
                distance_matrix[idx2, idx1] = dist
                p1 = exp1.center.towards(exp2.center, pathing_query_radius)
                p2 = exp2.center.towards(exp1.center, pathing_query_radius)
                path_dist = await self.api.client.query_pathing(p1, p2)
                if path_dist is None:
                    self.logger.warning("Cannot determine pathing distance between {} and {} (distance={:.2f})",
                                        exp1, exp2, dist)
                    path_dist = numpy.inf
                else:
                    path_dist += 2 * pathing_query_radius
                path_distance_matrix[idx1, idx2] = path_dist
                path_distance_matrix[idx2, idx1] = path_dist
                #self.logger.debug("Distances {} to {}: direct={:.2f}, path={:.2f}", exp1, exp2, dist, path_dist)
        return distance_matrix, path_distance_matrix

    # --- debug

    def on_debug(self) -> None:
        for exp in self.expansions:
            exp.on_debug()
        for idx1, exp1 in enumerate(self.expansions):
            for idx2, exp2 in enumerate(self.expansions[:idx1]):
                text = (f"d={self.expansion_distance_matrix[idx1, idx2]:.2f}, "
                        f"D={self.expansion_path_distance_matrix[idx1, idx2]:.2f}")
                self.debug.line(exp1.center, exp2.center, text_start=text)
                text = (f"d={self.expansion_distance_matrix[idx2, idx1]:.2f}, "
                        f"D={self.expansion_path_distance_matrix[idx2, idx1]:.2f}")
                self.debug.line(exp2.center, exp1.center, text_start=text)
