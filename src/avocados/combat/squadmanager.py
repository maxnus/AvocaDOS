import random
from collections.abc import Iterator, Callable
from time import perf_counter
from typing import TYPE_CHECKING, Optional

from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.manager import BotManager
from avocados.geometry import Circle
from avocados.geometry.util import squared_distance
from avocados.core.unitutil import normalize_tags
from avocados.combat.squad import Squad, SquadTask, SquadJoinTask, SquadRetreatTask

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


MAX_SQUAD_SIZE = 24
#RETREAT_STRENGTH_PERCENTAGE = 0.8
RETREAT_MIN_BASE_DISTANCE = 16.0
RETREAT_DISTANCE = 25.0
RETREAT_HEALTH_PERCENTAGE = 0.40
SQUAD_JOIN_DISTANCE = 2.0


class SquadManager(BotManager):
    _squads: dict[int, Squad]
    _tag_to_squad: dict[int, int]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._squads = {}
        self._tag_to_squad = {}

    async def on_step_start(self, step: int) -> None:
        # Remove dead tags
        self._tag_to_squad = {tag: squad_id for tag, squad_id in self._tag_to_squad.items()
                              if tag in self.api.alive_tags}

        for squad in list(self._squads.values()):
            squad._tags &= self.api.alive_tags
            if len(squad) == 0:
                self.delete(squad)

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        # Join squads

        self._join_squads()

        for squad in self:
            damage = sum(self.api.damage_received[unit.tag] for unit in squad.units)
            squad.damage_taken.appendleft(damage)

        self._start_retreat()
        self._stop_retreat()

        # Remove far units
        for squad in list(self._squads.values()):
            far_units = squad.units.further_than(14.0, squad.center)
            self.remove_units(squad, far_units)

        if step % 1000 == 0:
            self.status_dump()

        self.timings['step'].add(t0)

    def status_dump(self):
        self.logger.debug("{} Status Dump:", self)
        known_unit_ids = set()
        for squad in self:
            self.logger.debug("{}", squad)
            already_known = squad._tags & known_unit_ids
            if already_known:
                self.log.error("Units in more than one squad")
            already_known.update(squad._tags)
            for unit in squad.units:
                s = self._tag_to_squad.get(unit.tag, None)
                if s is None:
                    self.log.error("tag_to_squad is missing tag")
                if s != squad.id:
                    self.log.error("tag_to_squad pointing to wrong squad id")

    def __len__(self) -> int:
        return len(self._squads)

    def __iter__(self) -> Iterator[Squad]:
        yield from self._squads.values()

    def get(self, squad_id: int) -> Optional[Squad]:
        return self._squads.get(squad_id)

    def filter(self, func: Callable[[Squad], bool]) -> list[Squad]:
        return [s for s in self._squads.values() if func(s)]

    def sort(self, key: Callable[[Squad], float], *, reverse: bool = False) -> list[Squad]:
        return sorted(self._squads.values(), key=key, reverse=reverse)

    def get_squads_with_low_priority(self, max_priority: Optional[float] = 0.5) -> list[Squad]:
        if max_priority is None:
            squads = list(self._squads.values())
        else:
            squads = self.filter(lambda s: (s.task.priority if s.has_task() else 0) < max_priority)
        squads.sort(key=lambda s: s.task.priority if s.has_task() else 0)
        return squads

    def _filter_tags(self, tags: set[int]) -> set[int]:
        tags_filtered = tags.copy()
        # TODO: use _tags_to_squad
        for squad in self:
            if common_tags := tags & squad._tags:
                self.log.warning("Tags {} are already assigned to {}", common_tags, squad)
                tags_filtered -= common_tags
        return tags_filtered

    def create(self, units: Units | set[int], *,
               target_strength: Optional[float] = None,
               remove_from_squads: bool = False) -> Squad:
        if not units:
            raise ValueError("No units given")
        if target_strength is None:
            target_strength = self.combat.get_strength(units)
        squad = Squad(self.bot, target_strength=target_strength, _code=True)
        self.add_units(squad, units, remove_from_squads=remove_from_squads)
        self._squads[squad.id] = squad
        self.logger.debug("Created squad {}", squad)
        return squad

    def join(self, squad: Squad, *other: Squad) -> Squad:
        for s in other:
            self.transfer_units(s, squad)
            self.delete(s)
        return squad

    def delete(self, squad: Squad | int) -> None:
        id_ = squad.id if isinstance(squad, Squad) else squad
        squad = self._squads.pop(id_, None)
        if squad is None:
            self.log.warning("Squad {} not found", id_)
        else:
            self.remove_units(squad, squad._tags)
            self.logger.debug("Deleted squad {}", squad)

    def add_units(self, squad: Squad, units: Unit | Units | int | set[int], *,
                  remove_from_squads: bool = False) -> None:
        tags = normalize_tags(units)
        if remove_from_squads:
            self.remove_from_squads(units)
        tags = self._filter_tags(tags)
        for tag in tags:
            self._tag_to_squad[tag] = squad.id
        squad._tags.update(tags)

    def transfer_units(self, source: Squad, target: Squad, *, units: Optional[Units] = None) -> None:
        if units is None:
            units = source.units
        self.remove_units(source, units)
        self.add_units(target, units, remove_from_squads=False)

    def remove_units(self, squad: Squad, units: Unit | Units | int | set[int]) -> None:
        tags = normalize_tags(units)
        for tag in tags:
            if self._tag_to_squad.get(tag) == squad.id:
                self._tag_to_squad.pop(tag)
            else:
                self.log.warning("Tag {} was not assigned to {}", tag, squad)
        squad._tags.difference_update(tags)

    def has_squad(self, unit: Unit | int) -> bool:
        tag = unit.tag if isinstance(unit, Unit) else unit
        return tag in self._tag_to_squad

    def get_squad_of(self, unit: Unit | int) -> Optional[Squad]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        squad_id = self._tag_to_squad.get(tag, None)
        if squad_id is None:
            return None
        squad = self._squads.get(squad_id)
        if squad is None:
            self.log.error("Squad not found: {}", squad_id)
        return squad

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

    def with_task(self, task_type: type[SquadTask],
                  filter_: Optional[Callable[[SquadTask], bool]] = None) -> list[Squad]:
        return [s for s in self if isinstance(s.task, task_type)
                and len(s) > 0 and (filter_ is None or filter_(s.task))]

    def not_with_task(self, task_type: type[SquadTask],
                      filter_: Optional[Callable[[SquadTask], bool]] = None) -> list[Squad]:
        return [s for s in self if not isinstance(s.task, task_type)
                and len(s) > 0 and (filter_ is None or filter_(s.task))]

    # --- Private

    def _join_squads(self) -> None:
        for squad in self.with_task(task_type=SquadJoinTask):
            target_squad = squad.task.target
            if len(target_squad) == 0:
                squad.remove_task()
                continue
            if squad.spacing_to_squad(target_squad) <= SQUAD_JOIN_DISTANCE:
                self.join(target_squad, squad)

    def _start_retreat(self) -> None:
        for squad in self.not_with_task(task_type=SquadRetreatTask):
            # if (squad.strength < RETREAT_STRENGTH_PERCENTAGE * squad.target_strength
            if ((squad.damage_taken_percentage > RETREAT_HEALTH_PERCENTAGE
                 or squad.strength < self.combat.get_strength(self.api.all_enemy_units.closer_than(8, squad.center)))
                    and squad.center.distance_to(self.map.base.center) > RETREAT_MIN_BASE_DISTANCE):
                retreat_point = self.map.nearest_pathable(squad.center.towards(self.map.center, RETREAT_DISTANCE))
                retreat_area = Circle(retreat_point, 1.5)
                self.logger.debug("Ordering {} to retreat to {}", squad, retreat_area)
                squad.retreat(retreat_area, priority=1)  # , priority=min(squad.task_priority+0.1, ))

    def _stop_retreat(self) -> None:
        for squad in self.with_task(task_type=SquadRetreatTask):
            # if squad.all_units_in_area(squad.task.target):
            if squad.center in squad.task.target or self.time > squad.task.started + 20:
                self.logger.debug("{} has retreated to {}", squad, squad.task.target)
                squad.remove_task()
