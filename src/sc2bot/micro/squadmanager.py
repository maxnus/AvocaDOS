import random
from collections.abc import Iterator
from typing import TYPE_CHECKING, Optional

from s2clientprotocol.error_pb2 import NotEnoughRoomToLoadUnit
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.botobject import BotObject
from sc2bot.core.util import squared_distance
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

    def __len__(self) -> int:
        return len(self._squads)

    def __iter__(self) -> Iterator[Squad]:
        yield from self._squads.values()

    def get(self, squad_id: int) -> Optional[Squad]:
        return self._squads.get(squad_id)

    def create(self, units: Units | set[int]) -> Squad:
        tags = units.tags if isinstance(units, Units) else units
        for squad in self:
            if common_tags := tags & squad.tags:
                self.logger.warning("Tags {} are already assigned to {}", common_tags, squad)
                tags -= common_tags
        squad = Squad(self.bot, tags)
        self._squads[squad.id] = squad
        return squad

    def delete(self, squad: Squad | int) -> None:
        id_ = squad.id if isinstance(squad, Squad) else squad
        if self._squads.pop(id_, None) is None:
            self.logger.warning("Squad {} not found", id_)

    def get_squad_of_unit(self, unit: Unit | int) -> Optional[Squad]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        for squad in self:
            if tag in squad:
                return squad
        return None

    def random(self) -> Optional[Squad]:
        if len(self) == 0:
            return None
        return random.choice(list(self._squads.values()))

    def closest_to(self, target: Point2) -> Optional[Squad]:
        if len(self) == 0:
            return None
        closest_distance_sq = float('inf')
        closest_squad = None
        for squad in self:
            if (distance_sq :=  squared_distance(squad.center, target)) < closest_distance_sq:
                closest_distance_sq = distance_sq
                closest_squad = squad
        return closest_squad

    def smallest(self) -> Optional[Squad]:
        if len(self) == 0:
            return None
        smallest_size = float('inf')
        smallest_squad = None
        for squad in self:
            if (size := len(squad)) < smallest_size:
                smallest_size = size
                smallest_squad = squad
        return smallest_squad
