import math
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional

import numpy
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject



@dataclass
class SquadTask(ABC):
    pass


@dataclass
class SquadAttackTask(SquadTask):
    target: Point2 | Unit
    priority: float = field(default=0.5, compare=False)


@dataclass
class SquadDefendTask(SquadTask):
    target: Point2 | Unit
    priority: float = field(default=0.5, compare=False)


class Squad(BotObject):
    tags: set[int]
    task: Optional[SquadTask]
    spacing: float

    def __init__(self, bot, tags: Optional[set[int]] = None, _code: bool = False) -> None:
        super().__init__(bot)
        assert _code, "Squads should only be created by the SquadManager"
        self.tags = tags or set()
        self.task = None
        self.spacing = 1.0

    def __len__(self) -> int:
        return len(self.units)

    @property
    def units(self) -> Units:
        return self.bot.units.tags_in(self.tags)

    @property
    def strength(self) -> float:
        # TODO: better measure of strength
        return len(self)

    def __contains__(self, tag: int) -> bool:
        return tag in self.tags

    def add(self, units: Unit | int | Units | set[int]) -> None:
        self.squads.add_units(self, units)

    def remove(self, units: Unit | int | Units | set[int]) -> None:
        self.squads.remove_units(self, units)

    # --- Orders

    def attack(self, target: Unit | Point2) -> None:
        self.task = SquadAttackTask(target)

    def defend(self, target: Unit | Point2) -> None:
        self.task = SquadDefendTask(target)

    # --- Position

    def get_max_spread_squared(self) -> float:
        if len(self) < 2:
            return 1
        unit_sq_radius = sum(unit.radius*unit.radius for unit in self.units)
        return 4 * self.spacing**2 * unit_sq_radius

    def get_max_spread(self) -> float:
        if len(self) < 2:
            return 1
        return math.sqrt(self.get_max_spread_squared())

    @property
    def center(self) -> Optional[Point2]:
        if self.units.empty:
            return None
        return self.units.center

    def get_position_covariance(self) -> Optional[numpy.ndarray]:
        if self.units.empty:
            return None
        center = self.units.center
        deltas = [unit.position - center for unit in self.units]
        dx = sum(d[0] for d in deltas)
        dy = sum(d[1] for d in deltas)
        return numpy.asarray([[dx*dx, dx*dy], [dy*dx, dy*dy]])
