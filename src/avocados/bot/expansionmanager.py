from collections import Counter
from collections.abc import Iterable
from time import perf_counter
from typing import TYPE_CHECKING, Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados import api
from avocados.bot.scanmanager import ScanManager
from avocados.core.botobject import BotObject
from avocados.core.constants import TOWNHALL_TYPE_IDS
from avocados.core.manager import BotManager
from avocados.core.util import WithCallback
from avocados.geometry.util import same_point, get_best_score
from avocados.mapdata import MapManager
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class Expansion(BotObject):
    townhall_tag: int
    location: ExpansionLocation
    miners: dict[int, Point2]

    def __init__(self, bot: 'AvocaDOS', townhall: Unit, location: ExpansionLocation) -> None:
        super().__init__(bot)
        self.townhall_tag = townhall.tag
        self.location = location
        self.miners = {}

    @property
    def townhall(self) -> Optional[Unit]:
        return api.structures.find_by_tag(self.townhall_tag)

    def get_assignment(self) -> dict[Unit, Unit]:
        assignment = {}
        for worker_tag, mineral_position in self.miners.items():
            worker = api.workers.by_tag(worker_tag)
            if (minerals := self.location.get_mineral_field(mineral_position)) is not None:
                assignment[worker] = minerals
        return assignment

    def get_required_workers(self) -> int:
        return 2 * len(self.location.mineral_fields)

    def get_missing_workers(self) -> int:
        return self.get_required_workers() - len(self.miners)

    def get_assigned_worker_count(self) -> Counter[Point2]:
        return Counter(self.miners.values())

    def has_worker(self, worker: Unit) -> bool:
        return worker.tag in self.miners

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            return False
        empty_fields, single_fields = self.get_mineral_field_split()[:2]
        if empty_fields:
            mf = empty_fields.closest_to(worker)
        elif single_fields:
            mf = single_fields.closest_to(worker)
        else:
            return False
        self.miners[worker.tag] = mf.position
        return True

    def remove_worker(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        removed = self.miners.pop(tag, None)
        return bool(removed)

    def get_mineral_field_split(self) -> tuple[Units, Units, Units, Units]:
        """fields with no, one, two miners"""
        count = self.get_assigned_worker_count()
        empty_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 0], api)
        single_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 1], api)
        double_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 2], api)
        oversaturated_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] >= 3],
                                            api)
        return empty_fields, single_mining_fields, double_mining_fields, oversaturated_mining_fields

    def get_expected_mineral_rate(self, *, single_worker_rate: float = 1.068) -> float:
        """TODO: consider mineral field distance"""
        single_fields, double_fields, oversaturated_fields = self.get_mineral_field_split()[1:]
        return (2 * (len(double_fields) + len(oversaturated_fields)) + len(single_fields)) * single_worker_rate

    async def update_assignment(self) -> None:
        workers = api.workers.tags_in(self.miners.keys())
        self.miners.clear()
        # TODO: long distance mining?
        if not self.location.mineral_fields:
            api.log.caution("NoMinerals_{}", self.location)
            return
        # should already be sorted
        minerals = self.location.mineral_fields.sorted_by_distance_to(self.location.center)
        for mineral in 2 * minerals:
            if len(workers) == 0:
                break
            worker = workers.pop()
            self.logger.debug("Assigning {} to {}", worker, mineral)
            self.miners[worker.tag] = mineral.position

    def speed_mine(self) -> None:
        townhall = self.townhall
        if townhall is None:
            api.log.error("NoTownhall-{}", self.townhall_tag)
            return

        enemies = api.enemy_units.closer_than(8, townhall)

        for worker_tag, mineral_position in self.miners.items():
            worker = api.workers.find_by_tag(worker_tag)
            if worker is None:
                api.log.error("InvalidWorkerTag-{}", worker_tag)
                continue

            # Defend yourself TODO: do for all probes
            if worker.weapon_ready:
                close_enemies = enemies.in_attack_range_of(worker)
                if close_enemies:
                    worker.attack(close_enemies.closest_to(worker))
                    continue

            mineral_field = self.location.get_mineral_field(mineral_position)
            if mineral_field is None:
                api.log.error("InvalidMineralTag-{}", mineral_position)
                continue

            if worker.is_carrying_minerals:
                target_point = self.location.mining_return_targets.get(mineral_position)
                if target_point is None:
                    api.log.error("InvalidReturnTarget-{}", mineral_position)
                    continue
                target = townhall
            else:
                target_point = self.location.mining_gather_targets.get(mineral_position)
                if target_point is None:
                    api.log.error("InvalidGatherTarget-{}", mineral_position)
                    continue
                target = mineral_field

            def is_correct_order() -> bool:
                if not worker.orders:
                    return False
                order = worker.orders[0]
                if order.ability.exact_id in {AbilityId.HARVEST_RETURN_SCV, AbilityId.HARVEST_RETURN_MULE,
                                              AbilityId.HARVEST_RETURN_DRONE, AbilityId.HARVEST_RETURN_PROBE}:
                    return True
                if isinstance(order.target, int) and order.target in {townhall.tag, mineral_field.tag}:
                    return True
                if isinstance(order.target, Point2) and same_point(order.target, target_point):
                    return True
                return False

            distance = worker.distance_to(target_point)
            if (0.75 < distance < 2 and len(worker.orders) != 2) or not is_correct_order():
                api.order.move(worker, target_point)
                api.order.smart(worker, target, queue=True)


