from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit, UnitOrder
from sc2.unit_command import UnitCommand
from sc2.units import Units

from avocados.core.constants import UNIT_CREATION_ABILITIES, UPGRADE_ABILITIES
from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


@dataclass(repr=False, frozen=True)
class Order(ABC):

    @abstractmethod
    def __repr__(self) -> str:
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
        return max(abs(target1.x - target2.x), abs(target1.y - target2.y)) < 0.001
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

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.target})"

    @property
    def short_repr(self) -> str:
        return "G"

    @property
    def ability_id(self) -> AbilityId:
        return AbilityId.HARVEST_GATHER


class OrderManager(BotManager):
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

    async def on_step_start(self, step: int) -> None:
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

    def move(self, unit: Unit | Units, target: Point2 | Unit, *,
             queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, MoveOrder, target, queue=queue, force=force)

    def attack(self, unit: Unit | Units, target: Point2 | Unit, *,
               queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, AttackOrder, target, queue=queue, force=force)

    def ability(self, unit: Unit | Units, ability: AbilityId, target: Optional[Point2 | Unit] = None, *,
                queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, AbilityOrder, target, ability, queue=queue, force=force)

    def gather(self, unit: Unit | Units, target: Unit, *,
               queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, GatherOrder, target, queue=queue, force=force)

    def return_resource(self, unit: Unit | Units, *,
                        queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, ReturnResourceOrder, queue=queue, force=force)

    def build(self, unit: Unit | Units, utype: UnitTypeId, position: Point2 | Unit, *,
              queue: bool = False, force: bool = False) -> bool:
        return self._order(unit, BuildOrder, position, utype, queue=queue, force=force)

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
        orders = unit.orders
        if not orders:
            return True
        current_order = orders[-1] if queue else orders[0]
        return not order.matches(current_order)

    def _order(self, unit: Unit | Units, order_cls: type[Order],
               *order_args: Unit | Point2 | UnitTypeId | AbilityId | UpgradeId,
               queue: bool, force: bool) -> bool:
        if isinstance(unit, Units):
            return all(self._order(u, order_cls, *order_args, queue=queue, force=force) for u in unit)
        if not self._check_unit(unit, queue=queue):
            return False
        order = order_cls(*order_args)
        if force or self._is_new_order(unit, order, queue=queue):
            order.issue(unit, queue=queue)
        if queue and self.has_order(unit):
            self.orders[unit.tag].append(order)
        else:
            self.orders[unit.tag] = [order]
        return True
