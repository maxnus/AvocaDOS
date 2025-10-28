from typing import TYPE_CHECKING, Optional

from sc2.unit import Unit

from sc2bot.core.manager import Manager
from sc2bot.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from sc2bot.core.commander import Commander


class MiningManager(Manager):
    assignment: dict[ExpansionLocation, dict[int, int]]

    def __init__(self, commander: 'Commander') -> None:
        super().__init__(commander)
        self.assignment = {}

    async def add_expansion(self, expansion: ExpansionLocation) -> None:
        self.assignment[expansion] = {}
        await self.assign_miners()

    async def remove_expansion(self, expansion: ExpansionLocation) -> None:
        self.assignment.pop(expansion)
        await self.assign_miners()

    def get_townhall(self, expansion: ExpansionLocation) -> Optional[Unit]:
        return self.bot.townhalls.closest_to(expansion.center)

    async def assign_miners(self) -> None:
        for expansion in self.assignment.keys():
            exp_assignment = self.assignment[expansion] = {}

            # We accept all townhalls, not just the commanders
            townhall = self.get_townhall(expansion)
            if townhall is None:
                continue

            # TODO: long distance mining?
            if not expansion.mineral_fields:
                self.logger.info("No minerals at {}", expansion)
                continue

            minerals = sorted(expansion.mineral_fields, key=lambda m: m.distance_to(townhall))
            for mineral in 2*minerals:
                workers = await self.commander.pick_workers(mineral.position, number=1)
                for worker, _ in workers:
                    if worker.is_carrying_minerals:
                        target_point = expansion.mining_return_targets.get(mineral.tag)
                    else:
                        target_point = expansion.mining_gather_targets.get(mineral.tag)
                    if target_point is not None:
                        self.commander.order.move(worker, target_point)
                    else:
                        self.logger.error("Missing target point for mineral {}", mineral)
                    exp_assignment[worker.tag] = mineral.tag
                    self.logger.info("Assigning {} to {}", worker, mineral)

    async def on_step(self, step: int) -> None:
        # TODO: check dead tags

        for expansion, exp_assignment in self.assignment.items():

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

                if worker.is_carrying_minerals: #worker.is_returning:
                    target_point = expansion.mining_return_targets.get(mineral_tag)
                    #target_point2 = expansion.mining_gather_targets.get(mineral_tag)
                    if target_point is None:
                        self.logger.error("Invalid mining return target for: {}", mineral_tag)
                        continue
                    target = townhall
                else:
                    target_point = expansion.mining_gather_targets.get(mineral_tag)
                    #target_point2 = expansion.mining_return_targets.get(mineral_tag)
                    if target_point is None:
                        self.logger.error("Invalid mining gather target for: {}", mineral_tag)
                        continue
                    target = mineral_field

                distance = worker.distance_to(target_point)
                if 0.75 < distance < 2:
                    self.commander.order.move(worker, target_point)
                    self.commander.order.smart(worker, target, queue=True)
                    #self.commander.order.move(worker, target_point2, queue=True)
                # elif distance <= 0.75:
                #    self.commander.order.smart(worker, target)
                # elif distance >= 2:
                #     self.commander.order.move(worker, target_point)
