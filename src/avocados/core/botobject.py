from abc import ABC
from typing import TYPE_CHECKING, Optional, Any

from loguru._logger import Logger
from sc2.game_state import GameState

from avocados.core.apiextensions import ApiExtensions
from avocados.geometry.util import unique_id

if TYPE_CHECKING:
    from avocados.bot.buildingmanager import BuildingManager
    from avocados.core.logmanager import LogManager
    from avocados.core.botapi import BotApi
    from avocados.bot.avocados import AvocaDOS
    from avocados.mapdata import MapManager
    from avocados.debug.debugmanager import DebugManager
    from avocados.bot.historymanager import HistoryManager
    from avocados.bot.intelmanager import IntelManager
    from avocados.bot.ordermanager import OrderManager
    from avocados.bot.expansionmanager import ExpansionManager
    from avocados.bot.resourcemanager import ResourceManager
    from avocados.bot.objectivemanager import ObjectiveManager
    from avocados.bot.taunts import TauntManager
    from avocados.combat.squadmanager import SquadManager
    from avocados.combat.combatmanager import CombatManager


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
    def ext(self) -> ApiExtensions:
        return self.bot.ext

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
    def building(self) -> 'BuildingManager':
        return self.bot.building

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
    def expand(self) -> 'ExpansionManager':
        return self.bot.expand

    @property
    def squads(self) -> 'SquadManager':
        return self.bot.squads

    @property
    def combat(self) -> 'CombatManager':
        return self.bot.combat

    @property
    def taunt(self) -> 'TauntManager':
        return self.bot.taunt
