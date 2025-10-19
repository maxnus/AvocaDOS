import asyncio
import time

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from sc2bot.core.bot import BotBase
from sc2bot.core.tasks import UnitCountTask, UnitPendingTask, TaskStatus, AttackTask, MoveTask


class ByzBot(BotBase):

    async def on_start(self) -> None:
        await super().on_start()

        cmd = self.add_commander('ProxyMarine')

        # Always produce SCV
        #cmd.tasks.add(UnitCountTask(UnitTypeId.SCV, 19))
        third = self.get_expansion_location(6)
        cc1 = cmd.tasks.add(UnitCountTask(UnitTypeId.COMMANDCENTER, 1, deps=None, position=third))

        # Buildings
        #cmd.tasks.add(MoveTask(self.main_base_ramp.top_center, UnitTypeId.SCV, deps=None))
        supply1 = cmd.tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, deps=cc1))

        proxy_pos = self.get_proxy_location()
        #cmd.tasks.add(MoveTask(proxy_pos, {UnitTypeId.SCV: 2}, deps={supply1: TaskStatus.STARTED}))

        #rax = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 2, deps={supply1: TaskStatus.COMPLETED},
        #                                  position=proxy_pos, distance=10))

        rax = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 3, deps={supply1: TaskStatus.COMPLETED},
                                         position=proxy_pos, distance=10))
        #rax2 = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 1, deps={supply1: TaskStatus.COMPLETED},
        #                                   position=proxy_pos, distance=10))

        #rax2 = cmd.tasks.add(UnitCountTask(UnitTypeId.BARRACKS, 2, deps={rax1: TaskStatus.STARTED}))
        cmd.tasks.add(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, deps={rax: TaskStatus.COMPLETED}))

        cmd.tasks.add(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, deps={rax: TaskStatus.STARTED}))

        # Units
        marines = cmd.tasks.add(UnitCountTask(UnitTypeId.MARINE, 9, deps={rax: TaskStatus.STARTED}))

        # Attack
        attack = cmd.tasks.add(AttackTask(target=self.get_enemy_base_location(), deps={marines: TaskStatus.COMPLETED}))

    async def on_step(self, iteration: int) -> None:
        if iteration == 0:
            self.commander['ProxyMarine'].take_control(self.units | self.structures)
        #await asyncio.sleep(0.1)
        await super().on_step(iteration)


    #async def on_building_construction_started(self, unit: Unit) -> None:
