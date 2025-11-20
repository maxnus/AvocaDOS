from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId


# --- Mappings


TERRANBUILD_TO_STRUCTURE: dict[AbilityId, UnitTypeId] = {
    # TODO
    AbilityId.TERRANBUILD_ARMORY: UnitTypeId.ARMORY,
    AbilityId.TERRANBUILD_BARRACKS: UnitTypeId.BARRACKS,
    AbilityId.TERRANBUILD_COMMANDCENTER: UnitTypeId.COMMANDCENTER,
    AbilityId.TERRANBUILD_REFINERY: UnitTypeId.REFINERY,
    AbilityId.TERRANBUILD_SUPPLYDEPOT: UnitTypeId.SUPPLYDEPOT,
}


UNIT_CREATION_ABILITIES: dict[UnitTypeId, AbilityId] = {
    UnitTypeId.ARCHON: AbilityId.ARCHON_WARP_TARGET,
    UnitTypeId.ASSIMILATORRICH: AbilityId.PROTOSSBUILD_ASSIMILATOR,
    UnitTypeId.BANELINGCOCOON: AbilityId.MORPHZERGLINGTOBANELING_BANELING,
    UnitTypeId.CHANGELING: AbilityId.SPAWNCHANGELING_SPAWNCHANGELING,
    UnitTypeId.EXTRACTORRICH: AbilityId.ZERGBUILD_EXTRACTOR,
    UnitTypeId.INTERCEPTOR: AbilityId.BUILD_INTERCEPTORS,
    UnitTypeId.LURKERMPEGG: AbilityId.MORPH_LURKER,
    UnitTypeId.MULE: AbilityId.CALLDOWNMULE_CALLDOWNMULE,
    UnitTypeId.RAVAGERCOCOON: AbilityId.MORPHTORAVAGER_RAVAGER,
    UnitTypeId.REFINERYRICH: AbilityId.TERRANBUILD_REFINERY,
    UnitTypeId.TECHLAB: AbilityId.BUILD_TECHLAB,
    # Remaining items will get populated at runtime
}


UPGRADE_ABILITIES: dict[UpgradeId, AbilityId] = {
    # Populated at runtime
}


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


# Alternatives are reversible
ALTERNATIVE_UNIT_TYPES: list[set[UnitTypeId]] = [
    {UnitTypeId.BARRACKS, UnitTypeId.BARRACKSFLYING},
    {UnitTypeId.COMMANDCENTER, UnitTypeId.COMMANDCENTERFLYING},
    {UnitTypeId.ORBITALCOMMAND, UnitTypeId.ORBITALCOMMANDFLYING},
    {UnitTypeId.FACTORY, UnitTypeId.FACTORYFLYING},
    {UnitTypeId.STARPORT, UnitTypeId.STARPORTFLYING},
    {UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED},
    {UnitTypeId.SPINECRAWLER, UnitTypeId.SPINECRAWLERUPROOTED},
    {UnitTypeId.SPORECRAWLER, UnitTypeId.SPORECRAWLERUPROOTED},
    {UnitTypeId.GATEWAY, UnitTypeId.WARPGATE},
]


ALTERNATIVES: dict[UnitTypeId, set[UnitTypeId]] = {
    alt: alts for alts in ALTERNATIVE_UNIT_TYPES for alt in alts
}


UPGRADED_UNIT_IDS: dict[UnitTypeId, set[UnitTypeId]] = {
    UnitTypeId.COMMANDCENTER: {UnitTypeId.ORBITALCOMMAND, UnitTypeId.PLANETARYFORTRESS},
    UnitTypeId.HATCHERY: {UnitTypeId.LAIR, UnitTypeId.HIVE},
    UnitTypeId.LAIR: {UnitTypeId.HIVE},
    UnitTypeId.SPIRE: {UnitTypeId.GREATERSPIRE},
}


# --- UnitTypeId sets


CLOACKABLE_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.WIDOWMINE,   # TODO: check for upgrade
    UnitTypeId.BANSHEE,     # TODO: check for upgrade
    UnitTypeId.GHOST,       # TODO: check for upgrade
    UnitTypeId.LURKER,
    UnitTypeId.OBSERVER,
    UnitTypeId.DARKTEMPLAR,
})


