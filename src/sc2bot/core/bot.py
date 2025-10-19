import random
import sys
from enum import Enum
from time import perf_counter
from typing import Optional

from loguru import logger
from loguru._logger import Logger
from sc2.bot_ai import BotAI
from sc2.constants import IS_STRUCTURE
from sc2.game_data import Cost
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.ability_id import AbilityId

from sc2bot.core.commander import Commander
from sc2bot.core.history import History


class BotBase(BotAI):
    name: str
    seed: int
    logger: Logger
    debug_messages: list[str]
    commander: dict[str, Commander]
    history: History

    def __init__(self, name: str, *, seed: int = 0) -> None:
        super().__init__()
        self.name = name
        self.seed = seed
        random.seed(seed)
        self.debug_messages = []
        self.logger = logger.bind(bot=name, prefix='Bot', frame=0, time=0)
        self.history = History(self)

        def ingame_logging(message):
            if not hasattr(self, 'client'):
                return
            formatted = message.record['extra'].get('formatted', message)
            self.debug_messages.append(formatted)

        self.logger.add(
            sys.stderr,
            level="TRACE",
            filter=lambda record: record['extra'].get('bot') == name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )
        self.logger.add(
            ingame_logging,
            level="DEBUG",
            filter=lambda record: record['extra'].get('bot') == name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )
        self.commander = {}
        self.logger.debug("Initialized {}", self)

    def __repr__(self) -> str:
        return f"{self.name}(seed={self.seed})"

    async def on_start(self) -> None:
        self.client.game_step = 1

    async def on_step(self, iteration: int):
        self.logger = self.logger.bind(frame=iteration, time=self.time)

        self.history.on_step(iteration)
        await self.update_commanders(iteration)
        self.show_debug_info()

    # --- Debug

    def debug_text_screen(self,
                          lines: list[str] | str,
                          *,
                          position: tuple[float, float] = (0.005, 0.01),
                          size: int = 16, color: tuple[int, int, int] = (255, 255, 0),
                          max_lines: int = 10):
        y = position[1]
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            self.client.debug_text_screen(line, (position[0], y), size=size, color=color)
            y += size / 1000

    def debug_text_world(self,
                         lines: list[str] | str,
                         position: Unit | Point3,
                         *,
                         size: int = 16, color: tuple[int, int, int] = (0, 255, 0),
                         max_lines: int = 10):
        if isinstance(position, Unit):
            position = position.position3d
        offset = 0.0
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            line_position = position + Point3((0, offset, 0))
            self.client.debug_text_world(line, line_position, size=size, color=color)
            offset += size / 1000

    def show_debug_info(self):
        self.debug_text_screen(self.debug_messages)
        info = []
        for commander in self.commander.values():
            info.append(repr(commander))
            for task in commander.tasks:
                info.append("   "+ repr(task))
        self.debug_text_screen(info, position=(0.005, 0.4))

        mineral_rate, vespene_rate = self.history.get_resource_rates()
        self.debug_text_screen(f"{mineral_rate=:.2f}, {vespene_rate=:.2f}", position=(0.8, 0.05))

        mineral_rate, vespene_rate = self.estimate_resource_collection_rates()
        self.debug_text_screen(f"{mineral_rate=:.2f}, {vespene_rate=:.2f}", position=(0.8, 0.08))

        min_step, avg_step, max_step, last_step = self.step_time
        if last_step <= 10:
            color = (0, 255, 0)
        elif last_step <= 40:
            color = (255, 255, 0)
        else:
            color = (255, 0, 0)
        self.debug_text_screen(f"step time (ms): {last_step:.3f} (avg={avg_step:.3f}, min={min_step:.3f}"
                               f", max={max_step:.3f})", position=(0.73, 0.7), color=color)

        for commander in self.commander.values():
            for tag, order in commander.orders.items():
                unit = (self.units + self.structures).find_by_tag(tag)
                if unit is None:
                    continue
                self.debug_text_world(str(order), unit)

    # --- Commanders

    def add_commander(self, name, **kwargs) -> Commander:
        commander = Commander(self, name, **kwargs)
        self.commander[name] = commander
        logger.debug("Adding {}", commander)
        return commander

    async def update_commanders(self, iteration: int) -> None:
        for commander in self.commander.values():
            await commander.on_step(iteration)

    def get_controlling_commander(self, unit: Unit) -> Optional[Commander]:
        for commander in self.commander.values():
            if unit.tag in commander.tags:
                return commander
        return None

    # --- Macro utility

    async def expand(self) -> int:
        if not self.can_afford(UnitTypeId.COMMANDCENTER):
            return 0

        target = self.time / 60
        have = self.townhalls(UnitTypeId.COMMANDCENTER).amount
        pending = self.already_pending(UnitTypeId.COMMANDCENTER)
        to_build = int(target - have - pending)
        queued = 0
        for _ in range(to_build):
            await self.expand_now()
            queued += 1
        return queued

    async def build_supply(self):
        ccs = self.townhalls(UnitTypeId.COMMANDCENTER).ready
        if ccs.exists:
            cc = ccs.first
            if self.supply_left < 4 and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
                if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                    await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 5))

    # --- Base utility

    def get_attributes(self, utype: UnitTypeId) -> list[Enum]:
        return self.game_data.units[utype.value].attributes

    def is_structure(self, utype: UnitTypeId) -> bool:
        return IS_STRUCTURE in self.get_attributes(utype)

    def get_base_location(self) -> Point2:
        return self.townhalls.first.position

    def get_enemy_base_location(self) -> Point2:
        return self.enemy_start_locations[0]

    def get_expansion_location(self, n: int) -> Point2:
        base = self.get_base_location()
        if n == 0:
            return base
        expansions = self.get_sorted_expansion_locations(base)
        if n > len(expansions):
            raise ValueError(f"expansion {n}")
        return expansions[n - 1]

    def get_enemy_expansion_location(self, n: int) -> Point2:
        base = self.get_enemy_base_location()
        if n == 0:
            return base
        expansions = self.get_sorted_expansion_locations(base)
        if n > len(expansions):
            raise ValueError(f"expansion {n}")
        return expansions[n - 1]

    def get_sorted_expansion_locations(self, reference: Point2) -> list[Point2]:
        return list(sorted(
            self.expansion_locations_list, key=lambda e: e.distance_to(reference)
        ))

    def get_proxy_location(self) -> Point2:
        #return self.game_info.map_center.towards(self.get_enemy_base_location(), 25)
        return self.get_enemy_expansion_location(3)

    def get_scv_build_target(self, scv: Unit) -> Optional[Unit]:
        """Return the building unit that this SCV is constructing, or None."""
        if not scv.is_constructing_scv:
            return None
        # Try to match via nearby incomplete structure
        buildings_being_constructed = self.structures.filter(lambda s: s.build_progress < 1)
        if not buildings_being_constructed:
            return None
        target = buildings_being_constructed.closest_to(scv)
        if target and scv.distance_to(target) < 3:
            return target
        return None

    def get_cost(self, utype: UnitTypeId) -> Cost:
        return self.game_data.units[utype.value].cost

    def get_remaining_construction_time(self, scv: Unit) -> float:
        if not scv.is_constructing_scv:
            return 0
        building = self.get_scv_build_target(scv)
        if not building:
            return 0.0
        return self.get_cost(building.type_id).time * (1 - building.build_progress)

    async def get_travel_distances(self, units: Units, destination: Point2) -> list[float]:
        flying_units = units.flying
        if flying_units:
            raise NotImplementedError
        ground_units = units.not_flying
        query = [[unit.position, destination] for unit in ground_units]
        distances = await self.client.query_pathings(query)
        #distances = [d if d >= 0 else None for d in distances]
        return distances

    async def get_travel_time(self, unit: Unit, destination: Point2, *,
                              target_distance: float = 0.0) -> float:
        if unit.is_flying:
            distance = unit.distance_to(destination)
        else:
            distance = await self.client.query_pathing(unit.position, destination)
            if distance is None:
                # unreachable
                return float('inf')
        distance = max(distance - target_distance, 0)
        speed = 1.4 * unit.real_speed
        return distance / speed

    async def get_travel_times(self, units: Units, destination: Point2, *,
                               target_distance: float = 0.0) -> list[float]:
        #distances = [d if d is not None else float('inf') for d in await self.get_travel_distances(units, destination)]
        distances = await self.get_travel_distances(units, destination)
        times = [max(d - target_distance, 0) / (1.4 * unit.real_speed) for (unit, d) in zip(units, distances)]
        return times

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2]:
        match utype:
            case UnitTypeId.SUPPLYDEPOT:
                positions = [p for p in self.main_base_ramp.corner_depots if await self.can_place_single(utype, p)]
                if positions:
                    return self.get_base_location().closest(positions)
                return await self.find_placement(utype, near=self.get_base_location())
            case UnitTypeId.BARRACKS:
                if near is None:
                    position = self.main_base_ramp.barracks_correct_placement
                    if await self.can_place_single(utype, position):
                        return position
                    return await self.find_placement(utype, near=self.get_base_location(), addon_place=True)
                else:
                    return await self.find_placement(utype, near=near, max_distance=max_distance,
                                                     random_alternative=False, addon_place=True)
            case UnitTypeId.COMMANDCENTER:
                if near is None:
                    self.logger.error("NotImplemented")
                else:
                    return await self.find_placement(utype, near=near)
            case _:
                self.logger.error("Not implemented: {}", utype)
        return None

    def estimate_resource_collection_rates(self, *,
                                           excluded_workers: Optional[Unit | Units] = None,
                                           worker_mineral_rate: float = 1.0) -> tuple[float, float]:
        # TODO only correctly placed townhalls
        mineral_workers = 0
        for townhall in self.townhalls:
            mineral_workers += len(self.workers_mining_at(townhall, excluded_workers=excluded_workers))
        mineral_rate = max(worker_mineral_rate * mineral_workers, 0)
        return mineral_rate, 0

    def workers_mining_at(self, townhall: Unit, *,
                          excluded_workers: Optional[Unit | Units] = None,
                          radius: float = 10.0) -> Units:
        """Return number of workers currently mining minerals around a specific base."""
        nearby_minerals = self.mineral_field.closer_than(radius, townhall)
        if not nearby_minerals:
            return Units([], self)
        allowed_orders = {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}
        allowed_tags = {0, townhall.tag, *(m.tag for m in nearby_minerals)}
        workers = self.workers.closer_than(radius, townhall)
        if excluded_workers:
            excluded_workers_tags = (excluded_workers.tags if isinstance(excluded_workers, Units)
                                     else {excluded_workers.tag})
            workers = workers.tags_not_in(excluded_workers_tags)
        workers = workers.filter(lambda w: (w.orders and w.orders[0].ability.id in allowed_orders) and w.order_target in allowed_tags)
        return Units(workers, self)

    def time_for_cost(self, cost: Cost, *, excluded_workers: Optional[Unit | Units] = None) -> float:
        if self.minerals >= cost.minerals and self.vespene >= cost.vespene:
            return 0
        mineral_rate, vespene_rate = self.estimate_resource_collection_rates(excluded_workers=excluded_workers)
        time = 0
        if cost.minerals > 0:
            if mineral_rate == 0:
                return float('inf')
            time = max((cost.minerals - self.minerals) / mineral_rate, time)
        if cost.vespene > 0:
            if vespene_rate == 0:
                return float('inf')
            time = max((cost.vespene - self.vespene) / vespene_rate, time)
        return time

    async def on_unit_created(self, unit: Unit) -> None:
        self.logger.trace("Unit {} created", unit)
        # TODO fix
        self.commander['ProxyMarine'].take_control(unit)

    async def on_building_construction_started(self, unit: Unit) -> None:
        self.logger.trace("Building {} construction started", unit)
        # TODO fix
        self.commander['ProxyMarine'].take_control(unit)
