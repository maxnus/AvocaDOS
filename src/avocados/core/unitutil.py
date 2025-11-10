import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.geometry.util import squared_distance


def normalize_tags(unit: Unit | int | Units | set[int]) -> set[int]:
    if isinstance(unit, Unit):
        return {unit.tag}
    if isinstance(unit, int):
        return {unit}
    if isinstance(unit, Units):
        return unit.tags
    return unit


def get_closest_sq_distance(points1: Units, points2: Units | Unit | Point2) -> float:
    closest = float('inf')
    if isinstance(points2, Units):
        for p1 in points1:
            for p2 in points2:
                closest = min(closest, squared_distance(p1, p2))
    else:
        for p1 in points1:
            closest = min(closest, squared_distance(p1, points2))
    return closest


def get_closest_distance(points1: Units, points2: Units | Unit | Point2) -> float:
    return math.sqrt(get_closest_sq_distance(points1, points2))


def get_unit_type_counts(units: Iterable[Unit]) -> Counter[UnitTypeId]:
    counter = Counter()
    for unit in units:
        counter[unit.type_id] += 1
    return counter


def get_unique_unit_types(units: Iterable[Unit]) -> dict[Unit, int]:
    counter: dict[Unit, int] = defaultdict(int)
    representatives: dict[UnitTypeId, Unit] = {}
    for unit in units:
        if unit.type_id not in representatives:
            rep = representatives[unit.type_id] = unit
        else:
            rep = representatives[unit.type_id]
        counter[rep] += 1
    return counter


@dataclass
class UnitCost:
    minerals: float
    vespene: float
    supply: float

    def __repr__(self) -> str:
        return f"{self.minerals:.0f}M {self.vespene:.0f}G {self.supply:.1f}S"

    @property
    def resources(self) -> float:
        return self.minerals + self.vespene

    def __add__(self, other: 'UnitCost') -> Self:
        return UnitCost(
            minerals=self.minerals + other.minerals,
            vespene=self.vespene + other.vespene,
            supply=self.supply + other.supply,
        )

    def __sub__(self, other: 'UnitCost') -> Self:
        return UnitCost(
            minerals=self.minerals - other.minerals,
            vespene=self.vespene - other.vespene,
            supply=self.supply - other.supply,
        )

    def __mul__(self, factor: float) -> Self:
        return UnitCost(
            minerals=self.minerals * factor,
            vespene=self.vespene * factor,
            supply=self.supply * factor,
        )

    def __rmul__(self, factor: float) -> Self:
        return self * factor

    def __truediv__(self, divisor: float) -> Self:
        return UnitCost(
            minerals=self.minerals / divisor,
            vespene=self.vespene / divisor,
            supply=self.supply / divisor,
        )

    def __pow__(self, exponent: float) -> Self:
        return UnitCost(
            minerals=self.minerals ** exponent,
            vespene=self.vespene ** exponent,
            supply=self.supply ** exponent,
        )
