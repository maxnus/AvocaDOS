from dataclasses import dataclass
from typing import Self, TYPE_CHECKING

from sc2.position import Point2

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


@dataclass
class MapData:
    base: Point2
    base_center: Point2
    enemy_base: Point2
    center: Point2
    expansions: list[tuple[Point2, float]]
    enemy_expansions: list[tuple[Point2, float]]

    def get_proxy_location(self) -> Point2:
        return self.enemy_expansions[2][0]

    @classmethod
    async def analyze_map(cls, bot: 'BotBase') -> Self:
        # TODO: fix

        base = bot.start_location
        center = bot.game_info.map_center
        base_center = base.towards(center, 6)
        #distances = await bot.get_travel_distances(bot.expansion_locations_list[:4], base)
        distances = [base.distance_to(exp) for exp in bot.expansion_locations_list]
        expansions = [(exp, dist) for dist, exp in sorted(zip(distances, bot.expansion_locations_list))]

        enemy_base = bot.enemy_start_locations[0]
        #distances = await bot.get_travel_distances(bot.expansion_locations_list, enemy_base)
        distances = [enemy_base.distance_to(exp) for exp in bot.expansion_locations_list]
        enemy_expansions = [(exp, dist) for dist, exp in sorted(zip(distances, bot.expansion_locations_list))]

        return MapData(
            base=base,
            base_center=base_center,
            enemy_base=enemy_base,
            center=center,
            expansions=expansions,
            enemy_expansions=enemy_expansions
        )
