from typing import TYPE_CHECKING

from avocados.core.util import two_point_lerp
from avocados.core.manager import BotManager
from avocados.core.constants import TOWNHALL_TYPE_IDS
from avocados.bot.objective import AttackObjective, DefenseObjective

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


# class StrategyState(StrEnum):
#     ATTACK = "Attack"
#     DEFEND = "Defend"


class StrategyManager(BotManager):
    aggression: float
    minimum_attack_strength: float

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.aggression = 0.7
        self.minimum_attack_strength = 6.0

    async def on_step(self, step: int) -> None:
        if self.aggression >= 0.5:
            if (len(self.objectives.objectives_of_type(AttackObjective)) == 0
                    and self.combat.get_strength(self.bot.army) >= self.minimum_attack_strength):
                enemy_structures = self.api.enemy_structures
                late_game_score = self.get_late_game_score()
                self.logger.info("Late game score: {:.2%}", late_game_score)
                if late_game_score <= 0.2:
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
                self.objectives.add_attack_objective(target, duration=5, priority=self.aggression,
                                                     minimum_size=6)
        else:
            if len(self.objectives.objectives_of_type(DefenseObjective)) == 0:
                self.objectives.add_defense_objective(self.map.base.region_center)

    def get_late_game_score(self) -> float:
        """0: game just started, 1: late game"""
        # TODO
        time_score = two_point_lerp(self.time, 0, 20)
        supply_score = two_point_lerp(self.api.supply_used, 12, 200)
        return (time_score + supply_score) / 2
