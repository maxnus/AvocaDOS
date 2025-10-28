import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

import numpy as np
from sc2.position import Point2
from sc2.unit import Unit


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


@dataclass
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
