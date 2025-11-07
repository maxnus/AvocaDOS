import pytest
from sc2 import maps
from sc2.data import Race, Difficulty, Result
from sc2.main import run_game
from sc2.player import Computer

from avocados import create_avocados


AIE_S2_2025_MAPS = [
    'MagannathaAIE_v2',
    'UltraloveAIE_v2',
    'LeyLinesAIE_v3',
    'TorchesAIE_v4',
    'PylonAIE_v4',
    'PersephoneAIE_v4',
]


@pytest.mark.parametrize('map_name', AIE_S2_2025_MAPS)
def test_map(map_name):
    sc2map = maps.get(map_name)
    bot = create_avocados(leave_at=1)
    players = [bot, Computer(Race.Random, Difficulty.VeryHard)]
    result = run_game(sc2map, players=players)
    assert result == Result.Defeat
