import asyncio
import time

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit

from sc2bot.core.bot import BotBase
from sc2bot.core.tasks import UnitCountTask, UnitPendingTask, TaskStatus, AttackTask, MoveTask, ResearchTask, \
    HandoverUnitsTask


class SegFault0x(BotBase):

    def load_strategy(self) -> None:
        cmd = self.add_commander('ProxyMarine')
        atk = self.add_commander('ATK')

        # Always produce SCV
        cmd.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        cmd.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        proxy_location = self.map.enemy_expansions[4][0]
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

        atk.add_task(AttackTask(target=self.map.enemy_base))


    async def on_step(self, step: int) -> None:
        cmd = self.commander['ProxyMarine']
        if step == 0:
            cmd.add_units(self.units | self.structures)
        cmd.resources.reset(self.minerals, self.vespene)
        await super().on_step(step)

    #async def on_building_construction_started(self, unit: Unit) -> None:
