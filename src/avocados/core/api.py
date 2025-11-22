import asyncio
import random
from collections import defaultdict
from collections.abc import Callable, Awaitable
from time import perf_counter

from sc2.bot_ai import BotAI
from sc2.data import Result
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.apiextensions import ApiExtensions
from avocados.core.ordermanager import OrderManager


class Api(BotAI):
    ext: ApiExtensions
    game_step: int
    slowdown: float
    # Tag memory: TODO: Migrate to extensions?
    dead_tags: set[int]
    alive_tags: set[int]
    damage_received: dict[int, float]
    # callbacks
    _on_start_callbacks: list[Callable[[], Awaitable[None]]]
    _on_step_callbacks: list[Callable[[int], Awaitable[None]]]
    _on_end_callbacks: list[Callable[[Result], Awaitable[None]]]
    _on_unit_created_callbacks: list[Callable[[Unit], Awaitable[None]]]
    _on_unit_destroyed_callbacks: list[Callable[[int], Awaitable[None]]]
    _on_unit_took_damage_callbacks: list[Callable[[Unit, float], Awaitable[None]]]
    _on_building_construction_started_callbacks: list[Callable[[Unit], Awaitable[None]]]
    _on_building_construction_complete_callbacks: list[Callable[[Unit], Awaitable[None]]]


    def __init__(self, *,
                 seed: int = 0,
                 game_step: int = 1,
                 slowdown: float = 0,
                 ) -> None:
        super().__init__()
        random.seed(seed)
        self.ext = ApiExtensions(self)
        self.game_step = game_step
        self.slowdown = slowdown
        #
        self.alive_tags = set() # Initialized correctly in on_start
        self.dead_tags = set()
        self.damage_received = defaultdict(float)
        # Callbacks
        self._on_start_callbacks = []
        self._on_step_callbacks = []
        self._on_end_callbacks = []
        self._on_unit_created_callbacks = []
        self._on_unit_destroyed_callbacks = []
        self._on_unit_took_damage_callbacks = []
        self._on_building_construction_started_callbacks = []
        self._on_building_construction_complete_callbacks = []

    @property
    def step(self) -> int:
        return self.state.game_loop

    @property
    def order(self) -> OrderManager:
        return self.ext.order

    # --- Units

    @property
    def all_structures(self) -> Units:
        return self.structures + self.enemy_structures

    # --- Register callbacks

    def register_on_start(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._on_start_callbacks.append(callback)

    def register_on_step(self, callback: Callable[[int], Awaitable[None]]) -> None:
        self._on_step_callbacks.append(callback)

    def register_on_end(self, callback: Callable[[Result], Awaitable[None]]) -> None:
        self._on_end_callbacks.append(callback)

    def register_on_unit_created(self, callback: Callable[[Unit], Awaitable[None]]) -> None:
        self._on_unit_created_callbacks.append(callback)

    def register_on_unit_destroyed(self, callback: Callable[[int], Awaitable[None]]) -> None:
        self._on_unit_destroyed_callbacks.append(callback)

    def register_on_unit_took_damage(self, callback: Callable[[Unit, float], Awaitable[None]]) -> None:
        self._on_unit_took_damage_callbacks.append(callback)

    def register_on_building_construction_started(self, callback: Callable[[Unit], Awaitable[None]]) -> None:
        self._on_building_construction_started_callbacks.append(callback)

    def register_on_building_construction_complete(self, callback: Callable[[Unit], Awaitable[None]]) -> None:
        self._on_building_construction_complete_callbacks.append(callback)

    # --- Callbacks

    async def on_start(self) -> None:
        self.client.game_step = self.game_step
        self.alive_tags = self.all_units.tags
        await self.ext.on_start()
        for callback in self._on_start_callbacks:
            await callback()

    async def on_step(self, step: int):
        frame_start = perf_counter()
        # Update tag memory
        self.alive_tags.update(self.all_units.tags)
        self.dead_tags.update(self.state.dead_units)
        self.alive_tags.difference_update(self.dead_tags)

        await self.order.on_step_start(step)

        for callback in self._on_step_callbacks:
            await callback(step)

        await self.order.on_step_end(step)
        self.damage_received.clear()
        if self.slowdown:
            sleep = self.slowdown / 1000 - (perf_counter() - frame_start)
            if sleep > 0:
                await asyncio.sleep(sleep)

    async def on_end(self, game_result: Result) -> None:
        for callback in self._on_end_callbacks:
            await callback(game_result)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        self.damage_received[unit.tag] += amount_damage_taken
        for callback in self._on_unit_took_damage_callbacks:
            await callback(unit, amount_damage_taken)

    async def on_unit_created(self, unit: Unit) -> None:
        for callback in self._on_unit_created_callbacks:
            await callback(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        for callback in self._on_building_construction_started_callbacks:
            await callback(unit)

    async def on_building_construction_complete(self, unit: Unit) -> None:
        for callback in self._on_building_construction_complete_callbacks:
            await callback(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        for callback in self._on_unit_destroyed_callbacks:
            await callback(unit_tag)
