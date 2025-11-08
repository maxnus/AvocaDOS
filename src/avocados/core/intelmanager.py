from time import perf_counter
from typing import TYPE_CHECKING, Optional

import numpy
from numpy import ndarray
from sc2.position import Point2
from scipy.ndimage import gaussian_filter, distance_transform_edt

from avocados.core.manager import BotManager
from avocados.core.field import Field
from avocados.core.geomutil import Circle, Rectangle
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class IntelManager(BotManager):
    _time_last_visible: Optional[Field[float]]
    last_known_enemy_base: Optional[ExpansionLocation]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._time_last_visible = None   # Only initialized in on_start
        self.last_known_enemy_base = None

    async def on_start(self) -> None:
        self.last_known_enemy_base = self.map.known_enemy_start_location
        self._time_last_visible = Field((self.map.width, self.map.height), offset=self.map.playable_offset)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        mask: ndarray = (self.visibility.data == 2)  # noqa
        self._time_last_visible.data[mask] = self.time
        self.timings['step'].add(t0)

        # if step % 100 == 0:
        #     t0 = perf_counter()
        #     p = self.get_next_scout_location()
        #     self.log.warning("p = {}", p.center)
        #     self.debug.sphere(p, color='RED', duration=100 / 22.4)
        #     self.debug.line(p.center, self.map.center, color='RED', duration=100 / 22.4)
        #     self.timings['scout'].add(t0)

    @property
    def visibility(self) -> Field:
        return Field(self.api.state.visibility.data_numpy[self.map.playable_mask_yx].T, offset=self.map.playable_offset)

    def get_percentage_scouted(self) -> float:
        return numpy.sum(self.visibility.data > 0) / self.visibility.size

    def get_time_since_expansions_last_visible(self) -> dict[ExpansionLocation, float]:
        return {expansion : self.get_time_since_last_visible(expansion.get_townhall_area())
                for expansion in self.map.expansions}

    def get_time_since_last_visible(self, location: Point2 | Rectangle) -> float:
        if isinstance(location, Point2):
            return self.time - self._time_last_visible[location]
        if isinstance(location, Rectangle):
            return (self.time - self._time_last_visible[location]).min()
        raise TypeError(f"invalid type: {type(location)}")

    # def time_since_visible_map(self, *, sigma: float = 3.0) -> Field:
    #     data = gaussian_filter((self.time - self._time_last_visible).data, sigma=sigma)
    #     # import matplotlib.pyplot as plt
    #     # plt.imshow(self._time_last_visible, origin="lower")
    #     # plt.savefig(f"origin-{self.time}.png")
    #     # plt.imshow(blurred, origin="lower")
    #     # plt.savefig(f"blurred-{self.time}.png")
    #     return Field(data, offset=self._time_last_visible.offset)
    #
    # def get_next_scout_location(self, time_since_scout: float = 30, *, sigma: float = 3.0) -> Circle:
    #     tss = self.time_since_visible_map(sigma=sigma)
    #     dist = distance_transform_edt(tss > time_since_scout)
    #     #radius = dist.max()
    #     radius = 3
    #     center = Point2(numpy.unravel_index(dist.argmax(), dist.shape)) + self.map.playable_offset
    #     self.logger.info("RADIUS={}, CENTER={}".format(dist.max(), center))
    #     return Circle(center=center, radius=radius)
