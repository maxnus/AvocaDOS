import sys

from sc2 import maps
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty

from sc2bot.bots.amovebot import AMoveBot
from sc2bot.bots.segfault0x import SegFault0x
from sc2bot.core.bot import BotBase

if __name__ == "__main__":
    sc2map = maps.get("AcropolisLE")
    players = [
        #Bot(Race.Terran, SegFault0x()),
        Bot(Race.Terran, BotBase()),
        #Computer(Race.Protoss, Difficulty.VeryHard)
        Bot(Race.Protoss, AMoveBot()),
    ]
    run_game(sc2map, players=players, realtime='--realtime' in sys.argv)
