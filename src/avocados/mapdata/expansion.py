from typing import Any, TYPE_CHECKING, Optional

from sc2.position import Point2
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.geomutil import get_circle_intersections, Circle

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS

GATHER_RADIUS = 1.325
RETURN_RADIUS = 3.125 # CC = 2.75, SCV = 0.375 (TODO: are other races the same?)
MINERAL_LINE_CENTER_DISTANCE = 4.5


class ExpansionLocation(BotObject):
    center: Point2
    region_center: Point2
    mineral_fields_tags: set[int]
    vespene_geyser_tags: set[int]
    mineral_field_center: Optional[Point2]
    mineral_line_center: Optional[Point2]
    mining_gather_targets: dict[int, Point2]
    mining_return_targets: dict[int, Point2]

    def __init__(self, bot: 'AvocaDOS', location: Point2) -> None:
        super().__init__(bot)
        self.center = location
        self.mineral_fields_tags = (self.api.mineral_field.closer_than(8, self.center)
                                    .sorted_by_distance_to(self.center).tags)
        self.vespene_geyser_tags = (self.api.vespene_geyser.closer_than(8, self.center)
                                    .sorted_by_distance_to(self.center).tags)
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
            self.mining_gather_targets[mineral_field.tag] = gather_target
            # Return
            self.mining_return_targets[mineral_field.tag] = self.center.towards(gather_target, RETURN_RADIUS)
        if self.mineral_fields:
            self.mineral_field_center = (sum((mf.position for mf in self.mineral_fields), start=Point2((0, 0)))
                                        / len(self.mineral_fields))
            self.mineral_line_center = self.center.towards(self.mineral_field_center, MINERAL_LINE_CENTER_DISTANCE)
            self.region_center = self.center.towards(self.mineral_field_center, -10)
        else:
            self.mineral_field_center = None
            self.mineral_line_center = None
            self.region_center = self.center

    @property
    def mineral_fields(self) -> Units:
        return self.api.mineral_field.tags_in(self.mineral_fields_tags)

    @property
    def vespene_geyser(self) -> Units:
        return self.api.vespene_geyser.tags_in(self.vespene_geyser_tags)

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

    # --- debug

    def on_debug(self) -> None:
        self.debug.sphere_with_text(self.center, repr(self))
