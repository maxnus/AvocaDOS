from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

import numpy
from numpy import ndarray
from scipy.ndimage import gaussian_filter1d

from avocados.core.mathutil import filter_array_at


class AbstractTimeSeries(ABC):

    @property
    @abstractmethod
    def size(self) -> int:
        pass


class Timeseries[T](AbstractTimeSeries):
    _values: ndarray
    _max_size: Optional[int]
    _offset: int
    _step: int

    def __init__(self, values: ndarray,
                 start: int = 0,
                 length: int = 0,
                 max_size: Optional[int] = None,
                 ) -> None:
        super().__init__()
        if max_size is not None:
            raise NotImplementedError()
        self._values = values
        self._max_size = max_size
        self._offset = start
        self._step = self._offset + length - 1

    @classmethod
    def empty(cls, dtype: type[T], step: int = 0,
              *,
              initial_size: int = 128,
              max_size: Optional[int] = None,
              ) -> 'Timeseries[T]':
        values = numpy.zeros(initial_size, dtype=dtype)
        return cls(values, start=step, length=0, max_size=max_size)

    @property
    def size(self) -> int:
        return self._step - self._offset + 1

    @property
    def values(self) -> ndarray:
        return self._values[:self.size]

    @property
    def buffer_size(self) -> int:
        return self._values.size

    @property
    def step(self) -> int:
        return self._step

    def __iter__(self) -> Iterator[tuple[int, T]]:
        yield from enumerate(self.values, start=self._offset)

    def _normalize_slice(self, item: slice) -> slice:
        if item.start < 0:
            raise NotImplementedError
        if item.stop < 0:
            raise NotImplementedError
        if item.step is not None:
            raise NotImplementedError

        start = item.start - self._offset if item.start is not None else None
        stop = item.stop - self._offset if item.stop is not None else None
        step = None
        if start < 0:
            raise ValueError
        if stop < 0:
            raise ValueError
        return slice(start, stop, step)

    def __getitem__(self, item: int | slice) -> T | 'Timeseries[T]':
        if isinstance(item, int):
            return self.values[item - self._offset]
        if isinstance(item, slice):
            values = self.values[self._normalize_slice(item)]
            offset = item.start if item.start is not None else self._offset
            step = item.stop - 1 if item.stop is not None else self.step
            return Timeseries(values, start=offset, length=step)
        return NotImplemented

    def append(self, step: int, value: T) -> None:
        if self.size == 0:
            self._offset = step
        if self.size >= self.buffer_size:
            self._values.resize(2 * self.buffer_size)
        assert step == self.size
        self._values[self.size] = value
        self._step = step

    def value(self, step: Optional[int] = None) -> Optional[T]:
        if step is None:
            step = self._step
        if self.size == 0:
            return None
        if step < self._offset:
            return None
        if step > self.step:
            return None
        return self.values[step - self._offset]

    def filtered_value(self, step: Optional[int] = None, *,
                       sigma: float = 1.0, truncate: float = 3.0) -> float:
        """With Gaussian filter."""
        if step is None:
            step = self._step
        return filter_array_at(self.values, step - self._offset, sigma=sigma, truncate=truncate)

    def derivative(self, step: Optional[int] = None, steps: int = 100, *,
                   per_second: bool = True,
                   sigma: float = 0.0
                   ) -> Optional[T]:
        s1 = step or self.step
        s0 = s1 - steps
        if sigma > 0:
            v0 = self.filtered_value(s0, sigma=sigma)
            v1 = self.filtered_value(s1, sigma=sigma)
        else:
            v0 = self.value(s0)
            v1 = self.value(s1)
        if v0 is None or v1 is None:
            return None
        dt = steps / 22.4 if per_second else steps
        return (v1 - v0) / dt

    def time_until_value(self, value: T, *,
                         steps_for_derivative: int = 100, sigma_for_derivative: float = 0.0) -> Optional[float]:
        deriv = self.derivative(steps=steps_for_derivative, sigma=sigma_for_derivative)
        if deriv is None:
            return None
        current_value = self.value()
        if current_value > value and deriv >= 0:
            return float('inf')
        if current_value < value and deriv <= 0:
            return float('inf')
        if value == current_value:
            return 0.0
        return (value - current_value) / deriv

    def gaussian_filter(self, *, sigma: float = 1.0, mode: str = 'nearest') -> 'Timeseries[float]':
        filtered = gaussian_filter1d(self.values.astype(float), sigma=sigma, mode=mode)
        return type(self)(filtered, start=self._offset, length=self.step)

    def plot(self, path: Optional[Path | str] = None, *,
             yshift: float = 0.0,
             **kwargs) -> None:
        from matplotlib import pyplot as plt
        steps = numpy.arange(self._offset, self._offset + self.size)
        plt.plot(steps, self.values[:self.size] + yshift, **kwargs)
        plt.xlabel("Step")
        plt.ylabel("Value")
        plt.grid()
        if path is not None:
            plt.savefig(path)
