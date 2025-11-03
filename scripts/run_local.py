import sys

from sc2.data import Race

from avocados import create_avocados
from game_runner import GameRunner


if __name__ == "__main__":
    runner = GameRunner(
        bot=create_avocados(log_level='DEBUG', debug=True),
        opponent=Race.Terran,
        realtime='--realtime' in sys.argv,
        map_='PylonAIE_v4'
    )
    runner.run()
