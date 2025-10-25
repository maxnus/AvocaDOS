from sc2 import maps
from sc2.maps import Map
from sc2.position import Point2


class Sc2Map:
    name: str
    map: Map

    def __init__(self, name: str):
        self.name = name
        self.map = maps.get(name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name})"


class MicroTrainingMap(Sc2Map):
    micro_locations: list[Point2]

    def __init__(self, name: str, micro_locations: list[Point2]):
        super().__init__(name)
        self.micro_locations = micro_locations
