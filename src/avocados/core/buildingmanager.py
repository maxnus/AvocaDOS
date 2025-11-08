from typing import TYPE_CHECKING, Optional

import numpy
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit

from avocados.core.constants import PRODUCTION_BUILDING_TYPE_IDS, TOWNHALL_TYPE_IDS
from avocados.core.field import Field
from avocados.core.geomutil import Rectangle
from avocados.core.manager import BotManager
from avocados.core.util import CallbackOnAccess

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class BuildingManager(BotManager):
    placement_grid: Optional[Field[bool]]
    reserved_grid: Optional[Field[bool]]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.placement_grid = None  # Initialized on_start
        self.reserved_grid = None

    async def on_start(self) -> None:
        self.placement_grid = Field.from_pixelmap(self.api.game_info.placement_grid)
        self.reserved_grid = Field(numpy.full_like(self.placement_grid.data, True), offset=self.placement_grid.offset)

    async def on_step_start(self, step: int) -> None:
        self.reserved_grid.data[:] = True

    async def get_building_location(self, structure: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[CallbackOnAccess[Point2 | Unit]]:

        location = await self._get_building_location(structure=structure, near=near, max_distance=max_distance)
        if not location:
            return None

        footprint = self._get_footprint(structure, location)
        return CallbackOnAccess(location, self.reserve_area, footprint)

    def reserve_area(self, rect: Rectangle) -> None:
        self.reserved_grid[rect] = False

    # --- Private

    async def _get_building_location(self, structure: UnitTypeId, *,
                                     near: Optional[Point2] = None,
                                     max_distance: int = 10) -> Optional[Point2 | Unit]:

        match structure:
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
                                  if await self._can_place(structure, p)]
                if ramp_positions:
                    return self.map.start_location.center.closest(ramp_positions)
                if await self._can_place(structure, self.map.start_location.ramp.depot_in_middle):
                    return self.map.start_location.ramp.depot_in_middle
                return await self._find_placement(structure, self.map.start_location.region_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    ramp_position = self.map.start_location.ramp.barracks_correct_placement
                    if await self._can_place(structure, ramp_position, clearance=0):
                        return ramp_position
                    return await self._find_placement(structure, self.map.start_location.region_center)
                else:
                    return await self._find_placement(structure, near, max_distance=max_distance)

            case _:
                self.logger.error("Not implemented: {}", structure)
                return None

    def _get_footprint_size(self, structure: UnitTypeId) -> int:
        """1 (Sensor Tower), 2 (Spore), 3 (Barracks), or 5 (Nexus)"""
        footprint_size = int(2 * self.api.game_data.units[structure.value].footprint_radius)
        return footprint_size

    def _get_footprint(self, structure: UnitTypeId, location: Point2, *, clearance: Optional[int] = None) -> Rectangle:
        if clearance is None:
            clearance = 1 if structure in (PRODUCTION_BUILDING_TYPE_IDS | TOWNHALL_TYPE_IDS) else 0
        footprint_size = self._get_footprint_size(structure) + 2 * clearance
        return Rectangle.from_center(location, footprint_size, footprint_size)

    async def _can_place(self, structure: UnitTypeId, location: Point2, *,
                         clearance: Optional[int] = None,
                         include_addon: Optional[bool] = None) -> bool:
        # Check pathing grid first for performance
        footprint = self._get_footprint(structure, location, clearance=clearance)
        values = self.placement_grid[footprint] & self.reserved_grid[footprint]
        if not numpy.all(values):
            return False
        if include_addon is None:
            include_addon = structure in {UnitTypeId.BARRACKS, UnitTypeId.FACTORY, UnitTypeId.STARPORT}
        if include_addon:
            if not await self._can_place(UnitTypeId.SUPPLYDEPOT, location.offset(Point2((2.5, -0.5))),
                                         clearance=clearance):
                return False

        if footprint.shape == (1, 1):
            dummy = UnitTypeId.SENSORTOWER
        elif footprint.shape == (3, 3):
            dummy = UnitTypeId.BARRACKS
        elif footprint.shape == (5, 5):
            dummy = UnitTypeId.COMMANDCENTER
        else:
            # TODO: This will ignore clearance
            # missing cases for clearance=1: (4, 4) and (7, 7)
            dummy = structure

        return await self.api.can_place_single(dummy, location)

    # async def _get_placeable_points(self, stru):
    #     else:
    #         candidates = []
    #         for loc in location:
    #             footprint = self._get_footprint(structure, loc)
    #             values = self.placement_grid[footprint] & self.reserved_grid[footprint]
    #             if not numpy.all(values):
    #                 return False
    #
    #         return False

    # async def can_place_building(self, utype: UnitTypeId, position: Point2) -> bool:
    #
    #     point = position
    #     if not self.placement_grid[point]:
    #         return False
    #
    #     return await self.api.can_place_single(utype, point)
    # async def _get_placement_grid_at(self, rect: Rectangle) -> Field[bool]:
    #     pass

    async def _find_placement(self, structure: UnitTypeId, location: Point2, *,
                              max_distance: int = 10,
                              clearance: Optional[int] = None,
                              include_addon: Optional[bool] = None
                              ) -> Optional[Point2]:

        if await self._can_place(structure, location, clearance=clearance, include_addon=include_addon):
            return location
        if max_distance == 0:
            return None

        footprint = self._get_footprint(structure, location, clearance=clearance)

        if footprint.shape == (1, 1):
            dummy = UnitTypeId.SENSORTOWER
        elif footprint.shape == (3, 3):
            dummy = UnitTypeId.BARRACKS
        elif footprint.shape == (5, 5):
            dummy = UnitTypeId.COMMANDCENTER
        else:
            # TODO: This will ignore clearance
            # missing cases for clearance=1: (4, 4) and (7, 7)
            dummy = structure

        return await self.api.find_placement(dummy, near=location, max_distance=max_distance,
                                             random_alternative=False, addon_place=include_addon)

        # TODO
        # rect = Rectangle.from_center(location, 2*max_distance, 2*max_distance)
        #
        # candidates = []
        # for point in rect.get_grid_points():
        #     if await self._can_place(structure, point, include_addon=include_addon):
        #         candidates.append(point)
        #
        # if not candidates:
        #     return None
        #
        # return min(candidates, key=lambda p: p.distance_to(location) + 1e-3*p.x + 1e-6*p.y)
        #
        # return await self.api.find_placement(structure, near=location, max_distance=max_distance,
        #                                      random_alternative=random_alternative, addon_place=include_addon)
