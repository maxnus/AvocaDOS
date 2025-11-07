from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId

from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class BuildOrderManager(BotManager):
    build: Optional[str]

    def __init__(self, bot: 'AvocaDOS', build: Optional[str] = 'default') -> None:
        super().__init__(bot)
        if build == 'default':
            build = 'proxy_marine'
        self.build = build

    async def on_start(self) -> None:
        self.logger.debug("on_start started")
        if self.build:
            self.logger.info("Loading build: {}", self.build)
            func = getattr(self, f'load_{self.build}')
            func()
        self.logger.debug("on_start finished")

    def load_mass_marine(self) -> None:
        bot = self.bot
        obj = bot.objectives

        scv1 = obj.add_unit_count_objective(UnitTypeId.SCV, 13, priority=1)
        obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, 1, priority=0.9)

        # SCV
        scv2 = obj.add_unit_count_objective(UnitTypeId.SCV, 16, priority=0.7, deps=scv1)
        obj.add_unit_count_objective(UnitTypeId.SCV, 19, priority=0.4, deps=scv2)

        # Buildings

        rax123 = obj.add_unit_count_objective(UnitTypeId.BARRACKS, 3)
        rax456 = obj.add_unit_count_objective(UnitTypeId.BARRACKS, 6, reqs=('S', 23))

        obj.add_unit_count_objective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS, priority=0.8)

        # --- Supply
        obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 18))
        for number in range(3, 30):
            obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, number, reqs=('S', number * 8 + 2))

        # Units
        obj.add_unit_count_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS)

        obj.add_defense_objective(target=bot.map.start_base.region_center)

        squad_size = 8
        prev = None
        for loc in bot.map.enemy_start_locations:
            prev = obj.add_attack_objective(target=loc.center, minimum_size=squad_size, duration=5,
                                           reqs=(UnitTypeId.MARINE, squad_size),
                                           deps=prev, priority=0.7)
        for loc in bot.map.get_enemy_expansions(0):
            prev = obj.add_attack_objective(target=loc.center, strength=24, minimum_size=squad_size, duration=5,
                                           deps=prev, priority=0.7)

    def load_proxy_marine(self) -> None:
        bot = self.bot
        obj = bot.objectives

        scv = obj.add_unit_count_objective(UnitTypeId.SCV, 13, priority=1)
        obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, 1, priority=0.9)
        obj.add_unit_count_objective(UnitTypeId.SCV, 19, priority=0.7, deps=scv)

        proxy_location = bot.map.get_proxy_location()
        rax1234 = bot.objectives.add_unit_count_objective(UnitTypeId.BARRACKS, 4, position=proxy_location, distance=10)
        rax56 = bot.objectives.add_unit_count_objective(UnitTypeId.BARRACKS, 6, distance=10, priority=0.3, deps=rax1234)

        obj.add_unit_count_objective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS, priority=0.8)

        # --- Supply
        obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19))
        for number in range(3, 30):
            obj.add_unit_count_objective(UnitTypeId.SUPPLYDEPOT, number, reqs=('S', number * 8 + 2))

        # Units
        obj.add_unit_count_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS)
