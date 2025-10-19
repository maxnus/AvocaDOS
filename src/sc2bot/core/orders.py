from abc import ABC, abstractmethod
from dataclasses import dataclass

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit


class Order(ABC):

    @abstractmethod
    def __repr__(self) -> str:
        pass


@dataclass
class BuildOrder(Order):
    utype: UnitTypeId
    position: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name}, {self.position})"


@dataclass
class TrainOrder(Order):
    utype: UnitTypeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name})"


@dataclass
class MoveOrder(Order):
    target: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


@dataclass
class AttackOrder(Order):
    target: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


@dataclass
class GatherOrder(Order):
    target: Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"
