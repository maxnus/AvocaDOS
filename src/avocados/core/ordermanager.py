from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit, UnitOrder
from sc2.unit_command import UnitCommand
from sc2.units import Units

from avocados.core.constants import UNIT_CREATION_ABILITIES, UPGRADE_ABILITIES
from avocados.geometry.util import same_point


DEFAULT_ORDER_PRIORITY = 0.5


@dataclass(repr=False, frozen=True)
class Order(ABC):

    @abstractmethod
    def __repr__(self) -> str:
        pass

    @property
    @abstractmethod
    def priority(self) -> float:
        pass

    @property
    @abstractmethod
    def short_repr(self) -> str:
        pass

    @property
    @abstractmethod
    def ability_id(self) -> AbilityId:
        pass

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit(self.ability_id, queue=queue)

    def to_command(self, unit: Unit, *, queue: bool = False) -> UnitCommand:
        return UnitCommand(self.ability_id, unit, queue=queue)

    def matches(self, order: UnitOrder) -> bool:
        return order.ability.exact_id == self.ability_id


@dataclass(frozen=True)
class TrainOrder(Order):
    utype: UnitTypeId
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name})"

    @property
    def short_repr(self) -> str:
        return f"T({self.utype.name})"

    @property
    def ability_id(self) -> AbilityId:
        return UNIT_CREATION_ABILITIES[self.utype]


@dataclass(frozen=True)
class UpgradeOrder(Order):
    upgrade: UpgradeId
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.upgrade.name})"

    @property
    def short_repr(self) -> str:
        return f"U({self.upgrade.name})"

    @property
    def ability_id(self) -> AbilityId:
        return UPGRADE_ABILITIES[self.upgrade]


@dataclass(frozen=True)
class ReturnResourceOrder(Order):
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}"

    @property
    def short_repr(self) -> str:
        return "R"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.HARVEST_RETURN


# --- Orders with target


def is_same_target(target1: Unit | Point2 | None, target2: Unit | Point2 | None) -> bool:
    if isinstance(target1, Point2) and isinstance(target2, Point2):
        return same_point(target1, target2)
    return target1 == target2


@dataclass(repr=False, frozen=True)
class TargetOrder(Order, ABC):
    target: Unit | Point2 | None

    def issue(self, unit: Unit, *, queue: bool = False) -> None:
        unit(self.ability_id, target=self.target, queue=queue)

    def to_command(self, unit: Unit, *, queue: bool = False) -> UnitCommand:
        return UnitCommand(self.ability_id, unit, target=self.target, queue=queue)

    def matches(self, order: UnitOrder) -> bool:
        return order.ability.exact_id == self.ability_id and is_same_target(order.target, self.target)


@dataclass(frozen=True)
class MoveOrder(TargetOrder):
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "M"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.MOVE_MOVE


@dataclass(frozen=True)
class AttackOrder(TargetOrder):
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "A"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.ATTACK


@dataclass(frozen=True)
class AbilityOrder(TargetOrder):
    ability: AbilityId
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "C"

    @property
    def ability_id(self) -> AbilityId:
        return self.ability


@dataclass(frozen=True)
class SmartOrder(TargetOrder):
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "S"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.SMART


@dataclass(frozen=True)
class BuildOrder(TargetOrder):
    utype: UnitTypeId
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.utype.name}, {self.target})"

    @property
    def short_repr(self) -> str:
        return f"B({self.utype.name})"

    @property
    def ability_id(self) -> AbilityId:
        return UNIT_CREATION_ABILITIES[self.utype]


@dataclass(frozen=True)
class GatherOrder(TargetOrder):
    priority: float = field(default=DEFAULT_ORDER_PRIORITY, compare=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "G"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.HARVEST_GATHER


class OrderManager:
    orders: dict[Unit, list[Order]]

    def __init__(self) -> None:
        super().__init__()
        self.orders = {}

    async def on_step_start(self, step: int) -> None:
        self.orders.clear()

    async def on_step_end(self, step: int) -> None:
        for unit, orders in self.orders.items():
            for idx, order in enumerate(orders):
                queue = idx > 0
                if self._is_new_order(unit, order, queue=queue):
                    order.issue(unit, queue=queue)

    def has_order(self, unit: Unit) -> bool:
        return unit in self.orders

    def move(self, unit: Unit | Units, target: Point2 | Unit, *,
             queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, MoveOrder, target, queue=queue, priority=priority)

    def attack(self, unit: Unit | Units, target: Point2 | Unit, *,
               queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, AttackOrder, target, queue=queue, priority=priority)

    def ability(self, unit: Unit | Units, ability: AbilityId, target: Optional[Point2 | Unit] = None, *,
                queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, AbilityOrder, target, ability, queue=queue, priority=priority)

    def gather(self, unit: Unit | Units, target: Unit, *,
               queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, GatherOrder, target, queue=queue, priority=priority)

    def return_resource(self, unit: Unit | Units, *,
                        queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, ReturnResourceOrder, queue=queue, priority=priority)

    def build(self, unit: Unit | Units, utype: UnitTypeId, position: Point2 | Unit, *,
              queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, BuildOrder, position, utype, queue=queue, priority=priority)

    def train(self, unit: Unit | Units, utype: UnitTypeId, *,
              queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        # TODO: do not train if already training
        return self._order(unit, TrainOrder, utype, queue=queue, priority=priority)

    def upgrade(self, unit: Unit | Units, upgrade: UpgradeId, *,
                queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, UpgradeOrder, upgrade, queue=queue, priority=priority)

    def smart(self, unit: Unit | Units, target: Point2 | Unit, *,
              queue: bool = False, priority: float = DEFAULT_ORDER_PRIORITY) -> bool:
        return self._order(unit, SmartOrder, target, queue=queue, priority=priority)

    def _is_new_order(self, unit: Unit, order: Order, *, queue: bool) -> bool:
        """Check if the order is new or just repeated (and doesn't need to be sent to the API)."""
        orders = unit.orders
        if not orders:
            return True
        current_order = orders[-1] if queue else orders[0]
        return not order.matches(current_order)

    def _order(self, unit: Unit | Units, order_cls: type[Order],
               *order_args: Unit | Point2 | UnitTypeId | AbilityId | UpgradeId | Order,
               queue: bool,
               priority: float
               ) -> bool:
        if isinstance(unit, Units):
            return all(self._order(u, order_cls, *order_args, queue=queue, priority=priority) for u in unit)
        order = order_cls(*order_args, priority=priority)
        if queue and self.has_order(unit):
            self.orders[unit].append(order)
        else:
            current_orders = self.orders.get(unit)
            # if current_orders:
            #     if priority <= current_orders[0].priority:
            #         self.logger.debug("Ignoring {} due to {}", order, current_orders[0])
            #     else:
            #         self.logger.debug("Overriding {} due to {}", current_orders[0], order)
            if not current_orders or priority > current_orders[0].priority:
                self.orders[unit] = [order]
        return True
