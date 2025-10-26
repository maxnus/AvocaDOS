import math
from typing import Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2bot.core.manager import Manager
from sc2bot.core.util import get_squared_distance
from sc2bot.micro.weapons import Weapons


# THREAT_DISTANCE_PROFILE: dict[UnitTypeId, list[tuple[float, float]]] = {
#     # Worker
#     UnitTypeId.SCV: [(0.2, 1), (2, 0.2)],
#     UnitTypeId.DRONE: [(0.2, 1), (2, 0.2)],
#     UnitTypeId.PROBE: [(0.2, 1), (2, 0.2)],
#     # Terran
#     # Protoss
#     UnitTypeId.ZEALOT: [(0.2, 1), (3, 0.5)],
# }


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
    UnitTypeId.ZERGLING: 0.5,
    UnitTypeId.BANELING: 1.0,
    # Protoss
}



def get_closest_distance(units1: Units, units2: Units) -> float:
    closest = float('inf')
    for unit1 in units1:
        for unit2 in units2:
            closest = min(closest, get_squared_distance(unit1, unit2))
    return math.sqrt(closest)


class MicroManager(Manager):

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def weapon_ready(self, unit: Unit) -> bool:
        if unit.type_id == UnitTypeId.REAPER:
            # Cooldown starts at first shot
            prev_frame = self.bot.history.get_last_seen(unit)
            #if prev_frame is not None:
            #   self.logger.info("cooldowns {} {}", prev_frame.weapon_cooldown, unit.weapon_cooldown)
            if prev_frame and prev_frame.weapon_cooldown < 1 <= unit.weapon_cooldown:
                return True
        return unit.weapon_cooldown < 1

    def get_scan_range(self, unit: Unit, *, scan_factor: float = 0.75) -> float:
        scan_range = 0
        for weapon in Weapons.of_unit(unit):
            scan_range = max(weapon.range + scan_factor * unit.real_speed / weapon.speed, scan_range)
        return scan_range

    def get_threat_range(self, unit: Unit) -> float:
        # TODO
        return self.get_scan_range(unit)

    def get_attack_priorities(self, attacker: Units, targets: Units) -> dict[Unit, float]:
        """Attack priority is based on:
            1) Unit Type (i.e., Baneling > Zergling > Drone)
            2) Missing health of target (weakness)
            3) Distance
        All values are in [0, 1]
        """
        priorities: dict[Unit, float] = {}
        min_distance = get_closest_distance(attacker, targets)
        for target in targets:
            if target.is_structure:
                base = 0.0
            else:
                base = unit_type_attack_priority.get(target.type_id, 0.5)
            # t_damage, t_speed, t_range = target.calculate_damage_vs_target(attacker)
            weakness = 1 - target.shield_health_percentage
            distance = min_distance / (attacker.closest_distance_to(target) + 1e-15)
            priorities[target] = 0.9 * base + 0.08 * weakness + 0.02 * distance
        return priorities

    def get_defense_priority(self, defender: Unit, threat: Unit) -> float:
        """Defense priority is based on:
            1) Unit Type
            2) Distance
        """
        distance = defender.distance_to(threat)

        match threat.type_id:
            # Terran
            case UnitTypeId.MARINE:
                return lerp(distance, [(5, 0.2), (6, 0.1)])
            case UnitTypeId.REAPER:
                return lerp(distance, [(5, 0.2), (6, 0.1)])
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

            case UnitTypeId.ZERGLING:
                return lerp(distance, [(0.5, 0.8), (1.5, 0.5), (5.0, 0.2)])
            case UnitTypeId.BANELING:
                return lerp(distance, [(2.0, 1.0), (2.0, 0.5), (5.0, 0.3)])
            # Protoss
            case UnitTypeId.DISRUPTOR:
                return 1.0
            case UnitTypeId.COLOSSUS:
                return 1.0
            # --- Melee
            # Protoss
            case UnitTypeId.PROBE:
                return 0.4 if distance <= 3.0 else 0.1
            case UnitTypeId.ZEALOT:
                return lerp(distance, [(0.5, 0.8), (2.0, 0.5), (5.0, 0.2)])
            case UnitTypeId.ADEPT:
                return 0.8 if distance <= 4.0 else 0.2
            case UnitTypeId.ARCHON:
                return 0.8 if distance <= 3.0 else 0.2
            # --- Other


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

    def micro_units(self, *,
                    units: Optional[Units] = None,
                    enemies: Optional[Units] = None) -> None:
        if units is None:
            units = self.commander.units
        if enemies is None:
            enemies = self.get_enemies(units)

        group_attack_priorities = self.commander.combat.get_attack_priorities(units, enemies)
        if group_attack_priorities:
            group_target, group_target_prio = max(group_attack_priorities.items(), key=lambda kv: kv[1])
        else:
            group_target = None
            group_target_prio = 0

        for unit in units:
            self._micro_unit(unit, enemies=enemies, group_attack_priorities=group_attack_priorities,
                             group_target=group_target)

            # weapon_ready = self.weapon_ready(unit)
            # scan_range = self.get_scan_range(unit)
            # threat_range = self.get_threat_range(unit)
            #
            # if weapon_ready:
            #     attack_priorities_scan_range = {target: priority for target, priority
            #                                     in group_attack_priorities.items()
            #                                     if get_squared_distance(unit, target) <= scan_range**2}
            #     attack_priorities_attack_range = {target: priority for target, priority
            #                                       in attack_priorities_scan_range.items()
            #                                       if unit.target_in_range(target)}
            # else:
            #     attack_priorities_scan_range = {}
            #     attack_priorities_attack_range = {}
            #
            # if attack_priorities_attack_range:
            #     target, attack_prio = max(attack_priorities_attack_range.items(), key=lambda kv: kv[1])
            # else:
            #     target = None
            #     attack_prio = 0
            #
            # threats = enemies.closer_than(threat_range, unit)
            # defense_priorities = self.commander.combat.get_defense_priorities(unit, threats)
            # if defense_priorities:
            #     threat, defense_prio = max(defense_priorities.items(), key=lambda kv: kv[1])
            #     # TODO
            #     defense_position = unit.position.towards(threat, distance=-3*unit.distance_per_step)
            #     #if not self.bot.game_info.pathing_grid[(int(defense_position.x), int(defense_position.y))]:
            #     #    defense_position = marine.position.towards_with_random_angle(threat.position, distance=-2)
            # else:
            #     defense_prio = 0
            #     defense_position = None
            #
            # # if target and unit.weapon_cooldown == 0:
            # #     self.commander.order_attack(unit, target)
            # # elif group_target:
            # #      self.commander.order_attack(unit, group_target)
            #
            # #elif defense_position:
            # #    self.commander.order_move(unit, defense_position)
            #
            # if defense_prio >= 0.5:# or (defense_position and unit.shield_health_percentage < 0.2):
            #     self.commander.order_move(unit, defense_position)
            #
            # elif target and weapon_ready:
            #     self.commander.order_attack(unit, target)
            #
            # elif group_target and (unit.distance_to(group_target) >= unit.ground_range + unit.distance_to_weapon_ready):
            #     self.commander.order_attack(unit, group_target)
            #
            # elif defense_position and unit.shield_health_percentage < 1:
            #     self.commander.order_move(unit, defense_position)
            #
            # elif group_target is not None:
            #     self.commander.order_attack(unit, group_target)

    def _evaluate_defense(self, unit: Unit, *, enemies: Units) -> tuple[float, Point2]:
        threat_range = self.get_threat_range(unit)
        threats = enemies.closer_than(threat_range, unit)
        defense_priorities = self.commander.combat.get_defense_priorities(unit, threats)
        if not defense_priorities:
            return 0, unit.position
        threat, defense_prio = max(defense_priorities.items(), key=lambda kv: kv[1])
        # TODO
        defense_position = unit.position.towards(threat, distance=-3 * unit.distance_per_step)
        # if not self.bot.game_info.pathing_grid[(int(defense_position.x), int(defense_position.y))]:
        #    defense_position = marine.position.towards_with_random_angle(threat.position, distance=-2)
        return defense_prio, defense_position

    def _evaluate_offense(self, unit: Unit, *,
                          group_attack_priorities: dict[Unit, float]) -> tuple[float, Optional[Unit]]:
        weapon_ready = self.weapon_ready(unit)
        if not weapon_ready:
            return 0, None

        scan_range = self.get_scan_range(unit)
        attack_priorities_scan_range = {target: priority for target, priority
                                        in group_attack_priorities.items()
                                        if get_squared_distance(unit, target) <= scan_range ** 2}
        attack_priorities_attack_range = {target: priority for target, priority
                                          in attack_priorities_scan_range.items()
                                          if unit.target_in_range(target)}

        if not attack_priorities_attack_range:
            return 0, None

        target, attack_prio = max(attack_priorities_attack_range.items(), key=lambda kv: kv[1])
        return attack_prio, target

    def _micro_unit(self, unit: Unit, *,
                    enemies: Units,
                    group_attack_priorities: dict[Unit, float],
                    group_target: Optional[Unit]) -> bool:

        # --- Defense
        defense_prio, defense_position = self._evaluate_defense(unit, enemies=enemies)

        if defense_prio >= 0.5:  # or (defense_position and unit.shield_health_percentage < 0.2):
            return self.commander.order_move(unit, defense_position)

        # --- Offense
        attack_prio, target = self._evaluate_offense(unit, group_attack_priorities=group_attack_priorities)

        if target:
            return self.commander.order_attack(unit, target)

        if group_target and (unit.distance_to(group_target) >= unit.ground_range + unit.distance_to_weapon_ready):
            return self.commander.order_attack(unit, group_target)

        if defense_position and unit.shield_health_percentage < 0.8:
            return self.commander.order_move(unit, defense_position)

        if group_target is not None:
            return self.commander.order_attack(unit, group_target)

        return False
