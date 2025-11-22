from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2

from avocados import api
from avocados.bot.intelmanager import IntelManager
from avocados.core.constants import CLOACKABLE_TYPE_IDS
from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


SCAN_DURATION: int = 196


@dataclass(frozen=True)
class Scan:
    started: int
    location: Point2


class ScanManager(BotManager):
    intel: IntelManager
    ongoing_scans: list[Scan]

    def __init__(self, bot: 'AvocaDOS', *, intel_manager: IntelManager) -> None:
        super().__init__(bot)
        self.intel = intel_manager
        self.ongoing_scans = []

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()
        self.ongoing_scans = [scan for scan in self.ongoing_scans if step <= scan.started + SCAN_DURATION]
        self.timings['step_start'].add(t0)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        self._check_for_scans()
        self.timings['step'].add(t0)

    def scan_location(self, location: Point2, *, min_separation: float = 13.0) -> bool:
        for scan in self.ongoing_scans:
            if scan.location.distance_to(location) < min_separation:
                return False
        for orbital in api.structures(UnitTypeId.ORBITALCOMMAND).ready:
            if orbital.energy >= 50:
                scan = Scan(api.step, location)
                self.logger.debug("Ordering {} to scan {}", orbital, scan)
                self.ongoing_scans.append(scan)
                self.order.ability(orbital, AbilityId.SCANNERSWEEP_SCAN, location)
                return True
        return False

    def get_available_scans(self) -> int:
        scans = 0
        for orbital in api.structures(UnitTypeId.ORBITALCOMMAND).ready:
            scans += int(orbital.energy // 50)
        return scans

    # --- Private

    def _check_for_scans(self, *, min_strength: float = 3.0, max_distance: float = 6.0) -> None:
        available_scans = self.get_available_scans()
        if available_scans == 0:
            return
        hidden_enemies = api.enemy_units.of_type(CLOACKABLE_TYPE_IDS)
        burrowed_enemies = list(self.intel.enemy_burrowed_units.values())
        targets: list[tuple[Point2, float]] = []

        # Careful: we loop over both units and BurrowedUnit - but they both have the position attribute
        for enemy_unit in [*hidden_enemies, *burrowed_enemies]:
            # Check if it can be attacked
            friendly_strength = self.combat.get_strength(self.bot.forces.closer_than(max_distance, enemy_unit.position))
            enemy_strength = self.combat.get_strength(api.enemy_units.closer_than(max_distance, enemy_unit.position))
            if friendly_strength >= max(1.2 * enemy_strength, min_strength):
                targets.append((enemy_unit.position, 0.5))   # TODO different priorities
        if targets:
            target = max(targets, key=lambda x: x[1])
            self.scan_location(target[0])
