
from sc2.bot_ai import BotAI
from sc2.game_data import Cost


class History:
    bot: BotAI
    resources: list[tuple[int, int]]
    max_length: int

    def __init__(self, bot: BotAI, *, max_length: int = 1000) -> None:
        self.bot = bot
        self.resources = []
        self.max_length = max_length

    def on_step(self, frame: int) -> None:
        self.resources.append((self.bot.minerals, self.bot.vespene))
        if len(self.resources) > self.max_length:
            self.resources.pop(0)

    def get_resource_rates(self, frames: int = 20) -> tuple[float, float]:
        if len(self.resources) < frames + 1:
            return 0, 0
        mineral_rate = (self.resources[-1][0] - self.resources[-frames-1][0]) / frames
        vespene_rate = (self.resources[-1][1] - self.resources[-frames-1][1]) / frames
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
