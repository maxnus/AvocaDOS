import sys
from typing import TYPE_CHECKING, Optional, ClassVar

from loguru import logger as _logger
from sc2.client import Client
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point3, Point2
from sc2.unit import Unit

from sc2bot.debug.micro_scenario import MicroScenario

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)


class Debug:
    bot: 'BotBase'
    debug_messages: list[str]
    text_size: ClassVar[int] = 16
    micro_scenarios: dict[int, MicroScenario]
    # State
    map_revealed: bool
    enemy_control: bool
    # Config
    show_log: bool
    show_orders: bool
    show_commanders: bool

    def __init__(self, bot: 'BotBase') -> None:
        self.bot = bot
        self.debug_messages = []
        self.logger = _logger.bind(bot=bot.name, prefix='Bot', frame=0, time=0)
        self.micro_scenarios = {}
        self.map_revealed = False
        self.enemy_control = False
        self.show_log = True
        self.show_orders = False
        self.show_commanders = True

        def ingame_logging(message):
            if not hasattr(self, 'client'):
                return
            formatted = message.record['extra'].get('formatted', message)
            self.debug_messages.append(formatted)

        # self.logger.add(
        #     sys.stdout,
        #     level="TRACE",
        #     filter=lambda record: record['extra'].get('bot') == bot.name,
        #     format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        # )
        self.logger.add(
            ingame_logging,
            level="DEBUG",
            filter=lambda record: record['extra'].get('bot') == bot.name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )

    @property
    def client(self) -> Client:
        return self.bot.client

    async def reveal_map(self) -> None:
        if not self.map_revealed:
            await self.client.debug_show_map()
            self.map_revealed = True

    async def hide_map(self) -> None:
        if self.map_revealed:
            await self.client.debug_show_map()
            self.map_revealed = False

    async def control_enemy(self) -> None:
        if not self.control_enemy:
            await self.client.debug_control_enemy()
            self.enemy_control = True

    async def control_enemy_off(self) -> None:
        if self.control_enemy:
            await self.client.debug_control_enemy()
            self.enemy_control = False

    async def on_step_start(self, step: int) -> None:
        self.logger = self.logger.bind(step=step, time=self.bot.time)
        await self._handle_chat()

        scenarios_finished: set[int] = set()
        for scenario in self.micro_scenarios.values():
            if await scenario.step():
                scenarios_finished.add(scenario.id)
        for scenario_id in scenarios_finished:
            self.micro_scenarios.pop(scenario_id)
        if scenarios_finished and not self.micro_scenarios:
            await self.hide_map()
            await self.control_enemy_off()

    async def on_step_end(self, step: int) -> None:
        if self.show_log:
            self.text_screen(self.debug_messages)

        if self.show_commanders:
            info = []
            for commander in self.bot.commander.values():
                info.append(repr(commander))
                for task in commander.tasks:
                    info.append("   " + repr(task))
            self.text_screen(info, position=(0.005, 0.4))

        mineral_rate, vespene_rate = self.bot.history.get_resource_rates()
        self.text_screen(f"{mineral_rate=:.2f}, {vespene_rate=:.2f}", position=(0.8, 0.05))

        mineral_rate, vespene_rate = self.bot.estimate_resource_collection_rates()
        self.text_screen(f"{mineral_rate=:.2f}, {vespene_rate=:.2f}", position=(0.8, 0.08))

        min_step, avg_step, max_step, last_step = self.bot.step_time
        if last_step <= 10:
            color = GREEN
        elif last_step <= 40:
            color = YELLOW
        else:
            color = RED
        self.text_screen(f"step time (ms): {last_step:.1f} (avg={avg_step:.1f}, min={min_step:.1f}"
                         f", max={max_step:.1f})", position=(0.73, 0.7), color=color)

        if self.show_orders:
            for commander in self.bot.commander.values():
                for tag, order in commander.orders.items():
                    unit = (self.bot.units + self.bot.structures).find_by_tag(tag)
                    if unit is None:
                        continue
                    #self.text_world(str(order), unit)
                    self.box_with_text(unit, str(order))

        #if self.bot.map is not None:
        #    #for idx, expansion in enumerate(self.bot.map.enemy_expansions):
        #    #    self.box_with_text(expansion, f"Enemy expansion {idx}")
        #    for idx, expansion in enumerate(self.bot.map.expansions):
        #        self.box_with_text(expansion[0], f"Expansion {idx}: {expansion[1]}")

    def text_screen(self,
                    lines: list[str] | str,
                    *,
                    position: tuple[float, float] = (0.005, 0.01),
                    size: int = 16, color: tuple[int, int, int] = YELLOW,
                    max_lines: int = 10):
        y = position[1]
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            self.client.debug_text_screen(line, (position[0], y), size=size, color=color)
            y += size / 1000

    def text_world(self,
                   lines: list[str] | str,
                   position: Unit | Point3 | Point2,
                   *,
                   size: int = 16, color: tuple[int, int, int] = YELLOW,
                   max_lines: int = 10):
        position = self._normalize_point3(position)
        offset = 0.0
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            line_position = position + Point3((0, offset, 0))
            self.client.debug_text_world(line, line_position, size=size, color=color)
            offset += size / 1000

    def box(self, center: Unit | Point3 | Point2, size: Optional[float] = None, *,
            color: tuple[int, int, int] = YELLOW) -> None:
        center = self._normalize_point3(center)
        if size is None:
            if isinstance(center, Unit):
                if center.is_structure:
                    size = center.footprint_radius
                else:
                    size = center.radius
            else:
                size = 0.5
        self.client.debug_box2_out(center, half_vertex_length=size, color=color)

    def box_with_text(self, center: Unit | Point3 | Point2, text: str | list[str], size: Optional[float] = None, *,
                      color: tuple[int, int, int] = YELLOW) -> None:
        self.box(center, size, color=color)
        self.text_world(text, center, color=color)

    async def _handle_chat(self):
        for chat_message in self.bot.state.chat:
            self.logger.debug("Chat message: {}", chat_message.message)
            if chat_message.message.startswith('!'):
                cmd, *args = chat_message.message.split()
                valid_args = {'control_enemy', 'food', 'free', 'all_resources', 'god', 'minerals', 'gas',
                              'cooldown', 'tech_tree', 'upgrade', 'fast_build'}
                if cmd == '!debug' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.bot.debug_enabled = bool(int(args[0]))
                elif cmd == '!debug' and len(args) == 1 and args[0] in valid_args:
                    func = getattr(self.client, f'debug_{args[0]}', None)
                    if func is not None:
                        await func()
                elif cmd == '!micro':
                    if self.bot.game_info.map_name != '144-66':
                        continue

                    await self.reveal_map()
                    await self.control_enemy()
                    units = (
                        {UnitTypeId.MARINE: 8},
                        {UnitTypeId.ZEALOT: 4},
                    )
                    for row in range(6):
                        for col in range(6):
                            if (row, col) in {(5, 0), (5, 5)}:
                                continue
                            x = col * 24 + 12
                            y = row * 24 + 12
                            location = Point2((x, y))
                            scenario = MicroScenario(self.bot, units=units, location=location)
                            self.micro_scenarios[scenario.id] = scenario
                            await scenario.start()

                elif cmd == '!slow':
                    if len(args) == 0:
                        slowdown_time = 40
                    else:
                        try:
                            slowdown_time = float(args[0])
                        except ValueError:
                            continue
                    self.bot.slowdown_time = slowdown_time

    def _normalize_point3(self, point: Unit | Point3 | Point2) -> Point3:
        if isinstance(point, Point3):
            return point
        if isinstance(point, Unit):
            return point.position3d
        if isinstance(point, Point2):
            return Point3((point[0], point[1], self.bot.get_terrain_z_height(point)))
        raise TypeError(f"invalid argument: {point}")
