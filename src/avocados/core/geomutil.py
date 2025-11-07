import asyncio
import itertools
import math
import random
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from sc2.position import Point2
from sc2.unit import Unit


_id_counter = itertools.count()


def unique_id() -> int:
    return next(_id_counter)


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


def get_best_score[T](values: Collection[T], score_func: Callable[[T], float], *,
                      highest: bool = True) -> tuple[T, float]:
    minmax = max if highest else min
    return minmax([(value, score_func(value)) for value in values], key=lambda x: x[1])


def closest_point(points: Collection[Point2], target: Point2) -> tuple[Point2, float]:
    return get_best_score(points, score_func=lambda p: squared_distance(p, target))


def furthest_point(points: Collection[Point2], target: Point2) -> tuple[Point2, float]:
    return get_best_score(points, score_func=lambda p: -squared_distance(p, target))


@runtime_checkable
class Area(Protocol):
    center: Point2
    @property
    def size(self) -> float: ...
    @property
    def perimeter(self) -> float: ...
    @property
    def characteristic_length(self) -> float: ...
    def __contains__(self, point: Point2) -> bool: ...
    @property
    def random(self) -> Point2: ...
    def closest(self, points: Collection[Point2]) -> tuple[Point2, float]: ...
    def furthest(self, points: Collection[Point2]) -> tuple[Point2, float]: ...
    def bounding_rect(self, integral: bool) -> 'Rectangle': ...


@dataclass(frozen=True)
class Rectangle:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_center(cls, center: Point2, width: float, height: float) -> 'Rectangle':
        x = center.x - width / 2
        y = center.y - height / 2
        return Rectangle(x, y, width, height)

    @property
    def center(self) -> Point2:
        return Point2((self.x + self.width/2, self.y + self.height/2))

    @property
    def size(self) -> float:
        return self.width * self.height

    @property
    def x_end(self) -> float:
        return self.x + self.width

    @property
    def y_end(self) -> float:
        return self.y + self.height

    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

    @property
    def characteristic_length(self) -> float:
        return math.sqrt(self.width * self.height)

    def __contains__(self, point: Point2) -> bool:
        return (self.x <= point.x < self.x + self.width ) and (self.y <= point.y < self.y + self.height)

    def __add__(self, other: Point2) -> 'Rectangle':
        if isinstance(other, Point2):
            return Rectangle(self.x + other.x, self.y + other.y, self.width, self.height)
        return NotImplemented

    def __sub__(self, other: Point2) -> 'Rectangle':
        if isinstance(other, Point2):
            return Rectangle(self.x - other.x, self.y - other.y, self.width, self.height)
        return NotImplemented

    @property
    def random(self) -> Point2:
        x = self.x + random.uniform(0, self.width)
        y = self.y + random.uniform(0, self.height)
        return Point2((x, y))

    def closest(self, points: Collection[Point2]) -> tuple[Point2, float]:
        raise NotImplementedError

    def furthest(self, points: Collection[Point2]) -> tuple[Point2, float]:
        raise NotImplementedError

    def bounding_rect(self, integral: bool = False) -> 'Rectangle':
        if integral:
            x = int(math.floor(self.x))
            y = int(math.floor(self.y))
            width = int(math.ceil(self.x + self.width)) - x
            height = int(math.ceil(self.y + self.height)) - y
            return Rectangle(x, y, width, height)
        else:
            return self

    def rounded(self) -> 'Rectangle':
        return Rectangle(int(round(self.x)), int(round(self.y)), int(round(self.width)), int(round(self.height)))


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

    def bounding_rect(self, integral: bool = False) -> 'Rectangle':
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


def dot(a: Point2, b: Point2) -> float:
    return a.x * b.x + a.y * b.y


class LineSegment:
    start: Point2
    end: Point2

    def __init__(self, start: Point2 | Unit, end: Point2 | Unit) -> None:
        if isinstance(start, Unit):
            start = start.position
        if isinstance(end, Unit):
            end = end.position
        self.start = start
        self.end = end

    def distance_to(self, point: Point2 | Unit) -> float:
        """Shortest distance from any point on the line segment to a given point."""
        if isinstance(point, Unit):
            point = point.position
        segment = self.end - self.start
        v = point - self.start
        t = dot(v, segment) / dot(segment, segment)
        t = max(0.0, min(t, 1.0))
        q = self.start + t * segment
        distance = point.distance_to(q)
        return distance


def lerp(x, /, *points: tuple[float, float]) -> float:
    # Flat extrapolation
    if x <= points[0][0]:
        return points[0][1]
    if x > points[-1][0]:
        return points[-1][1]
    # LERP
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x <= x2:
            r = (x2 - x) / (x2 - x1)
            return r * y1 + (1 - r) * y2
    raise ValueError
