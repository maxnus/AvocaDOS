from collections.abc import Callable
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sc2.constants import PROTOSS_TECH_REQUIREMENT, TERRAN_TECH_REQUIREMENT, ZERG_TECH_REQUIREMENT, \
    EQUIVALENTS_FOR_TECH_PROGRESS, CREATION_ABILITY_FIX
from sc2.data import Race
from sc2.game_data import Cost, UnitTypeData
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.unitutil import UnitCost

if TYPE_CHECKING:
    from avocados import BotApi


class ApiExtensions:
    api: 'BotApi'

    def __init__(self, api: 'BotApi') -> None:
        super().__init__()
        self.api = api

    def get_unit_attributes(self, utype: UnitTypeId) -> list[Enum]:
        return self.api.game_data.units[utype.value].attributes

    def get_cost(self, utype: UnitTypeId) -> Cost:
        return self.api.game_data.units[utype.value].cost

    def get_tech_requirement(self, structure_type: UnitTypeId) -> list[UnitTypeId]:
        race_dict = {
            Race.Protoss: PROTOSS_TECH_REQUIREMENT,
            Race.Terran: TERRAN_TECH_REQUIREMENT,
            Race.Zerg: ZERG_TECH_REQUIREMENT,
        }
        requirement = race_dict[self.api.race].get(structure_type)
        if requirement is None:
            return []
        equivalent = EQUIVALENTS_FOR_TECH_PROGRESS.get(requirement, [])
        return [requirement, *equivalent]

    def get_unit_type_data(self, utype: UnitTypeId) -> Optional[UnitTypeData]:
        return self.api.game_data.units.get(utype.value)

    def get_units_with_target(self, target: Unit | Point2, *,
                              condition: Optional[Callable[[Unit], bool]] = None) -> Units:
        target = target.tag if isinstance(target, Unit) else target
        def unit_filter(unit: Unit) -> bool:
            if len(unit.orders) == 0:
                return False
            if unit.orders[0].target != target:
                return False
            return condition is None or condition(unit)

        units = (self.api.units + self.api.structures)
        return units.filter(unit_filter)

    def get_resource_collection_rates(self) -> tuple[float, float]:
        if self.api.state.game_loop < 100:
            # The properties below return 0 for first 100 steps
            return 10.0, 0.0
        mineral_rate = self.api.state.score.collection_rate_minerals / 60
        vespene_rate = self.api.state.score.collection_rate_vespene / 60
        return mineral_rate, vespene_rate

    def get_unit_velocity_vector(self, unit: Unit | int) -> Optional[Point2]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        unit_prev = self.api._all_units_previous_map.get(tag)
        if unit_prev is None:
            return None
        unit_now = unit if isinstance(unit, Unit) else self.api.all_units.find_by_tag(tag)
        if unit_now is None:
            return None
        delta = unit_now.position - unit_prev.position
        return delta / 22.4

    def get_creation_ability(self, utype: UnitTypeId) -> AbilityId:
        try:
            return self.api.game_data.units[utype.value].creation_ability.exact_id
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


    def get_scv_build_target(self, scv: Unit) -> Optional[Unit]:
        """Return the building unit that this SCV is constructing, or None."""
        if not scv.is_constructing_scv:
            return None
        # Try to match via nearby incomplete structure
        buildings_being_constructed = self.api.structures.filter(lambda s: s.build_progress < 1)
        if not buildings_being_constructed:
            return None
        target = buildings_being_constructed.closest_to(scv)
        if target and scv.distance_to(target) < 3:
            return target
        return None

    def get_unit_value(self, unit: UnitTypeId | Unit | Units) -> UnitCost:
        """Return 450 for orbital"""
        if isinstance(unit, Unit):
            unit = unit.type_id
        if isinstance(unit, Units):
            return sum((self.get_unit_value(u) for u in unit), start=UnitCost(0, 0, 0))

        cost = self.get_cost(unit)
        supply = self.api.game_data.units[unit.value]._proto.food_required
        return UnitCost(cost.minerals, cost.vespene, supply)

    def get_remaining_construction_time(self, scv_or_structure: Unit) -> float:
        if scv_or_structure.type_id == UnitTypeId.SCV:
            structure = self.get_scv_build_target(scv_or_structure)
            if not structure:
                return 0.0
        elif scv_or_structure.is_structure:
            structure = scv_or_structure
        else:
            raise ValueError(f"not an SCV or structure: {scv_or_structure}")

        return self.get_cost(structure.type_id).time * (1 - structure.build_progress) * 22.4
