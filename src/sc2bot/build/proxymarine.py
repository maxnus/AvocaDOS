from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId

from sc2bot.core.tasks import UnitCountTask, ResearchTask, HandoverUnitsTask, AttackTask

from .buildorder import BuildOrder


class ProxyMarine(BuildOrder):

    def load(self) -> None:
        main = self.bot.add_commander('Main')

        # SCV
        main.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        #rax_base = main.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = self.bot.map.get_proxy_location()
        rax = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                          reqs=(UnitTypeId.SCV, 14),
                                          position=proxy_location, distance=10))
        rax2 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                           reqs=UnitTypeId.BARRACKS,
                                           position=proxy_location, distance=10))

        main.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        main.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        main.add_task(HandoverUnitsTask(UnitTypeId.MARINE, 'Marines', reqs=(UnitTypeId.MARINE, 8), repeat=True))

        marines = self.bot.add_commander('Marines')
        marines.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
