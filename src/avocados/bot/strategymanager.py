import math
from typing import TYPE_CHECKING

import numpy

from avocados.core.timeseries import Timeseries
from avocados.core.util import two_point_lerp
from avocados.core.manager import BotManager
from avocados.core.constants import TOWNHALL_TYPE_IDS, PRODUCTION_BUILDING_TYPE_IDS
from avocados.bot.objective import AttackObjective, DefenseObjective
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

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.aggression = 0.7
        self.minimum_attack_strength = 5.0
        self.worker_priority = 0.4
        self.supply_priority = 0.6
        self.bonus_workers = 3
        self.absolute_bonus_supply = 1
        self.relative_bonus_supply = 0.05

    async def on_start(self) -> None:
        self.objectives.set_worker_objective(self.expand.get_required_workers() + self.bonus_workers,
                                             priority=self.worker_priority)
        self.objectives.set_supply_objective(1, priority=self.supply_priority)

    async def on_step(self, step: int) -> None:
        if self.aggression >= 0.5:
            if (len(self.objectives.objectives_of_type(AttackObjective)) == 0
                    and self.combat.get_strength(self.bot.army) >= self.minimum_attack_strength):
                enemy_structures = self.api.enemy_structures
                late_game_score = self.get_late_game_score()
                self.logger.info("Late game score: {:.2%}", late_game_score)
                if late_game_score <= 0.3:
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
                self.objectives.add_attack_objective(area, duration=5, priority=self.aggression,
                                                     minimum_size=3)
        else:
            if len(self.objectives.objectives_of_type(DefenseObjective)) == 0:
                self.objectives.add_defense_objective(Circle(self.map.base.region_center, 16))

        self.objectives.worker_objective.number = self.get_worker_target()
        self.objectives.supply_objective.number = self.get_supply_target()

    def get_worker_target(self) -> int:
        return self.expand.get_required_workers() + self.bonus_workers

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

    def get_late_game_score(self) -> float:
        """0: game just started, 1: late game"""
        # TODO
        time_score = two_point_lerp(self.time, 0, 15)
        supply_score = two_point_lerp(self.api.supply_used, 12, 200)
        return (time_score + supply_score) / 2

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
