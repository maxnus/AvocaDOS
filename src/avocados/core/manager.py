from abc import ABC
from collections import defaultdict
from typing import TYPE_CHECKING

from avocados.core.botobject import BotObject
from avocados.core.timings import Timings

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class BotManager(BotObject, ABC):
    timings: dict[str, Timings]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.timings = defaultdict(lambda: Timings(bot))
        self.logger.debug("Initializing {}", type(self).__name__)

    # --- Callbacks

    async def on_start(self) -> None:
        pass

    async def on_step(self, step: int) -> None:
        pass
