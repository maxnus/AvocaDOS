from collections import Counter
from typing import TYPE_CHECKING, Optional

from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.manager import Manager
from sc2bot.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from sc2bot.core.commander import Commander


class MiningManager(Manager):
    assignments: dict[ExpansionLocation, dict[int, int]]
    """location, worker_tag -> mineral_tag"""

    def __init__(self, commander: 'Commander') -> None:
        super().__init__(commander)
        self.assignments = {}

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
        empty_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 0], self.bot)
        single_mining_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 1], self.bot)
        double_mining_fields = Units([mf for mf in expansion.mineral_fields if count[mf.tag] == 2], self.bot)
        return empty_fields, single_mining_fields, double_mining_fields

    def has_worker(self, worker: Unit) -> bool:
        for assignment in self.assignments.values():
            if worker.tag in assignment:
                return True
        return False

    def add_worker(self, worker: Unit) -> bool:
        if self.has_worker(worker):
            self.logger.error("Worker {} already assigned to {}", worker, self)
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

    def _assign_worker(self, expansion: ExpansionLocation, worker: Unit, mineral: Unit) -> None:
        if expansion not in self.assignments:
            raise ValueError(f"Expansion {expansion} not in {self}")
        if worker.is_carrying_minerals:
            target_point = expansion.mining_return_targets.get(mineral.tag)
        else:
            target_point = expansion.mining_gather_targets.get(mineral.tag)
        if target_point is not None:
            self.commander.order.move(worker, target_point)
        else:
            self.logger.error("Missing target point for mineral {}", mineral)
        self.assignments[expansion][worker.tag] = mineral.tag
        self.logger.info("Assigning {} to {}", worker, mineral)

    def remove_worker(self, unit: Unit | int) -> bool:
        if isinstance(unit, Unit):
            tag = unit.tag
        else:
            tag = unit
        for assignment in self.assignments.values():
            if tag in assignment:
                assignment.pop(tag)
                return True
        #self.logger.debug("Worker {} not found in {}", unit, self)
        return False

    def get_townhall(self, expansion: ExpansionLocation) -> Optional[Unit]:
        return self.bot.townhalls.closest_to(expansion.center)

    async def assign_miners_at_expansion(self, expansion: ExpansionLocation) -> None:
        if expansion not in self.assignments:
            raise ValueError(f"unknown expansion: {expansion}")

        self.assignments[expansion].clear()

        # We accept all townhalls, not just the commanders
        townhall = self.get_townhall(expansion)
        if townhall is None:
            return

        # TODO: long distance mining?
        if not expansion.mineral_fields:
            self.logger.info("No minerals at {}", expansion)
            return

        # should already be sorted
        minerals = expansion.mineral_fields.sorted_by_distance_to(townhall)
        # Method 1
        for mineral in 2 * minerals:
            workers = await self.commander.pick_workers(mineral.position, number=1)
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

    async def on_step(self, step: int) -> None:
        # TODO: check dead tags
        for expansion, exp_assignment in self.assignments.items():
            expansion.debug_show()
            townhall = self.get_townhall(expansion)
            if townhall is None:
                self.logger.error("No townhall at {}", expansion)
                continue

            for worker_tag, mineral_tag in exp_assignment.items():
                worker = self.commander.workers.find_by_tag(worker_tag)
                if worker is None:
                    self.logger.error("Invalid worker tag: {}", worker_tag)
                    continue

                mineral_field = expansion.mineral_fields.find_by_tag(mineral_tag)
                if mineral_field is None:
                    self.logger.error("Invalid mineral field tag: {}", mineral_tag)
                    continue

                if worker.is_carrying_minerals:
                    target_point = expansion.mining_return_targets.get(mineral_tag)
                    if target_point is None:
                        self.logger.error("Invalid mining return target for: {}", mineral_tag)
                        continue
                    target = townhall
                else:
                    target_point = expansion.mining_gather_targets.get(mineral_tag)
                    if target_point is None:
                        self.logger.error("Invalid mining gather target for: {}", mineral_tag)
                        continue
                    target = mineral_field

                distance = worker.distance_to(target_point)
                if 0.75 < distance < 2:
                    self.commander.order.move(worker, target_point)
                    self.commander.order.smart(worker, target, queue=True)
                # elif worker.is_idle:
                #     self.logger.info("Restarting idle worker {}", worker)
                #     if distance <= 0.75:
                #         self.commander.order.smart(worker, target, force=True)
                #     elif distance >= 2:
                #         self.commander.order.move(worker, target_point, force=True)
