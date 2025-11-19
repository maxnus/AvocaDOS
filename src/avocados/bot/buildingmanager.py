from time import perf_counter
from typing import TYPE_CHECKING, Optional

import numpy
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from scipy.signal import convolve2d

from avocados.core.constants import (PRODUCTION_BUILDING_TYPE_IDS, TOWNHALL_TYPE_IDS, MINERAL_FIELD_TYPE_IDS,
                                     VESPENE_GEYSER_TYPE_IDS, ADDON_BUILDING_TYPE_IDS, GAS_TYPE_IDS)
from avocados.geometry.field import Field
from avocados.geometry.util import Rectangle
from avocados.core.manager import BotManager
from avocados.core.util import WithCallback
from avocados.mapdata.expansion import ExpansionLocation

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


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
                                    area: Optional[Rectangle] = None,
                                    include_addon: bool = True
                                    ) -> Optional[WithCallback[Point2 | Unit]]:

        t0 = perf_counter()
        location = await self._get_building_location(structure=structure, area=area, include_addon=include_addon)
        self.timings['get_building_location'].add(t0)
        if not location:
            return None

        footprint = self._get_footprint(structure, location)
        return WithCallback(location, self.reserve_area, footprint)

    def reserve_area(self, rect: Rectangle) -> None:
        self.reserved_grid[rect] = True

    # --- Private

    async def _get_building_location(self, structure: UnitTypeId, *,
                                     area: Optional[Rectangle] = None,
                                     include_addon: bool = True
                                     ) -> Optional[Point2 | Unit]:

        match structure:
            case UnitTypeId.SUPPLYDEPOT:
                ramp_positions = [p for p in self.map.start_location.ramp.corner_depots
                                  if self._can_place(structure, p)]
                if ramp_positions:
                    return self.map.start_location.center.closest(ramp_positions)
                if self._can_place(structure, self.map.start_location.ramp.depot_in_middle):
                    return self.map.start_location.ramp.depot_in_middle
                if area is None:
                    area = Rectangle.from_center(self.map.start_location.center, 40, 40)
                return await self._find_placement(structure, area)

            case UnitTypeId.BARRACKS:
                ramp_position = self.map.start_location.ramp.barracks_correct_placement
                if (area is None or ramp_position in area) and self._can_place(structure, ramp_position, clearance=0):
                    return ramp_position
                if area is None:
                    area = Rectangle.from_center(self.map.start_location.center, 40, 40)
                return await self._find_placement(structure, area, include_addon=include_addon)

            case UnitTypeId.REFINERY:
                if area is None:
                    area = Rectangle.from_center(self.map.start_location.center, 10, 10)
                geysers = (self.api.vespene_geyser.closer_than(area.characteristic_length, area.center)
                           .filter(lambda g: g.has_vespene))
                if not geysers:
                    return None
                if len(geysers) == 1:
                    return geysers.first
                geysers_contents = sorted([(geyser, geyser.vespene_contents) for geyser in geysers],
                                          key=lambda x: x[1], reverse=True)
                if geysers_contents[0][1] > geysers_contents[1][1]:
                    return geysers_contents[0][0]
                return geysers.closest_to(area.center)

            case UnitTypeId.COMMANDCENTER:
                exp = self._find_next_expansion(area=area)
                if exp is None:
                    return None
                return exp.center

            case _:
                self.log.error("NoImplBuildLoc{}", structure.name)
                return None

    def _find_next_expansion(self, *, area: Optional[Rectangle] = None) -> Optional[ExpansionLocation]:
        for exp in self.map.start_location.expansion_order:
            townhall_area = exp.get_townhall_area()
            if area is not None and townhall_area not in area:
                continue
            if self._can_place_footprint(townhall_area):
                return exp
        return None

    async def _find_placement(self,
                              structure: UnitTypeId,
                              area: Rectangle,
                              *,
                              clearance: Optional[tuple[int, ...] | int] = None,
                              include_addon: bool = True,
                              ) -> Optional[Point2]:

        building_area = area.overlap(self.map.playable_rect).enclosed_rect()
        if building_area.size == 0:
            self.log.error("BuildAreaSize{}", building_area.size)
            return None

        # if self._can_place(structure, building_area.center, clearance=clearance, include_addon=include_addon):
        #     return building_area.center

        footprint = self._get_footprint_shape(structure, clearance=clearance, include_addon=include_addon)
        locations = self._get_possible_locations(building_area, footprint)

        if not locations:
            return None

        location = min(locations, key=lambda p: p.distance_to(area.center))
        if include_addon and structure in ADDON_BUILDING_TYPE_IDS:
            return location.offset(Point2((-1, 0)))
        return location

    def _get_footprint(self, structure: UnitTypeId, location: Point2, *,
                       clearance: Optional[tuple[int, ...] | int] = None,
                       include_addon: bool = True,
                       ) -> Rectangle:
        width, height = self._get_footprint_shape(structure, include_addon=include_addon, clearance=clearance)
        if structure in ADDON_BUILDING_TYPE_IDS and include_addon:
            center = location.offset(Point2((1, 0)))
        else:
            center = location
        # TODO: clearance logic
        return Rectangle.from_center(center, width, height)

    def _get_footprint_shape(self, structure: UnitTypeId, *, include_addon: bool = True,
                             clearance: Optional[tuple[int, ...] | int] = None) -> tuple[int, int]:

        # Exceptions
        if structure.value == UnitTypeId.SUPPLYDEPOTLOWERED.value:
            width = height = 2
        elif structure.value == UnitTypeId.ORBITALCOMMAND.value:
            width = height = 5
        elif structure in MINERAL_FIELD_TYPE_IDS:
            width, height = (2, 1)
        elif structure in VESPENE_GEYSER_TYPE_IDS | GAS_TYPE_IDS:
            width = height = 3
        elif (unit_type_data := self.ext.get_unit_type_data(structure)) is None:
            self.log.error("NoUnitData{}", structure)
            width = height = 0
        elif unit_type_data.footprint_radius is not None:
            width = height = int(2 * unit_type_data.footprint_radius)
        else:
            self.logger.warning("Footprint radius of {} is None", structure)
            width = height = 0

        if include_addon and structure in ADDON_BUILDING_TYPE_IDS:
            width += 2

        if clearance is None:
            clearance = 1 if structure in (PRODUCTION_BUILDING_TYPE_IDS | TOWNHALL_TYPE_IDS) else 0
        if isinstance(clearance, int):
            clearance = 4 * (clearance,)
        if isinstance(clearance, tuple) and len(clearance) == 2:
            clearance = 2 * (clearance[0],) + 2 * (clearance[1],)

        width += clearance[0] + clearance[1]
        height += clearance[2] + clearance[3]

        return width, height

    def _can_place(self, structure: UnitTypeId, location: Point2, *,
                         clearance: Optional[int] = None,
                         include_addon: bool = True) -> bool:
        footprint = self._get_footprint(structure, location, clearance=clearance, include_addon=include_addon)
        return self._can_place_footprint(footprint)

    def _get_possible_locations(self, building_area: Rectangle, footprint: tuple[int, int]) -> list[Point2]:
        array = (
                self.map.placement_grid[building_area]
                & self.blocking_grid[building_area]
                & self.map.pathing_grid[building_area]
                & numpy.invert(self.reserved_grid[building_area])
                & numpy.invert(self.map.creep[building_area])
        ).astype(int)
        kernel = numpy.ones(footprint, dtype=int)
        count = convolve2d(array, kernel, mode='same')
        mask = (count == kernel.size)
        offset = (
            -0.5 if kernel.shape[0] % 2 == 0 else 0,
            -0.5 if kernel.shape[1] % 2 == 0 else 0,
        )
        grid_points = building_area.get_grid_points(offset=offset)
        try:
            points = grid_points[mask, :]
        except IndexError as exc:
            if self.log.error("BooleanMaskIndexError"):
                self.logger.exception(exc)
                self.logger.error('_rect_to_mask={}', self.map.placement_grid._rect_to_mask(building_area))
                self.logger.error("building_area={}", building_area)
                self.logger.error("shape of array={}", array.shape)
                self.logger.error("kernel={}", kernel)
                self.logger.error("shape of mask={}", mask.shape)
                self.logger.error("offset={}", offset)
                self.logger.error("shape of grid points={}", grid_points.shape)
            return []
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
        for structure in self.api.all_structures.not_flying:
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
