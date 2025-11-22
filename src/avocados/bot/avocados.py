from typing import Optional, Any

from loguru._logger import Logger
from sc2.data import Result
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from avocados import api
from avocados.__about__ import __version__
from avocados.bot.requestmanager import RequestManager
from avocados.bot.rolemanager import RoleManager
from avocados.bot.scanmanager import ScanManager
from avocados.bot.taunts import TauntManager
from avocados.bot.buildingmanager import BuildingManager
from avocados.bot.buildordermanager import BuildOrderManager
from avocados.bot.defensemanager import DefenseManager
from avocados.bot.memorymanager import MemoryManager
from avocados.bot.intelmanager import IntelManager
from avocados.bot.expansionmanager import ExpansionManager
from avocados.bot.strategymanager import StrategyManager
from avocados.core.manager import BotManager
from avocados.debug.debugmanager import DebugManager
from avocados.debug.micro_scenario_manager import MicroScenarioManager
from avocados.mapdata.mapmanager import MapManager
from avocados.bot.resourcemanager import ResourceManager
from avocados.bot.objectivemanager import ObjectiveManager
from avocados.combat.combatmanager import CombatManager
from avocados.combat.squadmanager import SquadManager


LOG_FORMAT = ("<level>[{level:8}]</level>"
              "<green>[{extra[step]}|{extra[time]}|{extra[prefix]}]</green>"
              " <level>{message}</level>")