BURROWED_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.DRONEBURROWED,
    UnitTypeId.QUEENBURROWED,
    UnitTypeId.ZERGLINGBURROWED,
    UnitTypeId.BANELINGBURROWED,
    UnitTypeId.ROACHBURROWED,
    UnitTypeId.RAVAGERBURROWED,
    UnitTypeId.HYDRALISKBURROWED,
    UnitTypeId.LURKERMPBURROWED,
    UnitTypeId.SWARMHOSTBURROWEDMP,
    UnitTypeId.INFESTORBURROWED,
    UnitTypeId.ULTRALISKBURROWED,
})


UNBURROWED_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.DRONE,
    UnitTypeId.QUEEN,
    UnitTypeId.ZERGLING,
    UnitTypeId.BANELING,
    UnitTypeId.ROACH,
    UnitTypeId.RAVAGER,
    UnitTypeId.HYDRALISK,
    UnitTypeId.LURKERMP,
    UnitTypeId.SWARMHOSTMP,
    UnitTypeId.INFESTOR,
    UnitTypeId.ULTRALISK,
})


assert len(BURROWED_TYPE_IDS) == len(UNBURROWED_TYPE_IDS)
BURROWED_TO_UNBURROWED_TYPE_IDS: dict[UnitTypeId, UnitTypeId] = {
    burrowed_id: unburrowed_id for burrowed_id, unburrowed_id in zip(BURROWED_TYPE_IDS, UNBURROWED_TYPE_IDS)
}


MINOR_STRUCTURES: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.CREEPTUMOR,
    UnitTypeId.CREEPTUMORBURROWED,
    UnitTypeId.CREEPTUMORQUEEN,
    UnitTypeId.AUTOTURRET,
})


MINERAL_FIELD_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.RICHMINERALFIELD,
    UnitTypeId.RICHMINERALFIELD750,
    UnitTypeId.MINERALFIELD,
    UnitTypeId.MINERALFIELD450,
    UnitTypeId.MINERALFIELD750,
    UnitTypeId.LABMINERALFIELD,
    UnitTypeId.LABMINERALFIELD750,
    UnitTypeId.PURIFIERRICHMINERALFIELD,
    UnitTypeId.PURIFIERRICHMINERALFIELD750,
    UnitTypeId.PURIFIERMINERALFIELD,
    UnitTypeId.PURIFIERMINERALFIELD750,
    UnitTypeId.BATTLESTATIONMINERALFIELD,
    UnitTypeId.BATTLESTATIONMINERALFIELD750,
    UnitTypeId.MINERALFIELDOPAQUE,
    UnitTypeId.MINERALFIELDOPAQUE900,
})


VESPENE_GEYSER_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.VESPENEGEYSER,
    UnitTypeId.SPACEPLATFORMGEYSER,
    UnitTypeId.RICHVESPENEGEYSER,
    UnitTypeId.PROTOSSVESPENEGEYSER,
    UnitTypeId.PURIFIERVESPENEGEYSER,
    UnitTypeId.SHAKURASVESPENEGEYSER,
})


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
    UnitTypeId.BANELINGNEST,
    UnitTypeId.HYDRALISKDEN,
    UnitTypeId.LURKERDEN,
    UnitTypeId.SPIRE,
    UnitTypeId.INFESTATIONPIT,
    UnitTypeId.ULTRALISKCAVERN,
    UnitTypeId.CYBERNETICSCORE,
    UnitTypeId.TWILIGHTCOUNCIL,
    UnitTypeId.TEMPLARARCHIVE,
    UnitTypeId.DARKSHRINE,
    UnitTypeId.ROBOTICSBAY,
    UnitTypeId.FLEETBEACON
})


STATIC_DEFENSE_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.BUNKER,
    UnitTypeId.MISSILETURRET,
    UnitTypeId.SENSORTOWER,
    UnitTypeId.SPINECRAWLER,
    UnitTypeId.SPINECRAWLERUPROOTED,
    UnitTypeId.SPORECRAWLER,
    UnitTypeId.SPORECRAWLERUPROOTED,
    UnitTypeId.PHOTONCANNON,
    UnitTypeId.SHIELDBATTERY,
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


ADDON_BUILDING_TYPE_IDS: frozenset[UnitTypeId] = frozenset({
    UnitTypeId.BARRACKS,
    UnitTypeId.FACTORY,
    UnitTypeId.STARPORT,
})
