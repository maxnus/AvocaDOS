import itertools
from collections.abc import Callable, Collection
from typing import TYPE_CHECKING, Optional

import numpy
from numpy import ndarray
from sc2.pixel_map import PixelMap
from sc2.position import Point2, Rect
from sc2.unit import Unit
from sc2.units import Units

from avocados.geometry.field import Field
from avocados.core.manager import BotManager
from avocados.geometry.region import Region
from avocados.geometry.util import Area, Rectangle
from avocados.mapdata.expansion import ExpansionLocation, StartLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class MapManager(BotManager):
    center: Point2
    placement_grid: Field[bool]
    pathing_grid: Field[bool]
    creep: Field[bool]
    terrain_height: Field[int]
    base: ExpansionLocation
    expansions: list[ExpansionLocation]
    expansion_distance_matrix: ndarray
    expansion_path_distance_matrix: ndarray
    # Start locations
    start_location: StartLocation
    enemy_start_locations: list[StartLocation]
    known_enemy_start_location: Optional[StartLocation] # Only set once known

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        # Initialization of variables happens in on_start

    @property
    def playable_area(self) -> Rect:
        return self.api.game_info.playable_area

    @property
    def playable_rect(self) -> Rectangle:
        return Rectangle.from_rect(self.api.game_info.playable_area)

    @property
    def playable_mask(self) -> tuple[slice, slice]:
        return (slice(self.playable_area.x, self.playable_area.right),
                slice(self.playable_area.y, self.playable_area.top))

    @property
    def playable_mask_yx(self) -> tuple[slice, slice]:
        return (slice(self.playable_area.y, self.playable_area.top),
                slice(self.playable_area.x, self.playable_area.right))

    @property
    def playable_offset(self) -> Point2:
        return self.bottom_left

    @property
    def bottom_left(self) -> Point2:
        return Point2((self.playable_area.x, self.playable_area.y))

    @property
    def bottom_right(self) -> Point2:
        return Point2((self.playable_area.right, self.playable_area.y))

    @property
    def top_left(self) -> Point2:
        return Point2((self.playable_area.x, self.playable_area.top))

    @property
    def top_right(self) -> Point2:
        return Point2((self.playable_area.right, self.playable_area.top))

    @property
    def width(self) -> int:
        return int(self.playable_area.width)

    @property
    def height(self) -> int:
        return int(self.playable_area.height)

    @property
    def total_width(self) -> int:
        return int(self.api.game_info.map_size.width)

    @property
    def total_height(self) -> int:
        return int(self.api.game_info.map_size.height)

    @property
    def number_expansions(self) -> int:
        return len(self.expansions)

    @property
    def all_start_locations(self) -> list[StartLocation]:
        return [self.start_location] + self.enemy_start_locations

    async def on_start(self) -> None:
        self.logger.debug("on_start started")
        self.center = self.api.game_info.map_center

        # Fields
        self.placement_grid = self.create_field_from_pixelmap(self.api.game_info.placement_grid)
        self.pathing_grid = self.create_field_from_pixelmap(self.api.game_info.pathing_grid)
        self.creep = self.create_field_from_pixelmap(self.api.state.creep)
        self.terrain_height = self.create_field_from_pixelmap(self.api.game_info.terrain_height)

        self.logger.info(
            "Map={}, size={}x{}, playable={}, center={}, placement_grid={}, pathing_grid={}, creep={}",
            self.api.game_info.map_name,
            self.total_width,
            self.total_height,
            self.playable_area,
            self.center,
            self.placement_grid,
            self.pathing_grid,
            self.creep
        )

        self.expansion_distance_matrix, self.expansion_path_distance_matrix = \
            await self._calculate_expansion_distances()

        start_locations = [self.api.start_location] + self.api.enemy_start_locations
        self.expansions = [(StartLocation if location in start_locations else ExpansionLocation)(self.bot, location)
                           for location in self._get_ordered_expansion()]

        self.start_location = StartLocation(self.bot, self.api.start_location)
        self.base = self.start_location # TODO: use later in case we lose the start_base
        self.enemy_start_locations = [StartLocation(self.bot, loc) for loc in self.api.enemy_start_locations]
        self.known_enemy_start_location = self.enemy_start_locations[0] if len(self.enemy_start_locations) == 1 else None
        self.logger.debug("on_start finished")

    async def on_step_start(self, step: int) -> None:
        self.pathing_grid.data = self.api.game_info.pathing_grid.data_numpy.transpose()[self.playable_mask]
        self.creep.data = self.api.state.creep.data_numpy.transpose()[self.playable_mask]

        # check for enemy start location

        # TODO: consider buildings on ramp or natural, if before ~3 min mark
        if self.known_enemy_start_location is None and step % 16 == 0:
            for loc in self.enemy_start_locations.copy():
                if self.api.enemy_structures.closer_than(10, loc.center):
                    self.logger.info("Found enemy start location at {}", loc)
                    self.enemy_start_locations = [loc]
                    break
                if self.any_part_of_area_is_visible(Rectangle.from_center(loc.center, 5, 5)):
                    self.logger.info("Enemy start location not at {}", loc)
                    self.enemy_start_locations.remove(loc)
            if len(self.enemy_start_locations) == 1:
                self.known_enemy_start_location = self.enemy_start_locations[0]
                self.logger.info("Enemy start location must be at {}", self.known_enemy_start_location)

    def create_field_from_pixelmap(self, pixelmap: PixelMap) -> Field:
        return Field(pixelmap.data_numpy.transpose()[self.playable_mask], offset=self.playable_offset)

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

    def any_part_of_area_is_visible(self, area: Area) -> bool:
        bounds = area.bounding_rect(integral=True)
        for x in range(int(bounds.x), int(bounds.x + bounds.width)):
            for y in range(int(bounds.y), int(bounds.y + bounds.width)):
                if (point := Point2((x, y))) not in area:
                    continue
                if self.state.visibility[point] > 0:    # 0: Hidden, 1: Fog, 2: Visible
                    return True
        return False

    # def get_expansion(self, *,
    #                   func: Callable[[ExpansionLocation], float],
    #                   exclude: Optional[ExpansionLocation | Collection[ExpansionLocation]] = None) -> ExpansionLocation:
    #     expansions = self.expansions
    #     if exclude is not None:
    #         if isinstance(exclude, ExpansionLocation):
    #             exclude = [exclude]
    #         expansions = [exp for exp in expansions if exp not in exclude]
    #     expansion = max(expansions, key=func)
    #     return expansion

    def get_expansions(self, *,
                       sort_by: Optional[Callable[[ExpansionLocation], float]] = None,
                       exclude: Optional[ExpansionLocation | Collection[ExpansionLocation]] = None,
                       reverse: bool = False) -> list[ExpansionLocation]:
        expansions = self.expansions
        if exclude is not None:
            if isinstance(exclude, ExpansionLocation):
                exclude = [exclude]
            expansions = [exp for exp in expansions if exp not in exclude]
        if sort_by is not None:
            expansions = sorted(expansions, key=sort_by, reverse=reverse)
        return expansions

    def get_proxy_location(self) -> Point2:
        start_location = self.enemy_start_locations[0]
        #fourth = min(start_location.expansion_order[3:5], key=lambda loc: loc.distance_to(start_location.line_third))
        #proxy =  fourth.center.towards(fourth.mineral_field_center, 3)
        #return start_location.line_third.center.towards(start_location.center, -2)

        third = start_location.line_third
        proxy = third.center.towards(third.mineral_field_center)

        self.logger.info("Proxy location: {}", proxy)
        return proxy

    def _get_ordered_expansion(self) -> list[Point2]:
        try:
            expansion_list = self.api.expansion_locations_list
        except AssertionError:
            return []
        # Sort bottom-left to top-right
        expansion_list.sort(key=lambda exp: 5*exp.y + exp.x)
        return expansion_list

    async def get_travel_times(self, units: Units, destination: Point2, *,
                               target_distance: float = 0.0) -> list[float]:
        #distances = [d if d is not None else float('inf') for d in await self.get_travel_distances(units, destination)]
        distances = await self.get_travel_distances(units, destination)
        # Too expensive at the moment, use euclidean distance instead
        #distances = [1.4 * unit.distance_to(destination) for unit in units]
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
        distances = [d if d is not None else float('inf') for d in distances]

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

    def floodfill(self, start: Point2, predicate: Callable[[Point2], bool], *,
                  max_distance: Optional[float] = None,
                  in_placement_grid: bool = True) -> Region:
        points: set[Point2] = set()
        queue: list[Point2] = [start]
        while queue:
            point = queue.pop()
            if point not in self.playable_rect:
                continue
            if point in points:
                continue
            if in_placement_grid and not self.map.placement_grid[point]:
                continue
            if max_distance is not None and point.distance_to(start) > max_distance:
                continue
            if predicate(point):
                points.add(point)
                queue += [Point2((point.x + dx, point.y + dy))
                          for dx in [-1, 0, 1] for dy in [-1, 0, 1]
                          if not (dx == 0 and dy == 0)]
        return Region(points)

    # --- Private

    async def _calculate_expansion_distances(self, *, pathing_query_radius: float = 3) -> tuple[ndarray, ndarray]:
        expansions = self._get_ordered_expansion()
        number_expansions = len(expansions)
        distance_matrix = numpy.zeros((number_expansions, number_expansions))
        path_distance_matrix = numpy.zeros((number_expansions, number_expansions))
        for idx1, exp1 in enumerate(expansions):
            for idx2, exp2 in enumerate(expansions[:idx1]):
                dist = exp1.distance_to(exp2)
                distance_matrix[idx1, idx2] = dist
                distance_matrix[idx2, idx1] = dist
                # TODO: Only needed for starter bases, so we should shift towards the ramp instead?
                p1 = exp1.towards(exp2, pathing_query_radius)
                p2 = exp2.towards(exp1, pathing_query_radius)
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
