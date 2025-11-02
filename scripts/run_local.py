import random
import sys
from pathlib import Path
from typing import Optional

from sc2 import maps
from sc2.data import Race, Difficulty
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.maps import Map
from sc2.player import Bot, Computer, BotProcess

from avocados import create_avocados


DEFAULT_MAP_FOLDER = Path(__file__).parents[1] / 'sc2maps/AIE/2025S2Maps'


def get_random_map(folder: Path = DEFAULT_MAP_FOLDER) -> str:
    maps = [f.stem for f in folder.glob('*.SC2Map')]
    map_name = random.choice(maps)
    return map_name


class GameRunner:
    map: Map
    bot: Bot
    opponent: Bot | BotProcess | Computer
    realtime: bool

    def __init__(self,
                 bot: Bot,
                 opponent: Bot | BotProcess | Computer | Race | Difficulty = Race.Random,
                 map_: Optional[Map | str] = None,
                 *,
                 realtime: bool = False) -> None:
        if map_ is None:
            map_ = get_random_map()
        if isinstance(map_, str):
            map_ = maps.get(map_)
        self.map = map_
        self.bot = bot
        if isinstance(opponent, Race):
            opponent = Computer(opponent, Difficulty.VeryHard)
        elif isinstance(opponent, Difficulty):
            opponent = Computer(Race.Random, opponent)
        self.opponent = opponent
        self.realtime = realtime

    def run(self):
        players = [self.bot, self.opponent]
        run_game(self.map, players=players, realtime=self.realtime)


def micro() -> GameRunner:
    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZEALOT: 4})
    micro_scenario = {UnitTypeId.MARINE: 8}
    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4})
    #micro_scenario = {UnitTypeId.REAPER: 8}
    #micro_scenario = {UnitTypeId.REAPER: 1}
    #micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.MARINE: 12}
    #micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4}
    runner = GameRunner(
        bot=create_avocados(micro_scenario=micro_scenario),
        map_='micro-training-4x4',
    )
    return runner


def macro() -> GameRunner:
    runner = GameRunner(
        bot=create_avocados(build='mass_marine', log_level='DEBUG'),
        #opponent=create_avocados(build='mass_marine'),
        realtime='--realtime' in sys.argv,
    )
    return runner


if __name__ == "__main__":
    #runner = micro()
    runner = macro()
    runner.run()
