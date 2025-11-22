from abc import ABC
from collections import defaultdict

from avocados.core.botobject import BotObject
from avocados.core.timings import Timings


class BotManager(BotObject, ABC):
    timings: dict[str, Timings]

    def __init__(self) -> None:
        super().__init__()
        self.timings = defaultdict(Timings)
        self.logger.debug("Initializing {}", type(self).__name__)
