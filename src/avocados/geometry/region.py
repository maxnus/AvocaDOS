import random
from typing import TYPE_CHECKING

from sc2.position import Point2

from avocados.core.botobject import BotObject
from avocados.geometry.util import Rectangle

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class Region(BotObject):
    points: set[Point2]

    def __init__(self, bot: 'AvocaDOS'):
        super().__init__(bot)
        self.points = set()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(size={self.size})"

    @property
    def center(self) -> Point2:
        if not self.points:
            raise RuntimeError(f'region {self} has no points')
        center = sum(self.points, start=Point2((0, 0))) / len(self.points)
        return center

    @property
    def size(self) -> int:
        return len(self.points)

    def __contains__(self, point: Point2) -> bool:
        return point in self.points

    def random(self) -> Point2:
        return random.choice(list(self.points))

    def bounding_rect(self) -> Rectangle:
        x_min = min(p.x for p in self.points)
        x_max = max(p.x for p in self.points)
        y_min = min(p.y for p in self.points)
        y_max = max(p.y for p in self.points)
        width = x_max - x_min
        height = y_max - y_min
        return Rectangle(x_min, y_min, width, height)
