from typing import TYPE_CHECKING, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit

from avocados.core.manager import BotManager
from avocados.core.util import CallbackOnAccess

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class BuildingManager(BotManager):
    _reserved: list

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self._reserved = []

    async def on_step(self, step: int) -> None:
        self._reserved.clear()

    async def get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[CallbackOnAccess[Point2 | Unit]]:

        location = await self._get_building_location(utype=utype, near=near, max_distance=max_distance)
        if not location:
            return None

        return CallbackOnAccess(location, self._reserved.append, location)

    async def _get_building_location(self, utype: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[Point2 | Unit]:

        match utype:
            case UnitTypeId.REFINERY:
                if near is None:
                    near = self.map.start_location.center
                geysers = self.api.vespene_geyser.closer_than(10.0, near).filter(lambda g: g.has_vespene)
                if not geysers:
                    return None
                if len(geysers) == 1:
                    return geysers.first
                geysers_contents = sorted([(geyser, geyser.vespene_contents) for geyser in geysers],
                                          key=lambda x: x[1], reverse=True)
                if geysers_contents[0][1] > geysers_contents[1][1]:
                    return geysers_contents[0][0]
                return geysers.closest_to(near)

            case UnitTypeId.SUPPLYDEPOT:
                ramp_positions = [p for p in self.map.start_location.ramp.corner_depots
                                  if await self.api.can_place_single(utype, p)]
                if ramp_positions:
                    return self.map.start_location.center.closest(ramp_positions)
                if await self.api.can_place_single(utype, self.map.start_location.ramp.depot_in_middle):
                    return self.map.start_location.ramp.depot_in_middle
                return await self.api.find_placement(utype, near=self.map.start_location.region_center,
                                                     random_alternative=False)

            case UnitTypeId.BARRACKS:
                if near is None:
                    ramp_position = self.map.start_location.ramp.barracks_correct_placement
                    if await self.api.can_place_single(utype, ramp_position):
                        return ramp_position
                    return await self.api.find_placement(utype, near=self.map.start_location.region_center,
                                                         addon_place=True, random_alternative=False)
                else:
                    return await self.api.find_placement(utype, near=near, max_distance=max_distance,
                                                         random_alternative=False, addon_place=True)

            case _:
                self.logger.error("Not implemented: {}", utype)
                return None
