from abc import ABC
from typing import TYPE_CHECKING

from loguru._logger import Logger

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase
    from sc2bot.core.commander import Commander


class System(ABC):
    commander: 'Commander'

    def __init__(self, commander: 'Commander') -> None:
        self.commander = commander

    def __repr__(self) -> str:
        return self.__class__.__name__

    @property
    def bot(self) -> 'BotBase':
        return self.commander.bot

    @property
    def logger(self) -> Logger:
        return self.commander.logger
