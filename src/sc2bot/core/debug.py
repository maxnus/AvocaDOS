import sys
from typing import TYPE_CHECKING, Optional, ClassVar

from loguru import logger
from sc2.client import Client
from sc2.position import Point3, Point2
from sc2.unit import Unit

if TYPE_CHECKING:
    from sc2bot.core.bot import BotBase


RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)

class Debug:
    bot: 'BotBase'
    debug_messages: list[str]
    text_size: ClassVar[int] = 16

    def __init__(self, bot: 'BotBase') -> None:
        self.bot = bot
        self.debug_messages = []
        self.logger = logger.bind(bot=bot.name, prefix='Bot', frame=0, time=0)

        def ingame_logging(message):
            if not hasattr(self, 'client'):
                return
            formatted = message.record['extra'].get('formatted', message)
            self.debug_messages.append(formatted)

        self.logger.add(
            sys.stderr,
            level="TRACE",
            filter=lambda record: record['extra'].get('bot') == bot.name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )
        self.logger.add(
            ingame_logging,
            level="DEBUG",
            filter=lambda record: record['extra'].get('bot') == bot.name,
            format="[{extra[frame]}|{extra[time]:.3f}|{extra[prefix]}] {message}"
        )

    @property
    def client(self) -> Client:
        return self.bot.client

    def normalize_point3(self, point: Unit | Point3 | Point2) -> Point3:
        if isinstance(point, Point3):
            return point
        if isinstance(point, Unit):
            return point.position3d
        if isinstance(point, Point2):
            return Point3((point[0], point[1], self.bot.get_terrain_z_height(point)))
        raise TypeError(f"invalid argument: {point}")

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
        position = self.normalize_point3(position)
        offset = 0.0
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            line_position = position + Point3((0, offset, 0))
            self.client.debug_text_world(line, line_position, size=size, color=color)
            offset += size / 1000

    def box(self, center: Unit | Point3 | Point2, size: Optional[float] = None, *,
            color: tuple[int, int, int] = YELLOW) -> None:
        center = self.normalize_point3(center)
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

    def on_step_start(self, step: int) -> None:
        self.logger = self.logger.bind(step=step, time=self.bot.time)

    def on_step_end(self, step: int) -> None:
        self.text_screen(self.debug_messages)
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
        self.text_screen(f"step time (ms): {last_step:.3f} (avg={avg_step:.3f}, min={min_step:.3f}"
                               f", max={max_step:.3f})", position=(0.73, 0.7), color=color)

        for commander in self.bot.commander.values():
            for tag, order in commander.orders.items():
                unit = (self.bot.units + self.bot.structures).find_by_tag(tag)
                if unit is None:
                    continue
                #self.text_world(str(order), unit)
                self.box_with_text(unit, str(order))

        if self.bot.map is not None:
            #for idx, expansion in enumerate(self.bot.map.enemy_expansions):
            #    self.box_with_text(expansion, f"Enemy expansion {idx}")
            for idx, expansion in enumerate(self.bot.map.expansions):
                self.box_with_text(expansion[0], f"Expansion {idx}: {expansion[1]}")
