from typing import TYPE_CHECKING

from avocados.core.util import two_point_lerp
from avocados.core.manager import BotManager
from avocados.core.constants import TOWNHALL_TYPE_IDS
from avocados.bot.objective import AttackObjective, DefenseObjective
from avocados.geometry import Circle

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


# class StrategyState(StrEnum):
#     ATTACK = "Attack"
#     DEFEND = "Defend"


class StrategyManager(BotManager):
    aggression: float
    minimum_attack_strength: float
    worker_priority: float
    supply_priority: float
    bonus_workers: int
    bonus_supply: int

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.aggression = 0.7
        self.minimum_attack_strength = 5.0
        self.worker_priority = 0.4
        self.supply_priority = 0.6
        self.bonus_workers = 3
        self.bonus_supply = 6

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

    def get_supply_target(self) -> int:
        # TODO: fix other races
        # pending_supply = int(
        #     self.api.already_pending(self.ext.townhall_utype) * 15
        #     + self.api.already_pending(self.ext.supply_utype) * 8
        # )
        # if self.api.supply_left <= self.bonus_supply:
        #     supply_target_total = int(min(self.api.supply_cap + self.bonus_supply, 200))
        # else:
        #     supply_target_total = int(self.api.supply_cap)
        supply_target_total = int(min(self.api.supply_used + self.bonus_supply, 200))
        ccs = len(self.api.townhalls)
        supply_target = supply_target_total - ccs * 15
        supply_unit_target = (supply_target + 7) // 8
        return supply_unit_target

    def get_late_game_score(self) -> float:
        """0: game just started, 1: late game"""
        # TODO
        time_score = two_point_lerp(self.time, 0, 15)
        supply_score = two_point_lerp(self.api.supply_used, 12, 200)
        return (time_score + supply_score) / 2
