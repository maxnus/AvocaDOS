from typing import Any, TYPE_CHECKING, Optional, Self

from sc2.game_info import Ramp
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados import api
from avocados.core.botobject import BotObject
from avocados.geometry.region import Region
from avocados.geometry import Circle, Rectangle, get_circle_intersections

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


GATHER_RADIUS = 1.325
RETURN_RADIUS = 3.125 # CC = 2.75, SCV = 0.375 (TODO: are other races the same?)
MINERAL_LINE_CENTER_DISTANCE = 4.5


class ExpansionLocation(BotObject):
    center: Point2
    terrain_height: int
    region_center: Point2
    mineral_fields_locations: set[Point2]
    vespene_geyser_locations: set[Point2]
    mineral_field_center: Optional[Point2]
    mineral_line_center: Optional[Point2]
    mining_gather_targets: dict[Point2, Point2]
    mining_return_targets: dict[Point2, Point2]

    def __init__(self, bot: 'AvocaDOS', location: Point2) -> None:
        super().__init__(bot)
        self.center = location
        self.terrain_height = self.map.terrain_height[self.center]

        self.mineral_fields_locations = {
            mf.position for mf in api.mineral_field.closer_than(8, self.center).sorted_by_distance_to(self.center)}
        self.vespene_geyser_locations = {
            vg.position for vg in api.vespene_geyser.closer_than(8, self.center).sorted_by_distance_to(self.center)}

        self.logger.debug("Found {} mineral fields and {} vespene geysers at {}",
                          len(self.mineral_fields_locations), len(self.vespene_geyser_locations), self)
        self.mining_gather_targets = {}
        self.mining_return_targets = {}
        for mineral_field in self.mineral_fields:
            # Gather
            gather_target = mineral_field.position.towards(self.center, GATHER_RADIUS)
            close_fields = self.mineral_fields.closer_than(GATHER_RADIUS, gather_target).tags_not_in({mineral_field.tag})
            for close_field in close_fields:
                points = get_circle_intersections(
                    Circle(mineral_field.position, GATHER_RADIUS),
                    Circle(close_field.position, GATHER_RADIUS)
                )
                if points:
                    gather_target = self.center.closest(points)
            self.mining_gather_targets[mineral_field.position] = gather_target
            # Return
            self.mining_return_targets[mineral_field.position] = self.center.towards(gather_target, RETURN_RADIUS)
        if self.mineral_fields:
            self.mineral_field_center = (sum((mf.position for mf in self.mineral_fields), start=Point2((0, 0)))
                                        / len(self.mineral_fields))
            self.mineral_line_center = self.center.towards(self.mineral_field_center, MINERAL_LINE_CENTER_DISTANCE)
            self.region_center = self.center.towards(self.mineral_field_center, -10)
        else:
            self.mineral_field_center = None
            self.mineral_line_center = None
            self.region_center = self.center

    def __repr__(self) -> str:
        return f"ExpLoc({self.center})"

    @property
    def index(self) -> int:
        return self.map.expansions.index(self)

    def get_townhall_area(self, *, size: float = 5.0) -> Rectangle:
        return Rectangle(self.center.x - size/2, self.center.y - size/2, width=size, height=size)

    def get_mineral_area(self) -> Optional[Rectangle]:
        if not self.mineral_fields:
            return None
        townhall_area = self.get_townhall_area()
        xmin = int(townhall_area.x)
        xmax = int(townhall_area.x_end)
        ymin = ymin0 = int(townhall_area.y)
        ymax = ymax0 = int(townhall_area.y_end)
        size = 3
        for x in range(xmin - size, xmax + size + 1):
            for y in range(ymin0 - size, ymax0 + size + 1):
                point = Point2((x, y))  # TODO: why not +0.5, +0.5?
                if point in townhall_area:
                    continue
                if self.mineral_fields.closest_distance_to(point) <= size:
                    xmin = min(x, xmin)
                    xmax = max(x, xmax)
                    ymin = min(y, ymin)
                    ymax = max(y, ymax)
        return Rectangle(xmin, ymin, xmax-xmin, ymax-ymin)

    def get_mineral_field(self, position: Point2) -> Optional[Unit]:
        mf = api.mineral_field.closest_to(position)
        if mf.distance_to(position) > 0:
            return None
        return mf

    def get_vespene_geyser(self, position: Point2) -> Optional[Unit]:
        vg = api.vespene_geyser.closest_to(position)
        if vg.distance_to(position) > 0:
            return None
        return vg

    @property
    def mineral_fields(self) -> Units:
        return api.mineral_field.filter(lambda mf: mf.position in self.mineral_fields_locations)

    @property
    def vespene_geyser(self) -> Units:
        return api.vespene_geyser.filter(lambda vg: vg.position in self.vespene_geyser_locations)

    def minerals(self) -> int:
        return sum(mf.mineral_contents for mf in self.mineral_fields)

    def vespene(self) -> int:
        return sum(vg.vespene_contents for vg in self.vespene_geyser)

    def __hash__(self) -> int:
        return hash(self.center)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ExpansionLocation):
            return self.center == other.center
        return NotImplemented

    def distance_to(self, other: Point2 | Self) -> float:
        if isinstance(other, ExpansionLocation):
            other = other.center
        return self.center.distance_to(other)

    def path_distance_to(self, other: Self) -> float:
        return float(self.map.expansion_path_distance_matrix[self.index, other.index])


class StartLocation(ExpansionLocation):
    _ramp: Optional[Ramp]
    _natural: Optional[ExpansionLocation]
    _line_third: Optional[ExpansionLocation]
    _triangle_third: Optional[ExpansionLocation]
    _expansion_order: Optional[list[ExpansionLocation]]
    _region: Region

    def __init__(self, bot: 'AvocaDOS', location: Point2) -> None:
        super().__init__(bot, location)
        self._ramp = None
        self._natural = None
        self._line_third = None
        self._triangle_third = None
        self._expansion_order = None
        self._region = self.map.floodfill(self.center, lambda p: self.map.terrain_height[p] == self.terrain_height,
                                          max_distance=32)

    @property
    def ramp(self) -> Ramp:
        if self._ramp is None:
            self._ramp = min(api.game_info.map_ramps, key=lambda r: r.top_center.distance_to(self.center))
        return self._ramp

    @property
    def region(self) -> Region:
        return self._region

    @property
    def natural(self) -> ExpansionLocation:
        if self._natural is None:
            self._natural = min(self.map.get_expansions(exclude=self), key=lambda exp: self.path_distance_to(exp))
        return self._natural

    @property
    def line_third(self) -> ExpansionLocation:
        if self._line_third is None:
            self._set_thirds()
        return self._line_third

    @property
    def triangle_third(self) -> ExpansionLocation:
        if self._triangle_third is None:
            self._set_thirds()
        return self._triangle_third

    @property
    def expansion_order(self) -> list[ExpansionLocation]:
        if self._expansion_order is None:
            self._expansion_order = self.map.get_expansions(
                sort_by=lambda exp: exp.distance_to(self.natural) - 0.5*exp.distance_to(self.map.center),
                exclude=self)
        return self._expansion_order

    def _set_thirds(self) -> None:
        thirds = self.expansion_order[1:3]
        distance_ratios = [t.distance_to(self) / t.distance_to(self.natural) for t in thirds]
        if distance_ratios[0] >= distance_ratios[1]:
            self._line_third, self._triangle_third = thirds
        else:
            self._triangle_third, self._line_third = thirds
