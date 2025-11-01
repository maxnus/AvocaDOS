from collections.abc import Iterator
from typing import TYPE_CHECKING

from sc2.units import Units

from sc2bot.core.botobject import BotObject
from sc2bot.micro.squad import Squad, SquadAttackTask

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


class SquadManager(BotObject):
    _squads: dict[int, Squad]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._squads = {}

    async def on_step(self, step: int) -> None:
        pass
        # for squad in self:
        #     if isinstance(squad.task, SquadAttackTask):
        #         self.order.attack(squad.units, squad.task.target)
        #     elif squad.task is None:
        #         pass
        #     else:
        #         self.logger.warning("Unknown squad task: {}", squad.task)

    def __iter__(self) -> Iterator[Squad]:
        yield from self._squads.values()

    def create_squad(self, units: Units | set[int]) -> Squad:
        tags = units.tags if isinstance(units, Units) else units
        squad = Squad(self.bot, tags)
        self._squads[squad.id] = squad
        return squad

    def delete_squad(self, squad: Squad | int) -> None:
        id_ = squad.id if isinstance(squad, Squad) else squad
        if self._squads.pop(id_, None) is None:
            self.logger.warning("Squad {} not found", id_)
