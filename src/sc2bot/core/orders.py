import itertools
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Any

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

from sc2bot.core.manager import Manager

if TYPE_CHECKING:
    from sc2bot.core.commander import Commander


_order_id_counter = itertools.count()


def _get_next_order_id() -> int:
    return next(_order_id_counter)


@dataclass(repr=False, frozen=True)
class Order(ABC):
    id: int = field(default_factory=_get_next_order_id, init=False, compare=False)

    @abstractmethod
    def __repr__(self) -> str:
        pass

    @abstractmethod
    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        pass

    # def __hash__(self) -> int:
    #     return self.id
    #
    # def __eq__(self, other: Any) -> bool:
    #     if isinstance(other, Order):
    #         return self.id == other.id
    #     return NotImplemented


@dataclass(frozen=True)
class BuildOrder(Order):
    utype: UnitTypeId
    position: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name}, {self.position})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.build(self.utype, position=self.position, queue=queue)


@dataclass(frozen=True)
class TrainOrder(Order):
    utype: UnitTypeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.train(self.utype, queue=queue)


@dataclass(frozen=True)
class ResearchOrder(Order):
    upgrade: UpgradeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.upgrade.name})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.research(self.upgrade, queue=queue)


@dataclass(frozen=True)
class MoveOrder(Order):
    target: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.move(self.target, queue=queue)


@dataclass(frozen=True)
class AttackOrder(Order):
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.attack(self.target, queue=queue)


@dataclass(frozen=True)
class AbilityOrder(Order):
    ability: AbilityId
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit(self.ability, target=self.target, queue=queue)


@dataclass(frozen=True)
class GatherOrder(Order):
    target: Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.gather(target=self.target, queue=queue)


@dataclass(frozen=True)
class ReturnResourceOrder(Order):

    def __repr__(self) -> str:
        return f"{type(self).__name__}"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.return_resource(queue=queue)


class OrderManager(Manager):
    orders: dict[int, list[Order]]
    """Orders of the current step"""
    previous_orders: dict[int, list[Order]]
    """Orders of the previous step"""
    last_orders: dict[int, list[Order]]
    """Last order of any previous step"""

    def __init__(self, commander: 'Commander') -> None:
        super().__init__(commander)
        self.orders = {}
        self.previous_orders = {}
        self.last_orders = {}

    async def on_step(self, step: int) -> None:
        # Clean orders of dead units
        alive_tags = self.commander.forces.tags
        self.orders = {tag: orders for tag, orders in self.orders.items() if tag in alive_tags}
        self.last_orders = {tag: orders for tag, orders in self.last_orders.items() if tag in alive_tags}

        self.last_orders.update(self.orders)
        self.previous_orders = self.orders
        self.orders = {}

        for order in list(self.commander.expected_units.keys()):
            if order not in self.last_orders.values():
                self.commander.remove_expected_unit(order)

    def get_order(self, unit: Unit) -> Optional[Order]:
        return self.orders.get(unit.tag)

    def has_order(self, unit: Unit) -> bool:
        return unit.tag in self.orders

    def move(self, unit: Unit, target: Point2, *, queue: bool = False) -> bool:
        return self._order(unit, MoveOrder, target, queue=queue)

    def attack(self, unit: Unit, target: Point2 | Unit, *, queue: bool = False) -> bool:
        return self._order(unit, AttackOrder, target, queue=queue)

    def ability(self, unit: Unit, ability: AbilityId, target: Point2 | Unit, *, queue: bool = False) -> bool:
        return self._order(unit, AbilityOrder, ability, target, queue=queue)

    def gather(self, unit: Unit, target: Unit, *, queue: bool = False) -> bool:
        return self._order(unit, GatherOrder, target, queue=queue)

    def return_resource(self, unit: Unit, *, queue: bool = False) -> bool:
        return self._order(unit, ReturnResourceOrder, queue=queue)

    def build(self, unit: Unit, utype: UnitTypeId, position: Point2 | Unit, *, queue: bool = False) -> bool:
        return self._order(unit, BuildOrder, utype, position, queue=queue)

    def train(self, unit: Unit, utype: UnitTypeId, *, queue: bool = False) -> bool:
        # TODO: do not train if already training
        return self._order(unit, TrainOrder, utype, queue=queue)

    def research(self, unit: Unit, upgrade: UpgradeId, *, queue: bool = False) -> bool:
        return self._order(unit, ResearchOrder, upgrade, queue=queue)

    def _check_unit(self, unit: Unit, *, queue: bool) -> bool:
        if not self.commander.has_units(unit):
            self.logger.error("{} does not control {}", self, unit)
            return False
        if not queue and unit.tag in self.orders:
            self.logger.error("unit {} already has orders: {}", unit, self.orders.get(unit.tag))
            return False
        return True

    def _is_new_order(self, unit: Unit, order: Order, *, queue: bool) -> bool:
        """Check if the order is new or just repeated (and doesn't need to be sent to the API)."""
        prev_orders = self.previous_orders.get(unit.tag)
        if not prev_orders:
            return True

        idx = 0 if not queue else -1
        return order != prev_orders[idx]

    def _order(self, unit: Unit, order_cls: type[Order],
               *order_args: Unit | Point2 | UnitTypeId | AbilityId | UpgradeId, queue: bool) -> bool:
        if not self._check_unit(unit, queue=queue):
            return False
        order = order_cls(*order_args)
        self.logger.trace("Order {} to {}", unit, order)
        if self._is_new_order(unit, order, queue=queue):
            order.issue(unit, queue=queue)
        self._add_order(unit, order, queue=queue)
        return True

    def _add_order(self, unit: Unit, order: Order, *, queue: bool) -> None:
        if queue:
            if not self.has_order(unit):
                self.orders[unit.tag] = []
            self.orders[unit.tag].append(order)
        else:
            self.orders[unit.tag] = [order]
