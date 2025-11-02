import math
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, Protocol, runtime_checkable

from sc2.cache import property_cache_once_per_frame
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.unitutil import get_unit_type_counts, get_unique_unit_types
from avocados.core.geomutil import Area, Circle, squared_distance


@runtime_checkable
class SquadTask(Protocol):
    priority: float


@dataclass
class SquadAttackTask(SquadTask):
    area: Area
    priority: float = field(default=0.5, compare=False)


@dataclass
class SquadDefendTask(SquadTask):
    area: Area
    priority: float = field(default=0.5, compare=False)


class SquadStatus(StrEnum):
    IDLE = "I"
    MOVING = "M"
    COMBAT = "C"
    AT_TARGET= "T"
    #GROUPING = "G"


class Squad(BotObject):
    tags: set[int]
    task: Optional[SquadTask]
    spacing: float
    leash: float
    status: SquadStatus
    status_changed: float

    def __init__(self, bot, tags: Optional[set[int]] = None, _code: bool = False) -> None:
        super().__init__(bot)
        assert _code, "Squads should only be created by the SquadManager"
        self.tags = tags or set()
        self.task = None
        self.spacing = 0.0
        self.leash = 10.0
        self.status = SquadStatus.IDLE
        self.status_changed = 0.0

    def __len__(self) -> int:
        return len(self.units)

    @property
    def units(self) -> Units:
        return self.bot.units.tags_in(self.tags)

    @property_cache_once_per_frame
    def strength(self) -> float:
        # TODO: better measure of strength
        return len(self)

    def set_status(self, status: SquadStatus) -> None:
        if status != self.status:
            self.status_changed = self.time
        self.status = status
        if status == SquadStatus.COMBAT:
            self.leash = 6.0
        elif status == SquadStatus.MOVING:
            self.leash = 4.0
        #elif status == SquadStatus.GROUPING:
        #    self.leash = 2.0
        else:
            self.leash = 10.0

    def get_unit_type_counts(self) -> Counter[UnitTypeId]:
        return get_unit_type_counts(self.units)

    def __contains__(self, tag: int) -> bool:
        return tag in self.tags

    def add(self, units: Unit | int | Units | set[int], *, remove_from_squads: bool = False) -> None:
        self.squads.add_units(self, units, remove_from_squads=remove_from_squads)

    def remove(self, units: Unit | int | Units | set[int]) -> None:
        self.squads.remove_units(self, units)

    # --- Distance

    def get_bounds(self) -> Circle:
        raise NotImplementedError()

    def distance_to(self, target: Point2 | Unit | Area) -> float:
        if isinstance(target, Point2):
            point = target
        elif isinstance(target, Unit):
            point = target.position
        elif isinstance(target, Area):
            point = target.center
        else:
            raise TypeError(f'invalid target type: {type(target)}')
        return max(math.sqrt(squared_distance(self.center, point)) - math.sqrt(self.radius_squared), 0)

    def closest_distance_to(self, target: Point2 | Unit | Area) -> float:
        if len(self) == 0:
            return float('inf')
        if isinstance(target, Area):
            return target.closest(self.units)[1]
        if isinstance(target, Unit):
            target = target.position
        return target.distance_to_closest(self.units)

    # --- Orders

    def attack(self, target: Point2, *, radius: float = 16.0, priority: float = 0.5) -> SquadAttackTask:
        area = Circle(target, radius)
        self.task = SquadAttackTask(area, priority=priority)
        return self.task    # noqa

    def defend(self, target: Point2, *, radius: float = 16.0, priority: float = 0.5) -> SquadDefendTask:
        area = Circle(target, radius)
        self.task = SquadDefendTask(area, priority=priority)
        return self.task    # noqa

    # --- Position

    @property_cache_once_per_frame
    def radius_squared(self) -> float:
        """Caching may not be correct, as units can change during frame."""
        if len(self) == 0:
            return 0.0
        if len(self) == 1:
            return self.units.first.radius**2
        unit_sq_radius = sum(number * (unit.radius + self.spacing)**2
                             for unit, number in get_unique_unit_types(self.units).items())
        return 2 * unit_sq_radius

    @property_cache_once_per_frame
    def leash_range(self) -> float:
        return math.sqrt(self.radius_squared) + self.leash

    # @property_cache_once_per_frame
    # def max_spread(self) -> float:
    #     """Caching may not be correct, as units can change during frame."""
    #     if len(self) < 2:
    #         return 1
    #     return math.sqrt(self.max_spread_squared)

    @property_cache_once_per_frame
    def center(self) -> Optional[Point2]:
        """Caching may not be correct, as units can change during frame."""
        if self.units.empty:
            return None
        return self.units.center

    # def get_position_covariance(self) -> Optional[numpy.ndarray]:
    #     if self.units.empty:
    #         return None
    #     center = self.units.center
    #     deltas = [unit.position - center for unit in self.units]
    #     dx = sum(d[0] for d in deltas)
    #     dy = sum(d[1] for d in deltas)
    #     return numpy.asarray([[dx*dx, dx*dy], [dy*dx, dy*dy]])
