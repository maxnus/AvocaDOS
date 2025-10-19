import asyncio
import time

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit

from sc2bot.core.bot import BotBase
from sc2bot.core.tasks import UnitCountTask, UnitPendingTask, TaskStatus, AttackTask, MoveTask, ResearchTask


class SegFault0x(BotBase):

    # def load_strategy(self) -> None:
    #     cmd = self.add_commander('ProxyMarine')
    #     tasks = cmd.tasks
    #     base = self.get_base_location()
    #
    #     # Always produce SCV
    #     tasks.add(UnitCountTask(UnitTypeId.SCV, 19))
    #
    #     # Buildings
    #     supply1 = tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
    #
    #     #rax = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 2, deps={supply1: TaskStatus.COMPLETED},
    #     #                                  position=proxy_pos, distance=10))
    #
    #     proxy_location = self.map.enemy_expansions[4][0]
    #     rax = tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 2,
    #                                   reqs=(UnitTypeId.SCV, 14),
    #                                   position=proxy_location, distance=10))
    #
    #     rax2 = tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 4,
    #                                    deps=rax,
    #                                    position=proxy_location, distance=10))
    #
    #     ref = tasks.add(UnitCountTask(UnitTypeId.REFINERY, 1, reqs=('S', 19)))
    #
    #     #rax2 = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 1, deps={supply1: TaskStatus.COMPLETED},
    #     #                                   position=proxy_pos, distance=10))
    #     #rax2 = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 2, deps={rax1: TaskStatus.STARTED}))
    #     tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
    #     tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
    #     rax_base = tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 5, reqs=UnitTypeId.ORBITALCOMMAND))
    #
    #     # --- Upgrades
    #     tasks.add(UnitCountTask(UnitTypeId.TECHLAB, 1, deps=rax_base, reqs=('G', 25), position=base, priority=100))
    #     tasks.add(ResearchTask(UpgradeId.STIMPACK, reqs=UnitTypeId.TECHLAB, position=base, priority=100))
    #     tasks.add(ResearchTask(UpgradeId.COMBATSHIELD, reqs=UpgradeId.STIMPACK, position=base, priority=100))
    #
    #     tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))
    #
    #     tasks.add(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))
    #
    #     # Units
    #     marines = tasks.add(UnitCountTask(UnitTypeId.MARINE, 9999, reqs=UnitTypeId.BARRACKS))
    #
    #     # Attack
    #     attack = tasks.add(AttackTask(target=self.get_enemy_base_location(), reqs=(UnitTypeId.MARINE, 8)))

    def load_strategy(self) -> None:
        cmd = self.add_commander('ProxyMarine')
        base = self.get_base_location()
        tasks = cmd.tasks
        supply = tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, priority=100))
        ref = tasks.add(UnitCountTask(UnitTypeId.REFINERY))
        rax = tasks.add(UnitCountTask(UnitTypeId.BARRACKS))
        tasks.add(UnitCountTask(UnitTypeId.BARRACKSTECHLAB, deps=rax, reqs=('G', 25), position=base, distance=20, priority=100))
        tasks.add(ResearchTask(UpgradeId.STIMPACK, reqs=UnitTypeId.BARRACKSTECHLAB, position=base, priority=100))
        tasks.add(ResearchTask(UpgradeId.COMBATSHIELD, reqs=UpgradeId.STIMPACK, position=base, priority=100))

    async def on_step(self, step: int) -> None:
        if step == 0:
            cmd = self.commander['ProxyMarine']
            cmd.take_control(self.units | self.structures)
        #await asyncio.sleep(0.1)
        await super().on_step(step)

    #async def on_building_construction_started(self, unit: Unit) -> None:
