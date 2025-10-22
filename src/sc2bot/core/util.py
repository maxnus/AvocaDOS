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
    minerals: int
    vespene: int
    supply: float

    def __repr__(self) -> str:
        return f"{self.minerals}M {self.vespene}G {self.supply:.1f}S"

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

    def __mul__(self, factor: int) -> Self:
        return UnitCost(
            minerals=self.minerals * factor,
            vespene=self.vespene * factor,
            supply=self.supply * factor,
        )

    def __rmul__(self, factor: int) -> Self:
        return self * factor
