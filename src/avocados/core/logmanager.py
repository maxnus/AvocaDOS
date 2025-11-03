from collections import Counter
from collections.abc import Callable, Hashable
from enum import StrEnum
from typing import Optional, Any, TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class WarningLevel(StrEnum):
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


warning_codes: dict[WarningLevel, str] = {
    WarningLevel.CAUTION: "CTN",
    WarningLevel.WARNING: "WRN",
    WarningLevel.ERROR: "ERR",
    WarningLevel.CRITICAL: "CRT",
}


class LogManager(BotObject):
    _tags_to_send: set[str]
    _tags_sent: set[str]
    _warnings_sent: Counter[Hashable]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._tags_to_send = set()
        self._tags_sent = set()
        self._warnings_sent = Counter()

    # --- Public

    async def on_step(self, step: int) -> None:
        for tag in self._tags_to_send:
            full_tag = f'Tag:{tag}'
            self.logger.info("Sending tag: {}", full_tag)
            await self.api.client.chat_send(full_tag, team_only=False)
            self._tags_sent.add(tag)
        self._tags_to_send.clear()

    def caution(self, message: str, *args: Any, key: Optional[Hashable] = None, tag: bool = False) -> None:
        self._raise(message, *args, level=WarningLevel.CAUTION, key=key, tag=tag)

    def warning(self, message: str, *args: Any, key: Optional[Hashable] = None, tag: bool = True) -> None:
        self._raise(message, *args, level=WarningLevel.WARNING, key=key, tag=tag)

    def error(self, message: str, *args: Any, key: Optional[Hashable] = None, tag: bool = True) -> None:
        self._raise(message, *args, level=WarningLevel.ERROR, key=key, tag=tag)

    def critical(self, message: str, *args: Any, key: Optional[Hashable] = None, tag: bool = True) -> None:
        self._raise(message, *args, level=WarningLevel.CRITICAL, key=key, tag=tag)

    def tag(self, tag: str, *, add_time: bool = True) -> None:
        if add_time:
            tag = f"[{self.api.time_formatted}]{tag}"
        if tag not in self._tags_sent:
            self._tags_to_send.add(tag)

    # --- Private

    def _raise(self, message: str, *args: Any, level: WarningLevel,
               key: Optional[Hashable] = None, tag: bool = True) -> None:
        message = message.format(*args)
        if key is None:
            key = message
        if key not in self._warnings_sent:
            self._warnings_sent[key] += 1
            logfunc = self._get_log_function(level)
            logfunc(message)
            if tag:
                self.tag(f"{warning_codes[level]}_{message[:80]}")

    def _get_log_function(self, level: WarningLevel) -> Callable:
        match level:
            case WarningLevel.CAUTION:
                return self.logger.warning
            case WarningLevel.WARNING:
                return self.logger.warning
            case WarningLevel.ERROR:
                return self.logger.error
            case WarningLevel.CRITICAL:
                return self.logger.critical
        raise ValueError(f"invalid warning level: {level}")
