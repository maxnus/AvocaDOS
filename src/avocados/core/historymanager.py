from typing import Optional, TYPE_CHECKING

from sc2.unit import Unit

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class HistoryManager(BotObject):
    resource_history: list[tuple[int, int]]
    units_last_seen: dict[int, tuple[int, Unit]]
    #enemy_units: dict[int, tuple[int, Unit]]
    max_length: int

    def __init__(self, bot: 'AvocaDOS', *, max_length: int = 1000) -> None:
        super().__init__(bot)
        self.resource_history = []
        self.max_length = max_length
        self.units_last_seen = {}
        #self.enemy_units = {}

    async def on_step(self, iteration: int) -> None:
        # Resources
        self.resource_history.append((self.api.minerals, self.api.vespene))
        if len(self.resource_history) > self.max_length:
            self.resource_history.pop(0)

        # Own
        for unit in self.api.units:
            self.units_last_seen[unit.tag] = (self.api.state.game_loop, unit)

        # Enemies
        for unit in self.api.enemy_units:
            prev_entry = self.units_last_seen.get(unit.tag)
            self.units_last_seen[unit.tag] = (self.api.state.game_loop, unit)
            if prev_entry is not None:
                assert prev_entry[0] < self.api.state.game_loop
                change = unit.health + unit.shield - prev_entry[1].health - prev_entry[1].shield
                if change < 0:
                    await self.api.on_unit_took_damage(unit, -change)

    def get_last_seen(self, unit: int | Unit) -> Optional[Unit]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        last_seen = self.units_last_seen.get(tag)
        return last_seen[1] if last_seen is not None else None
