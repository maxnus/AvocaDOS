import random
from pathlib import Path
from typing import Optional

from sc2 import maps
from sc2.data import Race, Difficulty
from sc2.main import run_game
from sc2.maps import Map
from sc2.player import Bot, Computer, BotProcess


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
            opponent = Computer(opponent, Difficulty.CheatInsane)
        elif isinstance(opponent, Difficulty):
            opponent = Computer(Race.Random, opponent)
        self.opponent = opponent
        self.realtime = realtime

    def run(self):
        players = [self.bot, self.opponent]
        run_game(self.map, players=players, realtime=self.realtime)
