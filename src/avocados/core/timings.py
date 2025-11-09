from time import perf_counter
from typing import Optional, TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class Timings(BotObject):
    """Per frame aggregation."""
    max_time: float
    total_time: float
    steps: int
    calls: int
    _previous_step: int
    _time_step: float

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.reset()

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(avg={self.average * 1000:.3f}ms, max={self.max * 1000:.3f}ms,"
                f" calls={self.calls})")

    def reset(self) -> None:
        self.max_time = 0
        self.total_time = 0
        self.steps = 0
        self.calls = 0
        self._previous_step = -1
        self._time_step = 0

    @property
    def average(self) -> float:
        if self.steps != 0:
            return self.total_time / self.steps
        if self.total_time == 0:
            return 0.0
        return float('nan')

    @property
    def max(self) -> float:
        return self.max_time

    def add(self, start_time: float) -> None:
        time = perf_counter() - start_time
        if self.bot.step == self._previous_step:
            self._time_step += time
        else:
            self._time_step = time
            self._previous_step = self.bot.step
            self.steps += 1

        self.max_time = max(self._time_step, self.max_time)
        self.total_time += time
        self.calls += 1
