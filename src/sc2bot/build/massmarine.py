from sc2.ids.unit_typeid import UnitTypeId

from sc2bot.core.tasks import UnitCountTask, HandoverUnitsTask, AttackTask

from .buildorder import BuildOrder


class MassMarine(BuildOrder):

    def load(self) -> None:
        main = self.bot.add_commander('Main')

        # SCV
        main.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        rax1 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 14)))
        #rax2 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2, reqs=(UnitTypeId.SCV, 15)))
        #rax3 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 3, reqs=(UnitTypeId.SCV, 16)))
        #rax4 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4, reqs=(UnitTypeId.SCV, 17)))
        #rax5 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 5, reqs=(UnitTypeId.SCV, 18)))
        #rax6 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 19)))

        main.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        main.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        main.add_task(HandoverUnitsTask(UnitTypeId.MARINE, 'Marines', reqs=(UnitTypeId.MARINE, 12), repeat=True))

        marines = self.bot.add_commander('Marines')
        marines.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
