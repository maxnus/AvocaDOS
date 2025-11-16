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


def worker_is_mining(worker: Unit, *,
                     expected_location: Optional[Point2] = None,
                     location_tolerance: float = 1.0) -> bool:
    if not worker.orders:
        return False
    order = worker.orders[0]
    if order.ability.id not in {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN, AbilityId.MOVE}:
        return False
    if (expected_location is not None and isinstance(order.target, Point2)
            and order.target.distance_to(expected_location) > location_tolerance):
        return False
    return True


class Expansion(BotObject):
    townhall: int
    location: ExpansionLocation
    miners: dict[int, Point2]

    def __init__(self, bot: 'AvocaDOS', townhall: Unit, location: ExpansionLocation) -> None:
        super().__init__(bot)
        self.townhall = townhall.tag
        self.location = location
        self.miners = {}

    def get_assignment(self) -> dict[Unit, Unit]:
        assignment = {}
        for worker_tag, mineral_position in self.miners.items():
            worker = self.api.workers.by_tag(worker_tag)
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
        empty_fields, single_fields, double_fields, oversaturated_fields = self.get_mineral_field_split()
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
        empty_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 0], self.api)
        single_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 1], self.api)
        double_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] == 2], self.api)
        oversaturated_mining_fields = Units([mf for mf in self.location.mineral_fields if count[mf.position] >= 3],
                                            self.api)
        return empty_fields, single_mining_fields, double_mining_fields, oversaturated_mining_fields

    async def update_assignment(self) -> None:
        self.miners.clear()
        # TODO: long distance mining?
        if not self.location.mineral_fields:
            self.log.caution("NoMinerals_{}", self.location)
            return
        # should already be sorted
        minerals = self.location.mineral_fields.sorted_by_distance_to(self.location.center)
        for mineral in 2 * minerals:
            worker = (await self.bot.pick_worker(mineral.position))[0]
            if worker is not None:
                self.logger.debug("Assigning {} to {}", worker.peak(), mineral)
                self.miners[worker.access().tag] = mineral.position

    def speed_mine(self) -> None:
        townhall = self.bot.townhalls.find_by_tag(self.townhall)
        if townhall is None:
            self.log.error("NoTownhall-{}", self.townhall)
            return

        enemies = self.api.enemy_units.closer_than(8, townhall)

        for worker_tag, mineral_position in self.miners.items():
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

            mineral_field = self.location.get_mineral_field(mineral_position)
            if mineral_field is None:
                self.log.error("InvalidMineralTag-{}", mineral_position)
                continue

            if worker.is_carrying_minerals:
                target_point = self.location.mining_return_targets.get(mineral_position)
                if target_point is None:
                    self.log.error("InvalidReturnTarget-{}", mineral_position)
                    continue
                target = townhall
            else:
                target_point = self.location.mining_gather_targets.get(mineral_position)
                if target_point is None:
                    self.log.error("InvalidGatherTarget-{}", mineral_position)
                    continue
                target = mineral_field

            distance = worker.distance_to(target_point)

            if 0.75 < distance < 2:# and len(worker.orders) != 2:
                self.order.move(worker, target_point)
                self.order.smart(worker, target, queue=True)

            # Get back to work
            elif not worker_is_mining(worker, expected_location=target_point):
                # self.logger.debug("Sending worker {} with order target {} and ability id {} back to mineral work,"
                #                   "target: {}",
                #                   worker, worker.orders[0].target if worker.orders else None,
                #                   worker.orders[0].ability if worker.orders else None,
                #                   target)
                self.bot.order.smart(worker, target, force=True)

            # elif worker.is_idle:
            #     self.logger.info("Restarting idle worker {}", worker)
            #     if distance <= 0.75:
            #         self.commander.order.smart(worker, target, force=True)
            #     elif distance >= 2:
            #         self.commander.order.move(worker, target_point, force=True)


class ExpansionManager(BotManager):
    expansions: dict[ExpansionLocation, Expansion]
    """location -> townhall tag"""

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.expansions = {}

    def __len__(self) -> int:
        return len(self.expansions)

    def __contains__(self, expansion: ExpansionLocation) -> bool:
        return expansion in self.expansions

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

    def get_required_workers(self) -> int:
        return sum(exp.get_required_workers() for exp in self.expansions.values())

    def get_missing_workers(self) -> int:
        return sum(exp.get_missing_workers() for exp in self.expansions.values())

    def get_assigned_worker_count_at_expansion(self, location: ExpansionLocation) -> Counter[Point2]:
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

    def get_mineral_fields(self) -> Units:
        all_minerals = [mf for exp in self.expansions.keys() for mf in exp.mineral_fields]
        return Units(all_minerals, self.api)

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
            for worker_tag, mineral_position in list(exp.miners.items()):
                if worker_tag not in self.api.alive_tags:
                    self.logger.debug("Dead worker={}", worker_tag)
                    self.remove_worker(worker_tag)
                if exp.location.get_mineral_field(mineral_position) is None:
                    self.logger.debug("Missing mineral field={}", mineral_position)
                    self.remove_worker(worker_tag)

    def _assign_idle_workers(self) -> None:
        def worker_filter(unit: Unit) -> bool:
            if self.order.has_order(unit):
                return False
            if unit.is_constructing_scv:
                return False
            if self.has_worker(unit):
                return False
            return True
        for worker in self.bot.workers.filter(worker_filter):
            if self.add_worker(worker):
                self.logger.debug("Assigning idle worker {}", worker)
