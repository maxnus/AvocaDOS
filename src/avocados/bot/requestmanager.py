from typing import Optional, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados import api
from avocados.bot.expansionmanager import ExpansionManager
from avocados.combat.squadmanager import SquadManager
from avocados.combat.util import get_strength
from avocados.core.constants import TRAINERS, RESEARCHERS
from avocados.core.manager import BotManager
from avocados.core.util import WithCallback
from avocados.geometry.util import LineSegment
from avocados.mapdata import MapManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class RequestManager(BotManager):
    map: MapManager
    squads: SquadManager
    expand: ExpansionManager

    def __init__(self, bot: 'AvocaDOS', *,
                 map_manager: MapManager,
                 squad_manager: SquadManager,
                 expansion_manager: ExpansionManager
                 ) -> None:
        super().__init__(bot)
        self.map = map_manager
        self.squads = squad_manager
        self.expand = expansion_manager

    async def pick_workers(self, location: Point2 | Unit | LineSegment, *,
                           number: int,
                           target_distance: float = 0.0,
                           include_moving: bool = True,
                           include_collecting: bool = True,
                           include_constructing: bool = True,
                           construction_time_discount: float = 0.7,
                           carrying_resource_penalty: float = 1.5,
                           ) -> list[tuple[WithCallback[Unit], float]]:

        def worker_filter(worker: Unit) -> bool:
            if api.order.has_order(worker):
                return False
            if worker.is_idle:
                return True
            if include_moving and worker.is_moving:
                return True
            if include_collecting and worker.is_collecting:
                return True
            if include_constructing and worker.is_constructing_scv:
                return True
            #if self.mining.has_worker(worker):
            #    return include_collecting
            return False

        workers = api.workers.filter(worker_filter)
        if not workers:
            return []
        # Prefilter for performance
        if isinstance(location, Unit):
            location = location.position
        if isinstance(location, Point2):
            if len(workers) > number + 10:
                workers = workers.closest_n_units(position=location, n=number + 10)
            travel_times = await self.map.get_travel_times(workers, location, target_distance=target_distance)
            workers_and_dist = {
                unit: travel_time
                      + (carrying_resource_penalty if unit.is_carrying_resource else 0)
                      + construction_time_discount * api.ext.get_remaining_construction_time(unit)
                for unit, travel_time in zip(workers, travel_times)
            }
        elif isinstance(location, LineSegment):
            # TODO: remove?
            workers_and_dist = {unit: location.distance_to(unit) for unit in workers}
        else:
            raise TypeError(f"unknown location type: {type(location)}")

        #result = heapq.nsmallest(number, workers_and_dist.items(), key=lambda item: item[1])
        result = sorted(workers_and_dist.items(), key=lambda x: x[1])[:number]
        with_callbacks = [
            (WithCallback(worker, self.expand.remove_worker if self.expand.has_worker(worker) else None, worker),
             distance) for worker, distance in result
        ]
        return with_callbacks

    async def pick_worker(self,
                          location: Point2 | Unit, *,
                          target_distance: float = 0.0,
                          include_moving: bool = True,
                          include_collecting: bool = True,
                          include_constructing: bool = True,
                          construction_time_discount: float = 0.7
                          ) -> tuple[Optional[WithCallback[Unit]], Optional[float]]:
        workers = await self.pick_workers(location=location, number=1,
                                          target_distance=target_distance,
                                          include_moving=include_moving,
                                          include_collecting=include_collecting,
                                          include_constructing=include_constructing,
                                          construction_time_discount=construction_time_discount)
        if not workers:
            return None, None
        return workers[0]

    def pick_trainer(self, utype: UnitTypeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        trainer_utype = TRAINERS.get(utype)
        if trainer_utype is None:
            api.log.error("No trainer for {}", utype)
            return None

        free_trainers = api.structures(trainer_utype).ready.idle.filter(lambda x: not api.order.has_order(x))
        #self.logger.trace("free trainers for {}: {}", utype.name, free_trainers)
        if not free_trainers:
            return None

        # Additional logic
        match utype:
            case UnitTypeId.ORBITALCOMMAND:
                trainers = free_trainers
            case UnitTypeId.SCV:
                trainers = free_trainers
            case UnitTypeId.MARINE | UnitTypeId.REAPER:
                # Prefer reactors, unless position is given
                # TODO: prioritize reactors even if position is passed, in close calls
                if position is None:
                    trainers = free_trainers.filter(lambda x: x.has_reactor)
                    if not trainers:
                        trainers = free_trainers.filter(lambda x: not x.has_techlab)
                    if not trainers:
                        trainers = free_trainers
                else:
                    trainers = free_trainers
            case UnitTypeId.MARAUDER:
                trainers = free_trainers.filter(lambda x: x.has_techlab)
            case UnitTypeId.BARRACKSTECHLAB | UnitTypeId.BARRACKSREACTOR:
                trainers = free_trainers.filter(lambda x: not x.has_add_on)
            case _:
                api.log.error("MissingTrainer{}", utype)
                return None
        if not trainers:
            return None
        if position is None:
            return trainers.random
        return trainers.closest_to(position)

    def pick_researcher(self, upgrade: UpgradeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        researcher_utype = RESEARCHERS[upgrade]
        researchers = api.structures(researcher_utype).idle.filter(lambda x: not api.order.has_order(x))
        if not researchers:
            return None
        if position is None:
            return researchers.random
        return researchers.closest_to(position)

    def pick_army(self, *, strength: Optional[float] = None, position: Optional[Point2] = None,
                  max_priority: float = 0.0) -> Units:

        if not api.army:
            return api.army

        def army_filter(unit: Unit) -> bool:
            squad = self.squads.get_squad_of(unit.tag)
            if squad is None:
                return True
            if not squad.has_task():
                return True
            return squad.task_priority < max_priority

        units = api.army.filter(army_filter)
        if not units:
            return units

        if position is None:
            units.sorted(lambda u: squad.task_priority if (squad := self.squads.get_squad_of(u.tag)) is not None else 0)
        else:
            # Pick units with smallest distance / priority difference
            units.sorted(lambda u: u.distance_to(position)
                                   / (max_priority - (squad.task_priority if (squad := self.squads.get_squad_of(u.tag)) is not None else 0)))
        if strength is not None:
            units_strength = 0.0
            for index, unit in enumerate(units):
                units_strength += get_strength(unit)
                if round(units_strength, 2) >= strength:
                    units = units.take(index + 1)
                    break
        return units
