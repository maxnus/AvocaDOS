from enum import StrEnum
from typing import TYPE_CHECKING

from avocados.core.manager import BotManager
from avocados.core.constants import TOWNHALL_TYPE_IDS
from avocados.core.objective import AttackObjective, DefenseObjective

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class StrategyState(StrEnum):
    ATTACK = "Attack"
    DEFEND = "Defend"


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
                if enemy_structures := self.api.enemy_structures:
                    enemy_townhalls = enemy_structures.of_type(TOWNHALL_TYPE_IDS)
                    target = (enemy_townhalls or enemy_structures).closest_to(self.bot.army.center).position
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
