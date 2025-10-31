from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2

from sc2bot.core.botobject import BotObject
from sc2bot.core.util import UnitCost
from sc2bot.debug.micro_scenario import MicroScenario, MicroScenarioResults

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class MicroScenarioManager(BotObject):
    bot: 'AvocaDOS'
    units: tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]
    running: bool
    number_scenarios: int
    scenarios: dict[int, MicroScenario]
    locations: list[Point2]
    free_locations: list[Point2]
    results: list[MicroScenarioResults]

    def __init__(self, bot: 'AvocaDOS', *,
                 units: dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]) -> None:
        super().__init__(bot)
        if isinstance(units, dict):
            units = (units, units)
        self.bot = bot
        self.units = units
        self.running = False
        self.number_scenarios = 0
        self.scenarios = {}
        self.locations = []
        self.free_locations = []
        self.results = []

    def get_locations(self) -> list[Point2]:
        locations = []
        if self.api.game_info.map_name == 'Micro Training 4x4':
            for row in range(4):
                y = row * 40 + 12
                for col in range(4):
                    x = col * 40 + 12
                    locations.append(Point2((x, y)))
        else:
            raise NotImplementedError(f"map {self.api.game_info.map_name}")
        return locations

    async def on_start(self, *, number_scenarios: int = 64) -> None:

        self.locations = self.get_locations()
        self.free_locations = self.locations.copy()

        self.running = True
        await self.debug.reveal_map()
        await self.debug.control_enemy()

        self.number_scenarios = number_scenarios
        for idx in range(min(self.number_scenarios, len(self.locations))):
            location = self.free_locations.pop(0)
            scenario = MicroScenario(self.bot, unit_types=self.units, location=location)
            self.scenarios[scenario.id] = scenario
            await scenario.start()

    async def on_step(self) -> Optional[float]:
        if not self.running:
            raise RuntimeError

        await self.debug.control_enemy_off()
        await self.debug.control_enemy()

        finished_ids: set[int] = set()
        for scenario in self.scenarios.values():
            if await scenario.step():
                result = await scenario.finish()
                self.results.append(result)
                finished_ids.add(scenario.id)

        for scenario_id in finished_ids:
            finished_scenario = self.scenarios.pop(scenario_id)
            # Restart
            if len(self.results) + len(self.scenarios) < self.number_scenarios:
                scenario = MicroScenario(self.bot, unit_types=self.units, location=finished_scenario.location)
                self.scenarios[scenario.id] = scenario
                await scenario.start()

        if finished_ids and not self.scenarios:
            await self.debug.hide_map()
            await self.debug.control_enemy_off()
            self.running = False
            return self.analyse()
        else:
            return None

    def analyse(self, *, vespene_mineral_value: float | tuple[float, float] = 2.0) -> float:
        if isinstance(vespene_mineral_value, float):
            vespene_mineral_value = (vespene_mineral_value, vespene_mineral_value)

        losses_p1, losses_p2 = zip(*[result.get_losses() for result in self.results])
        mean_loss_p1 = sum(losses_p1, start=UnitCost(0, 0, 0)) / len(losses_p1)
        mean_loss_p2 = sum(losses_p2, start=UnitCost(0, 0, 0)) / len(losses_p2)
        mean_squared_loss_p1 = sum([l**2 for l in losses_p1], start=UnitCost(0, 0, 0)) / len(losses_p1)
        mean_squared_loss_p2 = sum([l**2 for l in losses_p2], start=UnitCost(0, 0, 0)) / len(losses_p2)
        std_loss_p1 = (mean_squared_loss_p1 - mean_loss_p1 ** 2)**0.5
        std_loss_p2 = (mean_squared_loss_p2 - mean_loss_p2 ** 2)**0.5

        self.logger.info("[Player 1] minerals= {:4.0f} +/- {:4.0f}  vespene= {:4.0f} +/- {:4.0f}",
                         mean_loss_p1.minerals, std_loss_p1.minerals, mean_loss_p1.vespene, std_loss_p1.vespene)
        self.logger.info("[Player 2] minerals= {:4.0f} +/- {:4.0f}  vespene= {:4.0f} +/- {:4.0f}",
                         mean_loss_p2.minerals, std_loss_p2.minerals, mean_loss_p2.vespene, std_loss_p2.vespene)

        resource_lost_p1 = mean_loss_p1.minerals + vespene_mineral_value[0] * mean_loss_p1.vespene
        resource_lost_p2 = mean_loss_p2.minerals + vespene_mineral_value[1] * mean_loss_p2.vespene
        #self.bot.logger.info("[Total]    P1: {:.1f}  P2: {:.1f}",
        #                     resource_lost_p1, resource_lost_p2)

        wins_p1 = sum(1 for result in self.results if result.winner == 1)
        wins_p2 = sum(1 for result in self.results if result.winner == 2)
        win_rate_p1 = wins_p1 / len(self.results)
        win_rate_p2 = wins_p2 / len(self.results)
        self.logger.info("Win rates: P1={:.1%} P2={:.1%}", win_rate_p1, win_rate_p2)

        total_resources_lost = resource_lost_p1 + resource_lost_p2
        if total_resources_lost == 0:
            return 0.5
        rating_p1 = resource_lost_p2 / total_resources_lost
        rating_p2 = resource_lost_p1 / total_resources_lost
        self.logger.info("rating: P1 = {:.1%} P2 = {:.1%}", rating_p1, rating_p2)

        return rating_p1
