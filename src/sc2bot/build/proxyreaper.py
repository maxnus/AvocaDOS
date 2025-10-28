from sc2.ids.unit_typeid import UnitTypeId

from sc2bot.core.tasks import UnitCountTask, HandoverUnitsTask, AttackTask, MiningTask

from .buildorder import BuildOrder


class ProxyReaper(BuildOrder):

    def load(self) -> None:
        main = self.bot.add_commander('Main')
        reapers = self.bot.add_commander('Reapers')

        main.add_task(MiningTask(priority=10))

        # Always produce SCV until 16 + 3 + 2 = 21
        main.add_task(UnitCountTask(UnitTypeId.SCV, 21))

        # Buildings
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        rax_base = main.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = self.bot.map.get_proxy_location()
        rax = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                         reqs=(UnitTypeId.SCV, 14),
                                         position=proxy_location, distance=10))
        rax2 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                          reqs=UnitTypeId.BARRACKS,
                                          position=proxy_location, distance=10))

        main.add_task(UnitCountTask(UnitTypeId.REFINERY, 1, reqs=('S', 17)))
        main.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        main.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # --- Upgrades
        main.add_task(UnitCountTask(UnitTypeId.BARRACKSREACTOR, deps=rax_base, priority=100))

        # Units
        main.add_task(UnitCountTask(UnitTypeId.REAPER, 100, reqs=UnitTypeId.BARRACKS))
        main.add_task(HandoverUnitsTask(UnitTypeId.REAPER, 'Reapers', reqs=(UnitTypeId.REAPER, 4), repeat=True))

        reapers.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
