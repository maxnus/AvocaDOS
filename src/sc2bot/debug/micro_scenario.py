import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from sc2.client import Client
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.botobject import BotObject
from sc2bot.core.tasks import AttackTask
from sc2bot.core.util import UnitCost

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


@dataclass
class MicroScenarioResults:
    duration: float
    winner: int
    value_start_p1: UnitCost
    value_start_p2: UnitCost
    value_end_p1: UnitCost
    value_end_p2: UnitCost

    def get_losses(self) -> tuple[UnitCost, UnitCost]:
        loss_p1 = self.value_end_p1 - self.value_start_p1
        loss_p2 = self.value_end_p2 - self.value_start_p2
        return loss_p1, loss_p2


class MicroScenario(BotObject):
    id: int
    units_types: tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]
    location: Point2
    spawns: tuple[Point2, Point2]
    arena_size: tuple[float, float]
    max_duration: float
    # Set after started (TODO: separate class?):
    started: Optional[float]
    finished: Optional[float]
    tags_p1: Optional[set[int]]
    tags_p2: Optional[set[int]]
    # Class Variables
    _id_counter = itertools.count()

    def __init__(self, bot: 'AvocaDOS', *,
                 unit_types: dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]],
                 location: Optional[Point2] = None,
                 spawns: Optional[tuple[Point2, Point2]] = None,
                 max_duration: float = 60,
                 ) -> None:
        super().__init__(bot)
        self.id = next(MicroScenario._id_counter)
        if isinstance(unit_types, dict):
            unit_types = (unit_types, unit_types)
        self.units_types = unit_types
        if location is None:
            location = self.bot.map.center
        self.location = location
        if spawns is None:
            spawns = (location.offset(Point2((-8, 0))), location.offset(Point2((+8, 0))))
        self.spawns = spawns
        self.arena_size = (22, 22)
        self.max_duration = max_duration
        self.started = None
        self.finished = None
        self.tags_p1 = None
        self.tags_p2 = None

    @property
    def in_progress(self) -> bool:
        return self.started is not None and self.finished is None

    async def start(self) -> None:
        # Clean arena
        # units_in_arena = self._get_all_units_in_arena()
        # if units_in_arena:
        #     await self.client.debug_kill_unit(units_in_arena)

        for player in self.api.game_info.players:
            await self.api.client.debug_create_unit(
                [[utype, number, self.spawns[player.id - 1], player.id]
                 for utype, number in self.units_types[player.id - 1].items()]
            )
        self.started = self.bot.time

    async def step(self) -> bool:
        if self.started == self.bot.time:
            return False

        if self.in_progress:
            if self.tags_p1 is None:
                self._check_spawn()
                return False
            else:
                await self._check_finished()

        return self.finished is not None

    async def finish(self) -> Optional[MicroScenarioResults]:
        results = self._get_results()
        #self.bot.remove_commander(f'MicroScenario{self.id}')
        await self.api.client.debug_kill_unit(self.tags_p1 | self.tags_p2)
        return results

    async def _check_finished(self):
        units_p1, units_p2 = self._get_units()

        # idle enemies should attack
        enemies = units_p2 if self.api.player_id == 1 else units_p1
        for unit in enemies.idle:
            unit.attack(self.location)

        timeout = self.time >= self.started + self.max_duration
        has_finished = not units_p1 or not units_p2 or timeout
        if has_finished:
            self.finished = self.bot.time

    def _in_arena(self, point: Point2 | Unit) -> bool:
        if isinstance(point, Unit):
            point = point.position
        return (-self.arena_size[0] <= 2*(point.x - self.location.x) <= self.arena_size[0]
                and -self.arena_size[1] <= 2*(point.y - self.location.y) <= self.arena_size[1])

    def _get_all_units_in_arena(self) -> Units:
        return self.api.all_units.filter(lambda u: self._in_arena(u))

    def _get_units_in_arena(self) -> tuple[Units, Units]:
        units_in_arena = self._get_all_units_in_arena()
        units_p1 = units_in_arena.filter(lambda u: u.owner_id == 1)
        units_p2 = units_in_arena.filter(lambda u: u.owner_id == 2)
        return units_p1, units_p2

    def _get_units(self) -> tuple[Units, Units]:
        units_p1 = self.api.all_units.filter(lambda u: u.tag in self.tags_p1)
        units_p2 = self.api.all_units.filter(lambda u: u.tag in self.tags_p2)
        return units_p1, units_p2

    def _check_spawn(self):
        # Check if units have spawned
        units_p1, units_p2 = self._get_units_in_arena()
        if units_p1 and units_p2:
            self.tags_p1 = units_p1.tags
            self.tags_p2 = units_p2.tags
            #cmd = self.bot.add_commander(f'MicroScenario{self.id}')
            #cmd.add_units(units_p1 if self.api.player_id == 1 else units_p2)
            self.tasks.add(AttackTask(self.location))
            # for unit in units_p1:
            #     unit.attack(self.location)
            # for unit in units_p2:
            #     unit.attack(self.location)
            # await self.bot.debug.hide_map()
            # await self.bot.debug.control_enemy_off()

    def _get_results(self) -> MicroScenarioResults:
        if not self.finished:
            raise RuntimeError
        value_start_p1 = sum((number * self.api.get_unit_value(utype)
                              for utype, number in self.units_types[0].items()), start=UnitCost(0, 0, 0))
        value_start_p2 = sum((number * self.api.get_unit_value(utype)
                              for utype, number in self.units_types[1].items()), start=UnitCost(0, 0, 0))

        units_p1, units_p2 = self._get_units()
        if units_p1 and not units_p2:
            winner = 1
        elif units_p2 and not units_p1:
            winner = 2
        else:
            winner = 0
        value_end_p1 = self.api.get_unit_value(units_p1)
        value_end_p2 = self.api.get_unit_value(units_p2)

        results = MicroScenarioResults(
            duration=self.finished - self.started,
            winner=winner,
            value_start_p1=value_start_p1,
            value_start_p2=value_start_p2,
            value_end_p1=value_end_p1,
            value_end_p2=value_end_p2,
        )
        return results
