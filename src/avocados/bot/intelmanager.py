from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Optional

import numpy
from numpy import ndarray
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.constants import RESOURCE_COLLECTOR_TYPE_IDS, CLOACKABLE_TYPE_IDS, BURROWED_TYPE_IDS
from avocados.core.manager import BotManager
from avocados.core.timeseries import Timeseries
from avocados.geometry.field import Field
from avocados.geometry.util import Rectangle
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


SCAN_DURATION: int = 196
BURROW_DURATION: int = 224


@dataclass
class Scan:
    started: int
    location: Point2


class IntelManager(BotManager):
    last_known_enemy_base: Optional[ExpansionLocation]
    visibility: Field[int]
    last_visible: Field[float]
    enemy_race: Optional[Race]
    enemy_units: set[Unit]
    enemy_burrowed_units: dict[Unit, int]
    enemy_army_strength: Timeseries[float]
    enemy_utype_last_spotted: dict[UnitTypeId, int]
    ongoing_scans: list[Scan]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.last_known_enemy_base = None
        self.enemy_race = self.api.enemy_race if self.api.enemy_race != Race.Random else None   # Update for random players
        self.enemy_units = set()
        self.enemy_burrowed_units = {}
        self.enemy_army_strength = Timeseries.empty(float, initial_size=4096)
        self.enemy_utype_last_spotted = {}
        self.ongoing_scans = []

    async def on_start(self) -> None:
        self.last_known_enemy_base = self.map.known_enemy_start_location
        self.visibility = self.map.create_field_from_pixelmap(self.api.state.visibility)
        self.last_visible = Field((self.map.width, self.map.height), offset=self.map.playable_offset)

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()
        self.ongoing_scans = [scan for scan in self.ongoing_scans if step <= scan.started + SCAN_DURATION]
        self.visibility.data = self.api.state.visibility.data_numpy.transpose()[self.map.playable_mask]
        mask: ndarray = (self.visibility.data == 2)  # noqa
        self.last_visible.data[mask] = self.time
        self.enemy_units = {unit for unit in self.enemy_units if unit.tag in self.api.alive_tags}
        self.enemy_burrowed_units = {unit: burrowed_step for unit, burrowed_step in self.enemy_burrowed_units.items()
                                     if unit.tag in self.api.alive_tags and step <= burrowed_step + BURROW_DURATION}
        self.enemy_units.update(self.api.all_enemy_units)
        for unit in self.api.all_enemy_units:
            self.enemy_utype_last_spotted[unit.type_id] = step
            if unit.type_id in BURROWED_TYPE_IDS:
                self.enemy_burrowed_units[unit] = step

        enemy_army = {unit for unit in self.enemy_units if unit.type_id not in RESOURCE_COLLECTOR_TYPE_IDS}
        self.enemy_army_strength.append(step, self.combat.get_strength(enemy_army))
        self.timings['step_start'].add(t0)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        self._check_for_scans()
        self.timings['step'].add(t0)

    def get_percentage_scouted(self) -> float:
        return numpy.sum(self.visibility.data > 0) / self.visibility.size

    def get_time_since_expansions_last_visible(self) -> dict[ExpansionLocation, float]:
        return {expansion : self.get_time_since_last_visible(expansion.get_townhall_area())
                for expansion in self.map.expansions}

    def get_time_since_last_visible(self, location: Point2 | Rectangle) -> float:
        if isinstance(location, Point2):
            return self.time - self.last_visible[location]
        if isinstance(location, Rectangle):
            return (self.time - self.last_visible[location]).min()
        raise TypeError(f"invalid type: {type(location)}")

    def scan_location(self, location: Point2, *, min_separation: float = 13.0) -> bool:
        for scan in self.ongoing_scans:
            if scan.location.distance_to(location) < min_separation:
                return False
        for orbital in self.api.structures(UnitTypeId.ORBITALCOMMAND).ready:
            if orbital.energy >= 50:
                scan = Scan(self.step, location)
                self.logger.debug("Ordering {} to scan {}", orbital, scan)
                self.ongoing_scans.append(scan)
                self.order.ability(orbital, AbilityId.SCANNERSWEEP_SCAN, location)
                return True
        return False

    def get_available_scans(self) -> int:
        scans = 0
        for orbital in self.api.structures(UnitTypeId.ORBITALCOMMAND).ready:
            scans += int(orbital.energy // 50)
        return scans

    def _check_for_scans(self, *, min_strength: float = 3.0, max_distance: float = 6.0) -> None:
        available_scans = self.get_available_scans()
        if available_scans == 0:
            return
        hidden_enemies = self.api.enemy_units.of_type(CLOACKABLE_TYPE_IDS)
        burrowed_enemies = Units(list(self.enemy_burrowed_units.keys()), self.api)
        targets: list[tuple[Unit, float]] = []
        for enemy_unit in hidden_enemies + burrowed_enemies:
            # Check if it can be attacked
            friendly_strength = self.combat.get_strength(self.bot.forces.closer_than(max_distance, enemy_unit))
            if friendly_strength > min_strength:
                targets.append((enemy_unit, 0.5))   # TODO different priorities
        if targets:
            target = max(targets, key=lambda x: x[1])
            self.scan_location(target[0].position)


    # def get_next_scout_location(self, time_since_scout: float = 30, *, sigma: float = 3.0) -> Circle:
    #     tss = self.time_since_visible_map(sigma=sigma)
    #     dist = distance_transform_edt(tss > time_since_scout)
    #     #radius = dist.max()
    #     radius = 3
    #     center = Point2(numpy.unravel_index(dist.argmax(), dist.shape)) + self.map.playable_offset
    #     self.logger.info("RADIUS={}, CENTER={}".format(dist.max(), center))
    #     return Circle(center=center, radius=radius)
