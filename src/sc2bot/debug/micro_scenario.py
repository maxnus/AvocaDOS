import itertools
from typing import TYPE_CHECKING, Optional

from sc2.client import Client
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
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
    spawns: tuple[Point2, Point2]
    arena_size: tuple[float, float]
    simulation: int
    max_simulations: int
    max_duration: float
    total_loss_p1: UnitCost
    total_loss_p2: UnitCost
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
                 spawns: Optional[tuple[Point2, Point2]] = None,
                 max_simulations: int = 5,
                 max_duration: float = 300,
                 ) -> None:
        super().__init__()
        self.bot = bot
        self.id = next(MicroScenario._id_counter)
        if isinstance(units, dict):
            units = (units, units)
        self.units = units
        if location is None:
            location = self.bot.map.center
        self.location = location
        if spawns is None:
            spawns = (location.offset(Point2((-8, 0))), location.offset(Point2((+8, 0))))
        self.spawns = spawns
        self.arena_size = (22, 22)
        self.simulation = 0
        self.max_simulations = max_simulations
        self.max_duration = max_duration
        self.started = None
        self.finished = None
        self.tags_p1 = None
        self.tags_p2 = None
        self.total_loss_p1 = UnitCost(0, 0, 0)
        self.total_loss_p2 = UnitCost(0, 0, 0)

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
        self.simulation += 1

    async def start(self) -> bool:
        if self.simulation >= self.max_simulations:
            return False
        for player in self.bot.game_info.players:
            await self.client.debug_create_unit(
                [[utype, number, self.spawns[player.id - 1], player.id]
                 for utype, number in self.units[player.id - 1].items()]
            )
        self.started = self.bot.time
        return True

    def in_arena(self, point: Point2 | Unit) -> bool:
        if isinstance(point, Unit):
            point = point.position
        return (-self.arena_size[0] <= 2*(point.x - self.location.x) <= self.arena_size[0]
            and -self.arena_size[1] <= 2*(point.y - self.location.y) <= self.arena_size[1])

    def get_units_in_arena(self) -> tuple[Units, Units]:
        units_in_arena = self.bot.all_units.filter(lambda u: self.in_arena(u))
        units_p1 = units_in_arena.filter(lambda u: u.owner_id == 1)
        units_p2 = units_in_arena.filter(lambda u: u.owner_id == 2)
        return units_p1, units_p2

    def get_units(self) -> tuple[Units, Units]:
        units_p1 = self.bot.all_units.filter(lambda u: u.tag in self.tags_p1)
        units_p2 = self.bot.all_units.filter(lambda u: u.tag in self.tags_p2)
        return units_p1, units_p2

    def check_spawn(self):
        # Check if units have spawned
        units_p1, units_p2 = self.get_units_in_arena()
        if units_p1 and units_p2:
            self.tags_p1 = units_p1.tags
            self.tags_p2 = units_p2.tags
            cmd = self.bot.add_commander(f'MicroScenario{self.id}')
            cmd.add_units(units_p1 if self.bot.player_id == 1 else units_p2)
            cmd.add_task(AttackTask(self.location))
            # await self.client.debug_control_enemy()
            # for unit in units_p1:
            #     unit.attack(self.location)
            # for unit in units_p2:
            #     unit.attack(self.location)
            # await self.bot.debug.hide_map()
            # await self.bot.debug.control_enemy_off()

    async def check_finished(self):
        units_p1, units_p2 = self.get_units()

        # idle enemies should attack
        enemies = units_p2 if self.bot.player_id == 1 else units_p1
        for unit in enemies.idle:
            unit.attack(self.location)

        timeout = self.bot.time >= self.started + self.max_duration
        has_finished = not units_p1 or not units_p2 or timeout
        if has_finished:
            self.finished = self.bot.time
            loss_p1, loss_p2 = self.calculate_losses()
            self.total_loss_p1 += loss_p1
            self.total_loss_p2 += loss_p2
            await self.client.debug_kill_unit(self.tags_p1 | self.tags_p2)

    async def step(self) -> bool:
        if self.started == self.bot.time:
            return False

        if self.in_progress:
            if self.tags_p1 is None:
                self.check_spawn()
            else:
                await self.check_finished()
            return False

        if self.simulation + 1 >= self.max_simulations:
            self.bot.remove_commander(f'MicroScenario{self.id}')
            self.analyze()
            return True

        if self.bot.time >= self.finished + 2:
            self.reset()
            await self.start()

        return False

    def calculate_losses(self) -> tuple[UnitCost, UnitCost]:
        value_p1 = sum((number * self.bot.get_unit_value(utype) for utype, number in self.units[0].items()),
                       start=UnitCost(0, 0, 0))
        value_p2 = sum((number * self.bot.get_unit_value(utype) for utype, number in self.units[1].items()),
                       start=UnitCost(0, 0, 0))
        units_p1, units_p2 = self.get_units()
        value_p1_after = self.bot.get_unit_value(units_p1)
        value_p2_after = self.bot.get_unit_value(units_p2)
        loss_p1 = value_p1 - value_p1_after
        loss_p2 = value_p2 - value_p2_after
        return loss_p1, loss_p2

    def analyze(self) -> None:
        self.logger.info("Average Losses:")
        self.logger.info(f"Player 1: {self.total_loss_p1 / self.max_simulations}")
        self.logger.info(f"Player 2: {self.total_loss_p2 / self.max_simulations}")
        total_lost_resources = self.total_loss_p1.resources + self.total_loss_p2.resources
        if total_lost_resources:
            win_ratio_p1 = self.total_loss_p2.resources / total_lost_resources
        else:
            win_ratio_p1 = 0.5
        self.logger.info(f"Win ratio P1/P2: {win_ratio_p1:.1%} / {1-win_ratio_p1:.1%}")
