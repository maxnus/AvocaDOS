import itertools
from abc import ABC, abstractmethod
from collections.abc import Iterator
from enum import Enum, StrEnum
from typing import Optional, TYPE_CHECKING

from loguru._logger import Logger
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

if TYPE_CHECKING:
    from .commander import Commander


class TaskStatus(Enum):
    NOT_STARTED = 0
    STARTED = 1
    COMPLETED = 2
    FAILED = 3


class RequirementType(StrEnum):
    TIME = "T"
    SUPPLY = "S"
    MINERALS = "M"
    VESPENE = "G"


_task_id_counter = itertools.count()


def _get_next_id() -> int:
    return next(_task_id_counter)


Dependencies = dict[int, TaskStatus]
Requirements = list[tuple[RequirementType | UnitTypeId | UpgradeId, int | bool]]


class Task(ABC):
    id: int
    reqs: Requirements
    deps: Dependencies
    status: TaskStatus
    priority: int
    started: Optional[int]
    finished: Optional[int]
    timeout: Optional[int]

    def __init__(self,
                 reqs: Optional[Requirements | UnitTypeId | UpgradeId] = None,
                 deps: Optional[Dependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 status: TaskStatus = TaskStatus.NOT_STARTED,
                 started: Optional[int] = None,
                 finished: Optional[int] = None,
                 timeout: Optional[int] = None):
        self.id = _get_next_id()
        self.reqs = self._normalize_reqs(reqs)
        if deps is None:
            deps = {}
        elif isinstance(deps, int):
            deps = {deps: TaskStatus.COMPLETED}
        elif isinstance(deps, TaskStatus):
            deps = {self.id - 1: deps} if self.id > 0 else {}
        self.deps = deps
        self.priority = priority
        self.status = status
        self.started = started
        self.finished = finished
        self.timeout = timeout

    @staticmethod
    def _normalize_reqs(reqs: Optional[Requirements | UnitTypeId | UpgradeId]) -> Requirements:
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

    # def add_deps(self, *, started: Optional[list[int]] = None, completed: Optional[list[int]]) -> None:
    #     if started:
    #         for x in started:
    #             self.deps[x] = TaskStatus.STARTED
    #     if completed:
    #         for x in completed:
    #             self.deps[x] = TaskStatus.COMPLETED


class BuildTask(Task):
    utype: UnitTypeId
    position: Point2
    max_distance: float

    def __init__(self,
                 utype: UnitTypeId,
                 *,
                 reqs: Optional[Requirements] = None,
                 deps: Optional[Dependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 position: Optional[Point2] = None,
                 max_distance: Optional[float] = 10,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority)
        self.utype = utype
        self.position = position
        self.max_distance = max_distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, position={self.position}, priority={self.priority})"



class ResearchTask(Task):
    upgrade: UpgradeId
    position: Point2
    max_distance: float

    def __init__(self,
                 upgrade: UpgradeId,
                 *,
                 reqs: Optional[Requirements] = None,
                 deps: Optional[Dependencies | TaskStatus | int] =  None,
                 priority: int = 50,
                 position: Optional[Point2] = None,
                 max_distance: Optional[float] = 10,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority)
        self.upgrade = upgrade
        self.position = position
        self.max_distance = max_distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.upgrade.name}, position={self.position}, priority={self.priority})"


class UnitCountTask(Task):
    utype: UnitTypeId
    number: int
    position: Optional[Point2 | Unit]
    max_distance: int

    def __init__(self,
                 utype: UnitTypeId,
                 number: int = 1,
                 *,
                 reqs: Optional[Requirements] = None,
                 deps: Optional[Dependencies | TaskStatus | int] = None,
                 priority: int = 50,
                 position: Optional[Point2] = None,
                 distance: Optional[int] = 10,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority)
        self.utype = utype
        self.number = number
        self.position = position
        self.max_distance = distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, number={self.number}, position={self.position}, priority={self.priority})"


