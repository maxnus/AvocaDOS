from collections.abc import Iterable

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit


STRENGTH_OVERRIDES: dict[UnitTypeId, float] = {
    UnitTypeId.BUNKER: 4.0,
}


def get_strength(units: Unit | Iterable[Unit], *,
                 reference_hp: int = 45, reference_dps: float = 6.969937606352808) -> float:
    """Unupgraded marine has strength = 1.0"""
    # TODO armor, energy, abilities, upgrades
    if isinstance(units, Unit):
        # TODO: phoenix, oracle, etc
        if (strength_override := STRENGTH_OVERRIDES.get(units.type_id)) is not None:
            return strength_override

        if not units.can_attack_ground:
            return 0
        hp = units.health + units.shield
        if units.ground_dps != 0:
            ttk = min(hp / reference_dps, reference_hp / units.ground_dps)
        else:
            ttk = hp / reference_dps
        strength = 2 * (hp + ttk * (units.ground_dps - reference_dps)) / (hp + reference_hp)
    else:
        strength = sum(get_strength(unit, reference_hp=reference_hp, reference_dps=reference_dps)
                       for unit in units)
    return round(strength, 2)
