from typing import Optional

from sc2.ids.unit_typeid import UnitTypeId

from avocados.bot.objectivemanager import ObjectiveManager
from avocados.core.manager import BotManager
from avocados.mapdata import MapManager


class BuildOrderManager(BotManager):
    map: MapManager
    objectives: ObjectiveManager
    build: Optional[str]

    def __init__(self, build: Optional[str] = 'default', *,
                 map_manager: MapManager,
                 objective_manager: ObjectiveManager) -> None:
        super().__init__()
        self.map = map_manager
        self.objectives = objective_manager

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

    def load_proxy_marine(self) -> None:
        proxy_location = self.map.get_proxy_location()
        self.objectives.add_construction_objective(UnitTypeId.BARRACKS, 3, position=proxy_location,
                                                   include_addon=False, priority=0.8)
        self.objectives.add_construction_objective(UnitTypeId.BARRACKS, 4, position=proxy_location, priority=0.8,
                                                   reqs=UnitTypeId.BARRACKS)
        self.objectives.add_unit_objective(UnitTypeId.MARINE, 200, reqs=UnitTypeId.BARRACKS, priority=0.7)
