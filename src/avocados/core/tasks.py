import copy
from abc import ABC, abstractmethod
from enum import Enum, StrEnum
from typing import Optional, Self

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.util import unique_id


class TaskStatus(Enum):
    NOT_STARTED = 0
    STARTED = 1
    COMPLETED = 2


class TaskRequirementType(StrEnum):
    TIME = "T"
    SUPPLY = "S"
    MINERALS = "M"
    VESPENE = "G"


TaskDependencies = dict[int, TaskStatus]
TaskRequirements = list[tuple[TaskRequirementType | UnitTypeId | UpgradeId, int | bool]]


class Task(ABC):
    id: int
    reqs: TaskRequirements
    deps: TaskDependencies
    priority: int
    repeat: bool = False
    status: TaskStatus
    assigned: set[int]

    def __init__(self,
                 reqs: Optional[TaskRequirements | UnitTypeId | UpgradeId] = None,
                 deps: Optional[TaskDependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 repeat: bool = False,
                 status: TaskStatus = TaskStatus.NOT_STARTED,
                 ) -> None:
        self.id = unique_id()
        self.reqs = self._normalize_reqs(reqs)
        if deps is None:
            deps = {}
        elif isinstance(deps, int):
            deps = {deps: TaskStatus.COMPLETED}
        elif isinstance(deps, TaskStatus):
            deps = {self.id - 1: deps} if self.id > 0 else {}
        self.deps = deps
        self.priority = priority
        self.repeat = repeat
        self.status = status
        self.assigned = set()

    @staticmethod
    def _normalize_reqs(reqs: Optional[TaskRequirements | UnitTypeId | UpgradeId]) -> TaskRequirements:
        if reqs is None:
            return []
        if isinstance(reqs, (UnitTypeId, UpgradeId)):
            return [(reqs, 1)]
        if isinstance(reqs, tuple) and len(reqs) == 2:
            return [reqs]
        return reqs

    @abstractmethod
    def __repr__(self) -> str:
        pass

    def mark_complete(self) -> None:
        self.status = TaskStatus.COMPLETED

    def assign_units(self, units: Unit | Units | set[int]) -> None:
        if isinstance(units, Unit):
            units = {units.tag}
        elif isinstance(units, Units):
            units = units.tags
        self.assigned.update(units)

    def copy(self, status: Optional[TaskStatus] = None) -> Self:
        copied_task = copy.copy(self)
        copied_task.id = unique_id()
        copied_task.status = status or self.status
        return copied_task


class BuildingCountTask(Task):
    utype: UnitTypeId
    number: int
    position: Point2
    max_distance: float

    def __init__(self,
                 utype: UnitTypeId,
                 number: int = 1,
                 *,
                 reqs: Optional[TaskRequirements] = None,
                 deps: Optional[TaskDependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 repeat: bool = False,
                 position: Optional[Point2] = None,
                 max_distance: Optional[float] = 5,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.utype = utype
        self.position = position
        self.max_distance = max_distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, number={self.number}, position={self.position}, priority={self.priority})"


class UnitCountTask(Task):
    utype: UnitTypeId
    number: int
    position: Optional[Point2 | Unit]
    max_distance: int

    def __init__(self,
                 utype: UnitTypeId,
                 number: int = 1,
                 *,
                 reqs: Optional[TaskRequirements] = None,
                 deps: Optional[TaskDependencies | TaskStatus | int] = None,
                 priority: int = 50,
                 repeat: bool = False,
                 position: Optional[Point2] = None,
                 distance: Optional[int] = 10,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.utype = utype
        self.number = number
        self.position = position
        self.max_distance = distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, number={self.number}, position={self.position}, priority={self.priority})"


class ResearchTask(Task):
    upgrade: UpgradeId
    position: Point2
    max_distance: float

    def __init__(self,
                 upgrade: UpgradeId,
                 *,
                 reqs: Optional[TaskRequirements] = None,
                 deps: Optional[TaskDependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 repeat: bool = False,
                 position: Optional[Point2] = None,
                 max_distance: Optional[float] = 10,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.upgrade = upgrade
        self.position = position
        self.max_distance = max_distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.upgrade.name}, position={self.position}, priority={self.priority})"



class AttackOrDefenseTask(Task, ABC):
    target: Point2
    strength: Optional[float]
    minimum_size: int

    def __init__(self,
                 target: Point2,
                 strength: Optional[float] = None,
                 *,
                 minimum_size: int = 1,
                 reqs: Optional[TaskRequirements] = None,
                 deps: Optional[TaskDependencies | TaskStatus | int] = None,
                 priority: int = 50,
                 repeat: bool = False,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.target = target
        self.strength = strength
        self.minimum_size = minimum_size

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(target={self.target}, strength={self.strength}, priority={self.priority})"


class AttackTask(AttackOrDefenseTask):
    pass


class DefenseTask(AttackOrDefenseTask):
    pass
