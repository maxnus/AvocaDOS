from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId

from avocados.core.botobject import BotObject
from avocados.core.objective import UnitCountObjective, AttackObjective, DefenseObjective

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class BuildOrderManager(BotObject):
    build: Optional[str]

    def __init__(self, bot: 'AvocaDOS', build: Optional[str] = None) -> None:
        super().__init__(bot)
        self.build = build

    async def on_start(self) -> None:
        if self.build:
            func = getattr(self, f'load_{self.build}')
            func()

    def load_mass_marine(self) -> None:
        bot = self.bot

        # SCV
        bot.objectives.add(UnitCountObjective(UnitTypeId.SCV, 19))

        # Buildings
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))

        rax123 = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 3, reqs=(UnitTypeId.SCV, 14)))
        rax456 = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 6, reqs=('S', 23)))

        bot.objectives.add(UnitCountObjective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 18)))
        for number in range(3, 30):
            bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, number, reqs=('S', number * 8 + 2)))

        # Units
        bot.objectives.add(UnitCountObjective(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))

        bot.objectives.add(DefenseObjective(target=bot.map.ramp_defense_location, strength=6))
        bot.objectives.add(AttackObjective(target=bot.map.enemy_start_locations[0].center, minimum_size=6,
                                           reqs=(UnitTypeId.MARINE, 6)))

    def load_proxy_marine(self) -> None:
        bot = self.bot

        # SCV
        bot.objectives.add(UnitCountObjective(UnitTypeId.SCV, 19))

        # Buildings
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        #rax_base = main.add_task(UnitCountTask(UnitTypeId.BARRACKS))

        proxy_location = bot.map.get_proxy_location()
        rax = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 2,
                                                    reqs=(UnitTypeId.SCV, 14),
                                                    position=proxy_location, distance=10))
        rax2 = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 4,
                                                     reqs=UnitTypeId.BARRACKS,
                                                     position=proxy_location, distance=10))

        bot.objectives.add(UnitCountObjective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # Units
        bot.objectives.add(UnitCountObjective(UnitTypeId.MARINE, 100, reqs=UnitTypeId.BARRACKS))
        bot.objectives.add(AttackObjective(target=bot.map.enemy_start_locations[0].center))

    def load_proxy_reaper(self) -> None:
        bot = self.bot

        # Always produce SCV until 16 + 3 + 2 = 21
        bot.objectives.add(UnitCountObjective(UnitTypeId.SCV, 21))

        # Buildings
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 1, reqs=(UnitTypeId.SCV, 13)))
        rax_base = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS))

        proxy_location = bot.map.get_proxy_location()
        rax = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 2,
                                                    reqs=(UnitTypeId.SCV, 14),
                                                    position=proxy_location, distance=10))
        rax2 = bot.objectives.add(UnitCountObjective(UnitTypeId.BARRACKS, 4,
                                                     reqs=UnitTypeId.BARRACKS,
                                                     position=proxy_location, distance=10))

        #main.add_task(UnitCountTask(UnitTypeId.REFINERY, 2, reqs=('S', 16)))
        bot.objectives.add(UnitCountObjective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS))

        # --- Supply
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19)))
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 3, reqs=('S', 26)))
        bot.objectives.add(UnitCountObjective(UnitTypeId.SUPPLYDEPOT, 4, reqs=('S', 35)))

        # --- Upgrades
        #main.add_task(UnitCountTask(UnitTypeId.BARRACKSREACTOR, deps=rax_base, priority=100))

        # Units
        #main.add_task(UnitCountTask(UnitTypeId.REAPER, 100, reqs=UnitTypeId.BARRACKS))
        #main.add_task(HandoverUnitsTask(UnitTypeId.REAPER, 'Reapers', reqs=(UnitTypeId.REAPER, 4), repeat=True))

        bot.objectives.add(UnitCountObjective(UnitTypeId.REAPER, 100, reqs=UnitTypeId.BARRACKS))
        bot.objectives.add(AttackObjective(target=bot.map.enemy_start_locations[0].center))
