import asyncio
import random
from collections import defaultdict
from enum import Enum
from time import perf_counter
from typing import Optional

from sc2.bot_ai import BotAI
from sc2.constants import CREATION_ABILITY_FIX
from sc2.game_data import Cost
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.avocados import AvocaDOS
from avocados.core.unitutil import UnitCost


class BotApi(BotAI):
    bot: AvocaDOS
    game_step: int
    slowdown: float
    # Tag memory
    dead_tags: set[int]
    alive_tags: set[int]
    damage_received: dict[int, float]

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
        #
        self.alive_tags = set() # Initialized correctly in on_start
        self.dead_tags = set()
        self.damage_received = defaultdict(float)

    # --- Callbacks

    async def on_start(self) -> None:
        self.client.game_step = self.game_step
        self.alive_tags = self.all_units.tags
        await self.bot.on_start()

    async def on_step(self, step: int):
        frame_start = perf_counter()
        # Update tag memory
        self.alive_tags.update(self.all_units.tags)
        self.dead_tags.update(self.state.dead_units)
        self.alive_tags.difference_update(self.dead_tags)
        await self.bot.on_step(step)
        self.damage_received.clear()
        if self.slowdown:
            sleep = self.slowdown / 1000 - (perf_counter() - frame_start)
            if sleep > 0:
                await asyncio.sleep(sleep)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        self.damage_received[unit.tag] += amount_damage_taken
        await self.bot.on_unit_took_damage(unit, amount_damage_taken)

    async def on_unit_created(self, unit: Unit) -> None:
        # if unit.tag in self.dead_tags:
        #     raise ValueError(f"internal error: unit tag {unit.tag} already marked as dead")
        # self.alive_tags.add(unit.tag)
        await self.bot.on_unit_created(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        # if unit.tag in self.dead_tags:
        #     raise ValueError(f"internal error: unit tag {unit.tag} already marked as dead")
        # self.alive_tags.add(unit.tag)
        await self.bot.on_building_construction_started(unit)

    async def on_building_construction_finished(self, unit: Unit) -> None:
        await self.bot.on_building_construction_finished(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        # self.alive_tags.remove(unit_tag)
        # self.dead_tags.add(unit_tag)
        await self.bot.on_unit_destroyed(unit_tag)

    # --- Extra utility

    def get_resource_collection_rates(self) -> tuple[float, float]:
        if self.state.game_loop < 100:
            # The properties below return 0 for first 100 steps
            return 10.0, 0.0
        mineral_rate = self.state.score.collection_rate_minerals / 60
        vespene_rate = self.state.score.collection_rate_vespene / 60
        return mineral_rate, vespene_rate

    def get_unit_velocity_vector(self, unit: Unit | int) -> Optional[Point2]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        unit_prev = self._all_units_previous_map.get(tag)
        if unit_prev is None:
            return None
        unit_now = unit if isinstance(unit, Unit) else self.all_units.find_by_tag(tag)
        if unit_now is None:
            return None
        delta = unit_now.position - unit_prev.position
        return delta / 22.4

    def get_creation_ability(self, utype: UnitTypeId) -> AbilityId:
        try:
            return self.game_data.units[utype.value].creation_ability.exact_id
        except AttributeError:
            return CREATION_ABILITY_FIX.get(utype.value, 0)

    # TODO: pending at location
    # def get_pending(self, utype: UnitTypeId) -> list[float]:
    #     # replicate: self.bot.already_pending(utype)
    #
    #     # tuple[Counter[AbilityId], dict[AbilityId, float]]
    #     abilities_amount: Counter[AbilityId] = Counter()
    #     build_progress: dict[AbilityId, list[float]] = defaultdict(list)
    #     unit: Unit
    #     for unit in self.units + self.structures:
    #         for order in unit.orders:
    #             abilities_amount[order.ability.exact_id] += 1
    #         if not unit.is_ready and (self.bot.race != Race.Terran or not unit.is_structure):
    #             # If an SCV is constructing a building, already_pending would count this structure twice
    #             # (once from the SCV order, and once from "not structure.is_ready")
    #             creation_ability = CREATION_ABILITY_FIX.get(
    #                 unit.type_id, self.bot.game_data.units[unit.type_id.value].creation_ability.exact_id)
    #             abilities_amount[creation_ability] += 2 if unit.type_id == UnitTypeId.ARCHON else 1
    #             build_progress[creation_ability].append(unit.build_progress)
    #
    #     return abilities_amount, max_build_progress

    def get_unit_attributes(self, utype: UnitTypeId) -> list[Enum]:
        return self.game_data.units[utype.value].attributes

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
