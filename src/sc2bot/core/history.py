from collections import deque

from sc2.bot_ai import BotAI
from sc2.game_data import Cost


class History:
    bot: BotAI
    minerals: deque[int]
    vespene: deque[int]

    def __init__(self, bot: BotAI, *, maxlen: int = 100) -> None:
        self.bot = bot
        self.minerals = deque(maxlen=maxlen)
        self.vespene = deque(maxlen=maxlen)

    def on_step(self, frame: int) -> None:
        self.minerals.append(self.bot.minerals)
        self.vespene.append(self.bot.vespene)

    def get_mineral_rate(self, frames: int = 10) -> float:
        minerals = list(self.minerals)[-frames:]
        return sum(minerals) / len(minerals)

    def get_vespene_rate(self, frames: int = 10) -> float:
        vespene = list(self.vespene)[-frames:]
        return sum(vespene) / len(vespene)

    def time_for_cost(self, cost: Cost) -> float:
        if self.bot.minerals >= cost.minerals and self.bot.vespene >= cost.vespene:
            return 0

        time = 0
        if cost.minerals > 0:
            rate = self.get_mineral_rate()
            if rate == 0:
                return float('inf')
            time = max((cost.minerals - self.bot.minerals) / rate, time)
        if cost.vespene > 0:
            rate = self.get_vespene_rate()
            if rate == 0:
                return float('inf')
            time = max((cost.vespene - self.bot.vespene) / rate, time)
        return time
