from abc import ABC
from typing import Any

from loguru._logger import Logger

from avocados import api
from avocados.geometry.util import unique_id


class BotObject(ABC):
    id: int
    cache: dict[str, Any]

    def __init__(self) -> None:
        super().__init__()
        self.id = unique_id()
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
    def logger(self) -> Logger:
        return api.logger.bind(prefix=type(self).__name__)
