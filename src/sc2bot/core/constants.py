from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId


TRAINERS: dict[UnitTypeId, UnitTypeId | tuple[UnitTypeId, ...]] = {
    # --- Constructed in building
    # CC
    UnitTypeId.SCV: (UnitTypeId.COMMANDCENTER, UnitTypeId.ORBITALCOMMAND, UnitTypeId.PLANETARYFORTRESS),
    UnitTypeId.ORBITALCOMMAND: UnitTypeId.COMMANDCENTER,
    UnitTypeId.PLANETARYFORTRESS: UnitTypeId.COMMANDCENTER,
    # Rax
    UnitTypeId.MARINE: UnitTypeId.BARRACKS,
    UnitTypeId.MARAUDER: UnitTypeId.BARRACKS,
    UnitTypeId.REAPER: UnitTypeId.BARRACKS,
    UnitTypeId.GHOST: UnitTypeId.BARRACKS,
    # Factory
    UnitTypeId.HELLION: UnitTypeId.FACTORY,
    UnitTypeId.SIEGETANK: UnitTypeId.FACTORY,
    # Starport
    UnitTypeId.MEDIVAC: UnitTypeId.STARPORT,
    UnitTypeId.VIKINGFIGHTER: UnitTypeId.STARPORT,
    UnitTypeId.BATTLECRUISER: UnitTypeId.STARPORT,
    # Addons
    # TODO
    UnitTypeId.TECHLAB: (UnitTypeId.BARRACKS, UnitTypeId.FACTORY, UnitTypeId.STARPORT),
    UnitTypeId.REACTOR: (UnitTypeId.BARRACKS, UnitTypeId.FACTORY, UnitTypeId.STARPORT),
    UnitTypeId.BARRACKSTECHLAB: UnitTypeId.BARRACKS,
    UnitTypeId.BARRACKSREACTOR: UnitTypeId.BARRACKS,
    UnitTypeId.FACTORYTECHLAB: UnitTypeId.FACTORY,
    UnitTypeId.FACTORYREACTOR: UnitTypeId.FACTORY,
    UnitTypeId.STARPORTTECHLAB: UnitTypeId.STARPORT,
    UnitTypeId.STARPORTREACTOR: UnitTypeId.STARPORT,

    # -- Constructed by SCV
    UnitTypeId.SUPPLYDEPOT: UnitTypeId.SCV,
    UnitTypeId.BARRACKS: UnitTypeId.SCV,
    UnitTypeId.COMMANDCENTER: UnitTypeId.SCV,
    UnitTypeId.REFINERY: UnitTypeId.SCV,
}


RESEARCHERS: dict[UpgradeId, UnitTypeId] = {
    # Barracks Tech Lab
    UpgradeId.STIMPACK: UnitTypeId.BARRACKSTECHLAB,
    UpgradeId.SHIELDWALL: UnitTypeId.BARRACKSTECHLAB,   # Combat Shields
    UpgradeId.PUNISHERGRENADES: UnitTypeId.BARRACKSTECHLAB, # Marauder Slow
    # Engineering Bay
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL1: UnitTypeId.ENGINEERINGBAY,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL2: UnitTypeId.ENGINEERINGBAY,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL3: UnitTypeId.ENGINEERINGBAY,
    UpgradeId.TERRANINFANTRYARMORSLEVEL1: UnitTypeId.ENGINEERINGBAY,
    UpgradeId.TERRANINFANTRYARMORSLEVEL2: UnitTypeId.ENGINEERINGBAY,
    UpgradeId.TERRANINFANTRYARMORSLEVEL3: UnitTypeId.ENGINEERINGBAY,
}


ALTERNATIVES: dict[UnitTypeId, UnitTypeId | tuple[UnitTypeId, ...]] = {
    UnitTypeId.SUPPLYDEPOT: (UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED),
    UnitTypeId.SUPPLYDEPOTLOWERED: (UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED),
}
