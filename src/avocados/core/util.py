from collections.abc import Callable
from typing import Any, Optional, TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class WithCallback[T]:
    value: T
    callback: Optional[Callable[[...], Any]]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __init__(self, value: T, callback: Optional[Callable[[...], Any]], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.value = value
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value})"

    def peak(self) -> T:
        return self.value

    def access(self) -> T:
        if self.callback is not None:
            self.callback(*self.args, **self.kwargs)
        return self.value


class Timer(BotObject):
    duration: float
    _started: Optional[float]
    _callback: Optional[Callable[[...], Any]]

    def __init__(self, bot: 'AvocaDOS', duration: float, *, callback: Optional[Callable] = None) -> None:
        super().__init__(bot)
        self.duration = duration
        self._callback = callback

    @property
    def time_left(self) -> float:
        return max(self.duration - self.time_passed, 0)

    @property
    def time_passed(self) -> float:
        if self.running:
            return self.time - self._started
        return 0

    @property
    def running(self) -> bool:
        return self._started is not None

    def start(self) -> None:
        self._started = self.time

    def expired(self) -> bool:
        if not self.running:
            return False
        return self.time_left == 0