class ExpansionManager(BotManager):
    map: MapManager
    scan: ScanManager
    expansions: dict[ExpansionLocation, Expansion]
    """location -> townhall tag"""

    def __init__(self, bot: 'AvocaDOS', *, map_manager: MapManager, scan_manager: ScanManager) -> None:
        super().__init__(bot)
        self.map = map_manager
        self.scan = scan_manager

        self.expansions = {}

    def __len__(self) -> int:
        return len(self.expansions)

    def __contains__(self, expansion: ExpansionLocation) -> bool:
        return expansion in self.expansions

    async def on_start(self) -> None:
        self.add_expansion(self.map.start_location, api.townhalls.first)
        # TODO: repeat, when needed
        self.add_workers(api.workers)
        await self.update_assignment()

    async def on_step_start(self, step: int) -> None:
        self._check_for_dead_tags()

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        self._assign_idle_workers()
        #if self.update:
        #    await self.update_assignment()
        if step % 4 == 0:
            for exp in self.expansions.values():
                exp.speed_mine()
            self._drop_mules()
        self.timings['step'].add(t0)

    async def on_building_construction_complete(self, unit: Unit) -> None:
        if unit.type_id not in TOWNHALL_TYPE_IDS:
            return
        if self.has_townhall(unit):
            return
        location = min(self.map.expansions, key=lambda expansion: unit.distance_to(expansion.center))
        if unit.distance_to(location.center) > 3:
            return
        self.add_expansion(location, unit)

    def has_townhall(self, townhall: Unit) -> bool:
        for exp in self.expansions.values():
            if exp.townhall == townhall:
                return True
        return False

    def add_expansion(self, location: ExpansionLocation, townhall: Unit) -> None:
        self.logger.info("Adding {} at {}", townhall, location)
        self.expansions[location] = Expansion(self.bot, townhall, location)

    def remove_expansion(self, expansion: ExpansionLocation | Expansion) -> None:
        location = expansion.location if isinstance(expansion, Expansion) else expansion
        self.logger.info("Removing {}", location)
        self.expansions.pop(location)

    def get_required_workers(self) -> int:
        return sum(exp.get_required_workers() for exp in self.expansions.values())

    def get_missing_workers(self) -> int:
        return sum(exp.get_missing_workers() for exp in self.expansions.values())

    def get_assigned_worker_count_at_expansion(self, location: ExpansionLocation) -> Counter[Point2]:
        exp = self.expansions.get(location)
        if exp is None:
            api.log.error("No expansion at {}", location)
            return Counter()
        return exp.get_assigned_worker_count()

    def get_all_workers(self) -> Units:
        workers = []
        for exp in self.expansions.values():
            for worker_tag in exp.miners:
                worker = api.workers.find_by_tag(worker_tag)
                if worker is None:
                    api.log.error("MissingWorker{}", worker_tag)
                    continue
                workers.append(worker)
        return Units(workers, api)

    def get_mineral_fields(self) -> Units:
        all_minerals = [mf for exp in self.expansions.keys() for mf in exp.mineral_fields]
        return Units(all_minerals, api)

    def has_worker(self, worker: Unit) -> bool:
        return any(exp.has_worker(worker) for exp in self.expansions.values())

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            api.log.warning("SCV-{}-already-assigned-{}", worker, self)
            return False
        for exp in sorted(self.expansions.values(), key=lambda exp: worker.distance_to(exp.location.center)):
            if exp.add_worker(worker):
                return True
        return False

    def add_workers(self, workers: Iterable[Unit]) -> None:
        for worker in workers:
            self.add_worker(worker)

    def request_workers(self, location: Point2, *, number: int = 1,
                        max_distance: Optional[float] = None) -> list[WithCallback[Unit]]:
        workers = self.get_all_workers()
        if max_distance is not None:
            workers = workers.closer_than(max_distance, location)
        if not workers:
            return []
        workers = workers.closest_n_units(location, number)
        callbacks = [WithCallback(w, self.remove_worker, w) for w in workers]
        return callbacks

    def remove_worker(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        for exp in self.expansions.values():
            if exp.remove_worker(unit):
                return True
        api.log.warning("unknown-worker-{}", tag)
        return False

    async def update_assignment(self) -> None:
        for exp in self.expansions.values():
            await exp.update_assignment()

    def get_expected_mineral_rate(self, *, single_worker_rate: float = 1.068) -> float:
        """TODO: consider close vs far patches"""
        return sum(exp.get_expected_mineral_rate(single_worker_rate=single_worker_rate)
                   for exp in self.expansions.values())

    # --- Private

    def _check_for_dead_tags(self):
        # Check for dead tags
        for exp in list(self.expansions.values()):
            if exp.townhall_tag not in api.alive_tags:
                self.logger.info("Townhall at {} died", exp)
                self.remove_expansion(exp)
        for exp in self.expansions.values():
            for worker_tag, mineral_position in list(exp.miners.items()):
                if worker_tag not in api.alive_tags:
                    self.logger.debug("Dead worker={}", worker_tag)
                    self.remove_worker(worker_tag)
                if exp.location.get_mineral_field(mineral_position) is None:
                    self.logger.debug("Missing mineral field={}", mineral_position)
                    self.remove_worker(worker_tag)

    def _assign_idle_workers(self) -> None:
        def worker_filter(unit: Unit) -> bool:
            if api.order.has_order(unit):
                return False
            if unit.is_constructing_scv:
                return False
            if self.has_worker(unit):
                return False
            return True
        for worker in api.workers.filter(worker_filter):
            if self.add_worker(worker):
                self.logger.debug("Assigning idle worker {}", worker)

    def _drop_mules(self) -> None:
        scan_target = self.scan.scan_target
        for orbital in api.structures(UnitTypeId.ORBITALCOMMAND).ready.sorted_by_distance_to(
                self.map.base.center):
            available_spells = int(orbital.energy // 50)
            reserved_spells = min(scan_target, available_spells)
            scan_target -= reserved_spells
            remaining_spells = available_spells - reserved_spells
            for spell in range(remaining_spells):
                mineral_fields = self.get_mineral_fields()
                if not mineral_fields:
                    continue
                mineral_field, contents = get_best_score(mineral_fields, lambda mf: mf.mineral_contents)
                self.logger.debug("Dropping mule at {} with {} minerals", mineral_field, contents)
                api.order.ability(orbital, AbilityId.CALLDOWNMULE_CALLDOWNMULE, target=mineral_field)