class AvocaDOS:
    cache: dict[str, Any]
    # Manager
    map: Optional[MapManager]
    build: BuildOrderManager
    roles: RoleManager
    resources: ResourceManager
    objectives: ObjectiveManager
    squads: SquadManager
    intel: IntelManager
    scan: ScanManager
    combat: CombatManager
    expand: ExpansionManager
    memory: MemoryManager
    request: RequestManager
    building: BuildingManager
    strategy: StrategyManager
    taunt: TauntManager
    debug: Optional[DebugManager]
    micro_scenario: Optional[MicroScenarioManager]
    leave_at: Optional[float]

    def __init__(self,
                 *,
                 build: Optional[str] = 'default',
                 debug: bool = False,
                 micro_scenario: Optional[dict[UnitTypeId, int] | tuple[dict[UnitTypeId, int], dict[UnitTypeId, int]]] = None,
                 leave_at: Optional[float] = None,
                 ) -> None:
        super().__init__()
        self.cache = {}

        # Manager
        self.logger.debug("Initializing {}...", self)
        self.roles = RoleManager(self)
        self.map = MapManager(self)

        self.memory = MemoryManager(self)
        self.taunt = TauntManager(self)
        # One dependency
        self.intel = IntelManager(self, map_manager=self.map)
        self.scan = ScanManager(self, intel_manager=self.intel)
        self.squads = SquadManager(self, map_manager=self.map)
        #
        self.combat = CombatManager(self, memory_manager=self.memory, taunt_manager=self.taunt,
                                    squad_manager=self.squads)

        self.expand = ExpansionManager(self, map_manager=self.map, scan_manager=self.scan)
        self.request = RequestManager(self, map_manager=self.map, squad_manager=self.squads,
                                      expansion_manager=self.expand)
        self.defense = DefenseManager(self, expansion_manager=self.expand)
        self.resources = ResourceManager(self, expansion_manager=self.expand)
        self.building = BuildingManager(self, map_manager=self.map)
        self.objectives = ObjectiveManager(self, building_manager=self.building, resource_manager=self.resources,
                                           squad_manager=self.squads, request_manager=self.request)
        self.build = BuildOrderManager(self, build=build, map_manager=self.map, objective_manager=self.objectives)
        self.strategy = StrategyManager(self, map_manager=self.map, memory_manager=self.memory,
                                        resource_manager=self.resources, intel_manager=self.intel,
                                        expansion_manager=self.expand, objective_manager=self.objectives)
        self.debug = (DebugManager(self, map_manager=self.map, building_manager=self.building,
                                   memory_manager=self.memory, intel_manager=self.intel,
                                   expansion_manager=self.expand, objective_manager=self.objectives,
                                   squad_manager=self.squads, scan_manager=self.scan, strategy_manager=self.strategy)
                      if (debug or micro_scenario) else None)
        if micro_scenario is not None:
            self.micro_scenario = MicroScenarioManager(self, units=micro_scenario, map_manager=self.map,
                                                       squad_manager=self.squads, debug_manager=self.debug)
        else:
            self.micro_scenario = None
        self.leave_at = leave_at

        # Register callbacks
        api.register_on_start(self.on_start)
        api.register_on_step(self.on_step)
        api.register_on_end(self.on_end)
        api.register_on_unit_created(self.on_unit_created)
        api.register_on_unit_destroyed(self.on_unit_destroyed)
        api.register_on_unit_took_damage(self.on_unit_took_damage)
        api.register_on_building_construction_started(self.on_building_construction_started)
        api.register_on_building_construction_complete(self.on_building_construction_complete)

        self.logger.debug("{} initialized", self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({__version__})"

    @property
    def logger(self) -> Logger:
        return api.logger.bind(prefix=type(self).__name__)

    @property
    def managers(self) -> list[BotManager]:
        return [manager for name in vars(self) if isinstance(manager := getattr(self, name), BotManager)]

    # --- Callbacks

    async def on_start(self) -> None:
        await self.map.on_start()
        await self.expand.on_start()
        await self.building.on_start()
        await self.intel.on_start()
        await self.build.on_start()
        await self.strategy.on_start()

        if self.micro_scenario is not None:
            await self.micro_scenario.on_start()

    async def on_step_start(self, step: int) -> None:
        if step == 50:
            intro_line1 = "    Artificial  Villain  of  Cheesy  and"
            intro_line2 = "  Dishonorable  Offensive  Strategies"
            await api.client.chat_send(intro_line1, False)
            await api.client.chat_send(intro_line2, False)

        if step == 600:
            version = __version__.replace('.', '-')
            matchup = f"{str(api.race)[5]}v{str(api.enemy_race)[5]}"
            tag = f" v{version}  {api.game_info.map_name}  {matchup}"
            api.log.tag(tag, add_time=False)

        if step % 500 == 0:
            self._report_timings()

        # Cleanup steps / internal to manager
        await self.objectives.on_step_start(step)
        await self.expand.on_step_start(step)
        await self.map.on_step_start(step)
        await self.building.on_step_start(step)
        await self.intel.on_step_start(step)
        await self.scan.on_step_start(step)
        await self.resources.on_step_start(step)
        await self.memory.on_step_start(step)
        await self.squads.on_step_start(step)

    async def on_step(self, step: int):
        await self.on_step_start(step)

        if self.leave_at is not None and api.time >= self.leave_at - 1:
            api.log.tag('GG', add_time=False)
            if api.time >= self.leave_at:
                await api.client.leave()
            return

        if self.micro_scenario is not None and self.micro_scenario.running:
            await self.micro_scenario.on_step(step)

        # if self.time >= 180:
        #    self.logger.info("Minerals at 3 min = {}", self.minerals)
        await self.objectives.on_step(step)
        await self.scan.on_step(step)
        await self.defense.on_step(step)
        await self.squads.on_step(step)
        await self.combat.on_step(step)
        await self.strategy.on_step(step)
        await self.expand.on_step(step)
        await self._other(step)  # TODO: find a place for this

        await self.on_step_end(step)

    async def on_step_end(self, step: int) -> None:
        if self.debug:
            await self.debug.on_step(step)
        if step % 8 == 0:
            await self.taunt.on_step(step)

    async def on_end(self, game_result: Result) -> None:
        self.logger.info("Game result: {}", game_result)
        pass

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        pass

    async def on_unit_created(self, unit: Unit) -> None:
        pass

    async def on_building_construction_started(self, unit: Unit) -> None:
        pass

    async def on_building_construction_complete(self, unit: Unit) -> None:
        for manager in self.managers:
            func = getattr(manager, 'on_building_construction_complete', None)
            if func is not None:
                await func(unit)

    async def on_unit_destroyed(self, unit_tag: int) -> None:
        pass

    # --- Private

    async def _other(self, step: int) -> None:
        # TODO: find the right location in the code

        for unit in api.structures(UnitTypeId.SUPPLYDEPOT).ready.idle:
            if not api.enemy_units.not_flying.closer_than(4.5, unit):
                api.order.ability(unit, AbilityId.MORPH_SUPPLYDEPOT_LOWER)
        for unit in api.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready.idle:
            if api.enemy_units.not_flying.closer_than(3.5, unit):
                api.order.ability(unit, AbilityId.MORPH_SUPPLYDEPOT_RAISE)

        for cc in api.townhalls.of_type((UnitTypeId.COMMANDCENTER, UnitTypeId.ORBITALCOMMAND)).ready:
            enemies = api.all_enemy_units.closer_than(7, cc)
            if enemies and not api.workers.closer_than(6, cc):
                api.order.ability(cc, AbilityId.LIFT)
        for cc in api.townhalls.of_type((UnitTypeId.COMMANDCENTERFLYING, UnitTypeId.ORBITALCOMMANDFLYING)).ready:
            enemies = api.all_enemy_units.closer_than(8, cc)
            if not enemies:
                loc = min(self.map.expansions, key=lambda exp: exp.center.distance_to(cc))
                api.order.ability(cc, AbilityId.LAND, loc.center)

        for structure in api.structures_without_construction_SCVs:
            cancel = True
            if structure.health + structure.shield > 50:
                for unit, orders in api.order.orders.items():
                    if not orders:
                        continue
                    if (target := getattr(orders[0], 'target', None)) is not None:
                        if target == structure:
                            cancel = False
                            break
            if cancel:
                self.logger.debug("Cancelling {}", structure)
                api.order.ability(structure, AbilityId.CANCEL)
            else:
                self.logger.debug("Keeping {}", structure)

    def _report_timings(self) -> None:
        for manager in self.managers:
            if hasattr(manager, 'timings'):
                for key, timings in manager.timings.items():
                    self.logger.info("{:<16s} : {:<24s}: {}", type(manager).__name__, key, timings)
                    timings.reset()