from sc2.ids.unit_typeid import UnitTypeId

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

    # -- Constructed by SCV
    UnitTypeId.SUPPLYDEPOT: UnitTypeId.SCV,
    UnitTypeId.BARRACKS: UnitTypeId.SCV,
    UnitTypeId.COMMANDCENTER: UnitTypeId.SCV,
}

ALTERNATIVES: dict[UnitTypeId, UnitTypeId | tuple[UnitTypeId, ...]] = {
    UnitTypeId.SUPPLYDEPOT: (UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED),
    UnitTypeId.SUPPLYDEPOTLOWERED: (UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED),
}
