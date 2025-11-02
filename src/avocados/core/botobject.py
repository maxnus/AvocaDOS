from abc import ABC
from typing import TYPE_CHECKING, Optional, Any

from loguru._logger import Logger
from sc2.game_state import GameState

from avocados.core.geomutil import unique_id

if TYPE_CHECKING:
    from avocados.core.botapi import BotApi
    from avocados.core.avocados import AvocaDOS
    from avocados.mapdata import MapManager
    from avocados.debug.debugmanager import DebugManager
    from avocados.core.historymanager import HistoryManager
    from avocados.core.orders import OrderManager
    from avocados.core.miningmanager import MiningManager
    from avocados.core.resourcemanager import ResourceManager
    from avocados.core.objectivemanager import ObjectiveManager
    from avocados.micro.squadmanager import SquadManager
    from avocados.micro.combat import CombatManager


class BotObject(ABC):
    id: int
    bot: 'AvocaDOS'
    cache: dict[str, Any]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__()
        self.id = unique_id()
        self.bot = bot
        self.cache: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id})"

    @property
    def api(self) -> 'BotApi':
        return self.bot.api

    @property
    def state(self) -> GameState:
        return self.api.state

    @property
    def time(self) -> float:
        return self.bot.time

    @property
    def logger(self) -> Logger:
        return self.bot.logger.bind(prefix=type(self).__name__)

    # --- Other Manager

    @property
    def map(self) -> 'MapManager':
        return self.bot.map

    @property
    def debug(self) -> Optional['DebugManager']:
        return self.bot.debug

    @property
    def history(self) -> 'HistoryManager':
        return self.bot.history

    @property
    def order(self) -> 'OrderManager':
        return self.bot.order

    @property
    def resources(self) -> 'ResourceManager':
        return self.bot.resources

    @property
    def objectives(self) -> 'ObjectiveManager':
        return self.bot.objectives

    @property
    def mining(self) -> 'MiningManager':
        return self.bot.mining

    @property
    def squads(self) -> 'SquadManager':
        return self.bot.squads

    @property
    def combat(self) -> 'CombatManager':
        return self.bot.combat

    # --- Callbacks

    async def on_start(self) -> None:
        pass

    async def on_step(self, step: int) -> None:
        pass
