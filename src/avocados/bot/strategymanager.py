import math
from typing import TYPE_CHECKING, ClassVar

import numpy
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId

from avocados.core.timeseries import Timeseries
from avocados.core.util import two_point_lerp, lerp, snap
from avocados.core.manager import BotManager
from avocados.core.constants import TOWNHALL_TYPE_IDS, PRODUCTION_BUILDING_TYPE_IDS, CLOACKABLE_TYPE_IDS
from avocados.bot.objective import AttackObjective, DefenseObjective, UnitObjective, ConstructionObjective
from avocados.geometry import Circle

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class StrategyManager(BotManager):
    aggression: float
    minimum_attack_strength: float
    worker_priority: float
    supply_priority: float
    bonus_workers: int
    absolute_bonus_supply: int
    relative_bonus_supply: float
    expansion_score_threshold: float
    # Targets
    barracks_target: int
    scan_target: int
    # ClassVars
    max_workers: ClassVar[int] = 80

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.aggression = 0.7
        self.minimum_attack_strength = 5.0
        self.worker_priority = 0.4
        self.production_priority = 0.3
        self.supply_priority = 0.6
        self.orbital_priority = 0.65
        self.bonus_workers = 3
        self.absolute_bonus_supply = 1
        self.relative_bonus_supply = 0.05
        self.expansion_score_threshold = 0.5
        # Targets
        self.barracks_target: int = 0
        self.scan_target: int = 0

    async def on_start(self) -> None:
        self.objectives.set_worker_objective(self.expand.get_required_workers() + self.bonus_workers,
                                             priority=self.worker_priority)
        self.objectives.set_supply_objective(1, priority=self.supply_priority)
        self.objectives.set_expansion_objective(1)

    async def on_step(self, step: int) -> None:
        if self.aggression >= 0.5:
            if (len(self.objectives.objectives_of_type(AttackObjective)) == 0
                    and self.combat.get_strength(self.bot.army) >= self.minimum_attack_strength):
                enemy_structures = self.ext.enemy_major_structures
                late_game_score = self.get_late_game_score()
                self.logger.info("Late game score: {:.2%}", late_game_score)
                if late_game_score <= 0.25:
                    enemy_structures = enemy_structures.of_type(TOWNHALL_TYPE_IDS)
                if enemy_structures:
                    target = enemy_structures.closest_to(self.bot.army.center).position
                else:
                    reference_point = self.intel.last_known_enemy_base.center or self.map.center
                    targets = {exp: (time
                                     - 0.1 * exp.center.distance_to(reference_point)
                                     - 0.1 * exp.center.distance_to(self.bot.army.center))
                               for exp, time in self.intel.get_time_since_expansions_last_visible().items()}
                    target = max(targets.keys(), key=targets.get).center
                area = Circle(target, 16.0)

                if self.memory.army_strength.value() >= 2 * self.intel.enemy_army_strength.value():
                    squad_size = 3
                elif self.memory.army_strength.value() >= self.intel.enemy_army_strength.value():
                    squad_size = 5
                else:
                    squad_size = 10
                self.objectives.add_attack_objective(area, duration=5, priority=self.aggression,
                                                     minimum_size=squad_size)
        else:
            if len(self.objectives.objectives_of_type(DefenseObjective)) == 0:
                self.objectives.add_defense_objective(Circle(self.map.base.center, 16))

        self.objectives.worker_objective.number = self.get_worker_target()
        self.objectives.supply_objective.number = self.get_supply_target()
        self.objectives.expansion_objective.number = self.get_expansion_target()

        if ((ccs := self.api.townhalls.of_type(UnitTypeId.COMMANDCENTER).ready)
                   and self.ext.time_until_tech(UnitTypeId.ORBITALCOMMAND) == 0):
            existing_objectives = [obj for obj in self.objectives.objectives_of_type(UnitObjective)
                                   if obj.utype == UnitTypeId.ORBITALCOMMAND]
            number = len(ccs) + len(self.api.townhalls.of_type(UnitTypeId.ORBITALCOMMAND).ready)
            if existing_objectives:
                existing_objectives[0].number = number
            else:
                self.objectives.add_unit_objective(UnitTypeId.ORBITALCOMMAND, number=number,
                                                   priority=self.orbital_priority)

        if step % 16 == 0 and self.ext.time_until_tech(UnitTypeId.BARRACKS) == 0:
            existing_objectives = [obj for obj in self.objectives.objectives_of_type(ConstructionObjective)
                                   if obj.utype == UnitTypeId.BARRACKS]
            if not existing_objectives:
                self.barracks_target = snap(self.get_barracks_target(), self.barracks_target)
                if self.barracks_target > len(self.api.structures(UnitTypeId.BARRACKS)):
                    self.objectives.add_construction_objective(UnitTypeId.BARRACKS, number=self.barracks_target,
                                                               priority=self.production_priority)

        if step % 16 == 0:
            self.scan_target = snap(self.get_scan_target(), self.scan_target)

    def get_worker_target(self) -> int:
        workers = self.expand.get_required_workers() + self.bonus_workers
        for townhall, progress in self.ext.structures_in_production(self.ext.townhall_utype):
            location = min(self.map.expansions, key=lambda exp: townhall.distance_to(exp.center))
            if townhall.distance_to(townhall) < 3:
                workers += 2 * len(location.mineral_fields)
        return min(workers, self.max_workers)

    def get_supply_target(self, *, projection_horizon: float = 30.0) -> int:

        projection_steps = int(projection_horizon * 22.4)
        projected_supply = self.get_projected_supply_curve(steps=projection_steps)
        projected_supply_cap = self.get_projected_supply_cap_curve(steps=projection_steps)

        # if self.step % 200 == 0:
        #     self._proj_supply.append(projected_supply)
        #     self._proj_caps.append(projected_supply_cap)
        #
        # if self.step % 1000 == 0:
        #     plt.figure()
        #     self.memory.supply_cap.plot(color='C0')
        #     self.memory.supply.plot(color='C1')
        #     for idx, curve in enumerate(self._proj_caps):
        #         curve.plot(ls='-.', color='C2', yshift=+0.1 if idx % 2 == 0 else -0.1)
        #     for idx, curve in enumerate(self._proj_supply):
        #         curve.plot(ls=':', color='C3', yshift=+0.1 if idx % 2 == 0 else -0.1)
        #     plt.savefig(f'supply-{self.step}.png')

        supply_unit_value = int(self.ext.get_net_supply(self.ext.supply_utype))
        used_supply = int(self.api.supply_used)
        bonus_supply = self.absolute_bonus_supply + int(round(self.relative_bonus_supply * used_supply))
        max_missing_supply = numpy.max(projected_supply.values - projected_supply_cap.values) + bonus_supply
        max_missing_supply = max(int(math.ceil(max_missing_supply)), 0)
        supply_target = used_supply + supply_unit_value * ((max_missing_supply - 1) // supply_unit_value + 1)
        townhall_supply = int(sum(self.ext.get_net_supply(unit.type_id) for unit in self.api.townhalls.ready))
        supply_target -= townhall_supply
        supply_target = min(supply_target, 200)
        supply_unit_target = (supply_target - 1) // supply_unit_value + 1
        return supply_unit_target

    def get_expansion_target(self) -> int:
        if self.get_expansion_score() >= self.expansion_score_threshold:
            return len(self.expand) + 1
        return len(self.expand)

    def get_barracks_target(self) -> float:
        mineral_rate = self.expand.get_expected_mineral_rate()
        marine_rate = 2.778  # 50 minerals / 18 sec
        return mineral_rate / marine_rate

    def get_scan_target(self) -> float:
        if self.time < 180:
            return 0
        if self.intel.enemy_race in {Race.Terran, Race.Protoss}:
            last_step_cloakable = max(self.intel.enemy_utype_last_spotted.get(utype, -1) for utype in CLOACKABLE_TYPE_IDS)
            if last_step_cloakable == -1 or last_step_cloakable < self.step - 1344:
                return 0
        return max(len(self.api.structures(UnitTypeId.ORBITALCOMMAND).ready), 1)

    # --- Scores

    def get_late_game_score(self) -> float:
        """0: game just started, 1: late game"""
        # TODO
        time_score = two_point_lerp(self.time, 0, 900)   # 900s = 15min
        supply_score = two_point_lerp(self.api.supply_used, 12, 200)
        return (time_score + supply_score) / 2

    def get_expansion_score(self) -> float:
        """0 (don't expand) to 1 (expand now)"""
        # TODO base difference
        #time_score = lerp(self.time, (4, 0), (10, 1))

        minerals = self.expand.get_mineral_fields()
        number_expansions = len(self.expand)
        if number_expansions > 0:
            remaining_minerals_per_expansion = sum(mf.mineral_contents for mf in minerals) / number_expansions
            mineral_content_score = lerp(remaining_minerals_per_expansion, (0, 1), (10800, 0))
        else:
            mineral_content_score = 1.0

        missing_fields = (len(self.api.workers) - 2 * len(minerals) + 1) // 2
        mineral_field_score = lerp(missing_fields, (0, 0), (8, 1))

        minerals_score = lerp(self.resources.minerals, (300, 0), (500, 1))

        return 0.3 * mineral_content_score + 0.3 * mineral_field_score + 0.4 * minerals_score

    def is_opponent_revealed(self) -> bool:
        # TODO cliffs, line of sight blockers?
        max_vision_range = 11.0
        for structure in self.api.enemy_structures:
            for unit in (self.api.units + self.api.structures).closer_than(max_vision_range, structure.position):
                if unit.sight_range <= unit.distance_to(structure):
                    # Found a unit that could be spotting the structure
                    break
            else:
                # No unit can see this, so the opponent must be revealed
                return True
        return False

    def get_projected_supply_curve(self, *, steps: int = 1000) -> Timeseries[float]:
        """TODO: consider expected unit deaths?"""
        values = numpy.full(steps, self.api.supply_used, dtype=float)
        for trainer, production in self.ext.units_in_production().items():
            for utype, progress in production:
                # We assume that we queue the same unit again and again:
                steps_to_build = int(self.ext.get_cost(utype).time)
                start = int(steps_to_build * (1 - progress))
                supply_cost = self.ext.get_supply_cost(utype)
                while start < steps:
                    values[start:] += supply_cost
                    start += steps_to_build
        producing_buildings = TOWNHALL_TYPE_IDS.union(PRODUCTION_BUILDING_TYPE_IDS)
        for structure, progress in self.ext.structures_in_production(producing_buildings):
            # TODO: We assume they will queue a 1 supply unit when the construction finishes
            start = int(self.ext.get_cost(structure.type_id).time * (1 - progress))
            values[start:] += 1
        return Timeseries(values=values, start=self.step, length=steps)

    def get_projected_supply_cap_curve(self, *, steps: int = 1000) -> Timeseries[float]:
        """TODO: consider expected structure deaths?"""
        # TODO consider SCV on route to build location (no!)
        values = numpy.full(steps, self.api.supply_cap, dtype=float)
        for structure, progress in self.ext.structures_in_production():
            supply = self.ext.get_net_supply(structure.type_id)
            if supply != 0:
                steps_left = int(self.ext.get_cost(structure.type_id).time * (1 - progress))
                values[steps_left:] += supply
        return Timeseries(values=values, start=self.step, length=steps)
