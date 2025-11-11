import math
import random
from collections.abc import Collection
from dataclasses import dataclass

import numpy
from sc2.position import Point2

from avocados.geometry.region import Region
from avocados.geometry.util import squared_distance, closest_point, furthest_point, Rectangle


@dataclass(frozen=True)
class Circle:
    center: Point2
    radius: float

    @property
    def x(self) -> float:
        return self.center.x

    @property
    def y(self) -> float:
        return self.center.y

    @property
    def r(self) -> float:
        return self.radius

    @property
    def size(self) -> float:
        return math.pi * self.r**2

    @property
    def perimeter(self) -> float:
        return 2 * math.pi * self.r

    @property
    def characteristic_length(self) -> float:
        return 2/3 * self.radius

    def __contains__(self, point: Point2) -> bool:
        return squared_distance(self.center, point) <= self.radius**2

    @property
    def random(self) -> Point2:
        theta = random.uniform(0, 2 * math.pi)
        r = self.r * math.sqrt(random.random())
        x = self.x + r * math.cos(theta)
        y = self.y + r * math.sin(theta)
        return Point2((x, y))

    def closest(self, points: Collection[Point2]) -> tuple[Point2, float]:
        return closest_point(points, self.center)

    def furthest(self, points: Collection[Point2]) -> tuple[Point2, float]:
        return furthest_point(points, self.center)

    def bounding_rect(self, integral: bool = False) -> Rectangle:
        x = self.center.x - self.radius
        y = self.center.y - self.radius
        if integral:
            x = int(math.floor(x))
            y = int(math.floor(y))
            width = int(math.ceil(self.center.x + self.radius)) - x
            height = int(math.ceil(self.center.y + self.radius)) - y
        else:
            width = height = 2 * self.radius
        return Rectangle(x, y, width, height)

    def to_region(self) -> Region:
        # Bounding box of possible integer grid cells
        xmin = int(math.floor(self.center.x - self.radius - 0.5))
        xmax = int(math.ceil(self.center.x + self.radius - 0.5))
        ymin = int(math.floor(self.center.y - self.radius - 0.5))
        ymax = int(math.ceil(self.center.y + self.radius - 0.5))

        # Make a grid of (x, y)
        xs, ys = numpy.meshgrid(numpy.arange(xmin, xmax + 1), numpy.arange(ymin, ymax + 1))

        # Shift by 0.5 to get center of each cell
        x = xs + 0.5
        y = ys + 0.5

        # Mask points inside circle
        mask = (x - self.center.x) ** 2 + (y - self.center.y) ** 2 <= self.radius * self.radius

        # Extract coordinates
        array = numpy.stack([x[mask], y[mask]], axis=-1)
        points = {Point2(row) for row in array}
        return Region(points)


def get_circle_intersections(circle1: Circle, circle2: Circle) -> list[Point2]:
    dx = circle2.x - circle1.x
    dy = circle2.y - circle1.y
    dsq = dx*dx + dy*dy
    d = math.sqrt(dsq)

    # non intersecting
    if dsq > (circle1.r + circle2.r)**2:
        return []

    # One circle within the other
    if dsq < (circle1.r - circle2.r)**2:
        return []

    # coincident circles
    if dsq == 0 and circle1.r == circle2.r:
        return []

    a = (circle1.r**2 - circle2.r**2 + dsq) / (2 * d)
    h = math.sqrt(circle1.r**2 - a**2)
    x2 = circle1.x + a * dx / d
    y2 = circle1.y + a * dy / d
    x3 = x2 + h * dy / d
    y3 = y2 - h * dx / d
    x4 = x2 - h * dy / d
    y4 = y2 + h * dx / d

    return [Point2((x3, y3)), Point2((x4, y4))]
