from time import perf_counter
from typing import Optional


class Timings:
    max_time: Optional[float] = None
    min_time: Optional[float] = None
    total_time: float
    measurements: int

    def __init__(self) -> None:
        self.min_time = None
        self.max_time = None
        self.total_time = 0
        self.measurements = 0

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(avg={self.average * 1000:.3f}ms, min={self.min * 1000:.3f}ms, "
                f"max={self.max * 1000:.3f}ms)")

    @property
    def average(self) -> float:
        return self.total_time / self.measurements

    @property
    def min(self) -> float:
        return self.min_time

    @property
    def max(self) -> float:
        return self.max_time

    def add(self, start_time: float) -> None:
        time = perf_counter() - start_time
        self.min_time = min(time, self.min_time) if self.min_time is not None else time
        self.max_time = max(time, self.max_time) if self.max_time is not None else time
        self.total_time += time
        self.measurements += 1
