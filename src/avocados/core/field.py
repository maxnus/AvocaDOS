from pathlib import Path
from typing import Optional, Self, Any

import numpy
from numpy import ndarray
from sc2.position import Point2

try:
    import matplotlib.pyplot as plt
except (ImportError, ModuleNotFoundError):
    plt = None

from avocados.core.geomutil import Rectangle


class Field[T]:
    data: ndarray
    offset: Point2

    def __init__(self, arg: ndarray | tuple[int, int], *, offset: Optional[Point2] = None) -> None:
        if isinstance(arg, tuple):
            arg = numpy.zeros(arg)
        self.data = arg
        self.offset = offset or Point2((0, 0))

    @property
    def dtype(self) -> numpy.dtype:
        return self.data.dtype

    @classmethod
    def zeros_like(cls, other: Self) -> Self:
        return cls(numpy.zeros_like(other.data), offset=other.offset)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(width={self.width}, height={self.height}, offset={self.offset})"

    @property
    def width(self) -> int:
        return self.data.shape[0]

    @property
    def height(self) -> int:
        return self.data.shape[1]

    @property
    def size(self) -> int:
        return self.data.size

    def min(self) -> T:
        return self.data.min()

    def max(self) -> T:
        return self.data.max()

    def _point_to_indices(self, item: Point2) -> tuple[int, int]:
        point = item - self.offset
        return int(point[0]), int(point[1])

    def _rect_to_mask(self, item: Rectangle) -> tuple[slice, slice]:
        rect = item - self.offset
        #return slice(int(rect.x), int(math.ceil(rect.x_end))), slice(int(rect.y), int(math.ceil(rect.y_end)))
        x0 = max(int(rect.x), 0)
        y0 = max(int(rect.y), 0)
        x1 = max(int(rect.x_end), 0)
        y1 = max(int(rect.y_end), 0)
        mask = slice(x0, x1), slice(y0, y1)
        #return slice(int(rect.x + 0.5), int(rect.x_end + 0.5)), slice(int(rect.y + 0.5), int(rect.y_end + 0.5))
        return mask

    def __contains__(self, item: Point2) -> bool:
        x, y = self._point_to_indices(item)
        return 0 <= x < self.width and 0 <= y < self.height

    def __getitem__(self, item: Point2 | Rectangle) -> T | ndarray:
        if isinstance(item, Point2):
            return self.data[self._point_to_indices(item)]
        if isinstance(item, Rectangle):
            return self.data[self._rect_to_mask(item)]
        raise TypeError(f'invalid type: {type(item)}')

    def __setitem__(self, item: Point2 | Rectangle, value: T | ndarray) -> None:
        if isinstance(item, Point2):
            self.data[self._point_to_indices(item)] = value
        elif isinstance(item, Rectangle):
            self.data[self._rect_to_mask(item)] = value
        else:
            raise TypeError(f'invalid type: {type(item)}')

    def __add__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.data + other, offset=self.offset)
        return NotImplemented

    def __radd__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.data + other, offset=self.offset)
        return NotImplemented

    def __sub__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.data - other, offset=self.offset)
        return NotImplemented

    def __rsub__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(other - self.data, offset=self.offset)
        return NotImplemented

    def __mul__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.data * other, offset=self.offset)
        return NotImplemented

    def __rmul__(self, other: Any) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.data * other, offset=self.offset)
        return NotImplemented

    def plot(self, path: Optional[Path] = None) -> None:
        plt.imshow(self.data, origin="lower")
        if path is None:
            plt.show()
        else:
            plt.savefig(path)
