from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId

from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


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
        raise NotImplementedError
        bot = self.bot
        obj = bot.objectives
        # Buildings
        rax123 = obj.add_construction_objective(UnitTypeId.BARRACKS, 3)
        rax456 = obj.add_construction_objective(UnitTypeId.BARRACKS, 6, reqs=('S', 23))
        # Units
        obj.add_unit_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS)

    def load_proxy_marine(self) -> None:
        proxy_location = self.bot.map.get_proxy_location()
        self.bot.objectives.add_construction_objective(UnitTypeId.BARRACKS, 3, position=proxy_location,
                                                       include_addon=False, priority=0.8)
        self.bot.objectives.add_construction_objective(UnitTypeId.BARRACKS, 4, position=proxy_location, priority=0.8,
                                                       reqs=UnitTypeId.BARRACKS)
        self.bot.objectives.add_unit_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS, priority=0.7)

    def load_eco_test(self) -> None:
        self.strategy.get_worker_target = lambda *args: 16
        self.strategy.get_expansion_target = lambda *args: 1
        self.strategy.get_supply_target = lambda *args: 1
