from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

from sc2bot.core.manager import Manager

if TYPE_CHECKING:
    from sc2bot.core.commander import Commander


class Order(ABC):

    @abstractmethod
    def __repr__(self) -> str:
        pass


@dataclass
class BuildOrder(Order):
    utype: UnitTypeId
    position: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name}, {self.position})"


@dataclass
class TrainOrder(Order):
    utype: UnitTypeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name})"


@dataclass
class ResearchOrder(Order):
    upgrade: UpgradeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.upgrade.name})"


@dataclass
class MoveOrder(Order):
    target: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


@dataclass
class AttackOrder(Order):
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


@dataclass
class AbilityOrder(Order):
    ability: AbilityId
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


@dataclass
class GatherOrder(Order):
    target: Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"


class OrderManager(Manager):
    orders: dict[int, Order]
    previous_orders: dict[int, Order]
    last_orders: dict[int, Order]

    def __init__(self, commander: 'Commander') -> None:
        super().__init__(commander)
        self.orders = {}
        self.previous_orders = {}
        self.last_orders = {}

    async def on_step(self, step: int) -> None:
        self.last_orders.update(self.orders)
        self.previous_orders = self.orders
        self.orders = {}

    def get_order(self, unit: Unit) -> Optional[Order]:
        return self.orders.get(unit.tag)

    def has_order(self, unit: Unit) -> bool:
        return unit.tag in self.orders

    def move(self, unit: Unit, target: Point2) -> bool:
        if not self._check_unit(unit):
            return False
        order = MoveOrder(target)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.move(target)
        self.orders[unit.tag] = order
        return True

    def attack(self, unit: Unit, target: Point2 | Unit) -> bool:
        if not self._check_unit(unit):
            return False
        order = AttackOrder(target)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.attack(target)
        self.orders[unit.tag] = order
        return True

    def ability(self, unit: Unit, ability: AbilityId, target: Point2 | Unit) -> bool:
        if not self._check_unit(unit):
            return False
        order = AbilityOrder(ability, target)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit(ability, target)
        self.orders[unit.tag] = order
        return True

    def gather(self, unit: Unit, target: Unit) -> bool:
        if not self._check_unit(unit):
            return False
        order = GatherOrder(target)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.gather(target)
        self.orders[unit.tag] = order
        return True

    def build(self, unit: Unit, utype: UnitTypeId, position: Point2 | Unit) -> bool:
        if not self._check_unit(unit):
            return False
        if not self.commander.resources.spend(utype):
            return False
        order = BuildOrder(utype, position)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.build(utype, position=position)
        self.orders[unit.tag] = order
        return True

    def train(self, unit: Unit, utype: UnitTypeId) -> bool:
        # TODO: do not train if already training
        if not self._check_unit(unit):
            return False
        if not self.commander.resources.spend(utype):
            return False
        order = TrainOrder(utype)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.train(utype)
        self.orders[unit.tag] = order
        return True

    def research(self, unit: Unit, upgrade: UpgradeId) -> bool:
        if not self._check_unit(unit):
            return False
        if not self.commander.resources.spend(upgrade):
            return False
        order = ResearchOrder(upgrade)
        self.logger.trace("Order {} to {}", unit, order)
        if order != self.previous_orders.get(unit.tag):
            unit.research(upgrade)
        self.orders[unit.tag] = order
        return True

    def _check_unit(self, unit: Unit) -> bool:
        if not self.commander.has_units(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        if unit.tag in self.orders:
            self.logger.error("unit {} already has order: {}", unit, self.orders.get(unit.tag))
            raise ValueError
            return False
        return True
