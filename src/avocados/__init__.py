from sc2.data import Race
from sc2.player import Bot

from avocados.__about__ import __version__
from avocados.core.botapi import BotApi


def create_avocados(**kwargs) -> Bot:
    return Bot(Race.Terran, BotApi(**kwargs), name='AvocaDOS')
