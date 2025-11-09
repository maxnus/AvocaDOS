import math
from collections import Counter
from typing import Optional, TYPE_CHECKING, Any
import sys

from loguru import logger as _logger
from loguru._logger import Logger
from sc2.cache import property_cache_once_per_frame
from sc2.data import Result
from sc2.game_state import GameState
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.__about__ import __version__
from avocados.core.buildingmanager import BuildingManager
from avocados.core.buildordermanager import BuildOrderManager
from avocados.core.constants import TRAINERS, RESEARCHERS, RESOURCE_COLLECTOR_TYPE_IDS
from avocados.core.defensemanager import DefenseManager
from avocados.core.historymanager import HistoryManager
from avocados.core.intelmanager import IntelManager
from avocados.core.miningmanager import MiningManager
from avocados.core.strategymanager import StrategyManager
from avocados.core.unitutil import get_unit_type_counts
from avocados.core.logmanager import LogManager
from avocados.core.util import WithCallback
from avocados.debug.debugmanager import DebugManager
from avocados.debug.micro_scenario_manager import MicroScenarioManager
from avocados.mapdata.mapmanager import MapManager
from avocados.core.ordermanager import Order, OrderManager
from avocados.core.resourcemanager import ResourceManager
from avocados.core.objectivemanager import ObjectiveManager
from avocados.core.geomutil import LineSegment, get_best_score, dot
from avocados.combat.combatmanager import CombatManager
from avocados.combat.squadmanager import SquadManager

if TYPE_CHECKING:
    from avocados.core.botapi import BotApi


LOG_FORMAT = ("<level>[{level:8}]</level>"
              "<green>[{extra[step]}|{extra[time]}|{extra[prefix]}]</green>"
              " <level>{message}</level>")


