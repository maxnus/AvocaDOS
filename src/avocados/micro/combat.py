from typing import Optional, TYPE_CHECKING

from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from avocados.core.botobject import BotObject
from avocados.core.constants import TECHLAB_TYPE_IDS, REACTOR_TYPE_IDS, GAS_TYPE_IDS, TOWNHALL_TYPE_IDS, \
    UPGRADE_BUILDING_TYPE_IDS, PRODUCTION_BUILDING_TYPE_IDS, TECH_BUILDING_TYPE_IDS
from avocados.core.geomutil import lerp, squared_distance
from avocados.core.unitutil import get_closest_sq_distance
from avocados.micro.squad import Squad, SquadAttackTask, SquadDefendTask, SquadStatus, SquadJoinTask, SquadRetreatTask
from avocados.micro.weapons import Weapons

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class CombatManager(BotObject):
    # Parameters
    attack_priority_base_weight: float
    attack_priority_weakness_weight: float
    attack_priority_distance_weight: float
    attack_priority_base_weakness_correlation: float
    attack_priority_base_distance_correlation: float
    attack_priority_weakness_distance_correlation: float
    attack_priority_threshold: float
    defense_priority_threshold: float

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.attack_priority_base_weight = 0.75
        self.attack_priority_weakness_weight = 0.10
        self.attack_priority_distance_weight = 0.05
        self.attack_priority_base_weakness_correlation = 0.05
        self.attack_priority_base_distance_correlation = 0.05
        self.attack_priority_weakness_distance_correlation = 0.00
        self.attack_priority_threshold = 0.375  # attack_priority_base_weight/2
        self.defense_priority_threshold = 0.50

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    async def on_step(self, step: int) -> None:
        for squad in self.squads:
            await self.micro_squad(squad)

    # ---

    def get_strength(self, units: Units | Unit) -> float:
        # TODO
        if isinstance(units, Unit):
            return 0.7 * units.shield_health_percentage + 0.3
        return 0.7 * sum(u.shield_health_percentage for u in units) + 0.3 * len(units)

    def weapon_ready(self, unit: Unit) -> bool:
        if unit.type_id == UnitTypeId.REAPER:
            # Cooldown starts at first shot
            prev_frame = self.history.get_last_seen(unit)
            #if prev_frame is not None:
            #   self.logger.info("cooldowns {} {}", prev_frame.weapon_cooldown, unit.weapon_cooldown)
            if prev_frame and prev_frame.weapon_cooldown < 1 <= unit.weapon_cooldown:
                return True
        return unit.weapon_cooldown < 1

    async def get_abilities(self, units: Units) -> list[list[AbilityId]]:
        if not units:
            return []
        ability_list = await self.api.get_available_abilities(units)
        # Filter down to relevant
        keep = {
            AbilityId.KD8CHARGE_KD8CHARGE,
        }
        ability_list = [[ability for ability in abilities if ability in keep] for abilities in ability_list]
        return ability_list

    def get_scan_range(self, unit: Unit, *, scan_factor: float = 0.75) -> float:
        scan_range = 0
        for weapon in Weapons.of_unit(unit):
            scan_range = max(weapon.range + scan_factor * unit.real_speed / weapon.speed, scan_range)
        return scan_range

    def get_threat_range(self, unit: Unit) -> float:
        # TODO
        return self.get_scan_range(unit)

    def _get_powering_pylons(self, structure: Unit) -> Units:
        return self.api.enemy_structures.of_type(UnitTypeId.PYLON).closer_than(6.5, structure)

    def _get_pylon_attack_base_priority(self, target: Unit, *, floor: float = 0.15, ceiling: float = 0.80) -> float:
        priority = 0
        for structure in self.api.enemy_structures.closer_than(6.5, target):
            powering = self._get_powering_pylons(structure)
            match len(powering):
                case 1:
                    weight = 1.0
                case 2:
                    weight = 0.2
                case _:
                    weight = 0.0
            if structure.type_id == UnitTypeId.STARGATE:
                factor = 0.4
            elif structure.type_id == UnitTypeId.ROBOTICSBAY:
                factor = 0.35
            elif structure.type_id in {UnitTypeId.GATEWAY, UnitTypeId.WARPGATE}:
                factor = 0.30
            elif structure.type_id in TECH_BUILDING_TYPE_IDS:
                factor = 0.10
            elif structure.type_id in UPGRADE_BUILDING_TYPE_IDS:
                factor = 0.05
            else:
                factor = 0
            priority += weight * factor * min(2 * structure.shield_health_percentage, 1)
        return max(floor, min(priority, ceiling))

    def _get_attack_base_priority(self, target: Unit) -> float:

        match target.type_id:
            # --- Terran
            # Structures
            case UnitTypeId.MISSILETURRET: return 0.01
            case UnitTypeId.SUPPLYDEPOT | UnitTypeId.SUPPLYDEPOTLOWERED: return 0.10
            case _ if target.type_id in REACTOR_TYPE_IDS: return 0.12
            case _ if target.type_id in TECHLAB_TYPE_IDS: return 0.13
            case UnitTypeId.PLANETARYFORTRESS: return 0.15
            case UnitTypeId.AUTOTURRET: return 0.20
            case UnitTypeId.BUNKER: return 0.25
            # Units
            case UnitTypeId.MULE: return 0.35
            case UnitTypeId.SCV: return 0.50
            case UnitTypeId.MARAUDER: return 0.55
            case UnitTypeId.MARINE: return 0.60
            case UnitTypeId.REAPER: return 0.65
            case UnitTypeId.CYCLONE: return 0.65
            case UnitTypeId.HELLION: return 0.68
            case UnitTypeId.VIKINGASSAULT: return 0.67
            case UnitTypeId.HELLIONTANK: return 0.69
            case UnitTypeId.WIDOWMINE: return 0.70
            case UnitTypeId.WIDOWMINEBURROWED: return 0.70
            case UnitTypeId.SIEGETANK: return 0.70
            case UnitTypeId.GHOST: return 0.70
            case UnitTypeId.SIEGETANKSIEGED: return 0.80
            # Flying
            case UnitTypeId.VIKINGFIGHTER: return 0.53
            case UnitTypeId.MEDIVAC: return 0.69
            case UnitTypeId.LIBERATOR: return 0.70
            case UnitTypeId.LIBERATORAG: return 0.71
            case UnitTypeId.BATTLECRUISER: return 0.72
            case UnitTypeId.BANSHEE: return 0.75
            # --- Zerg
            # Structures
            case UnitTypeId.SPORECRAWLERUPROOTED: return 0.01
            case UnitTypeId.SPORECRAWLER: return 0.01
            case UnitTypeId.SPINECRAWLERUPROOTED: return 0.05
            case UnitTypeId.SPINECRAWLER: return 0.20
            # Units
            case UnitTypeId.EGG: return 0.00
            case UnitTypeId.LARVA: return 0.01
            case UnitTypeId.CHANGELING: return 0.10
            case UnitTypeId.CREEPTUMOR: return 0.12 # Which one is which?
            case UnitTypeId.CREEPTUMORBURROWED: return 0.13
            case UnitTypeId.CREEPTUMORQUEEN: return 0.14
            case UnitTypeId.CHANGELINGMARINE | UnitTypeId.CHANGELINGZEALOT | UnitTypeId.CHANGELINGZERGLING: return 0.11
            case UnitTypeId.BROODLING: return 0.35
            case UnitTypeId.OVERLORD: return 0.40
            case UnitTypeId.OVERLORDCOCOON: return 0.42
            case UnitTypeId.OVERSEER: return 0.45
            case UnitTypeId.DRONEBURROWED: return 0.49
            case UnitTypeId.DRONE: return 0.50
            case UnitTypeId.ROACHBURROWED : return 0.50
            case UnitTypeId.ROACH: return 0.55
            case UnitTypeId.ZERGLINGBURROWED: return 0.55
            case UnitTypeId.ZERGLING: return 0.60
            case UnitTypeId.QUEENBURROWED: return 0.55
            case UnitTypeId.QUEEN: return 0.60
            case UnitTypeId.HYDRALISKBURROWED: return 0.60
            case UnitTypeId.RAVAGER: return 0.62
            case UnitTypeId.HYDRALISK: return 0.65
            case UnitTypeId.BANELINGCOCOON: return 0.50
            case UnitTypeId.BANELINGBURROWED: return 0.90
            case UnitTypeId.BANELING: return 1.00
            # --- Protoss
            # Structures
            case UnitTypeId.PYLON: return self._get_pylon_attack_base_priority(target)
            case UnitTypeId.PHOTONCANNON: return 0.20
            case UnitTypeId.SHIELDBATTERY:
                return lerp(target.energy_percentage, (0, 0.10), (1, 0.30))
            # Units
            case UnitTypeId.PROBE: return 0.50
            case UnitTypeId.ZEALOT: return 0.55
            case UnitTypeId.PHOENIX: return 0.55
            case UnitTypeId.STALKER: return 0.60
            case UnitTypeId.VOIDRAY: return 0.65
            case UnitTypeId.SENTRY:
                # TODO: detect if sentry is the actual caster
                if target.has_buff(BuffId.GUARDIANSHIELD):
                    return 0.80
                else:
                    return 0.55
            case UnitTypeId.ADEPT: return 0.70
            case UnitTypeId.ADEPTPHASESHIFT: return 0.30
            case UnitTypeId.IMMORTAL:
                if target.has_buff(BuffId.IMMORTALOVERLOAD):
                    return 0.50
                else:
                    return 0.70
            case UnitTypeId.COLOSSUS: return 0.80
            case UnitTypeId.DISRUPTOR: return 0.85
            case UnitTypeId.HIGHTEMPLAR: return 0.90
            case UnitTypeId.WARPPRISM: return 0.90
            # Flying
            case UnitTypeId.INTERCEPTOR: return 0.40
            case UnitTypeId.OBSERVER: return 0.55
            case UnitTypeId.TEMPEST: return 0.70
            case UnitTypeId.ORACLE: return 0.75
            case UnitTypeId.CARRIER: return 0.80


            case _ if target.type_id in PRODUCTION_BUILDING_TYPE_IDS:
                return 0.08
            case _ if target.type_id in TECH_BUILDING_TYPE_IDS:
                return 0.07
            case _ if target.type_id in TOWNHALL_TYPE_IDS:
                return 0.06
            case _ if target.type_id in UPGRADE_BUILDING_TYPE_IDS:
                return 0.04
            case _ if target.type_id in GAS_TYPE_IDS:
                return 0.03

            case _:
                self.log.warning("MissAtkBasPrio {}", target.type_id.name)
                return 0.05 if target.is_structure else 0.50

    def get_attack_priorities(self, attacker: Units, targets: Units) -> dict[Unit, float]:
        """Attack priority is based on:
            1) Unit Type (i.e., Baneling > Zergling > Drone)
            2) Missing health of target (weakness)
            3) Distance
        All values are in [0, 1]
        """
        priorities: dict[Unit, float] = {}
        # TODO testing
        #min_distance = get_closest_distance(attacker, targets)
        min_sq_distance = max(get_closest_sq_distance(attacker, targets), 1)
        for target in targets:
            floor, ceil = 0.0, 1.0
            base = self._get_attack_base_priority(target)
            # t_damage, t_speed, t_range = target.calculate_damage_vs_target(attacker)
            weakness = 1 - target.shield_health_percentage**2
            #distance = min_distance / (attacker.closest_distance_to(target) + 1e-15)
            distance = min_sq_distance / max(get_closest_sq_distance(attacker, target), 1)
            priority = (
                    self.attack_priority_base_weight * base
                    + self.attack_priority_weakness_weight * weakness
                    + self.attack_priority_distance_weight * distance
                    + self.attack_priority_base_weakness_correlation * base * weakness
                    + self.attack_priority_base_distance_correlation * base * distance
                    + self.attack_priority_weakness_distance_correlation * weakness * distance
            )
            priorities[target] = max(floor, min(ceil, priority))
        return priorities

    def get_defense_priority(self, defender: Unit, threat: Unit) -> float:
        """Defense priority is based on:
            1) Unit Type
            2) Distance
        """
        distance = defender.distance_to(threat)
        attack_distance = distance - defender.radius - threat.radius

        match threat.type_id:
            # --- Terran
            case UnitTypeId.SCV: return lerp(attack_distance, (0.5, 0.5), (3, 0))
            case UnitTypeId.MARINE: return lerp(attack_distance, (5, 0.2), (6, 0.1))
            case UnitTypeId.REAPER: return lerp(attack_distance, (5, 0.2), (6, 0.1))
            case UnitTypeId.HELLION: return lerp(attack_distance, (4, 0.7), (5, 0.2))
            case UnitTypeId.HELLIONTANK: return lerp(attack_distance, (3, 0.8), (5, 0.2))
            case UnitTypeId.WIDOWMINE: return lerp(attack_distance, (4.5, 0.9), (5, 0.2))
            case UnitTypeId.SIEGETANK: return lerp(attack_distance, (7, 0.3))
            case UnitTypeId.SIEGETANKSIEGED:
                # TODO use facing (?)
                return lerp(attack_distance, (2, 0.8), (11, 0.8), (13, 0.2))

            # --- Zerg
            case UnitTypeId.DRONE: return lerp(attack_distance, (0.5, 0.5), (3, 0))
            case UnitTypeId.ZERGLING: return lerp(attack_distance, (0.5, 0.8), (1.5, 0.5), (5.0, 0.2))
            case UnitTypeId.BANELING: return lerp(attack_distance, (2.0, 1.0), (2.0, 0.5), (5.0, 0.3))
            # --- Protoss
            case UnitTypeId.PROBE: return lerp(attack_distance, (0.5, 0.5), (3, 0))
            case UnitTypeId.ZEALOT: return lerp(attack_distance, (0.5, 0.8), (2.0, 0.5), (5.0, 0.2))
            case UnitTypeId.ADEPTPHASESHIFT: return 0.7 if attack_distance <= 4 else 0.1
            case UnitTypeId.ADEPT: return lerp(attack_distance, (2, 0.7), (4, 0.5), (5, 0.2))
            case UnitTypeId.ARCHON: return 0.8 if attack_distance <= 3 else 0.2
            case UnitTypeId.DISRUPTOR: return 0.0
            case UnitTypeId.DISRUPTORPHASED: return lerp(distance, (1.5, 1.0), (3.5, 0))
            case UnitTypeId.COLOSSUS: return lerp(attack_distance, (6, 0.75), (0.8, 0.2))
            case _ if threat.can_attack: return 0.20
            case _: return 0

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

    def get_enemies(self, units: Units, *, scan_range: float = 5.0) -> Units:
        enemies = []
        for enemy in self.api.all_enemy_units:
            for unit in units:
                max_dist = (unit.ground_range + scan_range)**2
                if squared_distance(unit, enemy) <= max_dist:
                    enemies.append(enemy)
                    break
        return Units(enemies, self.api)

    async def micro_squad(self, squad: Squad, *,
                          enemies: Optional[Units] = None) -> None:
        # TODO: Move parts into SquadManager?
        if enemies is None:
            enemies = self.get_enemies(squad.units)

        squad_attack_priorities = self.combat.get_attack_priorities(squad.units, enemies)
        if squad_attack_priorities:
            squad_target, squad_target_priority = max(squad_attack_priorities.items(), key=lambda kv: kv[1])
            squad.set_status(SquadStatus.COMBAT)
            # TODO DEBUG
            if self.debug:
                for unit, priority in squad_attack_priorities.items():
                    if unit == squad_target:
                        color = 'RED'
                    elif priority >= 0.5:
                        color = 'YELLOW'
                    else:
                        color = 'GREEN'
                    self.debug.box_with_text(unit, f'{100*priority:.0f}', color=color)

        else:
            squad_target = None
            squad_target_priority = 0
            if isinstance(squad.task, (SquadAttackTask, SquadDefendTask, SquadRetreatTask)):
                # TODO: all units?
                if sum(unit.position in squad.task.target for unit in squad.units) >= max(0.75 * len(squad), 1):
                    squad.set_status(SquadStatus.AT_TARGET)
                else:
                    squad.set_status(SquadStatus.MOVING)
            elif isinstance(squad.task, SquadJoinTask):
                squad.set_status(SquadStatus.MOVING)
            else:
                squad.set_status(SquadStatus.IDLE)

        #if self.bot.state.game_loop % 20 == 0:
        #    abilities = await self.get_abilities(units)
        #else:
        #    abilities = [[] for _ in range(len(units))]
        abilities = await self.get_abilities(squad.units)
        for unit, unit_abilities in zip(squad.units, abilities):
            self._micro_unit(
                unit,
                enemies=enemies,
                abilities=unit_abilities,
                squad=squad,
                squad_attack_priorities=squad_attack_priorities,
                squad_target_priority=squad_target_priority,
                squad_target=squad_target
            )

    def _micro_unit(self, unit: Unit, *,
                    enemies: Units,
                    abilities: list[AbilityId],
                    squad: Squad,
                    squad_attack_priorities: dict[Unit, float],
                    squad_target_priority: float,
                    squad_target: Optional[Unit]) -> bool:

        # --- Offense
        weapon_ready = self.weapon_ready(unit)
        if weapon_ready and squad_attack_priorities:
            attack_prio, target = self._evaluate_offense(unit, squad_attack_priorities=squad_attack_priorities)
        else:
            attack_prio = 0
            target = None

        if target:
            return self.order.attack(unit, target)

        # --- Ability
        if abilities and squad_attack_priorities:
            ability_prio, ability_id, ability_target = self._evaluate_ability(
                unit, abilities=abilities, group_attack_priorities=squad_attack_priorities)
            if ability_prio > 0.5:
                return self.order.ability(unit, ability_id, ability_target)

        if isinstance(squad.task, SquadRetreatTask):
            return self.order.move(unit, squad.task.target.center)

        if squad_target_priority >= self.attack_priority_threshold and squad_target:
            dist_sq = (unit.ground_range + unit.radius + squad_target.radius + unit.distance_to_weapon_ready)**2
            if unit.distance_to_squared(squad_target) >= dist_sq:
                return self.order.attack(unit, squad_target)
                #intercept_point = self.bot.intercept_unit(unit, squad_target)
                #return self.order.attack(unit, intercept_point)

        # --- Defense
        defense_prio, defense_position = self._evaluate_defense(unit, enemies=enemies)

        if defense_prio >= self.defense_priority_threshold:  # or (defense_position and unit.shield_health_percentage < 0.2):
            return self.order.move(unit, defense_position)

        if defense_position and unit.shield_health_percentage < 0.8:
            return self.order.move(unit, defense_position)

        if squad_target_priority >= self.attack_priority_threshold and squad_target:
            return self.order.attack(unit, squad_target)
            #intercept_point = self.bot.intercept_unit(unit, squad_target)
            #return self.order.attack(unit, intercept_point)

        # Regroup
        #scan_sq = self.get_scan_range(unit)**2
        if len(squad) > 0 and squared_distance(unit, squad.center) >= squad.leash_range**2:
            return self.order.move(unit, squad.center)

        if isinstance(squad.task, (SquadAttackTask, SquadDefendTask)):
            if unit.position not in squad.task.target:
                 return self.order.move(unit, squad.task.target.center)
            if unit.is_idle:
                return self.order.move(unit, squad.task.target.random)
        elif isinstance(squad.task, SquadJoinTask):
            return self.order.move(unit, squad.task.target.center)

            ## Move to task location
            #if squared_distance(unit, squad.task.target) > scan_sq:
            #    return self.order.move(unit, squad.task.target)
            ## Attack
            #else:
            #    return self.order.move(unit, squad.task.target)
            #    ## TODO
            #    #if isinstance(squad.task, SquadAttackTask):
            #    #    return self.order.move(unit, squad.task.target)
            #    #elif isinstance(squad.task, SquadDefendTask):
            #    #    if not unit.orders:
            #    #        return self.order.move(unit, squad.task.target, queue=True)

        return False

    def _evaluate_defense(self, unit: Unit, *, enemies: Units) -> tuple[float, Optional[Point2]]:
        threat_range = self.get_threat_range(unit)
        threats = enemies.closer_than(threat_range, unit)
        defense_priorities = self.bot.combat.get_defense_priorities(unit, threats)
        if not defense_priorities:
            return 0, None
        threat, defense_prio = max(defense_priorities.items(), key=lambda kv: kv[1])
        # TODO
        if threat.type_id == UnitTypeId.SIEGETANKSIEGED and unit.distance_to(threat) <= 9:
            step = 3
        else:
            step = -3

        defense_position = unit.position.towards(threat, distance=step * unit.distance_per_step)
        # if not self.bot.game_info.pathing_grid[(int(defense_position.x), int(defense_position.y))]:
        #    defense_position = marine.position.towards_with_random_angle(threat.position, distance=-2)
        return defense_prio, defense_position

    def _target_in_range(self, unit: Unit, target: Unit) -> bool:
        # TODO
        return unit.target_in_range(target)
        # if target.type_id == UnitTypeId.SIEGETANKSIEGED:
        #     bonus_distance = 0
        # else:
        #     bonus_distance = 0
        # return unit.target_in_range(target, bonus_distance=bonus_distance)

    def _evaluate_offense(self, unit: Unit, *,
                          squad_attack_priorities: dict[Unit, float]) -> tuple[float, Optional[Unit]]:

        # scan_range = self.get_scan_range(unit)
        # attack_priorities_scan_range = {target: priority for target, priority
        #                                 in group_attack_priorities.items()
        #                                 if squared_distance(unit, target) <= scan_range ** 2}
        attack_priorities_attack_range = {target: priority for target, priority
                                          in squad_attack_priorities.items()
                                          if self._target_in_range(unit, target)}

        if not attack_priorities_attack_range:
            return 0, None

        target, attack_prio = max(attack_priorities_attack_range.items(), key=lambda kv: kv[1])
        return attack_prio, target

    def _evaluate_ability(self, unit: Unit, *,
                          abilities: list[AbilityId],
                          group_attack_priorities: dict[Unit, float]
                          ) -> tuple[float, Optional[AbilityId], Optional[Unit | Point2]]:

        for ability_id in abilities:
            attack_priorities_ability_range = {target: priority for target, priority
                                               in group_attack_priorities.items()
                                               if unit.in_ability_cast_range(ability_id, target)}

            if not attack_priorities_ability_range:
                continue

            if ability_id == AbilityId.KD8CHARGE_KD8CHARGE:
                target, ability_prio = max(attack_priorities_ability_range.items(), key=lambda kv: kv[1])
                # TODO
                #target = target.position.towards(unit, distance=0)
                return 1.0, ability_id, target

        return 0, None, None
