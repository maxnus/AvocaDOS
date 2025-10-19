from dataclasses import dataclass

from sc2.position import Point2


@dataclass
class MapKnowledge:
    base: Point2
    enemy_base: Point2
    expansions: list[tuple[Point2, float]]
    enemy_expansions: list[tuple[Point2, float]]

    def get_proxy_location(self) -> Point2:
        return self.enemy_expansions[2][0]
