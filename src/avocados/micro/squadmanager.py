import random
from collections.abc import Iterator
from typing import TYPE_CHECKING, Optional

from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.util import squared_distance, normalize_tags
from avocados.micro.squad import Squad, SquadAttackTask, SquadTask

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class SquadManager(BotObject):
    _squads: dict[int, Squad]
    _tag_to_squad: dict[int, int]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._squads = {}
        self._tag_to_squad = {}

    async def on_step(self, step: int) -> None:

        # Remove dead tags
        self._tag_to_squad = {tag: squad_id for tag, squad_id in self._tag_to_squad.items()
                              if tag in self.api.alive_tags}

        for squad in list(self._squads.values()):
            squad.tags &= self.api.alive_tags
            if len(squad) == 0:
                self.logger.info("Removing empty {}", squad)
                self._squads.pop(squad.id)

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

    def _filter_tags(self, tags: set[int]) -> set[int]:
        tags_filtered = tags.copy()
        # TODO: use _tags_to_squad
        for squad in self:
            if common_tags := tags & squad.tags:
                self.logger.warning("Tags {} are already assigned to {}", common_tags, squad)
                tags_filtered -= common_tags
        return tags_filtered

    def create(self, units: Units | set[int]) -> Squad:
        squad = Squad(self.bot, _code=True)
        self.add_units(squad, units)
        self._squads[squad.id] = squad
        return squad

    def delete(self, squad: Squad | int) -> None:
        id_ = squad.id if isinstance(squad, Squad) else squad
        squad = self._squads.pop(id_, None)
        if squad is None:
            self.logger.warning("Squad {} not found", id_)
        self.remove_units(squad, squad.tags)

    def add_units(self, squad: Squad, units: Unit | Units | int | set[int]) -> None:
        tags = normalize_tags(units)
        tags = self._filter_tags(tags)
        for tag in tags:
            self._tag_to_squad[tag] = squad.id
        squad.tags.update(tags)

    def remove_units(self, squad: Squad, units: Unit | Units | int | set[int]) -> None:
        tags = normalize_tags(units)
        for tag in tags:
            if self._tag_to_squad.get(tag) == squad.id:
                self._tag_to_squad.pop(tag)
            else:
                self.logger.warning("Tag {} was not assigned to {}", tag, squad)
        squad.tags.difference_update(tags)

    def get_squad_of_unit(self, unit: Unit | int) -> Optional[Squad]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        return self._tag_to_squad.get(tag, None)

    def remove_from_squads(self, units: Units | set[int]) -> None:
        tags = units.tags if isinstance(units, Units) else units
        for tag in tags:
            if (squad_id := self._tag_to_squad.get(tag, None)) is None:
                continue
            squad = self._squads[squad_id]
            self.remove_units(squad, tag)

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

    def with_task(self, task: SquadTask) -> list[Squad]:
        return [squad for squad in self if squad.task == task and len(squad) > 0]
