from sc2.data import Race
from sc2.player import Bot

from avocados.__about__ import __version__
from avocados.core.api import Api


api = Api()


def create_avocados(**kwargs) -> Bot:
    from avocados.bot.avocados import AvocaDOS
    AvocaDOS(**kwargs)
    return Bot(Race.Terran, api, name='AvocaDOS')
