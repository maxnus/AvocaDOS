import sys

from sc2 import maps
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty

from sc2bot.bots.segfault0x import SegFault0x


if __name__ == "__main__":
    sc2map = maps.get("AcropolisLE")
    bot = SegFault0x('SegFault0x')
    players = [Bot(Race.Terran, bot), Computer(Race.Protoss, Difficulty.VeryHard)]

    run_game(sc2map, players=players, realtime='--realtime' in sys.argv)
