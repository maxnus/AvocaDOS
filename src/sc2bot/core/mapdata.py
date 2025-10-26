from dataclasses import dataclass
from typing import Self, TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


@dataclass
class MapData:
    bot: 'AvocaDOS'
    center: Point2
    base_townhall: Point2
    base_center: Point2
    enemy_base: Point2
    expansions: list[tuple[Point2, float]]
    enemy_expansions: list[tuple[Point2, float]]

    def get_proxy_location(self) -> Point2:
        return self.enemy_expansions[2][0]

    @staticmethod
    def get_expansion_list(bot: 'BaseBot') -> list[Point2]:
        try:
            return bot.expansion_locations_list
        except AssertionError:
            return []

    @classmethod
    async def analyze_map(cls, bot: 'AvocaDOS') -> Self:
        # TODO: fix

        center = bot.game_info.map_center
        base_townhall = bot.start_location
        base_center = base_townhall.towards(center, 8)
        #distances = await bot.get_travel_distances(bot.expansion_locations_list[:4], base)
        expansion_list = cls.get_expansion_list(bot)
        distances = [base_townhall.distance_to(exp) for exp in expansion_list]
        expansions = [(exp, dist) for dist, exp in sorted(zip(distances, expansion_list))]

        enemy_base = bot.enemy_start_locations[0]
        #distances = await bot.get_travel_distances(bot.expansion_locations_list, enemy_base)
        distances = [enemy_base.distance_to(exp) for exp in expansion_list]
        enemy_expansions = [(exp, dist) for dist, exp in sorted(zip(distances, expansion_list))]

        return MapData(
            bot,
            center=center,
            base_townhall=base_townhall,
            base_center=base_center,
            enemy_base=enemy_base,
            expansions=expansions,
            enemy_expansions=enemy_expansions
        )

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:
        match utype:
            case UnitTypeId.REFINERY:
                if near is None:
                    near = self.bot.map.base_townhall
                geysers = self.bot.vespene_geyser.closer_than(10.0, near)
                if geysers:
                    return geysers.random

            case UnitTypeId.SUPPLYDEPOT:
                positions = [p for p in self.bot.main_base_ramp.corner_depots if await self.bot.can_place_single(utype, p)]
                if positions:
                    return self.bot.map.base_center.closest(positions)
                if await self.bot.can_place_single(utype, self.bot.main_base_ramp.depot_in_middle):
                    return self.bot.main_base_ramp.depot_in_middle
                return await self.bot.find_placement(utype, near=self.bot.map.base_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    position = self.bot.main_base_ramp.barracks_correct_placement
                    if await self.bot.can_place_single(utype, position):
                        return position
                    return await self.bot.find_placement(utype, near=self.bot.map.base_center, addon_place=True)
                else:
                    return await self.bot.find_placement(utype, near=near, max_distance=max_distance,
                                                    random_alternative=False, addon_place=True)
            case UnitTypeId.COMMANDCENTER:
                if near is None:
                    self.bot.logger.error("NotImplemented")
                else:
                    return await self.bot.find_placement(utype, near=near)
            case _:
                self.bot.logger.error("Not implemented: {}", utype)
        return None

    async def get_travel_times(self, units: Units, destination: Point2, *,
                               target_distance: float = 0.0) -> list[float]:
        #distances = [d if d is not None else float('inf') for d in await self.get_travel_distances(units, destination)]
        #distances = await self.get_travel_distances(units, destination)
        # Too expensive at the moment, use euclidean distance instead
        distances = [1.2 * unit.distance_to(destination) for unit in units]
        times = [max(d - target_distance, 0) / (1.4 * unit.real_speed) for (unit, d) in zip(units, distances)]
        return times

    async def get_travel_distances(self, start: Units | list[Point2], destination: Point2) -> list[float]:
        if isinstance(start, Units):
            flying_units = start.flying
            if flying_units:
                raise NotImplementedError
            ground_units = start.not_flying
            query = [[unit, destination] for unit in ground_units]
        else:
            query = [[position, destination] for position in start]
        #self.logger.warning("query={}", query)
        distances = await self.bot.client.query_pathings(query)
        #self.logger.warning("distances={}", distances)

        #distances = [d if d >= 0 else None for d in distances]
        return distances

    async def get_travel_time(self, unit: Unit, destination: Point2, *,
                              target_distance: float = 0.0) -> float:
        if unit.is_flying:
            distance = unit.distance_to(destination)
        else:
            distance = await self.bot.client.query_pathing(unit.position, destination)
            if distance is None:
                # unreachable
                return float('inf')
        distance = max(distance - target_distance, 0)
        speed = 1.4 * unit.real_speed
        return distance / speed
