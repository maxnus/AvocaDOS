from typing import TYPE_CHECKING, ClassVar

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from avocados.core.constants import WORKER_TYPE_IDS, STATIC_DEFENSE_TYPE_IDS, TOWNHALL_TYPE_IDS
from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class DefenseManager(BotManager):
    defense_distance: ClassVar[float] = 10.0

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)

    async def on_step(self, step: int) -> None:
        for townhall in self.api.townhalls:
            enemies = self.api.all_enemy_units.closer_than(self.defense_distance, townhall)
            if not enemies:
                continue
            if len(enemies) == 1 and enemies.first.type_id in WORKER_TYPE_IDS:
                continue

            for enemy in enemies:
                units_defending = self.ext.get_units_with_target(
                    enemy, condition=lambda u: u.distance_to(enemy) <= self.defense_distance)
                for defender in units_defending:
                    self.order.attack(defender, enemy)

                #self.logger.debug("Units already defending: {}", units_defending)

                required_defender = self._workers_to_defend(enemy) - len(units_defending)
                if required_defender <= 0:
                    continue
                # TODO: order army units / squads
                defenders = self.mining.request_workers(enemy.position, number=required_defender,
                                                        max_distance=self.defense_distance)
                for defender in defenders:
                    #self.logger.debug("Ordering {} to defend against {}", defender.value, enemy)
                    self.order.attack(defender.access(), enemy)

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