class UnitPendingTask(Task):
    utype: UnitTypeId
    position: Optional[Point2 | Unit]
    distance: float

    def __init__(self,
                 utype: UnitTypeId,
                 *,
                 reqs: Optional[Requirements] = None,
                 deps: Optional[Dependencies | TaskStatus | int] = None,
                 priority: int = 50,
                 position: Optional[Point2] = None,
                 distance: Optional[float] = 3.0,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority)
        self.utype = utype
        self.position = position
        self.distance = distance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(utype={self.utype.name}, position={self.position}, priority={self.priority}"


class OrderTask(Task):
    target: Point2
    units: Optional[dict[UnitTypeId, int]]

    def __init__(self,
                 target: Point2,
                 units: Optional[dict[UnitTypeId, int]] | UnitTypeId = None,
                 *,
                 reqs: Optional[Requirements] = None,
                 deps: Optional[Dependencies | TaskStatus | int] = None,
                 priority: int = 50,
                 ) -> None:
        super().__init__(reqs=reqs, deps=deps, priority=priority)
        if isinstance(units, UnitTypeId):
            units = {units: 1}
        self.units = units
        self.target = target

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(target={self.target}, units={self.units}, priority={self.priority})"


class MoveTask(OrderTask):
    pass


class AttackTask(OrderTask):
    pass


class TaskManager:
    commander: 'Commander'
    completed: dict[int, Task]
    current: dict[int, Task]
    future: dict[int, Task]

    def __init__(self, commander: 'Commander', tasks: Optional[dict[int, Task]]) -> None:
        self.commander = commander
        self.completed = {}
        self.current = {}
        self.future = tasks or {}

    @property
    def logger(self) -> Logger:
        return self.commander.logger

    def add(self, task: Task) -> int:
        self.future[task.id] = task
        return task.id

    def __bool__(self) -> bool:
        return bool(self.current)

    def __iter__(self) -> Iterator[Task]:
        yield from sorted(self.current.values(), key=lambda task: task.priority, reverse=True)

    def get_status(self, task_id: int) -> Optional[TaskStatus]:
        if task_id in self.current:
            return self.current[task_id].status
        if task_id in self.future:
            return self.future[task_id].status
        if task_id in self.completed:
            return self.completed[task_id].status
        self.logger.warning(f"Unknown task id: {task_id}")
        return None

    def _requirements_fulfilled(self, requirements: Requirements) -> bool:
        fulfilled = True
        for req_type, req_value in requirements:
            if isinstance(req_type, UnitTypeId):
                value = self.commander.forces(req_type).ready.amount
            elif isinstance(req_type, UpgradeId):
                value = req_type in self.commander.bot.state.upgrades
            elif req_type == RequirementType.TIME:
                value = self.commander.time
            elif req_type == RequirementType.SUPPLY:
                value = self.commander.supply_used
            elif req_type == RequirementType.MINERALS:
                value = self.commander.minerals
            elif req_type == RequirementType.VESPENE:
                value = self.commander.vespene
            else:
                self.logger.warning(f"Unknown requirement: {req_type}")
                continue
            if isinstance(value, bool):
                fulfilled = value == req_value and fulfilled
            else:
                fulfilled = value >= req_value and fulfilled
        return fulfilled

    def _dependencies_fulfilled(self, dependencies: Dependencies) -> bool:
        return all(self.get_status(dep) in {status, None} for dep, status in dependencies.items())

    def _task_ready(self, task: Task) -> bool:
        return self._dependencies_fulfilled(task.deps) and self._requirements_fulfilled(task.reqs)

    async def update_tasks(self, iteration: int) -> None:
        for task in self.current.copy().values():
            if task.status == TaskStatus.COMPLETED:
                task.finished = iteration
                self.current.pop(task.id)
                self.completed[task.id] = task
                self.logger.debug("Completed {}", task)

        for task in self.future.copy().values():
            if self._task_ready(task):
                task = self.future.pop(task.id)
                task.status = TaskStatus.STARTED
                task.started = iteration
                self.current[task.id] = task
                self.logger.debug("Started {}", task)

    # def _check_timeout(self, objective: Task, iteration: int) -> bool:
    #     if objective.timeout is None:
    #         return False
    #     if objective.status != TaskStatus.IN_PROGRESS:
    #         return False
    #     if iteration < objective.started + objective.timeout:
    #         return False
    #     objective.status = TaskStatus.FAILED
    #     self.logger.debug("Objective {} timed out", objective)
    #     return True
