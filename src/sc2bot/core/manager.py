from abc import ABC
from typing import TYPE_CHECKING

from loguru._logger import Logger


if TYPE_CHECKING:
    from sc2bot.core.botapi import BotApi
    from sc2bot.core.avocados import AvocaDOS
    from sc2bot.mapdata import MapManager
    from sc2bot.debug.debugmanager import DebugManager
    from sc2bot.core.historymanager import HistoryManager
    from sc2bot.core.orders import OrderManager


class Manager(ABC):
    bot: 'AvocaDOS'

    def __init__(self, bot: 'AvocaDOS') -> None:
        self.bot = bot

    def __repr__(self) -> str:
        return self.__class__.__name__

    @property
    def api(self) -> 'BotApi':
        return self.bot.api

    @property
    def logger(self) -> Logger:
        return self.bot.logger.bind(prefix=type(self).__name__)

    # --- Other Manager

    @property
    def map(self) -> 'MapManager':
        return self.bot.map

    @property
    def debug(self) -> 'DebugManager':
        return self.bot.debug

    @property
    def history(self) -> 'HistoryManager':
        return self.bot.history

    @property
    def order(self) -> 'OrderManager':
        return self.bot.order
