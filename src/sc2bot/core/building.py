from typing import Optional, TYPE_CHECKING

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


async def get_building_location(bot: 'BotBase', utype: UnitTypeId, *,
                                near: Optional[Point2] = None,
                                max_distance: int = 10) -> Optional[Point2 | Unit]:
    match utype:
        case UnitTypeId.REFINERY:
            if near is None:
                near = bot.map.base_townhall
            geysers = bot.vespene_geyser.closer_than(10.0, near)
            if geysers:
                return geysers.random

        case UnitTypeId.SUPPLYDEPOT:
            positions = [p for p in bot.main_base_ramp.corner_depots if await bot.can_place_single(utype, p)]
            if positions:
                return bot.map.base_center.closest(positions)
            if await bot.can_place_single(utype, bot.main_base_ramp.depot_in_middle):
                return bot.main_base_ramp.depot_in_middle
            return await bot.find_placement(utype, near=bot.map.base_center)

        case UnitTypeId.BARRACKS:
            if near is None:
                position = bot.main_base_ramp.barracks_correct_placement
                if await bot.can_place_single(utype, position):
                    return position
                return await bot.find_placement(utype, near=bot.map.base_center, addon_place=True)
            else:
                return await bot.find_placement(utype, near=near, max_distance=max_distance,
                                                random_alternative=False, addon_place=True)
        case UnitTypeId.COMMANDCENTER:
            if near is None:
                bot.logger.error("NotImplemented")
            else:
                return await bot.find_placement(utype, near=near)
        case _:
            bot.logger.error("Not implemented: {}", utype)
    return None
