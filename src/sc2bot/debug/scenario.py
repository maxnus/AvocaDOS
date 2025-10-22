import itertools
from typing import TYPE_CHECKING, Optional

from sc2.client import Client
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.units import Units

from sc2bot.core.tasks import AttackTask
from sc2bot.core.util import UnitCost

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


class MicroScenario:
    bot: 'BotBase'
    id: int
    units: tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]
    location: Point2
    separation: float
    spawn_p1: Point2
    spawn_p2: Point2
    simulation: int
    max_simulations: int
    max_duration: float
    # Set after started (TODO: separate class?):
    started: Optional[float]
    finished: Optional[float]
    tags_p1: Optional[set[int]]
    tags_p2: Optional[set[int]]
    cost_p1: Optional[UnitCost]
    cost_p2: Optional[UnitCost]
    # Class Variables
    _id_counter = itertools.count()

    def __init__(self, bot: 'BotBase',
                 units: dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]],
                 *,
                 location: Optional[Point2] = None,
                 separation: float = 10,
                 max_simulations: int = 5,
                 max_duration: float = 30,
                 ) -> None:
        super().__init__()
        self.bot = bot
        self.id = next(MicroScenario._id_counter)
        if isinstance(units, dict):
            units = (units, units)
        self.units = units
        if location is None:
            location = self.bot.map.center.towards(self.bot.map.base_center, 5.0)
        self.location = location
        self.separation = separation
        self.spawn_p1 = self.location.towards(self.bot.start_location, self.separation / 2)
        self.spawn_p2 = self.location.towards(self.bot.start_location, -self.separation / 2)
        self.simulation = 0
        self.max_simulations = max_simulations
        self.max_duration = max_duration
        self.started = None
        self.finished = None
        self.tags_p1 = None
        self.tags_p2 = None
        self.cost_p1 = None
        self.cost_p2 = None

    @property
    def client(self) -> Client:
        return self.bot.client

    @property
    def logger(self):
        return self.bot.logger

    @property
    def in_progress(self) -> bool:
        return self.started is not None and self.finished is None

    def reset(self) -> None:
        self.started = None
        self.finished = None
        self.tags_p1 = None
        self.tags_p2 = None
        self.cost_p1 = None
        self.cost_p2 = None
        self.simulation += 1

    async def start(self) -> bool:
        if self.simulation >= self.max_simulations:
            return False

        if current_units := self.bot.all_units.closer_than(self.separation + 2, self.location):
            await self.client.debug_kill_unit(current_units)

        for player in self.bot.game_info.players:
            spawn = self.spawn_p1 if player.id == 1 else self.spawn_p2
            await self.client.debug_create_unit(
                [[utype, number, spawn, player.id] for utype, number in self.units[player.id - 1].items()]
            )

        await self.client.move_camera(self.location)

        self.started = self.bot.time
        return True

    async def step(self) -> bool:
        if self.started == self.bot.time:
            return False

        if self.in_progress:
            if self.tags_p1 is None:
                # Check if units have spawned
                units_p1 = (self.bot.all_units.closer_than(self.separation / 2, self.spawn_p1)
                            .filter(lambda u: u.owner_id == 1))
                units_p2 = (self.bot.all_units.closer_than(self.separation / 2, self.spawn_p2)
                            .filter(lambda u: u.owner_id == 2))
                if units_p1 and units_p2:
                    self.tags_p1 = units_p1.tags
                    self.tags_p2 = units_p2.tags

                    cmd = self.bot.add_commander(f'MicroScenario{self.id}')
                    cmd.add_units(units_p1)
                    cmd.add_task(AttackTask(self.location))

                    # await self.client.debug_control_enemy()
                    for unit in units_p2:
                        unit.attack(self.location)

                return False

            units_p1 = self.get_units(1)
            units_p2 = self.get_units(2)

            timeout = self.bot.time >= self.started + self.max_duration
            has_finished = not units_p1 or not units_p2 or timeout
            if has_finished:
                self.finished = self.bot.time
                self.analyze()
                await self.client.debug_kill_unit(self.tags_p1 | self.tags_p2)
            return False

        if self.simulation + 1 >= self.max_simulations:
            self.bot.remove_commander(f'MicroScenario{self.id}')
            return True

        if self.bot.time >= self.finished + 2:
            self.reset()
            await self.start()

        return False

    # async def end(self) -> bool:
    #     if not self.finished:
    #         return False
    #     self.analyze()
    #     await self.client.debug_kill_unit(self.tags_p1 | self.tags_p2)
    #     return True

    def get_units(self, player: int) -> Units:
        tags = self.tags_p1 if player == 1 else self.tags_p2
        units = self.bot.all_units.filter(lambda u: u.tag in tags and u.owner_id == player)
        return units

    def analyze(self) -> None:
        value_p1 = sum((number * self.bot.get_unit_value(utype) for utype, number in self.units[0].items()),
                       start=UnitCost(0, 0, 0))
        value_p2 = sum((number * self.bot.get_unit_value(utype) for utype, number in self.units[1].items()),
                       start=UnitCost(0, 0, 0))
        value_p1_after = self.bot.get_unit_value(self.get_units(1))
        value_p2_after = self.bot.get_unit_value(self.get_units(2))
        loss_p1 = value_p1 - value_p1_after
        loss_p2 = value_p2 - value_p2_after
        lost_supply_ratio_p1 = loss_p1.supply / value_p1.supply if value_p1.supply else float('nan')
        lost_supply_ratio_p2 = loss_p2.supply / value_p2.supply if value_p2.supply else float('nan')
        self.logger.info(f"Player 1: {value_p1} -> {value_p1_after} - lost: {loss_p1}, {lost_supply_ratio_p1:.1%}")
        self.logger.info(f"Player 2: {value_p2} -> {value_p2_after} - lost: {loss_p2}, {lost_supply_ratio_p2:.1%}")
        win_ratio = loss_p2.supply / (loss_p1.supply + loss_p2.supply)
        self.logger.info(f"Win ratio P1/P2: {win_ratio:.1%} / {1-win_ratio:.1%}")
