from abc import ABC
from typing import TYPE_CHECKING

from loguru._logger import Logger
from sc2.unit import Unit

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class System(ABC):
    bot: 'AvocaDOS'

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__()
        self.bot = bot

    def __repr__(self) -> str:
        return self.__class__.__name__

    @property
    def logger(self) -> Logger:
        return self.bot.logger

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        pass
