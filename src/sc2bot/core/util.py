import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

from sc2.position import Point2
from sc2.unit import Unit


async def wait_until(predicate: Callable[..., Any], check_interval: float = 1) -> None:
    """Repeatedly check predicate() until it returns True."""
    while not predicate():
        await asyncio.sleep(check_interval)


def squared_distance(pos1: Unit | Point2, pos2: Unit | Point2) -> float:
    if isinstance(pos1, Unit):
        p1 = pos1.position
    else:
        p1 = pos1
    if isinstance(pos2, Unit):
        p2 = pos2.position
    else:
        p2 = pos2
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return dx * dx + dy * dy


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
