import copy
from abc import ABC
from enum import Enum, StrEnum
from typing import Optional, Self, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.geometry.util import unique_id, Rectangle, Area

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class ObjectiveStatus(Enum):
    NOT_STARTED = 0
    STARTED = 1
    COMPLETED = 2
    FAILED = 3


class ObjectiveRequirementType(StrEnum):
    TIME = "T"
    SUPPLY = "S"
    MINERALS = "M"
    VESPENE = "G"


DEFAULT_PRIORITY = 0.5


ObjectiveDependencies = dict[int, ObjectiveStatus]
ObjectiveRequirements = list[tuple[ObjectiveRequirementType | UnitTypeId | UpgradeId, int | bool]]


class Objective(BotObject, ABC):
    reqs: ObjectiveRequirements
    deps: ObjectiveDependencies
    priority: float
    repeat: bool = False
    persistent: bool = False
    status: ObjectiveStatus
    assigned: set[int]

    def __init__(self,
                 bot: 'AvocaDOS',
                 reqs: Optional[ObjectiveRequirements | UnitTypeId | UpgradeId] = None,
                 deps: Optional[ObjectiveDependencies | ObjectiveStatus | int] =  None,
                 priority: float = DEFAULT_PRIORITY,
                 repeat: bool = False,
                 persistent: bool = False,
                 status: ObjectiveStatus = ObjectiveStatus.NOT_STARTED,
                 ) -> None:
        super().__init__(bot)
        self.reqs = self._normalize_reqs(reqs)
        if deps is None:
            deps = {}
        elif isinstance(deps, int):
            deps = {deps: ObjectiveStatus.COMPLETED}
        elif isinstance(deps, ObjectiveStatus):
            deps = {self.id - 1: deps} if self.id > 0 else {}
        self.deps = deps
        if not (0 <= priority <= 1):
            self.log.error("Priority must be between 0 and 1")
            priority = 0 if priority < 0 else 1
        self.priority = priority
        self.repeat = repeat
        self.persistent = persistent
        self.status = status
        self.assigned = set()

    @staticmethod
    def _normalize_reqs(reqs: Optional[ObjectiveRequirements | UnitTypeId | UpgradeId]) -> ObjectiveRequirements:
        if reqs is None:
            return []
        if isinstance(reqs, (UnitTypeId, UpgradeId)):
            return [(reqs, 1)]
        if isinstance(reqs, tuple) and len(reqs) == 2:
            return [reqs]
        return reqs

    def mark_complete(self) -> None:
        if not self.persistent:
            self.status = ObjectiveStatus.COMPLETED

    def assign_units(self, units: Unit | Units | set[int]) -> None:
        if isinstance(units, Unit):
            units = {units.tag}
        elif isinstance(units, Units):
            units = units.tags
        self.assigned.update(units)

    def copy(self, status: Optional[ObjectiveStatus] = None) -> Self:
        copied_task = copy.copy(self)
        copied_task.id = unique_id()
        copied_task.status = status or self.status
        return copied_task


class ConstructionObjective(Objective):
    utype: UnitTypeId
    number: int
    position: Optional[Rectangle]
    max_workers: int
    include_addon: bool

    def __init__(self,
                 bot: 'AvocaDOS',
                 utype: UnitTypeId,
                 number: int = 1,
                 max_workers: Optional[int] = None,
                 include_addon: bool = True,
                 *,
                 reqs: Optional[ObjectiveRequirements] = None,
                 deps: Optional[ObjectiveDependencies | ObjectiveStatus | int] = None,
                 priority: float = DEFAULT_PRIORITY,
                 repeat: bool = False,
                 position: Optional[Point2 | Rectangle] = None,
                 max_distance: int = 16,
                 ) -> None:
        super().__init__(bot=bot, reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.utype = utype
        self.number = number
        if isinstance(position, Point2):
            position = Rectangle.from_center(position, 2 * max_distance, 2 * max_distance)
        if isinstance(position, Rectangle):
            position = position.enclosed_rect()
        self.position = position
        self.max_workers = max_workers or number
        self.include_addon = include_addon

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, number={self.number}, position={self.position}, priority={self.priority})"


