from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Optional

import numpy
from numpy import ndarray
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit

from avocados import api
from avocados.combat.util import get_strength
from avocados.core.constants import (RESOURCE_COLLECTOR_TYPE_IDS, BURROWED_TYPE_IDS,
                                     UNBURROWED_TYPE_IDS)
from avocados.core.manager import BotManager
from avocados.core.timeseries import Timeseries
from avocados.geometry.field import Field
from avocados.geometry.util import Rectangle
from avocados.mapdata import MapManager
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


BURROW_TRACK_DURATION: int = 224  # 10 seconds


@dataclass(frozen=True)
class BurrowedUnit:
    tag: int
    position: Point2
    utype: UnitTypeId
    last_spotted: int

    def __hash__(self) -> int:
        return self.tag

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BurrowedUnit):
            return self.tag == other.tag
        return NotImplemented


class IntelManager(BotManager):
    map: MapManager

    last_known_enemy_base: Optional[ExpansionLocation]
    visibility: Field[int]
    last_visible: Field[float]
    enemy_race: Optional[Race]
    enemy_units: set[Unit]
    enemy_burrowed_units: dict[int, BurrowedUnit]
    enemy_army_strength: Timeseries[float]
    enemy_utype_last_spotted: dict[UnitTypeId, int]

    def __init__(self, bot: 'AvocaDOS', map_manager: MapManager) -> None:
        super().__init__(bot)
        self.map = map_manager

        self.last_known_enemy_base = None
        self.enemy_race = api.enemy_race if api.enemy_race != Race.Random else None   # Update for random players
        self.enemy_units = set()
        self.enemy_burrowed_units = {}
        self.enemy_army_strength = Timeseries.empty(float, initial_size=4096)
        self.enemy_utype_last_spotted = {}

    async def on_start(self) -> None:
        self.last_known_enemy_base = self.map.known_enemy_start_location
        self.visibility = self.map.create_field_from_pixelmap(api.state.visibility)
        self.last_visible = Field((self.map.width, self.map.height), offset=self.map.playable_offset)

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()
        self.visibility.data = api.state.visibility.data_numpy.transpose()[self.map.playable_mask]
        mask: ndarray = (self.visibility.data == 2)  # noqa
        self.last_visible.data[mask] = api.time

        self.enemy_units = {unit for unit in self.enemy_units if unit.tag in api.alive_tags}
        self.enemy_burrowed_units = {tag: unit for tag, unit in self.enemy_burrowed_units.items()
                                     if tag in api.alive_tags and step <= unit.last_spotted + BURROW_TRACK_DURATION}
        self.enemy_units.update(api.all_enemy_units)
        for unit in api.all_enemy_units:
            self.enemy_utype_last_spotted[unit.type_id] = step
            if unit.type_id in BURROWED_TYPE_IDS:
                self.enemy_burrowed_units[unit.tag] = BurrowedUnit(unit.tag, unit.position, unit.type_id, step)
            elif unit.type_id in UNBURROWED_TYPE_IDS:
                self.enemy_burrowed_units.pop(unit.tag, None)

        enemy_army = {unit for unit in self.enemy_units if unit.type_id not in RESOURCE_COLLECTOR_TYPE_IDS}
        self.enemy_army_strength.append(step, get_strength(enemy_army))
        self.timings['step_start'].add(t0)

    def get_percentage_scouted(self) -> float:
        return numpy.sum(self.visibility.data > 0) / self.visibility.size

    def get_time_since_expansions_last_visible(self) -> dict[ExpansionLocation, float]:
        return {expansion : self.get_time_since_last_visible(expansion.get_townhall_area())
                for expansion in self.map.expansions}

    def get_time_since_last_visible(self, location: Point2 | Rectangle) -> float:
        if isinstance(location, Point2):
            return api.time - self.last_visible[location]
        if isinstance(location, Rectangle):
            return (api.time - self.last_visible[location]).min()
        raise TypeError(f"invalid type: {type(location)}")

    # def get_next_scout_location(self, time_since_scout: float = 30, *, sigma: float = 3.0) -> Circle:
    #     tss = api.time_since_visible_map(sigma=sigma)
    #     dist = distance_transform_edt(tss > time_since_scout)
    #     #radius = dist.max()
    #     radius = 3
    #     center = Point2(numpy.unravel_index(dist.argmax(), dist.shape)) + self.map.playable_offset
    #     self.logger.info("RADIUS={}, CENTER={}".format(dist.max(), center))
    #     return Circle(center=center, radius=radius)