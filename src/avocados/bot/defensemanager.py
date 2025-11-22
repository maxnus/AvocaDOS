from typing import ClassVar

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from avocados import api
from avocados.bot.expansionmanager import ExpansionManager
from avocados.core.constants import WORKER_TYPE_IDS, STATIC_DEFENSE_TYPE_IDS, TOWNHALL_TYPE_IDS
from avocados.core.manager import BotManager


class DefenseManager(BotManager):
    expand: ExpansionManager
    defense_distance: ClassVar[float] = 8.0

    def __init__(self, *, expansion_manager: ExpansionManager) -> None:
        super().__init__()
        self.expand = expansion_manager

    async def on_step(self, step: int) -> None:
        for expansion in self.expand.expansions.values():
            enemies = api.all_enemy_units.closer_than(self.defense_distance,
                                                      expansion.location.mineral_line_center)
            if not enemies:
                continue
            if len(enemies) == 1 and enemies.first.type_id in WORKER_TYPE_IDS:
                continue

            for enemy in enemies:
                units_defending = api.ext.get_units_with_target(
                    enemy, condition=lambda u: u.distance_to(enemy) <= self.defense_distance)
                for defender in units_defending:
                    api.order.attack(defender, enemy)

                if enemy.is_flying:
                    continue

                required_defender = self._workers_to_defend(enemy) - len(units_defending)
                if required_defender <= 0:
                    continue
                # TODO: order army units / squads
                defenders = self.expand.request_workers(enemy.position, number=required_defender,
                                                        max_distance=self.defense_distance)
                for defender in defenders:
                    #self.logger.debug("Ordering {} to defend against {}", defender.value, enemy)
                    api.order.attack(defender.access(), enemy)

    def _workers_to_defend(self, target: Unit) -> int:
        if target.type_id in WORKER_TYPE_IDS:
            return 1
        if target.type_id in {UnitTypeId.REAPER, UnitTypeId.ZERGLING, UnitTypeId.ADEPT}:
            return 2
        if target.type_id == UnitTypeId.PYLON:
            return 4
        if target.type_id in STATIC_DEFENSE_TYPE_IDS:
            return 4
        if target.type_id in {UnitTypeId.ZEALOT, UnitTypeId.STALKER}:
            return 4
        if target.type_id in TOWNHALL_TYPE_IDS:
            return 6
        return 3
