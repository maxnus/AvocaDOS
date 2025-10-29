import asyncio
import math
import sys
from time import perf_counter
from typing import TYPE_CHECKING, Optional, ClassVar

from loguru import logger as _logger
from loguru._logger import Logger
from sc2.client import Client
from sc2.position import Point3, Point2
from sc2.unit import Unit

from sc2bot.core.system import System

if TYPE_CHECKING:
    from sc2bot.core.avocados import AvocaDOS


RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)


class DebugSystem(System):
    text_size: ClassVar[int] = 16
    # State
    map_revealed: bool
    enemy_control: bool
    slowdown: float
    frame_start: Optional[float]
    # Frame data
    debug_messages: list[str]
    damage_taken: dict[Unit, float]
    # Config
    show_log: bool
    show_orders: bool
    show_commanders: bool
    show_combat: bool

    def __init__(self, bot: 'AvocaDOS', *, slowdown: float = 0.0, log_level: str = "DEBUG") -> None:
        super().__init__(bot)
        self.debug_messages = []
        self.damage_taken = {}
        self.shot_last_frame = set()
        self._logger = _logger.bind(bot=bot.name, prefix='Bot', frame=0, time=0)
        self.slowdown = slowdown
        self.frame_start = None
        self.map_revealed = False
        self.enemy_control = False
        self.show_log = False
        self.show_orders = False
        self.show_commanders = True
        self.show_combat = True

        def ingame_logging(message):
            if not hasattr(self, 'client'):
                return
            formatted = message.record['extra'].get('formatted', message)
            self.debug_messages.append(formatted)

        self.logger.add(
            sys.stdout,
            level=log_level,
            filter=lambda record: record['extra'].get('bot') == bot.name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )
        self._logger.add(
            ingame_logging,
            level="DEBUG",
            filter=lambda record: record['extra'].get('bot') == bot.name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )

    @property
    def client(self) -> Client:
        return self.bot.client

    @property
    def logger(self) -> Logger:
        return self._logger

    # Controls

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

    # Callbacks

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        assert unit not in self.damage_taken
        self.damage_taken[unit] = amount_damage_taken

    async def on_step_start(self, step: int) -> None:
        self._logger = self.logger.bind(step=self.bot.state.game_loop, time=self.bot.time)
        self.frame_start = perf_counter()
        await self._handle_chat()

    async def on_step_end(self, step: int) -> None:
        if self.show_log:
            self.text_screen(self.debug_messages)

        if self.show_commanders:
            info = []
            for commander in self.bot.commanders.values():
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
            for commander in self.bot.commanders.values():
                for tag, orders in commander.order.orders.items():
                    if not orders:
                        continue
                    unit = (self.bot.units + self.bot.structures).find_by_tag(tag)
                    if unit is None:
                        continue
                    self.box_with_text(unit, str(orders[0]))

        if self.show_combat:
            for commander in self.bot.commanders.values():
                for unit in commander.units:
                    if unit.weapon_cooldown != 0:
                        #bar = f"{unit.weapon_cooldown:.3f}"
                        #bar = ";".join([str(w) for w in unit._weapons])
                        text = f'({math.ceil(unit.weapon_cooldown)})'
                        self.text_world(text, unit.position3d + Point3((0, 0, -0.5)),
                                        size=12, color=CYAN)

                    if unit.orders:
                        order = unit.orders[0]
                        if isinstance(order.target, int):
                            target = self.bot.all_units.find_by_tag(order.target)
                        else:
                            target = order.target
                        if target is not None:
                            self.line(unit, target)
                        #self.text_world(str(order), unit, size=14)
            for unit, damage in self.damage_taken.items():
                color = RED if damage > 0 else GREEN
                self.text_world(f"[{self.bot.state.game_loop}] -{damage:.2f}", unit.position3d + Point3((0, 0, 1.2)),
                                size=12, color=color)

        self.damage_taken.clear()

        #if self.bot.map is not None:
        #    #for idx, expansion in enumerate(self.bot.map.enemy_expansions):
        #    #    self.box_with_text(expansion, f"Enemy expansion {idx}")
        #    for idx, expansion in enumerate(self.bot.map.expansions):
        #        self.box_with_text(expansion[0], f"Expansion {idx}: {expansion[1]}")

        if self.slowdown and self.frame_start:
            sleep = self.slowdown / 1000 - (perf_counter() - self.frame_start)
            if sleep > 0:
                await asyncio.sleep(sleep)

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

    def line(self, start: Point2 | Point3 | Unit, end: Point2 | Point3 | Unit, *,
             color: tuple[int, int, int] = YELLOW) -> None:
        start = self._normalize_point3(start)
        end = self._normalize_point3(end)
        self.client.debug_line_out(start, end, color=color)

    async def _handle_chat(self):
        cheats = {'!control_enemy', '!food', '!free', '!all_resources', '!god', '!minerals', '!gas',
                  '!cooldown', '!tech_tree', '!upgrade', '!fast_build'}

        for chat_message in self.bot.state.chat:
            self.logger.debug("Chat message: {}", chat_message.message)
            if chat_message.message.startswith('!'):
                cmd, *args = chat_message.message.split()

                if cmd == '!log' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_log = bool(int(args[0]))

                elif cmd == '!cmd' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_commanders = bool(int(args[0]))

                elif cmd == '!orders' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_orders = bool(int(args[0]))

                elif cmd == '!debug' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.bot.debug_enabled = bool(int(args[0]))

                elif cmd in cheats:
                    func = getattr(self.client, f'debug_{cmd[1:]}', None)
                    if func is not None:
                        await func()

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
