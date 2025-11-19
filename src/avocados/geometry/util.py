import asyncio
import itertools
import math
import random
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable, Self, Optional

import numpy
from sc2.position import Point2, Rect
from sc2.unit import Unit


_id_counter = itertools.count()


def unique_id() -> int:
    return next(_id_counter)


def same_point(point1: Point2, point2: Point2) -> bool:
    return max(abs(point1.x - point2.x), abs(point1.y - point2.y)) < 0.001


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

    def __repr__(self) -> str:
        return f"Rect({self.x}, {self.y}, {self.width}, {self.height})"

    @classmethod
    def from_center(cls, center: Point2, width: float, height: float) -> 'Rectangle':
        x = center.x - width / 2
        y = center.y - height / 2
        return Rectangle(x, y, width, height)

    @classmethod
    def from_rect(cls, rect: Rect) -> 'Rectangle':
        return Rectangle(rect.x, rect.y, rect.width, rect.height)

    @property
    def center(self) -> Point2:
        return Point2((self.x + self.width/2, self.y + self.height/2))

    @property
    def size(self) -> float:
        return self.width * self.height

    @property
    def shape(self) -> tuple[float, float]:
        return self.width, self.height

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

    def __contains__(self, point: 'Point2 | tuple[int, int] | Rectangle') -> bool:
        if isinstance(point, Rectangle):
            return (
                    self.x <= point.x
                    and self.y <= point.y
                    and self.x_end >= point.x_end
                    and self.y_end >= point.y_end
            )
        return (self.x <= point[0] < self.x_end) and (self.y <= point[1] < self.y_end)

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

    def bounding_rect(self, integral: bool = False) -> Self:
        if integral:
            x = int(math.floor(self.x))
            y = int(math.floor(self.y))
            width = int(math.ceil(self.x_end)) - x
            height = int(math.ceil(self.y_end)) - y
            return type(self)(x, y, width, height)
        else:
            return self

    def enclosed_rect(self) -> Self:
        x = int(math.ceil(self.x))
        y = int(math.ceil(self.y))
        width = int(math.floor(self.x_end)) - x
        height = int(math.floor(self.y_end)) - y
        return type(self)(x, y, width, height)

    def overlaps(self, other: Self) -> bool:
        return not (
            self.x_end <= other.x
            or self.x >= other.x_end
            or self.y_end <= other.y
            or self.y >= other.y_end
        )

    def overlap(self, other: Self) -> Optional[Self]:
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        x_end = min(self.x_end, other.x_end)
        y_end = min(self.y_end, other.y_end)
        # No overlap
        if x_end <= x or y_end <= y:
            return None
        return type(self)(x, y, x_end - x, y_end - y)

    def get_grid_points(self, *,
                        shift: tuple[float, float] = (0.5, 0.5),
                        offset: tuple[float, float] = (0.0, 0.0)) -> numpy.ndarray:
        """All points with coordinates (*.5, *.5) inside the rectangle."""
        i0 = int(self.x + shift[0])
        j0 = int(self.y + shift[1])
        i1 = int(self.x_end - shift[0] + 1)
        j1 = int(self.y_end - shift[1] + 1)
        xs = numpy.arange(i0, i1) + shift[0] + offset[0]
        ys = numpy.arange(j0, j1) + shift[1] + offset[1]
        mesh = numpy.meshgrid(xs, ys, indexing='ij')
        grid_points = numpy.stack(mesh, axis=-1)

        # grid_points2 = numpy.zeros((i1-i0, j1-j0, 2))
        # for i, x in enumerate(range(i0, i1)):
        #     for j, y in enumerate(range(j0, j1)):
        #         grid_points2[i, j, 0] = x + shift[0] + offset[0]
        #         grid_points2[i, j, 1] = y + shift[1] + offset[1]
        # assert numpy.all(grid_points == grid_points2)

        return grid_points

    def tile(self, shape: tuple[float, float]) -> list[Point2]:
        """Fill rectangle with instances of another rectangle, centered at the returned list of points"""
        points = []
        width, height = shape
        px = x0 = self.x + width / 2
        py = self.y + height / 2
        while True:
            points.append(Point2((px, py)))
            dx = min(self.x_end - px - width / 2, width)
            if dx >= 0.5:
                px += dx
            else:
                px = x0
                dy = min(self.y_end - py - height / 2, height)
                if dy >= 0.5:
                    py += dy
                else:
                    break
        return points


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
