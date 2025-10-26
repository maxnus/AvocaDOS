from typing import Optional, TYPE_CHECKING

from sc2.game_data import Cost
from sc2.unit import Unit

from sc2bot.core.system import System

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


class History(System):
    resources: list[tuple[int, int]]
    units_last_seen: dict[int, tuple[int, Unit]]
    #enemy_units: dict[int, tuple[int, Unit]]
    max_length: int

    def __init__(self, bot: 'BotBase', *, max_length: int = 1000) -> None:
        super().__init__(bot)
        self.resources = []
        self.max_length = max_length
        self.units_last_seen = {}
        #self.enemy_units = {}

    async def on_step(self, iteration: int) -> None:
        # Resources
        self.resources.append((self.bot.minerals, self.bot.vespene))
        if len(self.resources) > self.max_length:
            self.resources.pop(0)

        # Own
        for unit in self.bot.units:
            self.units_last_seen[unit.tag] = (self.bot.state.game_loop, unit)

        # Enemies
        for unit in self.bot.enemy_units:
            prev_entry = self.units_last_seen.get(unit.tag)
            self.units_last_seen[unit.tag] = (self.bot.state.game_loop, unit)
            if prev_entry is not None:
                assert prev_entry[0] < self.bot.state.game_loop
                change = unit.health + unit.shield - prev_entry[1].health - prev_entry[1].shield
                if change < 0:
                    await self.bot.on_unit_took_damage(unit, -change)

    def get_last_seen(self, unit: int | Unit) -> Optional[Unit]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        last_seen = self.units_last_seen.get(tag)
        return last_seen[1] if last_seen is not None else None

    def get_resource_rates(self, steps: int = 20) -> tuple[float, float]:
        """Per ingame second (22.4 frames)"""
        if len(self.resources) < steps + 1:
            return 0, 0
        factor = 22.4 / (steps * self.bot.client.game_step)
        mineral_rate = factor * (self.resources[-1][0] - self.resources[-steps - 1][0])
        vespene_rate = factor * (self.resources[-1][1] - self.resources[-steps - 1][1])
        return mineral_rate, vespene_rate

    def time_for_cost(self, cost: Cost) -> float:
        if self.bot.minerals >= cost.minerals and self.bot.vespene >= cost.vespene:
            return 0
        mineral_rate, vespene_rate = self.get_resource_rates()
        time = 0
        if cost.minerals > 0:
            if mineral_rate == 0:
                return float('inf')
            time = max((cost.minerals - self.bot.minerals) / mineral_rate, time)
        if cost.vespene > 0:
            if vespene_rate == 0:
                return float('inf')
            time = max((cost.vespene - self.bot.vespene) / vespene_rate, time)
        return time
