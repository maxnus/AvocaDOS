from dataclasses import dataclass
from typing import Optional

import numpy
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.botobject import BotObject


class SquadTask:
    pass


@dataclass
class SquadAttackTask(SquadTask):
    target: Point2 | Unit


@dataclass
class SquadDefendTask(SquadTask):
    target: Point2 | Unit


class Squad(BotObject):
    tags: set[int]
    task: Optional[SquadTask]

    def __init__(self, bot, tags: Optional[set[int]] = None ) -> None:
        super().__init__(bot)
        self.tags = tags or set()
        self.task = None

    def __len__(self) -> int:
        return len(self.units)

    @property
    def units(self) -> Units:
        return self.bot.units.tags_in(self.tags)

    def __contains__(self, tag: int) -> bool:
        return tag in self.tags

    def add(self, unit: Unit | int | Units | set[int]) -> None:
        if isinstance(unit, Unit):
            tags = {unit.tag}
        elif isinstance(unit, int):
            tags = {unit}
        elif isinstance(unit, Units):
            tags = unit.tags
        else:
            tags = unit
        self.tags.update(tags)

    # --- Orders

    def attack(self, target: Unit | Point2) -> None:
        self.task = SquadAttackTask(target)

    # --- Position

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
