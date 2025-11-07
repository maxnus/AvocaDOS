import sys
from argparse import ArgumentParser

from sc2.data import Race

from avocados import create_avocados
from game_runner import GameRunner


parser = ArgumentParser()
parser.add_argument("--map", default=None)
parser.add_argument("--opponent-race", type=lambda race: getattr(Race, race), default=Race.Random)
parser.add_argument("--realtime", action="store_true", default=False)


if __name__ == "__main__":
    args = parser.parse_known_args()[0]
    runner = GameRunner(
        bot=create_avocados(log_level='DEBUG', debug=True),
        opponent=args.opponent_race,
        realtime=args.realtime,
        map_=args.map,
        ##map_='MagannathaAIE_v2'
        ##map_='UltraloveAIE_v2'
        #map_='LeyLinesAIE_v3'
        ##map_='TorchesAIE_v4'
        ##map_='PylonAIE_v4'
        ##map_='PersephoneAIE_v4'
    )
    runner.run()