class UnitObjective(Objective):
    utype: UnitTypeId
    number: int
    position: Optional[Rectangle]

    def __init__(self,
                 bot: 'AvocaDOS',
                 utype: UnitTypeId,
                 number: int = 1,
                 *,
                 reqs: Optional[ObjectiveRequirements] = None,
                 deps: Optional[ObjectiveDependencies | ObjectiveStatus | int] = None,
                 priority: float = DEFAULT_PRIORITY,
                 repeat: bool = False,
                 position: Optional[Point2 | Rectangle] = None,
                 max_distance: int = 16,
                 persistent: bool = False,
                 ) -> None:
        super().__init__(bot=bot, reqs=reqs, deps=deps, priority=priority, repeat=repeat, persistent=persistent)
        self.utype = utype
        self.number = number
        if isinstance(position, Point2):
            position = Rectangle.from_center(position, 2 * max_distance, 2 * max_distance)
        if isinstance(position, Rectangle):
            position = position.enclosed_rect()
        self.position = position

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, number={self.number}, position={self.position}, priority={self.priority})"


class WorkerObjective(UnitObjective):
    def __init__(self,
                 bot: 'AvocaDOS',
                 number: int,
                 *,
                 priority: float = DEFAULT_PRIORITY,
                 ) -> None:
        super().__init__(bot=bot, utype=bot.ext.worker_utype, number=number, priority=priority, persistent=True)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(number={self.number}, priority={self.priority})"


class SupplyObjective(Objective):
    number: int

    def __init__(self,
                 bot: 'AvocaDOS',
                 number: int,
                 *,
                 priority: float = DEFAULT_PRIORITY,
                 ) -> None:
        super().__init__(bot=bot, priority=priority, persistent=True)
        self.number = number

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(number={self.number}, priority={self.priority})"

    @property
    def utype(self) -> UnitTypeId:
        return self.ext.supply_utype

    @property
    def position(self) -> None:
        return None


class ResearchObjective(Objective):
    upgrade: UpgradeId
    position: Point2
    max_distance: float

    def __init__(self,
                 bot: 'AvocaDOS',
                 upgrade: UpgradeId,
                 *,
                 reqs: Optional[ObjectiveRequirements] = None,
                 deps: Optional[ObjectiveDependencies | ObjectiveStatus | int] =  None,
                 priority: float = DEFAULT_PRIORITY,
                 repeat: bool = False,
                 position: Optional[Point2] = None,
                 max_distance: Optional[float] = 10,
                 ) -> None:
        super().__init__(bot=bot, reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.upgrade = upgrade
        self.position = position
        self.max_distance = max_distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.upgrade.name}, position={self.position}, priority={self.priority})"


class AttackOrDefenseObjective(Objective, ABC):
    target: Area
    strength: float
    minimum_size: int
    duration: Optional[float]

    def __init__(self,
                 bot: 'AvocaDOS',
                 target: Area,
                 strength: float = 100.0,
                 *,
                 minimum_size: int = 1,
                 duration: Optional[float] = None,
                 reqs: Optional[ObjectiveRequirements] = None,
                 deps: Optional[ObjectiveDependencies | ObjectiveStatus | int] = None,
                 priority: float = DEFAULT_PRIORITY,
                 repeat: bool = False,
                 ) -> None:
        super().__init__(bot=bot, reqs=reqs, deps=deps, priority=priority, repeat=repeat)
        self.target = target
        self.strength = strength
        self.minimum_size = minimum_size
        self.duration = duration

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(target={self.target}, strength={self.strength}, priority={self.priority})"


class AttackObjective(AttackOrDefenseObjective):
    pass


class DefenseObjective(AttackOrDefenseObjective):
    pass
