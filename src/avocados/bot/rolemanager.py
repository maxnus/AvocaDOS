from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit

from avocados.combat.squad import Squad
from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class Role(ABC):

    @property
    @abstractmethod
    def assigned(self) -> int:
        pass

    @property
    @abstractmethod
    def duration(self) -> Optional[int]:
        pass

    @property
    @abstractmethod
    def priority(self) -> float:
        pass


@dataclass
class MiningRole(Role):
    mineral_tag: int
    townhall_tag: int
    assigned: int
    priority: float = 0.5
    duration: Optional[int] = None


@dataclass
class SquadRole(Role):
    squad: Squad
    assigned: int
    priority: float = 0.5
    duration: Optional[int] = None


@dataclass
class BuildRole(Role):
    structure: UnitTypeId
    location: Point2
    assigned: int
    priority: float = 0.5
    duration: Optional[int] = None


@dataclass
class DefenseRole(Role):
    target: Unit
    assigned: int
    priority: float = 0.5
    duration: Optional[int] = None


class RoleManager(BotManager):
    _roles: dict[int, Role]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._roles = {}

    async def on_step_start(self, step: int) -> None:
        for tag, role in self._roles.items():
            if role.duration is not None and self.step > role.assigned + role.duration:
                self.remove(tag)

    def has(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        return tag in self._roles

    def get(self, unit: Unit | int) -> Optional[Role]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        return self._roles.get(tag)

    def set(self, unit: Unit | int, role: Role) -> None:
        tag = unit.tag if isinstance(unit, Unit) else unit
        self._roles[tag] = role

    def remove(self, unit: Unit | int) -> Optional[Role]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        return self._roles.pop(tag, None)

    def clear(self) -> None:
        self._roles.clear()

    def set_mining(self, unit: Unit, townhall: Unit, mineral_field: Unit, *,
                   duration: Optional[int] = None,
                   priority: float = 0.5) -> None:
        role = MiningRole(mineral_field.tag, townhall.tag, self.step, priority=priority, duration=duration)
        self.set(unit, role)

    def set_squad(self, unit: Unit, squad: Squad, *,
                  duration: Optional[int] = None,
                  priority: float = 0.5) -> None:
        role = SquadRole(squad, self.step, priority=priority, duration=duration)
        self.set(unit, role)

    def set_build(self, unit: Unit, structure: UnitTypeId, location: Point2, *,
                  priority: float = 0.5,
                  duration: Optional[int] = None) -> None:
        role = BuildRole(structure, location, self.step, priority=priority, duration=duration)
        self.set(unit, role)

    def set_defend(self, unit: Unit, target: Unit, *,
                   priority: float = 0.5,
                   duration: Optional[int] = None) -> None:
        role = DefenseRole(target, self.step, priority=priority, duration=duration)
        self.set(unit, role)
