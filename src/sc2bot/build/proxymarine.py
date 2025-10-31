from sc2.ids.unit_typeid import UnitTypeId

from sc2bot.core.tasks import UnitCountTask, AttackTask

from .buildorder import BuildOrder


class ProxyMarine(BuildOrder):

    def load(self) -> None:
        commander = self.bot.commander

        # SCV
        commander.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        #rax_base = main.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = self.bot.map.get_proxy_location()
        rax = commander.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                          reqs=(UnitTypeId.SCV, 14),
                                          position=proxy_location, distance=10))
        rax2 = commander.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                           reqs=UnitTypeId.BARRACKS,
                                           position=proxy_location, distance=10))

        commander.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        commander.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        commander.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        commander.add_task(AttackTask(target=self.bot.map.enemy_start_locations[0].center))
