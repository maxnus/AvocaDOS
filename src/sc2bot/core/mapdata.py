from dataclasses import dataclass
from typing import Self, TYPE_CHECKING

from sc2.position import Point2

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


@dataclass
class MapData:
    center: Point2
    base_townhall: Point2
    base_center: Point2
    enemy_base: Point2
    expansions: list[tuple[Point2, float]]
    enemy_expansions: list[tuple[Point2, float]]

    def get_proxy_location(self) -> Point2:
        return self.enemy_expansions[2][0]

    @classmethod
    async def analyze_map(cls, bot: 'BotBase') -> Self:
        # TODO: fix

        center = bot.game_info.map_center
        base_townhall = bot.start_location
        base_center = base_townhall.towards(center, 8)
        #distances = await bot.get_travel_distances(bot.expansion_locations_list[:4], base)
        distances = [base_townhall.distance_to(exp) for exp in bot.expansion_locations_list]
        expansions = [(exp, dist) for dist, exp in sorted(zip(distances, bot.expansion_locations_list))]

        enemy_base = bot.enemy_start_locations[0]
        #distances = await bot.get_travel_distances(bot.expansion_locations_list, enemy_base)
        distances = [enemy_base.distance_to(exp) for exp in bot.expansion_locations_list]
        enemy_expansions = [(exp, dist) for dist, exp in sorted(zip(distances, bot.expansion_locations_list))]

        return MapData(
            center=center,
            base_townhall=base_townhall,
            base_center=base_center,
            enemy_base=enemy_base,
            expansions=expansions,
            enemy_expansions=enemy_expansions
        )
