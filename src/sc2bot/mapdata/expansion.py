from typing import Any, TYPE_CHECKING

from sc2.position import Point2
from sc2.units import Units

from sc2bot.core.system import System

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


GATHER_RADIUS = 1.325
RETURN_RADIUS = 3.125 # CC = 2.75, SCV = 0.375 (TODO: are other races the same?)


class ExpansionLocation(System):
    center: Point2
    mineral_fields: Units
    vespene_geyser: Units
    mining_gather_targets: dict[int, Point2]
    mining_return_targets: dict[int, Point2]

    def __init__(self, bot: 'AvocaDOS', location: Point2) -> None:
        super().__init__(bot)
        self.center = location
        self.mineral_fields = self.bot.mineral_field.closer_than(8, self.center)
        self.vespene_geyser = self.bot.vespene_geyser.closer_than(8, self.center)
        self.mining_gather_targets = {}
        self.mining_return_targets = {}
        for mineral_field in self.mineral_fields:
            self.mining_gather_targets[mineral_field.tag] = mineral_field.position.towards(self.center, GATHER_RADIUS)
            self.mining_return_targets[mineral_field.tag] = self.center.position.towards(mineral_field, RETURN_RADIUS)

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
