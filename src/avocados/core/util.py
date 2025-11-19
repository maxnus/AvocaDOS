from collections.abc import Callable
from typing import Any, Optional, TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


def clip(value: float, min_value: float = 0, max_value: float = 1) -> float:
    return max(min(value, max_value), min_value)


def snap(value: float, previous_value: int, *, tolerance: float = 1.0) -> int:
    if abs(value - previous_value) < tolerance:
        return previous_value
    return int(round(value))


def lerp(x, /, *points: tuple[float, float]) -> float:
    # Flat extrapolation
    if x <= points[0][0]:
        return points[0][1]
    if x > points[-1][0]:
        return points[-1][1]
    # LERP
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x <= x2:
            r = (x2 - x) / (x2 - x1)
            return r * y1 + (1 - r) * y2
    raise ValueError


def two_point_lerp(value: float, lower: float, upper: float, *,
                   lower_value: float = 0.0, upper_value: float = 1.0) -> float:
    if value <= lower:
        return lower_value
    if value >= upper:
        return upper_value
    p = (upper - value) / (upper - lower)
    return p * lower_value + (1 - p) * upper_value


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
