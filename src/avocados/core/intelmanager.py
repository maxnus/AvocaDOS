from time import perf_counter
from typing import TYPE_CHECKING

import numpy
from numpy import ndarray
from sc2.position import Point2
from scipy.ndimage import gaussian_filter, distance_transform_edt

from avocados.core.botobject import BotManager
from avocados.core.geomutil import Circle

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class IntelManager(BotManager):
    _time_last_visible: ndarray

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._time_last_visible = None   # Only initialized in on_start

    async def on_start(self) -> None:
        self._time_last_visible = numpy.zeros((self.map.width, self.map.height), dtype=float)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        mask: ndarray = self.visibility == 2  # noqa
        self._time_last_visible[mask] = self.time
        self.timings['step'].add(t0)

        if step % 100 == 0:
            t0 = perf_counter()
            p = self.get_next_scout_location()
            self.log.warning("p = {}", p.center)
            self.debug.sphere(p, color='RED', duration=100 / 22.4)
            self.debug.line(p.center, self.map.center, color='RED', duration=100 / 22.4)
            self.timings['scout'].add(t0)

    @property
    def visibility(self) -> ndarray:
        return self.api.state.visibility.data_numpy[self.map.playable_mask]

    def get_percentage_scouted(self) -> float:
        return numpy.sum(self.visibility > 0) / self.visibility.size

    def time_since_scouted(self, *, sigma: float = 3.0) -> ndarray:
        blurred = gaussian_filter(self.time - self._time_last_visible, sigma=sigma)
        # import matplotlib.pyplot as plt
        # plt.imshow(self._time_last_visible, origin="lower")
        # plt.savefig(f"origin-{self.time}.png")
        # plt.imshow(blurred, origin="lower")
        # plt.savefig(f"blurred-{self.time}.png")
        return blurred

    def get_next_scout_location(self, time_since_scout: float = 30, *, sigma: float = 3.0) -> Circle:
        tss = self.time_since_scouted(sigma=sigma)
        dist = distance_transform_edt(tss > time_since_scout)
        #radius = dist.max()
        radius = 3
        center = Point2(numpy.unravel_index(dist.argmax(), dist.shape)) + self.map.playable_offset
        self.logger.info("RADIUS={}, CENTER={}".format(dist.max(), center))
        return Circle(center=center, radius=radius)
