from typing import Any, TYPE_CHECKING

from sc2.position import Point2
from sc2.units import Units

from sc2bot.core.manager import Manager
from sc2bot.core.util import get_circle_intersections, Circle

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS

GATHER_RADIUS = 1.325
RETURN_RADIUS = 3.125 # CC = 2.75, SCV = 0.375 (TODO: are other races the same?)
MINERAL_LINE_CENTER_DISTANCE = 4.5


class ExpansionLocation(Manager):
    center: Point2
    base_center: Point2
    mineral_fields: Units
    vespene_geyser: Units
    mineral_field_center: Point2
    mineral_line_center: Point2
    mining_gather_targets: dict[int, Point2]
    mining_return_targets: dict[int, Point2]

    def __init__(self, bot: 'AvocaDOS', location: Point2) -> None:
        super().__init__(bot)
        self.center = location
        self.mineral_fields = self.api.mineral_field.closer_than(8, self.center).sorted_by_distance_to(self.center)
        self.vespene_geyser = self.api.vespene_geyser.closer_than(8, self.center).sorted_by_distance_to(self.center)
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
        self.mineral_field_center = (sum((mf.position for mf in self.mineral_fields), start=Point2((0, 0)))
                                     / len(self.mineral_fields))
        self.mineral_line_center = self.center.towards(self.mineral_field_center, MINERAL_LINE_CENTER_DISTANCE)
        self.base_center = self.center.towards(self.mineral_field_center, -10)

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

    def debug_show(self):
        for point in self.mining_gather_targets.values():
            self.debug.box(point, size=0.25, color=(255, 0, 0))
        for point in self.mining_return_targets.values():
            self.debug.box(point, size=0.25, color=(0, 0, 255))
        #self.bot.debug.box(self.mineral_field_center, size=0.25, color=(0, 255, 0))
        self.debug.box(self.mineral_line_center, size=0.25, color=(0, 255, 0))
