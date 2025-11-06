from abc import ABC
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Any

from loguru._logger import Logger
from sc2.game_state import GameState

from avocados.core.geomutil import unique_id
from avocados.core.timings import Timings

if TYPE_CHECKING:
    from avocados.core.logmanager import LogManager
    from avocados.core.botapi import BotApi
    from avocados.core.avocados import AvocaDOS
    from avocados.mapdata import MapManager
    from avocados.debug.debugmanager import DebugManager
    from avocados.core.historymanager import HistoryManager
    from avocados.core.intelmanager import IntelManager
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

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BotObject):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def api(self) -> 'BotApi':
        return self.bot.api

    @property
    def state(self) -> GameState:
        return self.bot.state

    @property
    def step(self) -> float:
        return self.bot.step

    @property
    def time(self) -> float:
        return self.bot.time

    @property
    def logger(self) -> Logger:
        return self.bot.logger.bind(prefix=type(self).__name__)

    # --- Other Manager

    @property
    def log(self) -> 'LogManager':
        return self.bot.log

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
    def intel(self) -> 'IntelManager':
        return self.bot.intel

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


class BotManager(BotObject, ABC):
    timings: dict[str, Timings]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.timings = defaultdict(Timings)
        self.logger.debug("Initializing {}", type(self).__name__)

    # --- Callbacks

    async def on_start(self) -> None:
        pass

    async def on_step(self, step: int) -> None:
        pass
