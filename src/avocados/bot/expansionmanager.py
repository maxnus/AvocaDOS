from collections import Counter
from time import perf_counter
from typing import TYPE_CHECKING, Optional

from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.manager import BotManager
from avocados.core.util import WithCallback
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class Expansion(BotObject):
    townhall: int
    location: ExpansionLocation
    miners: dict[int, int]

    def __init__(self, bot: 'AvocaDOS', townhall: Unit, location: ExpansionLocation) -> None:
        super().__init__(bot)
        self.townhall = townhall.tag
        self.location = location
        self.miners = {}

    def get_assigned_worker_count(self) -> Counter[int]:
        return Counter(self.miners.values())

    def has_worker(self, worker: Unit) -> bool:
        return worker.tag in self.miners

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            return False
        empty_fields, single_fields, double_fields = self.get_mineral_field_split()
        if empty_fields:
            mf = empty_fields.closest_to(worker)
        elif single_fields:
            mf = single_fields.closest_to(worker)
        elif double_fields:
            mf = double_fields.closest_to(worker)
        else:
            return False
        self.miners[worker.tag] = mf.tag
        return True

    def remove_worker(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        removed = self.miners.pop(tag, None)
        return bool(removed)

    def get_mineral_field_split(self) -> tuple[Units, Units, Units]:
        """fields with no, one, two miners"""
        count = self.get_assigned_worker_count()
        empty_fields = Units([mf for mf in self.location.mineral_fields if count[mf.tag] == 0], self.api)
        single_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.tag] == 1], self.api)
        double_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.tag] == 2], self.api)
        return empty_fields, single_mining_fields, double_mining_fields

    async def update_assignment(self) -> None:
        self.miners.clear()
        # TODO: long distance mining?
        if not self.location.mineral_fields:
            self.log.caution("NoMinerals_{}", self.location)
            return
        # should already be sorted
        minerals = self.location.mineral_fields.sorted_by_distance_to(self.location.center)
        for mineral in 2 * minerals:
            workers = await self.bot.pick_workers(mineral.position, number=1)
            for worker, _ in workers:
                self.logger.debug("Assigning {} to {}", worker.peak(), mineral)
                self.miners[worker.access().tag] = mineral.tag

    def speed_mine(self) -> None:
        townhall = self.bot.townhalls.find_by_tag(self.townhall)
        if townhall is None:
            self.log.error("NoTownhall-{}", self.townhall)
            return

        enemies = self.api.enemy_units.closer_than(8, townhall)

        for worker_tag, mineral_tag in self.miners.items():
            worker = self.bot.workers.find_by_tag(worker_tag)
            if worker is None:
                self.log.error("InvalidWorkerTag-{}", worker_tag)
                continue

            # Defend yourself
            if worker.weapon_ready:
                close_enemies = enemies.in_attack_range_of(worker)
                if close_enemies:
                    worker.attack(close_enemies.closest_to(worker))
                    continue

            mineral_field = self.location.mineral_fields.find_by_tag(mineral_tag)
            if mineral_field is None:
                self.log.error("InvalidMineralTag-{}", mineral_tag)
                continue

            if worker.is_carrying_minerals:
                target_point = self.location.mining_return_targets.get(mineral_tag)
                if target_point is None:
                    self.log.error("InvalidReturnTarget-{}", mineral_tag)
                    continue
                target = townhall
            else:
                target_point = self.location.mining_gather_targets.get(mineral_tag)
                if target_point is None:
                    self.log.error("InvalidGatherTarget-{}", mineral_tag)
                    continue
                target = mineral_field

            distance = worker.distance_to(target_point)
            if 0.75 < distance < 2:
                self.order.move(worker, target_point)
                self.order.smart(worker, target, queue=True)

            # Get back to work
            elif not self._worker_is_working(worker, target_point):
                # self.logger.debug("Sending worker {} with order target {} and ability id {} back to mineral work",
                #                   worker, worker.orders[0].target if worker.orders else None,
                #                   worker.orders[0].ability if worker.orders else None)
                self.bot.order.smart(worker, target)

            # elif worker.is_idle:
            #     self.logger.info("Restarting idle worker {}", worker)
            #     if distance <= 0.75:
            #         self.commander.order.smart(worker, target, force=True)
            #     elif distance >= 2:
            #         self.commander.order.move(worker, target_point, force=True)

    def _worker_is_working(self, worker: Unit, expected_location: Point2, *,
                           location_tolerance: float = 1.0) -> bool:
        if not worker.orders:
            return False
        order = worker.orders[0]
        if order.ability.id not in {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN, AbilityId.MOVE}:
            return False
        if isinstance(order.target, Point2) and order.target.distance_to(expected_location) > location_tolerance:
            return False
        return True


