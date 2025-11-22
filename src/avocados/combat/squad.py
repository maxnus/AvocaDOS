import math
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, Protocol, runtime_checkable, Any

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados import api
from avocados.combat.util import get_strength
from avocados.core.botobject import BotObject
from avocados.core.unitutil import get_unit_type_counts, get_unique_unit_types
from avocados.geometry import Area, Circle


COMBAT_LEASH = 4.0
MOVE_LEASH = 2.0
DEFAULT_LEASH = 14.0


@runtime_checkable
class SquadTask(Protocol):
    target: Any
    priority: float
    started: float


@dataclass
class SquadAttackTask(SquadTask):
    target: Area
    priority: float = field(default=0.5, compare=False)
    started: float = field(default=0.0, compare=False)


@dataclass
class SquadDefendTask(SquadTask):
    target: Area
    priority: float = field(default=0.5, compare=False)
    started: float = field(default=0.0, compare=False)


@dataclass
class SquadRetreatTask(SquadTask):
    target: Area
    priority: float = field(default=0.5, compare=False)
    started: float = field(default=0.0, compare=False)


@dataclass
class SquadJoinTask(SquadTask):
    target: 'Squad'
    priority: float = field(default=0.5, compare=False)
    started: float = field(default=0.0, compare=False)


class SquadStatus(StrEnum):
    IDLE = "I"
    MOVING = "M"
    COMBAT = "C"
    AT_TARGET= "T"


class Squad(BotObject):
    spacing: float
    status: SquadStatus
    status_changed: float
    target_strength: float
    _tags: set[int]
    _tasks: list[SquadTask]
    damage_taken: deque[float]

    def __init__(self, tags: Optional[set[int]] = None, *,
                 target_strength: float,
                 _code: bool = False) -> None:
        super().__init__()
        assert _code, "Squads should only be created by the SquadManager"
        self._tags = tags or set()
        self._tasks = []
        self.target_strength = target_strength
        self.spacing = 0.0
        self.status = SquadStatus.IDLE
        self.status_changed = 0.0
        self.damage_taken = deque(maxlen=100)

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(id={self.id}, size={self.size}, spacing={self.spacing},"
                f" status={self.status}, status_changed={self.status_changed})")

    def __len__(self) -> int:
        return self.size

    @property
    def size(self) -> int:
        return len(self.units)

    @property
    def units(self) -> Units:
        return api.units.tags_in(self._tags)

    def __contains__(self, tag: int) -> bool:
        return tag in self._tags

    def set_status(self, status: SquadStatus) -> None:
        if status != self.status:
            self.status_changed = api.time
        self.status = status

    # Strength

    #@property_cache_once_per_frame
    @property
    def strength(self) -> float:
        return get_strength(self.units)

    def get_unit_type_counts(self) -> Counter[UnitTypeId]:
        return get_unit_type_counts(self.units)

    @property
    def health_max(self) -> float:
        return sum(u.health_max for u in self.units)

    @property
    def damage_taken_percentage(self) -> float:
        return sum(self.damage_taken) / self.health_max

    # --- Distance

    def get_bounds(self) -> Circle:
        raise NotImplementedError()

    # def distance_to(self, target: Point2 | Unit | Area) -> float:
    #     if isinstance(target, Point2):
    #         point = target
    #     elif isinstance(target, Unit):
    #         point = target.position
    #     elif isinstance(target, Area):
    #         point = target.center
    #     else:
    #         raise TypeError(f'invalid target type: {type(target)}')
    #     return max(math.sqrt(squared_distance(self.center, point)) - math.sqrt(self.radius_squared), 0)

    def distance_to_from_radius(self, point: Point2) -> float:
        return self.center.distance_to(point) - self.radius

    def spacing_to_squad(self, other: 'Squad') -> float:
        return self.distance_to_from_radius(other.center) - other.radius

    def closest_distance_to(self, target: Point2 | Unit | Area) -> float:
        if len(self) == 0:
            return float('inf')
        if isinstance(target, Area):
            return target.closest(self.units)[1]
        if isinstance(target, Unit):
            target = target.position
        return target.distance_to_closest(self.units)

    def all_units_in_area(self, area: Area) -> bool:
        return all(u.position in area for u in self.units)

    # --- Task

    @property
    def task(self) -> Optional[SquadTask]:
        if not self._tasks:
            return None
        return self._tasks[0]

    def has_task(self) -> bool:
        return bool(self._tasks)

    @property
    def task_priority(self) -> float:
        return self.task.priority if self.has_task() else 0

    def remove_task(self, index: int = 0) -> SquadTask:
        return self._tasks.pop(index)

    def attack(self, area: Area, *, priority: float = 0.5,
               queue: bool = False) -> SquadAttackTask:
        task = SquadAttackTask(area, priority=priority, started=api.time)
        self._add_task(task, queue=queue)
        return task

    def defend(self, area: Area, *, priority: float = 0.5,
               queue: bool = False) -> SquadDefendTask:
        task = SquadDefendTask(area, priority=priority, started=api.time)
        self._add_task(task, queue=queue)
        return task

    def join(self, squad: 'Squad', *, priority: float = 0.5,
             queue: bool = False) -> SquadJoinTask:
        task = SquadJoinTask(squad, priority=priority, started=api.time)
        self._add_task(task, queue=queue)
        return task

    def retreat(self, area: Area, *, priority: float = 0.5, queue: bool = False) -> SquadRetreatTask:
        task = SquadRetreatTask(area, priority=priority, started=api.time)
        self._add_task(task, queue=queue)
        return task

    def _add_task(self, task: SquadTask, *, queue: bool) -> None:
        if queue:
            if len(self._tasks) == 0 or task != self._tasks[-1]:
                self.logger.info("Queuing new task {} for {}", task, self)
        else:
            if task != self.task:
                self.logger.info("Setting new task {} for {}", task, self)
            self._tasks.clear()
        self._tasks.append(task)

    # --- Position

    #@property_cache_once_per_frame
    @property
    def radius_squared(self) -> float:
        """Caching may not be correct, as units can change during frame."""
        if len(self) == 0:
            return 0.0
        if len(self) == 1:
            return self.units.first.radius**2
        unit_sq_radius = sum(number * (unit.radius + self.spacing)**2
                             for unit, number in get_unique_unit_types(self.units).items())
        return 2 * unit_sq_radius

    @property
    def radius(self) -> float:
        return math.sqrt(self.radius_squared)

    #@property_cache_once_per_frame
    @property
    def leash_range(self) -> float:
        if self.status == SquadStatus.COMBAT:
            leash = COMBAT_LEASH
        elif self.status == SquadStatus.MOVING:
            leash = MOVE_LEASH
        else:
            leash = DEFAULT_LEASH
        return math.sqrt(self.radius_squared) + leash

    #@property_cache_once_per_frame
    @property
    def center(self) -> Optional[Point2]:
        """Caching may not be correct, as units can change during frame."""
        if self.units.empty:
            return None
        if len(self) == 2:
            return self.units.first.position if self.units.first.tag < self.units[-1].tag else self.units[-1].position
        return self.units.closest_to(self.geometric_center).position

    @property
    def geometric_center(self) -> Optional[Point2]:
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
