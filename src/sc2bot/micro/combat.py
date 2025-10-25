import math
from collections import defaultdict
from typing import Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.system import System
from sc2bot.core.tasks import AttackTask


THREAT_DISTANCE_PROFILE: dict[UnitTypeId, list[tuple[float, float]]] = {
    # Worker
    UnitTypeId.SCV: [(0.2, 1), (2, 0.2)],
    UnitTypeId.DRONE: [(0.2, 1), (2, 0.2)],
    UnitTypeId.PROBE: [(0.2, 1), (2, 0.2)],
    # Terran
    # Protoss
    UnitTypeId.ZEALOT: [(0.2, 1), (3, 0.5)],
}


def piecewise(distance, points: list[tuple[float, float]]) -> float:
    for d, t in points:
        if distance <= d:
            return t
    return 0


def lerp(distance, points: list[tuple[float, float]]) -> float:
    # Flat extrapolation
    if distance <= points[0][0]:
        return points[0][1]
    if distance > points[-1][0]:
        return points[-1][1]
    # LERP
    for (d1, t1), (d2, t2) in zip(points, points[1:]):
        if distance <= d2:
            p = (d2 - distance) / (d2 - d1)
            return p * t1 + (1 - p) * t2
    raise ValueError


unit_type_attack_priority: dict[UnitTypeId, float] = {
    # Terran
    UnitTypeId.SCV: 0.1,
    UnitTypeId.MARINE: 0.5,
    UnitTypeId.REAPER: 0.6,
    UnitTypeId.MARAUDER: 0.4,
    UnitTypeId.GHOST: 0.7,
    # Zerg
    # Protoss
}


def get_squared_distance(unit1: Unit, unit2: Unit) -> float:
    p1 = unit1.position
    p2 = unit2.position
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return dx * dx + dy * dy


def get_closest_distance(units1: Units, units2: Units) -> float:
    closest = float('inf')
    for unit1 in units1:
        for unit2 in units2:
            closest = min(closest, get_squared_distance(unit1, unit2))
    return math.sqrt(closest)


class MicroManager(System):

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def get_attack_priorities(self, attacker: Units, targets: Units) -> dict[Unit, tuple[float, float, float]]:
        """Attack priority is based on:
            1) Unit Type (i.e., Baneling > Zergling > Drone)
            2) Missing health of target (weakness)
            3) Distance
        All values are in [0, 1]
        """
        priorities: dict[Unit, tuple[float, float, float]] = {}
        min_distance = get_closest_distance(attacker, targets)
        for target in targets:
            if target.is_structure:
                base = 0.0
            else:
                base = unit_type_attack_priority.get(target.type_id, 0.5)
            # t_damage, t_speed, t_range = target.calculate_damage_vs_target(attacker)
            weakness = 1 - target.shield_health_percentage
            distance = attacker.closest_distance_to(target) / (min_distance + 1e-15)
            priorities[target] = (base, weakness, distance)
        return priorities

    def get_defense_priority(self, defender: Unit, threat: Unit) -> float:
        """Defense priority is based on:
            1) Unit Type
            2) Distance
        """
        distance = defender.distance_to(threat)

        match threat.type_id:
            # --- Splash
            # Terran
            case UnitTypeId.HELLION:
                return 1.0
            case UnitTypeId.HELLIONTANK:
                return 1.0
            case UnitTypeId.WIDOWMINE:
                return 1.0
            case UnitTypeId.SIEGETANK:
                # TODO use facing
                return 1.0
            # Zerg
            case UnitTypeId.BANELING:
                return 1.0
            # Protoss
            case UnitTypeId.DISRUPTOR:
                return 1.0
            case UnitTypeId.COLOSSUS:
                return 1.0
            # --- Melee
            # Zerg
            case UnitTypeId.ZERGLING:
                return lerp(distance, [(1.0, 0.8), (3.0, 0.2)])
            # Protoss
            case UnitTypeId.PROBE:
                return 0.4 if distance <= 3.0 else 0.1
            case UnitTypeId.ZEALOT:
                return lerp(distance, [(1.0, 0.8), (3.0, 0.2)])
            case UnitTypeId.ADEPT:
                return 0.8 if distance <= 4.0 else 0.2
            case UnitTypeId.ARCHON:
                return 0.8 if distance <= 3.0 else 0.2
            # --- Other
            case UnitTypeId.MARINE:
                return lerp(distance, [(5, 0.2), (6, 0.1)])

        return 0.0

    def get_defense_priorities(self, defender: Unit, threats: Units) -> dict[Unit, float]:
        return {threat: self.get_defense_priority(defender, threat) for threat in threats}

    # def get_possible_damage_per_target(self, units: Units, enemies: Units) -> tuple[dict[int, float], dict[int, Units]]:
    #     damage = defaultdict(float)
    #     attackers = defaultdict(lambda: Units([], self.bot))
    #     for unit in units:
    #         if unit.weapon_cooldown > 0:
    #             continue
    #         targets = enemies.in_attack_range_of(unit)
    #         for target in targets:
    #             damage[target.tag] += unit.calculate_damage_vs_target(target)
    #             attackers[target.tag].append(unit)
    #
    #     return damage, attackers

    def get_enemies(self, units: Units, *, max_distance: float = 12) -> Units:
        enemies = []
        for enemy in self.bot.enemy_units:
            for unit in units:
                if get_squared_distance(unit, enemy) <= max_distance * max_distance:
                    enemies.append(enemy)
                    break
        return Units(enemies, self.bot)

    def micro(self, *,
              units: Optional[Units] = None,
              enemies: Optional[Units] = None,
              scan_range: float = 10) -> None:
        if units is None:
            units = self.commander.units
        if enemies is None:
            enemies = self.get_enemies(units)

        attack_priorities = self.commander.combat.get_attack_priorities(units, enemies)
        if attack_priorities:
            group_target, group_target_prio = max(attack_priorities.items(), key=lambda kv: kv[1])
        else:
            group_target = None
            group_target_prio = 0

        for unit in units:
            if unit.weapon_cooldown == 0:
                attack_priorities_for_unit = {target: priority for target, priority in attack_priorities.items()
                                              if unit.target_in_range(target)}
            else:
                attack_priorities_for_unit = {}

            marine_enemies = enemies.closer_than(scan_range, unit)

            if attack_priorities_for_unit:
                target, attack_prio = max(attack_priorities_for_unit.items(), key=lambda kv: kv[1])
            else:
                target = None
                attack_prio = 0

            defense_priorities = self.commander.combat.get_defense_priorities(unit, marine_enemies)
            if defense_priorities:
                threat, defense_prio = max(defense_priorities.items(), key=lambda kv: kv[1])
                defense_position = unit.position.towards(threat, distance=-2*unit.distance_per_step)
                #if not self.bot.game_info.pathing_grid[(int(defense_position.x), int(defense_position.y))]:
                #    defense_position = marine.position.towards_with_random_angle(threat.position, distance=-2)
            else:
                defense_prio = 0
                defense_position = None

            if defense_prio >= 0.5:
                self.commander.order_move(unit, defense_position)
            elif target and unit.weapon_cooldown == 0:
                self.commander.order_attack(unit, target)
            elif group_target and (unit.distance_to(group_target) >= unit.ground_range + unit.distance_to_weapon_ready):
                self.commander.order_attack(unit, group_target)
            elif defense_position and unit.shield_health_percentage < 0.8:
                self.commander.order_move(unit, defense_position)
            elif group_target is not None:
                self.commander.order_attack(unit, group_target)