class ExpansionManager(BotManager):
    expansions: dict[ExpansionLocation, Expansion]
    """location -> townhall tag"""

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.expansions = {}

    async def on_start(self) -> None:
        self.add_expansion(self.map.base, self.api.townhalls.first)
        # TODO: repeat, when needed
        await self.update_assignment()

    async def on_step_start(self, step: int) -> None:
        self._check_for_dead_tags()

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        self._assign_idle_workers()
        #if self.update:
        #    await self.update_assignment()
        for exp in self.expansions.values():
            exp.speed_mine()
        self.timings['step'].add(t0)

    def add_expansion(self, location: ExpansionLocation, townhall: Unit) -> None:
        self.logger.info("Adding {} at {}", townhall, location)
        self.expansions[location] = Expansion(self.bot, townhall, location)

    def remove_expansion(self, expansion: ExpansionLocation | Expansion) -> None:
        location = expansion.location if isinstance(expansion, Expansion) else expansion
        self.logger.info("Removing {}", location)
        self.expansions.pop(location)

    def get_assigned_worker_count_at_expansion(self, location: ExpansionLocation) -> Counter[int]:
        exp = self.expansions.get(location)
        if exp is None:
            self.log.error("No expansion at {}", location)
            return Counter()
        return exp.get_assigned_worker_count()

    def get_all_workers(self) -> Units:
        workers = []
        for exp in self.expansions.values():
            for worker_tag in exp.miners:
                worker = self.bot.workers.find_by_tag(worker_tag)
                if worker is None:
                    self.log.error("MissingWorker{}", worker_tag)
                    continue
                workers.append(worker)
        return Units(workers, self.api)

    def get_mineral_field_split_at_expansion(self, location: ExpansionLocation) -> tuple[Units, Units, Units]:
        """fields with no, one, two miners"""
        count = self.get_assigned_worker_count_at_expansion(location)
        empty_fields = Units([mf for mf in location.mineral_fields if count[mf.tag] == 0], self.api)
        single_mining_fields = Units([mf for mf in location.mineral_fields if count[mf.tag] == 1], self.api)
        double_mining_fields = Units([mf for mf in location.mineral_fields if count[mf.tag] == 2], self.api)
        return empty_fields, single_mining_fields, double_mining_fields

    def has_worker(self, worker: Unit) -> bool:
        return any(exp.has_worker(worker) for exp in self.expansions.values())

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            self.log.warning("SCV-{}-already-assigned-{}", worker, self)
            return False
        for exp in self.expansions.values():
            if exp.add_worker(worker):
                return True
        return False

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
        self.log.warning("unknown-worker-{}", tag)
        return False

    async def update_assignment(self) -> None:
        for exp in self.expansions.values():
            await exp.update_assignment()

    # --- Private

    def _check_for_dead_tags(self):
        # Check for dead tags
        for exp in list(self.expansions.values()):
            if exp.townhall not in self.api.alive_tags:
                self.logger.info("Townhall at {} died", exp)
                self.remove_expansion(exp)
        for exp in self.expansions.values():
            for worker_tag, mineral_tag in list(exp.miners.items()):
                if worker_tag not in self.api.alive_tags or mineral_tag not in self.api.alive_tags:
                    self.logger.info("Empty mineral field={} or dead worker={}", mineral_tag, worker_tag)
                    self.remove_worker(worker_tag)

    def _assign_idle_workers(self) -> bool:
        def worker_filter(unit: Unit) -> bool:
            if self.order.has_order(unit):
                return False
            if unit.is_constructing_scv:
                return False
            if self.has_worker(unit):
                return False
            return True
        assigned = False
        for worker in self.bot.workers.filter(worker_filter):
            if self.add_worker(worker):
                self.logger.debug("Assigning idle worker {}", worker)
                assigned = True
                self.update = True
        return assigned
