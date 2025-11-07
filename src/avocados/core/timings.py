from time import perf_counter
from typing import Optional, TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class Timings(BotObject):
    """Per frame aggregation."""
    max_time: Optional[float] = None
    min_time: Optional[float] = None
    total_time: float
    steps: int
    calls: int
    _previous_step: int
    _time_step: float

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.min_time = None
        self.max_time = None
        self.total_time = 0
        self.steps = 0
        self.calls = 0
        self._previous_step = -1
        self._time_step = 0

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(avg={self.average * 1000:.3f}ms, min={self.min * 1000:.3f}ms, "
                f"max={self.max * 1000:.3f}ms)")

    @property
    def average(self) -> float:
        return self.total_time / self.steps

    @property
    def min(self) -> float:
        return self.min_time

    @property
    def max(self) -> float:
        return self.max_time

    def add(self, start_time: float) -> None:
        time = perf_counter() - start_time
        if self.bot.step == self._previous_step:
            self._time_step += time
        else:
            self._time_step = time
            self.steps += 1

        self.min_time = min(self._time_step, self.min_time) if self.min_time is not None else self._time_step
        self.max_time = max(self._time_step, self.max_time) if self.max_time is not None else self._time_step
        self.total_time += time
        self.calls += 1
