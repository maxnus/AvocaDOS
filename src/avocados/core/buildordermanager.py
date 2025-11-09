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

        scv1 = obj.add_unit_objective(UnitTypeId.SCV, 13, priority=1)
        obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, 1, priority=0.9)

        # SCV
        scv2 = obj.add_unit_objective(UnitTypeId.SCV, 16, priority=0.7, deps=scv1)
        obj.add_unit_objective(UnitTypeId.SCV, 19, priority=0.4, deps=scv2)

        # Buildings

        rax123 = obj.add_construction_objective(UnitTypeId.BARRACKS, 3)
        rax456 = obj.add_construction_objective(UnitTypeId.BARRACKS, 6, reqs=('S', 23))

        obj.add_unit_objective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS, priority=0.4)

        # --- Supply
        obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 18))
        for number in range(3, 30):
            obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, number, reqs=('S', number * 8 + 2))

        # Units
        obj.add_unit_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS)

        obj.add_defense_objective(target=bot.map.start_location.region_center)

    def load_proxy_marine(self) -> None:
        bot = self.bot
        obj = bot.objectives

        scv = obj.add_unit_objective(UnitTypeId.SCV, 13, priority=1)
        obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, 1, priority=0.9)
        obj.add_unit_objective(UnitTypeId.SCV, 16, priority=0.4, deps=scv)

        proxy_location = bot.map.get_proxy_location()
        rax123 = bot.objectives.add_construction_objective(UnitTypeId.BARRACKS, 3, position=proxy_location, priority=0.8)
        rax4 = bot.objectives.add_construction_objective(UnitTypeId.BARRACKS, 4, position=proxy_location, priority=0.8,
                                                         reqs=UnitTypeId.BARRACKS)
        rax_home = bot.objectives.add_construction_objective(UnitTypeId.BARRACKS, 2,
                                                             position=self.map.start_location.region_center,
                                                             priority=0.3, deps=rax123)

        supply2 = obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, 2, reqs=('S', 19), priority=0.7)
        obj.add_unit_objective(UnitTypeId.ORBITALCOMMAND, 1, reqs=UnitTypeId.BARRACKS, deps=supply2, priority=0.4)

        # --- Supply
        for number in range(3, 30):
            obj.add_construction_objective(UnitTypeId.SUPPLYDEPOT, number, reqs=('S', number * 8 + 2), priority=0.6)

        # Units
        obj.add_unit_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS)
