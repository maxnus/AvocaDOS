from sc2.ids.unit_typeid import UnitTypeId

from sc2bot.core.tasks import UnitCountTask, AttackTask

from .buildorder import BuildOrder


class MassMarine(BuildOrder):

    def load(self) -> None:
        commander = self.bot.commander

        # SCV
        commander.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        rax1 = commander.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 14)))
        #rax2 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2, reqs=(UnitTypeId.SCV, 15)))
        #rax3 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 3, reqs=(UnitTypeId.SCV, 16)))
        #rax4 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4, reqs=(UnitTypeId.SCV, 17)))
        #rax5 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 5, reqs=(UnitTypeId.SCV, 18)))
        #rax6 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 19)))

        commander.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        commander.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))

        commander.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
