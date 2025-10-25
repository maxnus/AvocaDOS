import math
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


def threat_distance_profile(distance, points: list[tuple[float, float]]) -> float:
    # Flat extrapolation
    if distance <= points[0][0]:
        return points[0][1]
    if distance >= points[-1][0]:
        return points[-1][1]
    # LERP
    for (d1, t1), (d2, t2) in zip(points, points[1:]):
        if distance <= d2:
            p = (d2 - distance) / (d2 - d1)
            return p * t1 + (1 - p) * t2
    raise RuntimeError


class CombatSim(System):

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def get_attack_priority(self, attacker: Unit, target: Unit) -> float:
        if target.is_structure:
            return 0.0

        a_damage, a_speed, a_range = attacker.calculate_damage_vs_target(target)
        if a_damage == 0:
            return 0.0

        t_damage, t_speed, t_range = target.calculate_damage_vs_target(attacker)

        return target.health_max + target.shield_max - target.health - target.shield + 1

        #a_in_range = attacker.target_in_range(target)
        #t_in_range = target.target_in_range(attacker)

        #a_dps = a_damage / a_speed
        #t_dps = t_damage / t_speed
        #a_ttk = target.health / a_dps
        #t_ttk = attacker.health / t_dps

        a_atk = math.ceil(target.health / a_damage)
        assert a_atk > 0
        assert a_speed > 0
        a_ttk = attacker.weapon_cooldown + (a_atk - 0.5) * a_speed

        if t_damage > 0:
            t_atk = math.ceil(attacker.health / t_damage)
            t_ttk = target.weapon_cooldown + (t_atk - 0.5) * t_speed
        else:
            #t_atk = float('inf')
            t_ttk = float('inf')
        return max(1 / a_ttk, 1 / t_ttk)

    def get_attack_priorities(self, attacker: Unit, targets: Units) -> list[float]:
        return [self.get_attack_priority(attacker, target) for target in targets]

    def get_defense_priority(self, defender: Unit, threat: Unit) -> float:
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
                return 0.8 if distance <= 3.0 else 0.2
            # Protoss
            case UnitTypeId.PROBE:
                return 0.4 if distance <= 3.0 else 0.1
            case UnitTypeId.ZEALOT:
                return 0.8 if distance <= 2.0 else 0.2
            case UnitTypeId.ADEPT:
                return 0.8 if distance <= 4.0 else 0.2
            case UnitTypeId.ARCHON:
                return 0.8 if distance <= 3.0 else 0.2

        return 0.0

    def get_defence_priorities(self, defender: Unit, threats: Units) -> list[float]:
        return [self.get_defense_priority(defender, enemy) for enemy in threats]

    def marine_micro(self, task: AttackTask, *, units: Optional[Units] = None,
                     scan_range: float = 7.5) -> None:
        if units is None:
            units = self.commander.units
        for marine in units(UnitTypeId.MARINE):

            enemies = self.bot.enemy_units.closer_than(scan_range, marine)
            if not enemies:
                self.commander.order_move(marine, task.target)
                continue

            attack_priorities = list(zip(self.commander.combat.get_attack_priorities(marine, enemies), enemies))
            defense_priorities = list(zip(self.commander.combat.get_defence_priorities(marine, enemies), enemies))

            highest_attack_priority, target = max(attack_priorities, key=lambda p: p[0])
            highest_defense_priority, threat = max(defense_priorities, key=lambda p: p[0])
            defense_position = marine.position.towards(threat, distance=-2.0)

            if marine.weapon_cooldown < 0.01:
                self.commander.order_attack(marine, target)
            else:
                self.commander.order_move(marine, defense_position)
            #self.commander.order_move(marine, defense_position)

            # Attack
            # if marine.weapon_cooldown > 0.03:
            #     if highest_attack_priority > 0:
            #         self.commander.order_attack(marine, target)
            #         #marine.move(defense_position, queue=True)
            #     else:
            #         self.commander.order_move(marine, task.target)

            # Defend
            # else: # marine.weapon_cooldown > 0.01:
            #     if highest_defense_priority > 0:
            #         self.commander.order_move(marine, defense_position)
            #     else:
            #         self.commander.order_move(marine, task.target)
