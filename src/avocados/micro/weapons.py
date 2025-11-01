from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator, Self

from sc2.data import TargetType
from sc2.unit import Unit


class WeaponType(IntEnum):
    ANY = TargetType.Any.value
    GROUND = TargetType.Ground.value
    AIR = TargetType.Air.value


@dataclass
class Weapon:
    type: WeaponType
    attacks: int
    damage: float
    speed: float
    range: float


@dataclass
class Weapons:
    weapons: list[Weapon]

    def __len__(self) -> int:
        return len(self.weapons)

    def __iter__(self) -> Iterator[Weapon]:
        yield from self.weapons

    @classmethod
    def of_unit(cls, unit: Unit) -> Self:
        weapons = []
        for weapon in unit._weapons:
            weapons.append(
                Weapon(
                    type=WeaponType(weapon.type),
                    attacks=weapon.attacks,
                    damage=weapon.damage,
                    speed=weapon.speed,
                    range=weapon.range)
            )
        return Weapons(weapons)

    @property
    def max_range(self) -> float:
        return max(w.range for w in self.weapons)
