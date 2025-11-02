import asyncio
import itertools
import math
import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np
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


@runtime_checkable
class Area(Protocol):

    @property
    def center(self) -> Point2:
        pass

    @property
    def size(self) -> float:
        pass

    @property
    def perimeter(self) -> float:
        pass

    @property
    def characteristic_length(self) -> float:
        pass

    @property
    def random(self) -> Point2:
        pass


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

    @property
    def random(self) -> Point2:
        theta = random.uniform(0, 2 * math.pi)
        r = self.r * math.sqrt(random.random())
        x = self.x + r * math.cos(theta)
        y = self.y + r * math.sin(theta)
        return Point2((x, y))


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
        t = np.dot(v, segment) / np.dot(segment, segment)
        t = np.clip(t, 0, 1)
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
