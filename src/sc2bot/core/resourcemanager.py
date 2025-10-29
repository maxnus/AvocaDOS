from typing import Optional, TYPE_CHECKING

from sc2.game_data import Cost
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.manager import Manager

if TYPE_CHECKING:
    from sc2bot.core.commander import Commander


class ResourceManager(Manager):
    total_minerals: int
    total_vespene: int
    spent_minerals: int
    spent_vespene: int
    reserved_minerals: int
    reserved_vespene: int

    def __init__(self, commander: 'Commander', *, minerals: int = 0, vespene: int = 0) -> None:
        super().__init__(commander)
        self.reset(minerals, vespene)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.minerals}, {self.vespene})"

    def reset(self, minerals: int, vespene: int) -> None:
        self.total_minerals = minerals
        self.total_vespene = vespene
        self.spent_minerals = 0
        self.spent_vespene = 0
        self.reserved_minerals = 0
        self.reserved_vespene = 0

    @property
    def minerals(self) -> int:
        return self.total_minerals - self.spent_minerals - self.reserved_minerals

    @property
    def vespene(self) -> int:
        return self.total_vespene - self.spent_vespene - self.reserved_vespene

    def calculate_cost(self, item: UnitTypeId | UpgradeId | AbilityId) -> Cost:
        return self.bot.calculate_cost(item)

    def can_afford(self, item: UnitTypeId | UpgradeId | AbilityId | Cost) -> bool:
        if isinstance(item, Cost):
            cost = item
        else:
            cost = self.calculate_cost(item)
        return max(self.minerals, 0) >= cost.minerals and max(self.vespene, 0) >= cost.vespene

    def can_afford_in(self, item: UnitTypeId | UpgradeId | AbilityId | Cost, *,
                      excluded_workers: Optional[Unit | Units] = None) -> float:
        if isinstance(item, Cost):
            cost = item
        else:
            cost = self.calculate_cost(item)
        if self.minerals >= cost.minerals and self.vespene >= cost.vespene:
            return 0
        mineral_rate, vespene_rate = self.bot.estimate_resource_collection_rates(excluded_workers=excluded_workers)
        time = 0
        if cost.minerals > 0:
            if mineral_rate == 0:
                return float('inf')
            time = max((cost.minerals - self.minerals) / mineral_rate, time)
        if cost.vespene > 0:
            if vespene_rate == 0:
                return float('inf')
            time = max((cost.vespene - self.vespene) / vespene_rate, time)
        return time

    def spend(self, item: UnitTypeId | UpgradeId | AbilityId | Cost) -> bool:
        cost = self.calculate_cost(item)
        if self.can_afford(cost):
            self.spent_minerals += cost.minerals
            self.spent_vespene += cost.vespene
            return True
        else:
            return False

    def reserve(self, item: UnitTypeId | UpgradeId | AbilityId | Cost) -> None:
        cost = self.calculate_cost(item)
        self.reserved_minerals += cost.minerals
        self.reserved_vespene += cost.vespene

