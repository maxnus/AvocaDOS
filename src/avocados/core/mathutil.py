import numpy
from numpy import ndarray
import scipy


def filter_array_at(array: numpy.ndarray, index: int, sigma: float = 1.0, truncate: float = 3.0) -> float:
    """Gaussian filter"""
    halfsize = int(truncate * sigma)
    size = 2 * halfsize + 1
    signal_center = index
    signal_start = max(signal_center - halfsize, 0)
    signal_stop = min(signal_center + halfsize + 1, array.size)
    kernel = scipy.signal.windows.gaussian(size, std=sigma)
    kernel /= numpy.sum(kernel)
    all_values = numpy.zeros_like(kernel)
    window_start = halfsize - (signal_center - signal_start)
    window_stop = window_start + signal_stop - signal_start
    signal = array[signal_start:signal_stop]
    all_values[:window_start] = signal[0]
    all_values[window_stop:] = signal[-1]
    all_values[window_start:window_stop] = signal
    filtered = numpy.dot(all_values, kernel)
    return filtered


def sigmoid[T: float | ndarray](x: T, k: float = 1.0) -> T:
    return 1 / (1 + numpy.exp(-k * (x - 0.5)))


def clipped_sigmoid[T: float | ndarray](x: T, k: float = 1.0) -> T:
    lx = sigmoid(x, k=k)
    l0 = sigmoid(0, k=k)
    l1 = sigmoid(1, k=k)
    return (lx - l0) / (l1 - l0)
