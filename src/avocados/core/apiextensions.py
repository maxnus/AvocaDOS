import math
from collections.abc import Callable, Iterable
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sc2.constants import (PROTOSS_TECH_REQUIREMENT, TERRAN_TECH_REQUIREMENT, ZERG_TECH_REQUIREMENT,
                           EQUIVALENTS_FOR_TECH_PROGRESS, CREATION_ABILITY_FIX, abilityid_to_unittypeid)
from sc2.data import Race
from sc2.game_data import Cost, UnitTypeData
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.constants import (TRAINERS, TERRANBUILD_TO_STRUCTURE, MINOR_STRUCTURES, UNIT_CREATION_ABILITIES,
                                     UPGRADE_ABILITIES)
from avocados.core.ordermanager import OrderManager
from avocados.core.unitutil import UnitCost
from avocados.geometry.util import dot

if TYPE_CHECKING:
    from avocados.core.api import Api


class ApiExtensions:
    order: OrderManager
    worker_utype: UnitTypeId
    townhall_utype: UnitTypeId
    supply_utype: UnitTypeId

    def __init__(self, api: 'Api') -> None:
        super().__init__()
        self.api = api
        self.order = OrderManager()

    async def on_start(self) -> None:

        # Fill UNIT_CREATION_ABILITIES
        for utype in list(UnitTypeId):
            unit_data = self.api.game_data.units.get(utype.value)
            if unit_data is None:
                continue
            ability_data = unit_data.creation_ability
            if ability_data is None:
                continue
            if utype not in UNIT_CREATION_ABILITIES:
                UNIT_CREATION_ABILITIES[utype] = ability_data.exact_id

        # Fill UPGRADE_ABILITIES
        for upgrade in list(UpgradeId):
            upgrade_data = self.api.game_data.upgrades.get(upgrade.value)
            if upgrade_data is None:
                continue
            ability_data = upgrade_data.research_ability
            if ability_data is None:
                continue
            UPGRADE_ABILITIES[upgrade] = ability_data.exact_id

        self.worker_utype, self.townhall_utype, self.supply_utype = {
            Race.Terran: (UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, UnitTypeId.SUPPLYDEPOT),
            Race.Zerg: (UnitTypeId.DRONE, UnitTypeId.HATCHERY, UnitTypeId.OVERLORD),
            Race.Protoss: (UnitTypeId.PROBE, UnitTypeId.NEXUS, UnitTypeId.PYLON),
        }[self.api.race]

    # ---

    @property
    def enemy_major_structures(self) -> Units:
        return self.api.enemy_structures.exclude_type(MINOR_STRUCTURES)

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
        return UNIT_CREATION_ABILITIES[utype]

    def get_upgrade_ability(self, upgrade: UpgradeId) -> AbilityId:
        return UPGRADE_ABILITIES[upgrade]

    def creation_ability_to_unit_type(self, ability: AbilityId) -> Optional[UnitTypeId]:
        if (type_id := abilityid_to_unittypeid.get(ability)) is not None:
            return type_id
        return TERRANBUILD_TO_STRUCTURE.get(ability)

    def get_trainer_type(self, utype: UnitTypeId) -> Optional[UnitTypeId | tuple[UnitTypeId, ...]]:
        return TRAINERS.get(utype)

    def get_supply_cost(self, utype: UnitTypeId) -> float:
        return self.api.game_data.units[utype.value]._proto.food_required

    def get_net_supply(self, utype: UnitTypeId) -> float:
        proto = self.api.game_data.units[utype.value]._proto
        return proto.food_provided - proto.food_required

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

        return self.get_cost(structure.type_id).time * (1 - structure.build_progress) / 22.4

    def time_until_tech(self, structure_type: UnitTypeId) -> float:
        requirements = self.get_tech_requirement(structure_type)
        if not requirements:
            return 0
        for req in requirements:
            if self.api.structures(req).ready:
                return 0
        remaining_time = float('inf')
        for req in requirements:
            for structure in self.api.structures(req):
                remaining_time = min(self.get_remaining_construction_time(structure), remaining_time)
        return remaining_time

    #@property_cache_once_per_frame # TODO: cache, state
    def units_in_production(self) -> dict[int, list[tuple[UnitTypeId, float]]]:
        production: dict[int, list[tuple[UnitTypeId, float]]] = {}
        for trainer in (self.api.units + self.api.structures):
            production_size = 2 if trainer.has_reactor else 1
            orders = trainer.orders[:production_size]
            prod = [(unit_type, order.progress) for order in orders
                    if (unit_type := self.creation_ability_to_unit_type(order.ability.exact_id)) is not None]
            if prod:
                production[trainer.tag] = prod
        return production

    def structures_in_production(self, unit_type: Optional[UnitTypeId | Iterable[UnitTypeId]] = None
                                 ) -> list[tuple[Unit, float]]:
        """TODO: only consider those with active SCV"""
        production: list[tuple[Unit, float]] = []
        structures = self.api.structures.not_ready
        if unit_type is not None:
            structures = structures.of_type(unit_type)
        for structure in structures:
            production.append((structure, structure.build_progress))
        return production

    def intercept_unit(self, unit: Unit, target: Unit, *,
                       max_intercept_distance: float = 10.0) -> Point2:
        """TODO: friendly units"""
        d = target.position - unit.position
        dsq = dot(d, d)
        # if dsq > 200:
        #     # Far away, don't try to intercept
        #     return target.position

        v = self.get_unit_velocity_vector(target)
        if v is None:
            #self.logger.debug("No target velocity")
            return target.position
        s = 1.4 * unit.real_speed
        vsq = dot(v, v)
        ssq = s * s
        denominator = vsq - ssq
        if abs(denominator) < 1e-8:
            #self.logger.debug("Linear case")
            # TODO: linear case
            return target.position

        dv = dot(d, v)
        disc = dv*dv - denominator * dsq
        if disc < 0:
            #self.logger.debug("No real solution")
            # no real solution
            return target.position
        sqrt = math.sqrt(disc)
        tau1 = (-dv + sqrt) / denominator
        tau2 = (-dv - sqrt) / denominator
        tau = min(tau1, tau2)
        intercept = target.position + tau * v
        #self.logger.debug("{} intercepting {} at {}", unit.position, target.position, intercept)
        return intercept
