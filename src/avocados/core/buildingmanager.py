from time import perf_counter
from typing import TYPE_CHECKING, Optional

import numpy
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from scipy.signal import convolve2d

from avocados.core.constants import (PRODUCTION_BUILDING_TYPE_IDS, TOWNHALL_TYPE_IDS, MINERAL_FIELD_TYPE_IDS,
                                     VESPENE_GEYSER_TYPE_IDS, ADDON_BUILDING_TYPE_IDS)
from avocados.core.field import Field
from avocados.core.geomutil import Rectangle
from avocados.core.manager import BotManager
from avocados.core.util import CallbackOnAccess

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class BuildingManager(BotManager):
    reserved_grid: Field[bool]
    blocking_grid: Field[bool]
    resource_blocking_grid: Field[bool]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        # attributes initialized in on_start

    async def on_start(self) -> None:
        self.reserved_grid = Field(numpy.full_like(self.map.placement_grid.data, False, dtype=bool),
                                   offset=self.map.placement_grid.offset)
        self.blocking_grid = Field(numpy.full_like(self.map.placement_grid.data, False, dtype=bool),
                                   offset=self.map.placement_grid.offset)
        self.resource_blocking_grid = Field(numpy.full_like(self.map.placement_grid.data, False, dtype=bool),
                                            offset=self.map.placement_grid.offset)

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()
        self.reserved_grid.data[:] = False
        if step % 16 == 0:
            self._update_resource_blocking_grid()
        self._update_blocking_grid()
        self.timings['step'].add(t0)

    async def get_building_location(self, structure: UnitTypeId, *,
                                    near: Optional[Point2] = None,
                                    max_distance: int = 10) -> Optional[CallbackOnAccess[Point2 | Unit]]:

        t0 = perf_counter()
        location = await self._get_building_location(structure=structure, near=near, max_distance=max_distance)
        self.timings['get_building_location'].add(t0)
        if not location:
            return None

        footprint = self._get_footprint(structure, location)
        return CallbackOnAccess(location, self.reserve_area, footprint)

    def reserve_area(self, rect: Rectangle) -> None:
        self.reserved_grid[rect] = True

    # --- Private

    async def _get_building_location(self, structure: UnitTypeId, *,
                                     near: Optional[Point2] = None,
                                     max_distance: int = 10) -> Optional[Point2 | Unit]:

        match structure:
            case UnitTypeId.SUPPLYDEPOT:
                ramp_positions = [p for p in self.map.start_location.ramp.corner_depots
                                  if self._can_place(structure, p)]
                if ramp_positions:
                    return self.map.start_location.center.closest(ramp_positions)
                if self._can_place(structure, self.map.start_location.ramp.depot_in_middle):
                    return self.map.start_location.ramp.depot_in_middle
                return await self._find_placement(structure, self.map.start_location.region_center)

            case UnitTypeId.BARRACKS:
                if near is None:
                    ramp_position = self.map.start_location.ramp.barracks_correct_placement
                    if self._can_place(structure, ramp_position, clearance=0):
                        return ramp_position
                    return await self._find_placement(structure, self.map.start_location.region_center)
                else:
                    return await self._find_placement(structure, near, max_distance=max_distance)

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

            case _:
                self.log.error("NoImplBuildLoc{}", structure.name)
                return None

    async def _find_placement(self,
                              structure: UnitTypeId, location: Point2, *,
                              max_distance: int = 10,
                              clearance: Optional[int] = None,
                              include_addon: bool = True,
                              ) -> Optional[Point2]:

        if self._can_place(structure, location, clearance=clearance, include_addon=include_addon):
            return location
        if max_distance == 0:
            return None

        footprint = self._get_footprint(structure, location, clearance=clearance, include_addon=include_addon)
        building_area = Rectangle.from_center(location,
                                              2*max_distance + footprint.width,
                                              2*max_distance + footprint.height)
        locations = self._get_possible_locations(building_area, footprint)

        if not locations:
            return None

        location = min(locations, key=lambda p: p.distance_to(location))
        if include_addon and structure in ADDON_BUILDING_TYPE_IDS:
            return location.offset(Point2((-1, 0)))
        return location

    def _get_footprint(self, structure: UnitTypeId, location: Point2, *,
                       clearance: Optional[int] = None,
                       include_addon: bool = True,
                       ) -> Rectangle:
        width, height = self._get_footprint_size(structure, include_addon=include_addon)
        if clearance is None:
            clearance = 1 if structure in (PRODUCTION_BUILDING_TYPE_IDS | TOWNHALL_TYPE_IDS) else 0
        if clearance:
            width += 2 * clearance
            height += 2 * clearance
        if structure in ADDON_BUILDING_TYPE_IDS and include_addon:
            center = location.offset(Point2((1, 0)))
        else:
            center = location
        return Rectangle.from_center(center, width, height)

    def _get_footprint_size(self, structure: UnitTypeId, *, include_addon: bool = True) -> tuple[int, int]:
        """1 (Sensor Tower), 2 (Spore), 3 (Barracks), or 5 (Nexus)"""
        if structure == UnitTypeId.SUPPLYDEPOTLOWERED:
            return 2, 2
        if structure in MINERAL_FIELD_TYPE_IDS:
            return 2, 1
        if structure in VESPENE_GEYSER_TYPE_IDS:
            return 3, 3

        unit_type_data = self.api.get_unit_type_data(structure)
        if unit_type_data is None:
            self.log.error("NoUnitData{}", structure)
            return 0, 0

        width = height = int(2 * unit_type_data.footprint_radius)
        if include_addon and structure in ADDON_BUILDING_TYPE_IDS:
            width += 2
        return width, height

    def _can_place(self, structure: UnitTypeId, location: Point2, *,
                         clearance: Optional[int] = None,
                         include_addon: bool = True) -> bool:
        footprint = self._get_footprint(structure, location, clearance=clearance, include_addon=include_addon)
        return self._can_place_footprint(footprint)

    def _get_possible_locations(self, building_area: Rectangle, footprint: Rectangle) -> list[Point2]:
        array = (
                self.map.placement_grid[building_area]
                & self.blocking_grid[building_area]
                & self.map.pathing_grid[building_area]
                & numpy.invert(self.reserved_grid[building_area])
                & numpy.invert(self.map.creep[building_area])
        ).astype(int)
        kernel = numpy.ones((int(footprint.width), int(footprint.height)), dtype=int)
        count = convolve2d(array, kernel, mode='same')
        mask = (count == kernel.size)
        points = numpy.asarray(building_area.get_grid_points())[mask]
        result = [Point2((float(x), float(y))) for x, y in points]
        return result

    def _can_place_footprint(self, footprint: Rectangle) -> bool:
        return (
            numpy.all(self.map.placement_grid[footprint])
            and numpy.all(self.blocking_grid[footprint])
            and numpy.all(self.map.pathing_grid[footprint])
            and not numpy.any(self.reserved_grid[footprint])
            and not numpy.any(self.map.creep[footprint])
        )

    def _update_blocking_grid(self) -> None:
        self.blocking_grid.data[:] = self.resource_blocking_grid.data
        for structure in self.api.all_structures:
            footprint = self._get_footprint(structure.type_id, structure.position)
            self.blocking_grid[footprint] = False

    def _update_resource_blocking_grid(self) -> None:
        self.resource_blocking_grid.data[:] = True
        for structure in self.api.mineral_field + self.api.vespene_geyser:
            footprint = self._get_footprint(structure.type_id, structure.position)
            self.resource_blocking_grid[footprint] = False

    # --- Not in Use

    async def _can_place_api(self, footprint: Rectangle) -> bool:
        dummy, locations = self._can_place_api_generate_requests(footprint)
        return all(await self.api.can_place(dummy, locations))

    def _can_place_api_generate_requests(self, footprint: Rectangle) -> tuple[UnitTypeId, list[Point2]]:
        dummy_footprints = {
            UnitTypeId.BARRACKS: (3, 3),
            UnitTypeId.SUPPLYDEPOT: (2, 2),
            UnitTypeId.SENSORTOWER: (1, 1),
        }
        dummy = dummy_footprint = None
        for dummy, dummy_footprint in dummy_footprints.items():
            if dummy_footprint[0] <= footprint.width and dummy_footprint[1] <= footprint.height:
                break

        # Exact match
        if dummy_footprint == footprint.shape:
            return dummy, [footprint.center]

        # Fill rectangle with dummy_footprint
        points = footprint.tile(dummy_footprint)
        return dummy, points

    async def _get_api_blocking_grid(self) -> Field[bool]:
        """Very expensive for the entire map (~2s)!"""
        points = self.map.playable_rect.get_grid_points(flatten=True)
        results = await self.api.can_place(UnitTypeId.SENSORTOWER, points)
        data = numpy.asarray(results).reshape((self.map.width, self.map.height))
        return Field(data, offset=self.map.playable_offset)
