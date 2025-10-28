import asyncio
import sys
from typing import Optional

from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.maps import Map
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty

from sc2bot.core.avocados import AvocaDOS


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
                 realtime: bool = False) -> None:
        if isinstance(map_, str):
            map_ = maps.get(map_)
        self.map = map_
        self.bot = bot
        self.opponent = opponent
        self.realtime = realtime

    def run(self):
        players = [self.bot, self.opponent]
        run_game(self.map, players=players, realtime=self.realtime)


def micro():
    # map_name = "AcropolisLE"
    map_name = 'micro-training-4x4'

    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZEALOT: 4})
    #micro_scenario = {UnitTypeId.MARINE: 8}
    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4})
    #micro_scenario = {UnitTypeId.REAPER: 8}
    #micro_scenario = {UnitTypeId.REAPER: 1}
    #micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.MARINE: 12}
    micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4}

    slowdown_time = 0
    #slowdown_time = 1000

    runner = GameRunner(
        map_name,
        bot=Bot(Race.Terran, AvocaDOS(slowdown=slowdown_time, micro_scenario=micro_scenario)),
        #opponent=Bot(Race.Protoss, AMoveBot())
        opponent = Computer(Race.Protoss, Difficulty.Hard),
    )
    runner.run()


def macro():
    runner = GameRunner(
        'AcropolisLE',
        bot=Bot(Race.Terran, AvocaDOS(build='proxyreaper', log_level='DEBUG')),
        #opponent=Computer(Race.Protoss, Difficulty.Hard),
        opponent=Computer(Race.Protoss, Difficulty.Easy),
        realtime='--realtime' in sys.argv,
    )
    runner.run()


if __name__ == "__main__":
    #micro()
    macro()

