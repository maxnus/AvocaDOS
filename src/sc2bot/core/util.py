import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self


async def wait_until(predicate: Callable[..., Any], check_interval: float = 1) -> None:
    """Repeatedly check predicate() until it returns True."""
    while not predicate():
        await asyncio.sleep(check_interval)


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
