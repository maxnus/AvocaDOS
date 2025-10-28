from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId

from sc2bot.core.tasks import UnitCountTask, ResearchTask, HandoverUnitsTask, AttackTask

from .buildorder import BuildOrder


class ProxyReaper(BuildOrder):

    def load(self) -> None:
        cmd = self.bot.add_commander('ProxyMarine')
        atk = self.bot.add_commander('ATK')

        # Always produce SCV
        cmd.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        cmd.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        proxy_location = self.bot.map.enemy_expansions[4][0]
        rax = cmd.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                         reqs=(UnitTypeId.SCV, 14),
                                         position=proxy_location, distance=10))
        rax2 = cmd.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                          reqs=UnitTypeId.BARRACKS,
                                          position=proxy_location, distance=10))
        rax_base = cmd.add_task(UnitCountTask(UnitTypeId.BARRACKS, 5, deps=rax2))

        cmd.add_task(UnitCountTask(UnitTypeId.REFINERY, 1, reqs=('S', 17)))
        cmd.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        cmd.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        cmd.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        cmd.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # --- Upgrades
        cmd.add_task(UnitCountTask(UnitTypeId.BARRACKSTECHLAB, deps=rax_base, priority=100))
        cmd.add_task(ResearchTask(UpgradeId.STIMPACK, reqs=UnitTypeId.BARRACKSTECHLAB, priority=100))
        cmd.add_task(ResearchTask(UpgradeId.SHIELDWALL, reqs=UpgradeId.STIMPACK, priority=100))

        # Units
        cmd.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        cmd.add_task(HandoverUnitsTask(UnitTypeId.MARINE, 'ATK', reqs=(UnitTypeId.MARINE, 6), repeat=True))

        atk.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
