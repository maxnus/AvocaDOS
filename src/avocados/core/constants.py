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

    # -- By ability
    UnitTypeId.MULE: UnitTypeId.ORBITALCOMMAND,
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


# --- UnitTypeId sets


WORKER_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.DRONE,
    UnitTypeId.DRONEBURROWED,
    UnitTypeId.SCV,
    UnitTypeId.PROBE
})


RESOURCE_COLLECTOR_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    *WORKER_TYPE_IDS,
    UnitTypeId.MULE,
})


TOWNHALL_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.COMMANDCENTER,
    UnitTypeId.COMMANDCENTERFLYING,
    UnitTypeId.ORBITALCOMMAND,
    UnitTypeId.ORBITALCOMMANDFLYING,
    UnitTypeId.PLANETARYFORTRESS,
    UnitTypeId.HATCHERY,
    UnitTypeId.LAIR,
    UnitTypeId.HIVE,
    UnitTypeId.NEXUS
})


GAS_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.ASSIMILATOR,
    UnitTypeId.ASSIMILATORRICH,
    UnitTypeId.REFINERY,
    UnitTypeId.REFINERYRICH,
    UnitTypeId.EXTRACTOR,
    UnitTypeId.EXTRACTORRICH,
})


PRODUCTION_BUILDING_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.BARRACKS,
    UnitTypeId.BARRACKSFLYING,
    UnitTypeId.FACTORY,
    UnitTypeId.FACTORYFLYING,
    UnitTypeId.STARPORT,
    UnitTypeId.STARPORTFLYING,
    UnitTypeId.GATEWAY,
    UnitTypeId.WARPGATE,
    UnitTypeId.STARGATE,
    UnitTypeId.ROBOTICSFACILITY
})


UPGRADE_BUILDING_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.ENGINEERINGBAY,
    UnitTypeId.ARMORY,
    UnitTypeId.EVOLUTIONCHAMBER,
    UnitTypeId.SPIRE,
    UnitTypeId.FORGE,
    UnitTypeId.CYBERNETICSCORE
})


TECH_BUILDING_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.ARMORY,
    UnitTypeId.GHOSTACADEMY,
    UnitTypeId.FUSIONCORE,
    UnitTypeId.SPAWNINGPOOL,
    UnitTypeId.ROACHWARREN,
    UnitTypeId.HYDRALISKDEN,
    UnitTypeId.LURKERDEN,
    UnitTypeId.SPIRE,
    UnitTypeId.INFESTATIONPIT,
    UnitTypeId.ULTRALISKCAVERN,
    UnitTypeId.CYBERNETICSCORE,
    UnitTypeId.TWILIGHTCOUNCIL,
    UnitTypeId.DARKSHRINE,
    UnitTypeId.ROBOTICSBAY,
    UnitTypeId.FLEETBEACON
})


REACTOR_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.REACTOR,
    UnitTypeId.BARRACKSREACTOR,
    UnitTypeId.FACTORYREACTOR,
    UnitTypeId.STARPORTREACTOR,
})


TECHLAB_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.TECHLAB,
    UnitTypeId.BARRACKSTECHLAB,
    UnitTypeId.FACTORYTECHLAB,
    UnitTypeId.STARPORTTECHLAB,
})


ADDON_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    *REACTOR_TYPE_IDS,
    *TECHLAB_TYPE_IDS
})

