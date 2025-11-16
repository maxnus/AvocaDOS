import asyncio
import random
from collections import defaultdict
from time import perf_counter

from sc2.bot_ai import BotAI
from sc2.data import Result
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.apiextensions import ApiExtensions
from avocados.bot.avocados import AvocaDOS


class BotApi(BotAI):
    ext: ApiExtensions
    bot: AvocaDOS
    game_step: int
    slowdown: float
    # Tag memory: TODO: Migrate to extensions?
    dead_tags: set[int]
    alive_tags: set[int]
    damage_received: dict[int, float]

    def __init__(self, *,
                 seed: int = 0,
                 game_step: int = 1,
                 slowdown: float = 0,
                 **kwargs
                 ) -> None:
        super().__init__()
        random.seed(seed)
        self.ext = ApiExtensions(self)
        self.bot = AvocaDOS(self, **kwargs)
        self.game_step = game_step
        self.slowdown = slowdown
        #
        self.alive_tags = set() # Initialized correctly in on_start
        self.dead_tags = set()
        self.damage_received = defaultdict(float)

    # --- Units

    @property
    def all_structures(self) -> Units:
        return self.structures + self.enemy_structures

    # --- Callbacks

    async def on_start(self) -> None:
        await self.ext.on_start()
        self.client.game_step = self.game_step
        self.alive_tags = self.all_units.tags
        await self.bot.on_start()

    async def on_step(self, step: int):
        frame_start = perf_counter()
        # Update tag memory
        self.alive_tags.update(self.all_units.tags)
        self.dead_tags.update(self.state.dead_units)
        self.alive_tags.difference_update(self.dead_tags)
        await self.bot.on_step(step)
        self.damage_received.clear()
        if self.slowdown:
            sleep = self.slowdown / 1000 - (perf_counter() - frame_start)
            if sleep > 0:
                await asyncio.sleep(sleep)

    async def on_end(self, game_result: Result) -> None:
        await self.bot.on_end(game_result)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        self.damage_received[unit.tag] += amount_damage_taken
        await self.bot.on_unit_took_damage(unit, amount_damage_taken)

    async def on_unit_created(self, unit: Unit) -> None:
        # if unit.tag in self.dead_tags:
        #     raise ValueError(f"internal error: unit tag {unit.tag} already marked as dead")
        # self.alive_tags.add(unit.tag)
        await self.bot.on_unit_created(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        # if unit.tag in self.dead_tags:
        #     raise ValueError(f"internal error: unit tag {unit.tag} already marked as dead")
        # self.alive_tags.add(unit.tag)
        await self.bot.on_building_construction_started(unit)

    async def on_building_construction_complete(self, unit: Unit) -> None:
        await self.bot.on_building_construction_complete(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        # self.alive_tags.remove(unit_tag)
        # self.dead_tags.add(unit_tag)
        await self.bot.on_unit_destroyed(unit_tag)
