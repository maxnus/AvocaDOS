from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId

from sc2bot.core.manager import Manager
from sc2bot.core.tasks import UnitCountTask, AttackTask

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class BuildOrderManager(Manager):
    build: Optional[str]

    def __init__(self, bot: 'AvocaDOS', build: Optional[str] = None) -> None:
        super().__init__(bot)
        self.build = build or 'mass_marine'

    async def on_start(self) -> None:
        func = getattr(self, f'load_{self.build}')
        func()

    def load_mass_marine(self) -> None:
        bot = self.bot

        # SCV
        bot.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        rax1 = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 14)))
        #rax2 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2, reqs=(UnitTypeId.SCV, 15)))
        #rax3 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 3, reqs=(UnitTypeId.SCV, 16)))
        #rax4 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4, reqs=(UnitTypeId.SCV, 17)))
        #rax5 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 5, reqs=(UnitTypeId.SCV, 18)))
        #rax6 = main.add_task(UnitCountTask(UnitTypeId.BARRACKS, 6, reqs=(UnitTypeId.SCV, 19)))

        bot.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        bot.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))

        bot.add_task(AttackTask(target=bot.map.enemy_start_locations[0].center))

    def load_proxy_marine(self) -> None:
        bot = self.bot

        # SCV
        bot.add_task(UnitCountTask(UnitTypeId.SCV, 19))

        # Buildings
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        #rax_base = main.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = bot.map.get_proxy_location()
        rax = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                               reqs=(UnitTypeId.SCV, 14),
                                               position=proxy_location, distance=10))
        rax2 = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                                reqs=UnitTypeId.BARRACKS,
                                                position=proxy_location, distance=10))

        bot.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        bot.add_task(UnitCountTask(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        bot.add_task(AttackTask(target=bot.map.enemy_start_locations[0].center))

    def load_proxy_reaper(self) -> None:
        bot = self.bot

        # Always produce SCV until 16 + 3 + 2 = 21
        bot.add_task(UnitCountTask(UnitTypeId.SCV, 21))

        # Buildings
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        rax_base = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = bot.map.get_proxy_location()
        rax = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS, 2,
                                               reqs=(UnitTypeId.SCV, 14),
                                               position=proxy_location, distance=10))
        rax2 = bot.add_task(UnitCountTask(UnitTypeId.BARRACKS, 4,
                                                reqs=UnitTypeId.BARRACKS,
                                                position=proxy_location, distance=10))

        #main.add_task(UnitCountTask(UnitTypeId.REFINERY, 2, reqs=('S', 16)))
        bot.add_task(UnitCountTask(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        bot.add_task(UnitCountTask(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # --- Upgrades
        #main.add_task(UnitCountTask(UnitTypeId.BARRACKSREACTOR, deps=rax_base, priority=100))

        # Units
        #main.add_task(UnitCountTask(UnitTypeId.REAPER, 100, reqs=UnitTypeId.BARRACKS))
        #main.add_task(HandoverUnitsTask(UnitTypeId.REAPER, 'Reapers', reqs=(UnitTypeId.REAPER, 4), repeat=True))

        bot.add_task(UnitCountTask(UnitTypeId.REAPER, 100, reqs=UnitTypeId.BARRACKS))
        bot.add_task(AttackTask(target=bot.map.enemy_start_locations[0].center))
