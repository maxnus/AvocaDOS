from typing import Optional, Self, Any

import numpy
from numpy import ndarray
from sc2.pixel_map import PixelMap
from sc2.position import Point2

from avocados.core.geomutil import Rectangle


class Field[T]:
    data: ndarray
    offset: Point2

    def __init__(self, arg: ndarray | tuple[int, int], *, offset: Optional[Point2] = None) -> None:
        if isinstance(arg, tuple):
            arg = numpy.zeros(arg)
        self.data = arg
        self.offset = offset or Point2((0, 0))

    @classmethod
    def from_pixelmap(cls, pixelmap: PixelMap, *, offset: Optional[Point2] = None) -> Self:
        return cls(pixelmap.data_numpy.transpose(), offset=offset)

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

    def __getitem__(self, item: Point2 | Rectangle) -> T | ndarray:
        if isinstance(item, Point2):
            point = item - self.offset
            return self.data[int(round(point.x)), int(round(point.y))]
        if isinstance(item, Rectangle):
            rect = (item - self.offset).rounded()
            return self.data[rect.x : rect.x_end, rect.y : rect.y_end]
        raise TypeError(f'invalid type: {type(item)}')

    def __setitem__(self, item: Point2 | Rectangle, value: T | ndarray) -> None:
        if isinstance(item, Point2):
            point = item - self.offset
            self.data[int(round(point.x)), int(round(point.y))] = value
        elif isinstance(item, Rectangle):
            rect = (item - self.offset).rounded()
            self.data[rect.x : rect.x_end, rect.y : rect.y_end] = value
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