class AvocaDOS:
    api: 'BotApi'
    name: str
    logger: Logger
    cache: dict[str, Any]
    # Manager
    log: LogManager
    map: Optional[MapManager]
    build: BuildOrderManager
    order: OrderManager
    resources: ResourceManager
    objectives: ObjectiveManager
    squads: SquadManager
    combat: CombatManager
    mining: MiningManager
    history: HistoryManager
    building: BuildingManager
    strategy: StrategyManager
    debug: Optional[DebugManager]
    micro_scenario: Optional[MicroScenarioManager]
    leave_at: Optional[float]
    # Other
    previous_orders: dict[int, Optional[Order]]

    def __init__(self, api: 'BotApi', *,
                 name: str = 'AvocaDOS',
                 build: Optional[str] = 'default',
                 debug: bool = False,
                 log_level: str = "DEBUG",
                 log_file: Optional[str] = None,
                 micro_scenario: Optional[dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]] = None,
                 leave_at: Optional[float] = 20 * 60,
                 ) -> None:
        super().__init__()
        self.api = api
        self.name = name
        self.logger = _logger.bind(bot=name, prefix=name, step=0, time=0)
        self.logger.remove()
        self.logger.add(
            sys.stdout,
            level=log_level,
            filter=lambda record: record['extra'].get('bot') == self.name,
            format=LOG_FORMAT,
        )
        if log_file:
            self.logger.add(
                f'data/{log_file}',
                level=log_level,
                filter=lambda record: record['extra'].get('bot') == self.name,
                format=LOG_FORMAT,
                rotation='1 day',
                retention='14 days',
            )
        self.cache = {}

        # Manager
        self.log = LogManager(self)
        self.logger.debug("Initializing {}...", self)
        self.build = BuildOrderManager(self, build=build)
        self.order = OrderManager(self)
        self.resources = ResourceManager(self)
        self.map = MapManager(self)
        self.intel = IntelManager(self)     # requires map
        self.objectives = ObjectiveManager(self)
        self.squads = SquadManager(self)
        self.combat = CombatManager(self)
        self.defense = DefenseManager(self)
        self.mining = MiningManager(self)
        self.history = HistoryManager(self)
        self.building = BuildingManager(self)
        self.strategy = StrategyManager(self)
        self.debug = DebugManager(self) if (debug or micro_scenario) else None
        if micro_scenario is not None:
            self.micro_scenario = MicroScenarioManager(self, units=micro_scenario)
        else:
            self.micro_scenario = None
        self.leave_at = leave_at
        self.logger.debug("{} initialized", self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({__version__})"

    async def on_start(self) -> None:
        version = __version__.replace('.', '-')
        matchup = f"{str(self.api.race)[5]}v{str(self.api.enemy_race)[5]}"
        tag = f"{self.name} v{version} {self.api.game_info.map_name} {matchup}"
        self.log.tag(tag, add_time=False)

        await self.map.on_start()
        await self.building.on_start()
        await self.intel.on_start()
        await self.build.on_start()

        if self.micro_scenario is not None:
            await self.micro_scenario.on_start()

        await self.mining.add_expansion(self.map.start_location)

    async def on_step_start(self, step: int) -> None:
        self.logger = self.logger.bind(step=self.api.state.game_loop, time=self.api.time_formatted)

        if step % 500 == 0:
            self._report_timings()

        await self.log.on_step(step)

        # Cleanup steps / internal to manager
        await self.mining.on_step_start(step)
        await self.map.on_step_start(step)
        await self.building.on_step_start(step)
        await self.intel.on_step_start(step)
        await self.resources.on_step_start(step)
        await self.history.on_step_start(step)
        await self.order.on_step_start(step)
        await self.squads.on_step_start(step)

    async def on_step(self, step: int):
        await self.on_step_start(step)

        if self.leave_at is not None and self.time >= self.leave_at - 1:
            self.log.tag('GG', add_time=False)
            if self.time >= self.leave_at:
                await self.api.client.leave()
            return

        if self.micro_scenario is not None and self.micro_scenario.running:
            await self.micro_scenario.on_step(step)

        # if self.time >= 180:
        #    self.logger.info("Minerals at 3 min = {}", self.minerals)
        await self.objectives.on_step(step)
        await self.defense.on_step(step)
        await self.squads.on_step(step)
        await self.combat.on_step(step)
        await self.strategy.on_step(step)
        await self.other(step)  # TODO: find a place for this
        await self.mining.on_step(step)
        if self.debug:
            await self.debug.on_step(step)

    async def on_end(self, game_result: Result) -> None:
        self.logger.info("Game result: {}", game_result)
        pass

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        pass

    async def on_unit_created(self, unit: Unit) -> None:
        pass

    async def on_building_construction_started(self, unit: Unit) -> None:
        pass

    async def on_building_construction_finished(self, unit: Unit) -> None:
        pass

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        pass

    # --- Properties

    @property
    def step(self) -> int:
        return self.state.game_loop

    @property
    def time(self) -> float:
        return self.api.time

    @property
    def state(self) -> GameState:
        return self.api.state

    # --- Units

    @property
    def units(self) -> Units:
        return self.api.units

    @property
    def workers(self) -> Units:
        return self.api.workers

    @property_cache_once_per_frame
    def army(self) -> Units:
        def army_filter(unit: Unit) -> bool:
            if unit.type_id in RESOURCE_COLLECTOR_TYPE_IDS:
                return False
            return True
        return self.units.filter(army_filter)

    @property
    def structures(self) -> Units:
        return self.api.structures

    @property
    def townhalls(self) -> Units:
        return self.api.townhalls

    @property
    def forces(self) -> Units:
        return self.units + self.structures

    def get_unit_type_counts(self) -> Counter[UnitTypeId]:
        return get_unit_type_counts(self.forces)

    # --- Pick unit

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
            if self.order.has_order(worker):
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

        workers = self.workers.filter(worker_filter)
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
                      + construction_time_discount * self.api.get_remaining_construction_time(unit)
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
            (WithCallback(worker, self.mining.remove_worker if self.mining.has_worker(worker) else None, worker),
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
            self.log.error("No trainer for {}", utype)
            return None

        free_trainers = self.structures(trainer_utype).ready.idle.filter(lambda x: not self.order.has_order(x))
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
                self.log.warning("Trainer for {} not implemented", utype)
                return None
        if not trainers:
            return None
        if position is None:
            return trainers.random
        return trainers.closest_to(position)

    def pick_researcher(self, upgrade: UpgradeId, *, position: Optional[Point2] = None) -> Optional[Unit]:
        researcher_utype = RESEARCHERS[upgrade]
        researchers = self.structures(researcher_utype).idle.filter(lambda x: not self.order.has_order(x))
        if not researchers:
            return None
        if position is None:
            return researchers.random
        return researchers.closest_to(position)

    def pick_army(self, *, strength: Optional[float] = None, position: Optional[Point2] = None,
                  max_priority: float = 0.0) -> Units:

        if not self.army:
            return self.army

        def army_filter(unit: Unit) -> bool:
            squad = self.squads.get_squad_of(unit.tag)
            if squad is None:
                return True
            if not squad.has_task():
                return True
            return squad.task_priority < max_priority

        units = self.army.filter(army_filter)
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
                units_strength += self.combat.get_strength(unit)
                if units_strength >= strength:
                    units = units.take(index + 1)
                    break
        return units

    # --- Callbacks

    async def other(self, step: int) -> None:
        # TODO: find the right location in the code

        for unit in self.structures(UnitTypeId.SUPPLYDEPOT).ready.idle:
            if not self.api.enemy_units.not_flying.closer_than(4.5, unit):
                self.order.ability(unit, AbilityId.MORPH_SUPPLYDEPOT_LOWER)
        for unit in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready.idle:
            if self.api.enemy_units.not_flying.closer_than(3.5, unit):
                self.order.ability(unit, AbilityId.MORPH_SUPPLYDEPOT_RAISE)

        if step % 8 == 0:
            for orbital in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
                if orbital.energy >= 50:
                    mineral_fields = self.api.mineral_field.closer_than(8, orbital.position)
                    if not mineral_fields:
                        continue
                    #mineral_field = mineral_fields.closest_to(orbital.position)
                    mineral_field, contents = get_best_score(mineral_fields, lambda mf: mf.mineral_contents)
                    self.logger.debug("Dropping mule at {} with {} minerals", mineral_field, contents)
                    self.order.ability(orbital, AbilityId.CALLDOWNMULE_CALLDOWNMULE, target=mineral_field)

    # --- Utility

    def time_until_tech(self, structure_type: UnitTypeId) -> float:
        requirements = self.api.get_tech_requirement(structure_type)
        if not requirements:
            return 0
        for req in requirements:
            if self.structures(req).ready:
                return 0
        remaining_time = float('inf')
        for req in requirements:
            for structure in self.structures(req):
                remaining_time = min(self.api.get_remaining_construction_time(structure), remaining_time)
        return remaining_time

    def intercept_unit(self, unit: Unit, target: Unit, *,
                       max_intercept_distance: float = 10.0) -> Point2:
        """TODO: friendly units"""
        d = target.position - unit.position
        dsq = dot(d, d)
        # if dsq > 200:
        #     # Far away, don't try to intercept
        #     return target.position

        v = self.api.get_unit_velocity_vector(target)
        if v is None:
            self.logger.debug("No target velocity")
            return target.position
        s = 1.4 * unit.real_speed
        vsq = dot(v, v)
        ssq = s * s
        denominator = vsq - ssq
        if abs(denominator) < 1e-8:
            self.logger.debug("Linear case")
            # TODO: linear case
            return target.position

        dv = dot(d, v)
        disc = dv*dv - denominator * dsq
        if disc < 0:
            self.logger.debug("No real solution")
            # no real solution
            return target.position
        sqrt = math.sqrt(disc)
        tau1 = (-dv + sqrt) / denominator
        tau2 = (-dv - sqrt) / denominator
        tau = min(tau1, tau2)
        intercept = target.position + tau * v
        self.logger.debug("{} intercepting {} at {}", unit.position, target.position, intercept)
        return intercept

    # --- Private

    def _report_timings(self) -> None:
        managers = [
            self.intel,
            self.history,
            self.building,
            self.mining,
            self.squads,
            self.defense,
            self.combat,
            self.objectives,
            self.debug
        ]
        for manager in managers:
            if manager is None:
                continue
            for key, timings in manager.timings.items():
                self.logger.info("{:<16s} : {:<24s}: {}", type(manager).__name__, key, timings)
                timings.reset()
