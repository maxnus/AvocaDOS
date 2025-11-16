from time import perf_counter
from typing import Optional, TYPE_CHECKING

from sc2.unit import Unit

from avocados.core.manager import BotManager
from avocados.core.timeseries import Timeseries

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


INITIAL_TIMESERIES_SIZE = 4096


class MemoryManager(BotManager):
    units_last_seen: dict[int, tuple[int, Unit]]
    #enemy_units: dict[int, tuple[int, Unit]]
    max_length: int
    #
    minerals: Timeseries[int]
    vespene: Timeseries[int]
    supply: Timeseries[int]
    supply_cap: Timeseries[int]
    supply_workers: Timeseries[int]

    def __init__(self, bot: 'AvocaDOS', *, max_length: int = 1000) -> None:
        super().__init__(bot)
        self.max_length = max_length
        self.units_last_seen = {}
        #self.enemy_units = {}
        self.minerals = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.vespene = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply_cap = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply_workers = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()

        # Observations
        self.minerals.append(step, self.api.minerals)
        self.vespene.append(step, self.api.vespene)
        self.supply.append(step, int(self.api.supply_used))
        self.supply_cap.append(step, int(self.api.supply_cap))
        self.supply_workers.append(step, int(self.api.supply_workers))

        # Own
        for unit in self.api.units:
            self.units_last_seen[unit.tag] = (self.api.state.game_loop, unit)

        # Enemies
        # TODO: Move to botapi?
        for unit in self.api.enemy_units:
            prev_entry = self.units_last_seen.get(unit.tag)
            self.units_last_seen[unit.tag] = (self.api.state.game_loop, unit)
            if prev_entry is not None:
                assert prev_entry[0] < self.api.state.game_loop
                change = unit.health + unit.shield - prev_entry[1].health - prev_entry[1].shield
                if change < 0:
                    await self.api.on_unit_took_damage(unit, -change)
        self.timings['step'].add(t0)

    def get_last_seen(self, unit: int | Unit) -> Optional[Unit]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        last_seen = self.units_last_seen.get(tag)
        return last_seen[1] if last_seen is not None else None
