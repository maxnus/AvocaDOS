import asyncio
import random
from enum import Enum
from time import perf_counter
from typing import Optional

from sc2.bot_ai import BotAI
from sc2.constants import IS_STRUCTURE
from sc2.game_data import Cost
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.avocados import AvocaDOS
from sc2bot.core.util import UnitCost


class BotApi(BotAI):
    bot: AvocaDOS
    game_step: int
    slowdown: float

    def __init__(self, *,
                 seed: int = 0,
                 game_step: int = 1,
                 slowdown: float = 0,
                 **kwargs
                 ) -> None:
        super().__init__()
        random.seed(seed)
        self.bot = AvocaDOS(self, **kwargs)
        self.game_step = game_step
        self.slowdown = slowdown

    # --- Callbacks

    async def on_start(self) -> None:
        self.client.game_step = self.game_step
        await self.bot.on_start()

    async def on_step(self, step: int):
        frame_start = perf_counter()
        await self.bot.on_step(step)
        if self.slowdown:
            sleep = self.slowdown / 1000 - (perf_counter() - frame_start)
            if sleep > 0:
                await asyncio.sleep(sleep)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await self.bot.on_unit_took_damage(unit, amount_damage_taken)

    async def on_unit_created(self, unit: Unit) -> None:
        pass

    async def on_building_construction_started(self, unit: Unit) -> None:
        pass

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        pass

    # --- Extra utility

    def get_attributes(self, utype: UnitTypeId) -> list[Enum]:
        return self.game_data.units[utype.value].attributes

    def is_structure(self, utype: UnitTypeId) -> bool:
        return IS_STRUCTURE in self.get_attributes(utype)

    def get_scv_build_target(self, scv: Unit) -> Optional[Unit]:
        """Return the building unit that this SCV is constructing, or None."""
        if not scv.is_constructing_scv:
            return None
        # Try to match via nearby incomplete structure
        buildings_being_constructed = self.structures.filter(lambda s: s.build_progress < 1)
        if not buildings_being_constructed:
            return None
        target = buildings_being_constructed.closest_to(scv)
        if target and scv.distance_to(target) < 3:
            return target
        return None

    def get_cost(self, utype: UnitTypeId) -> Cost:
        return self.game_data.units[utype.value].cost

    def get_unit_value(self, unit: UnitTypeId | Unit | Units) -> UnitCost:
        """Return 450 for orbital"""
        if isinstance(unit, Unit):
            unit = unit.type_id
        if isinstance(unit, Units):
            return sum((self.get_unit_value(u) for u in unit), start=UnitCost(0, 0, 0))

        cost = self.get_cost(unit)
        supply = self.game_data.units[unit.value]._proto.food_required
        return UnitCost(cost.minerals, cost.vespene, supply)

    def get_remaining_construction_time(self, scv: Unit) -> float:
        if not scv.is_constructing_scv:
            return 0
        building = self.get_scv_build_target(scv)
        if not building:
            return 0
        return self.get_cost(building.type_id).time * (1 - building.build_progress)

    def estimate_resource_collection_rates(self, *,
                                           excluded_workers: Optional[Unit | Units] = None,
                                           worker_mineral_rate: float = 1.0) -> tuple[float, float]:
        # TODO only correctly placed townhalls
        mineral_workers = 0
        for townhall in self.townhalls:
            mineral_workers += len(self.workers_mining_at(townhall, excluded_workers=excluded_workers))
        mineral_rate = max(worker_mineral_rate * mineral_workers, 0)
        return mineral_rate, 0

    def workers_mining_at(self, townhall: Unit, *,
                          excluded_workers: Optional[Unit | Units] = None,
                          radius: float = 10.0) -> Units:
        """Return number of workers currently mining minerals around a specific base."""
        nearby_minerals = self.mineral_field.closer_than(radius, townhall)
        if not nearby_minerals:
            return Units([], self)
        allowed_orders = {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}
        allowed_tags = {0, townhall.tag, *(m.tag for m in nearby_minerals)}
        workers = self.workers.closer_than(radius, townhall)
        if excluded_workers:
            excluded_workers_tags = (excluded_workers.tags if isinstance(excluded_workers, Units)
                                     else {excluded_workers.tag})
            workers = workers.tags_not_in(excluded_workers_tags)
        workers = workers.filter(lambda w: (w.orders and w.orders[0].ability.id in allowed_orders) and w.order_target in allowed_tags)
        return Units(workers, self)

