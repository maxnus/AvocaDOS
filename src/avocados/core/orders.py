from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.util import unique_id

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


@dataclass(repr=False, frozen=True)
class Order(ABC):
    #id: int = field(default_factory=unique_id, init=False, compare=False)

    @abstractmethod
    def __repr__(self) -> str:
        pass

    @property
    @abstractmethod
    def short_repr(self) -> str:
        pass

    @abstractmethod
    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        pass


@dataclass(frozen=True)
class BuildOrder(Order):
    utype: UnitTypeId
    position: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name}, {self.position})"

    @property
    def short_repr(self) -> str:
        return f"B({self.utype.name})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.build(self.utype, position=self.position, queue=queue)


@dataclass(frozen=True)
class TrainOrder(Order):
    utype: UnitTypeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name})"

    @property
    def short_repr(self) -> str:
        return f"T({self.utype.name})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.train(self.utype, queue=queue)


@dataclass(frozen=True)
class UpgradeOrder(Order):
    upgrade: UpgradeId

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.upgrade.name})"

    @property
    def short_repr(self) -> str:
        return f"U({self.upgrade.name})"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.research(self.upgrade, queue=queue)


@dataclass(frozen=True)
class MoveOrder(Order):
    target: Point2

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "M"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.move(self.target, queue=queue)


@dataclass(frozen=True)
class AttackOrder(Order):
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "A"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.attack(self.target, queue=queue)


@dataclass(frozen=True)
class AbilityOrder(Order):
    ability: AbilityId
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "C"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit(self.ability, target=self.target, queue=queue)


@dataclass(frozen=True)
class SmartOrder(Order):
    target: Point2 | Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "S"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.smart(target=self.target, queue=queue)


@dataclass(frozen=True)
class GatherOrder(Order):
    target: Unit

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "G"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.gather(target=self.target, queue=queue)


@dataclass(frozen=True)
class ReturnResourceOrder(Order):

    def __repr__(self) -> str:
        return f"{type(self).__name__}"

    @property
    def short_repr(self) -> str:
        return "R"

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit.return_resource(queue=queue)


class OrderManager(BotObject):
    orders: dict[int, list[Order]]
    """Orders of the current step"""
    orders_prev: dict[int, list[Order]]
    """Orders of the previous step"""
    orders_last: dict[int, list[Order]]
    """Last order of any previous step"""

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.orders = {}
        self.orders_prev = {}
        self.orders_last = {}

    async def on_step(self, step: int) -> None:
        # Clean orders of dead units (TODO is this really necessary? why not just keep them)
        # alive_tags = self.commander.forces.tags
        # self.orders = {tag: orders for tag, orders in self.orders.items() if tag in alive_tags}
        # self.last_orders = {tag: orders for tag, orders in self.last_orders.items() if tag in alive_tags}

        self.orders_last.update(self.orders)
        self.orders_prev = self.orders
        self.orders = {}

    def get_orders(self, unit: Unit) -> Optional[list[Order]]:
        return self.orders.get(unit.tag)

    def has_order(self, unit: Unit) -> bool:
        return unit.tag in self.orders

    def move(self, unit: Unit | Units, target: Point2, *,
             queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, MoveOrder, target, queue=queue, force=force)

    def attack(self, unit: Unit | Units, target: Point2 | Unit, *,
               queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, AttackOrder, target, queue=queue, force=force)

    def ability(self, unit: Unit | Units, ability: AbilityId, target: Point2 | Unit, *,
                queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, AbilityOrder, ability, target, queue=queue, force=force)

    def gather(self, unit: Unit | Units, target: Unit, *,
               queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, GatherOrder, target, queue=queue, force=force)

    def return_resource(self, unit: Unit | Units, *,
                        queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, ReturnResourceOrder, queue=queue, force=force)

    def build(self, unit: Unit | Units, utype: UnitTypeId, position: Point2 | Unit, *,
              queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, BuildOrder, utype, position, queue=queue, force=force)

    def train(self, unit: Unit | Units, utype: UnitTypeId, *,
              queue: bool = False, force: bool = False) -> bool:
        # TODO: do not train if already training
        return self._order(unit, TrainOrder, utype, queue=queue, force=force)

    def upgrade(self, unit: Unit | Units, upgrade: UpgradeId, *,
                queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, UpgradeOrder, upgrade, queue=queue, force=force)

    def smart(self, unit: Unit | Units, target: Point2 | Unit, *,
              queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, SmartOrder, target, queue=queue, force=force)

    def _check_unit(self, unit: Unit, *, queue: bool) -> bool:
        if not queue and unit.tag in self.orders:
            self.logger.error("Unit {} already has orders: {}", unit, self.orders.get(unit.tag))
            return False
        return True

    def _is_new_order(self, unit: Unit, order: Order, *, queue: bool) -> bool:
        """Check if the order is new or just repeated (and doesn't need to be sent to the API)."""
        #prev_orders = self.orders_prev.get(unit.tag)

        # These orders should always be considered new:
        if isinstance(order, TrainOrder):
            return True

        prev_orders = self.orders_last.get(unit.tag)
        if not prev_orders:
            return True

        idx = 0 if not queue else -1
        return order != prev_orders[idx]

    def _order(self, unit: Unit | Units, order_cls: type[Order],
               *order_args: Unit | Point2 | UnitTypeId | AbilityId | UpgradeId,
               queue: bool, force: bool) -> bool:
        if isinstance(unit, Units):
            return all(self._order(u, order_cls, *order_args, queue=queue, force=force) for u in unit)

        if not self._check_unit(unit, queue=queue):
            return False
        order = order_cls(*order_args)
        #self.logger.trace("Order {} to {}", unit, order)
        if force or self._is_new_order(unit, order, queue=queue):
            #self.logger.info("New order to unit {}: {}", unit, order)
            order.issue(unit, queue=queue)
        # else:
        #     self.logger.info("Unit {} already has order {} in orders {}", unit, order, self.orders.get(unit.tag))

        if queue:
            self._queue_order(unit, order)
        else:
            self._set_order(unit, order)
        return True

    def _set_order(self, unit: Unit, order: Order) -> None:
        self.orders[unit.tag] = [order]

    def _queue_order(self, unit: Unit, order: Order) -> None:
        if self.has_order(unit):
            self.orders[unit.tag].append(order)
        else:
            self._set_order(unit, order)
