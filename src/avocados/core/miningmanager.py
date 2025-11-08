from collections import Counter
from time import perf_counter
from typing import TYPE_CHECKING, Optional

from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.manager import BotManager
from avocados.core.util import CallbackOnAccess
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class MiningManager(BotManager):
    assignments: dict[ExpansionLocation, dict[int, int]]
    """location, worker_tag -> mineral_tag"""

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.assignments = {}

    async def on_step_start(self, step: int) -> None:
        self._check_for_dead_tags()

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        self._assign_idle_workers()
        self._speed_mine()
        self.timings['step'].add(t0)

    async def add_expansion(self, expansion: ExpansionLocation) -> None:
        self.assignments[expansion] = {}
        await self.assign_miners()

    async def remove_expansion(self, expansion: ExpansionLocation) -> None:
        self.assignments.pop(expansion)
        await self.assign_miners()

    def get_assigned_worker_count_at_expansion(self, expansion: ExpansionLocation) -> Counter[int]:
        if expansion not in self.assignments:
            raise ValueError(f"Expansion {expansion} not in {self}")
        counter = Counter(self.assignments[expansion].values())
        return counter

    def get_mineral_field_split_at_expansion(self, expansion: ExpansionLocation) -> tuple[Units, Units, Units]:
        count = self.get_assigned_worker_count_at_expansion(expansion)
        empty_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 0], self.api)
        single_mining_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 1], self.api)
        double_mining_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 2], self.api)
        return empty_fields, single_mining_fields, double_mining_fields

    def has_worker(self, worker: Unit) -> bool:
        for assignment in self.assignments.values():
            if worker.tag in assignment:
                return True
        return False

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            self.logger.warning("Worker {} already assigned to {}", worker, self)
            if self.debug:
                self.debug.text("Worker already assigned", worker, size=16, color=(255, 0, 0), duration=10)
            return False

        for expansion, assignment in self.assignments.items():
            empty_fields, single_fields, double_fields = self.get_mineral_field_split_at_expansion(expansion)
            if empty_fields:
                mf = empty_fields.closest_to(worker)
            elif single_fields:
                mf = single_fields.closest_to(worker)
            elif double_fields:
                mf = double_fields.closest_to(worker)
            else:
                continue
            self._assign_worker(expansion, worker, mf)
            return True

        return False

    def request_workers(self, location: Point2, *, number: int = 1,
                        max_distance: Optional[float] = None) -> list[CallbackOnAccess[Unit]]:
        workers = Units([], self.api)
        for expansion, assignment in self.assignments.items():
            for worker_tag in assignment:
                worker = self.bot.workers.find_by_tag(worker_tag)
                if worker is not None:
                    workers.append(worker)
                else:
                    self.log.error("Worker with tag {} not found", worker_tag)
        if max_distance is not None:
            workers = workers.closer_than(max_distance, location)
        if not workers:
            return []
        workers = workers.closest_n_units(location, number)
        callbacks = [CallbackOnAccess(w, self.remove_worker, w) for w in workers]
        return callbacks

    def remove_worker(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        for assignment in self.assignments.values():
            if tag in assignment:
                #self.logger.debug("Removing worker {}", unit)
                assignment.pop(tag)
                return True
        #self.logger.debug("Worker {} not found in {}", unit, self)
        return False

    async def assign_miners_at_expansion(self, expansion: ExpansionLocation) -> None:
        if expansion not in self.assignments:
            raise ValueError(f"unknown expansion: {expansion}")

        self.assignments[expansion].clear()

        townhall = self._get_townhall(expansion)
        if townhall is None:
            return

        # TODO: long distance mining?
        if not expansion.mineral_fields:
            self.log.caution("No minerals at {}", expansion)
            return

        # should already be sorted
        minerals = expansion.mineral_fields.sorted_by_distance_to(townhall)
        # Method 1
        for mineral in 2 * minerals:
            workers = await self.bot.pick_workers(mineral.position, number=1)
            for worker, _ in workers:
                self._assign_worker(expansion, worker, mineral)

        # Method 2
        # free_slots = {mineral: 2 for mineral in minerals}
        # workers = await self.commander.pick_workers(expansion.mineral_field_center, number=2 * len(minerals))
        # self.logger.info("Assigning {} workers to {} mineral fields", len(workers), len(minerals))
        # for worker, _ in workers:
        #     if not free_slots:
        #         break
        #
        #     free_minerals = Units(free_slots.keys(), self.bot)
        #     mineral = free_minerals.closest_to(worker)
        #     assignment[worker.tag] = mineral.tag
        #     self.logger.info("Assigning {} to {}", worker, mineral)
        #
        #     if worker.is_carrying_minerals:
        #         target_point = expansion.mining_return_targets.get(mineral.tag)
        #     else:
        #         target_point = expansion.mining_gather_targets.get(mineral.tag)
        #     if target_point is not None:
        #         self.commander.order.move(worker, target_point)
        #     else:
        #         self.logger.error("Missing target point for mineral {}", mineral)
        #
        #     free_slots[mineral] -= 1
        #     if free_slots[mineral] == 0:
        #         free_slots.pop(mineral)

    async def assign_miners(self) -> None:
        for expansion in self.assignments:
            await self.assign_miners_at_expansion(expansion)

    # --- Private

    def _get_townhall(self, expansion: ExpansionLocation) -> Optional[Unit]:
        townhalls = self.api.townhalls
        if not townhalls:
            return None
        return townhalls.closest_to(expansion.center)

    def _assign_worker(self, expansion: ExpansionLocation, worker: Unit, mineral: Unit) -> None:
        if expansion not in self.assignments:
            raise ValueError(f"Expansion {expansion} not in {self}")
        # if worker.is_carrying_minerals:
        #     target_point = expansion.mining_return_targets.get(mineral.tag)
        # else:
        #     target_point = expansion.mining_gather_targets.get(mineral.tag)
        # if target_point is not None:
        #     self.bot.order.move(worker, target_point)
        # else:
        #     self.logger.error("Missing target point for mineral {}", mineral)
        self.assignments[expansion][worker.tag] = mineral.tag
        #self.logger.debug("Assigning {} to {}", worker, mineral)

    def _check_for_dead_tags(self):
        for expansion, exp_assignment in self.assignments.items():
            for worker_tag in list(exp_assignment.keys()):
                mineral_tag = exp_assignment[worker_tag]
                if worker_tag not in self.api.alive_tags or mineral_tag not in self.api.alive_tags:
                    self.logger.info("Empty mineral field={} or dead worker={}", mineral_tag, worker_tag)
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
            self.add_worker(worker)

    def _speed_mine(self) -> None:
        for expansion in self.assignments:
            self._speed_mine_at_expansion(expansion)

    def _speed_mine_at_expansion(self, expansion: ExpansionLocation) -> None:
        if expansion not in self.assignments:
            raise ValueError(f"unknown expansion: {expansion}")
        assignment = self.assignments[expansion]

        townhall = self._get_townhall(expansion)
        if townhall is None:
            self.log.error("No townhall at {}", expansion)
            return

        enemies = self.api.enemy_units.closer_than(8, townhall)

        for worker_tag, mineral_tag in assignment.items():
            worker = self.bot.workers.find_by_tag(worker_tag)
            if worker is None:
                self.log.error("Invalid worker tag: {}", worker_tag)
                continue

            # Defend yourself
            if worker.weapon_ready:
                close_enemies = enemies.in_attack_range_of(worker)
                if close_enemies:
                    worker.attack(close_enemies.closest_to(worker))
                    continue

            mineral_field = expansion.mineral_fields.find_by_tag(mineral_tag)
            if mineral_field is None:
                self.log.error("Invalid mineral field tag: {}", mineral_tag)
                continue

            if worker.is_carrying_minerals:
                target_point = expansion.mining_return_targets.get(mineral_tag)
                if target_point is None:
                    self.log.error("Invalid mining return target for: {}", mineral_tag)
                    continue
                target = townhall
            else:
                target_point = expansion.mining_gather_targets.get(mineral_tag)
                if target_point is None:
                    self.log.error("Invalid mining gather target for: {}", mineral_tag)
                    continue
                target = mineral_field

            distance = worker.distance_to(target_point)
            if 0.75 < distance < 2:
                self.bot.order.move(worker, target_point)
                self.bot.order.smart(worker, target, queue=True)

            # Get back to work
            elif not worker.orders or worker.orders[0].target not in {townhall, mineral_field}:
                self.bot.order.smart(worker, target)

            # elif worker.is_idle:
            #     self.logger.info("Restarting idle worker {}", worker)
            #     if distance <= 0.75:
            #         self.commander.order.smart(worker, target, force=True)
            #     elif distance >= 2:
            #         self.commander.order.move(worker, target_point, force=True)
