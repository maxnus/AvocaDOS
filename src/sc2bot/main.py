from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.maps import Map
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty

from sc2bot.bots.amovebot import AMoveBot
from sc2bot.bots.segfault0x import SegFault0x
from sc2bot.core.bot import BotBase


class GameRunner:
    map: Map
    bot: Bot
    opponent: Bot | Computer
    realtime: bool

    def __init__(self,
                 map_: Map | str,
                 bot: Bot,
                 opponent: Bot | Computer,
                 *,
                 realtime: bool = False):
        if isinstance(map_, str):
            map_ = maps.get(map_)
        self.map = map_
        self.bot = bot
        self.opponent = opponent
        self.realtime = realtime

    def run(self):
        players = [self.bot, self.opponent]
        run_game(self.map, players=players, realtime=self.realtime)


if __name__ == "__main__":
    # map_name = "AcropolisLE"
    map_name = '144-66'
    runner = GameRunner(
        map_name,
        bot=Bot(Race.Terran, BotBase()),
        #opponent=Bot(Race.Protoss, AMoveBot())
        opponent = Computer(Race.Protoss, Difficulty.Hard),
    )
    runner.run()
