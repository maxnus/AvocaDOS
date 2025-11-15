import math
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from typing import TYPE_CHECKING, Optional, ClassVar, Protocol

from sc2.client import Client
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point3, Point2
from sc2.unit import Unit, UnitOrder

from avocados.geometry.field import Field
from avocados.core.manager import BotManager
from avocados.geometry import Circle, Region
from avocados.combat.squad import SquadAttackTask, SquadDefendTask, SquadJoinTask, SquadRetreatTask

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


class Color:
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    PINK = (255, 0, 255)
    CYAN = (0, 255, 255)
    ORANGE = (255, 128, 0)
    BLACK = (0, 0, 0)
    DARK_GREY = (192, 192, 192)
    GREY = (128, 128, 128)
    WHITE = (255, 255, 255)


ColorType = tuple[int, int, int] | str


def normalize_color(color: tuple[int, int, int] | str) -> tuple[int, int, int]:
    if isinstance(color, str):
        return getattr(Color, color.upper())
    return color


def mix_colors(color1: ColorType, color2: ColorType, factor: float) -> ColorType:
    color1 = normalize_color(color1)
    color2 = normalize_color(color2)
    return (
            int(factor * color1[0] + (1 - factor) * color2[0]),
            int(factor * color1[1] + (1 - factor) * color2[1]),
            int(factor * color1[2] + (1 - factor) * color2[2]),
    )


def get_color_for_order(order: UnitOrder) -> tuple[int, int, int]:
    match order.ability.id:
        case AbilityId.MOVE:
            return Color.GREEN
        case AbilityId.ATTACK:
            return Color.RED if isinstance(order.target, int) else Color.ORANGE
        case AbilityId.HARVEST_GATHER | AbilityId.HARVEST_RETURN:
            return Color.CYAN
        case _:
            return Color.DARK_GREY


class DebugItem(Protocol):
    color: tuple[int, int, int]
    created: float
    duration: float


@dataclass
class DebugLine:
    start: Point3
    end: Point3
    text_center: Optional[str]
    text_start: Optional[str]
    text_end: Optional[str]
    text_offset: int
    text_size: Optional[int]
    color: tuple[int, int, int]
    created: float
    duration: float


@dataclass
class DebugSphere:
    center: Point3
    radius: float
    color: tuple[int, int, int]
    created: float
    duration: float


@dataclass
class DebugWorldText:
    position: Point3 | Unit
    text: str
    size: int
    color: tuple[int, int, int]
    created: float
    duration: float


class DebugLayers(StrEnum):
    LOG = 'log'
    EXP = 'exp'
    EXP_DIST = 'expdist'
    COMBAT = 'combat'
    TASKS = 'tasks'
    ORDERS = 'orders'
    SQUADS = 'squads'
    EXTRA = 'extra'
    GRID = 'grid'
    PATHING = 'pathing'
    PLACEMENT = 'placement'
    BLOCKING = 'blocking'
    RESERVED = 'reserved'
    CREEP = 'creep'
    HEIGHT = 'height'


class DebugManager(BotManager):
    text_size: ClassVar[int] = 16
    # State
    map_revealed: bool
    enemy_control: bool
    # Frame data
    damage_taken: dict[Unit, float]
    # Config
    show: dict[str, bool]
    # Temporary displays
    debug_items: list[DebugItem]

    def __init__(self, bot: 'AvocaDOS') -> None:
        super().__init__(bot)
        self.damage_taken = {}
        self.shot_last_frame = set()
        self.frame_start = None
        self.map_revealed = False
        self.enemy_control = False
        self.show = {
            DebugLayers.EXTRA: True
        }
        self.debug_items = []

    @property
    def client(self) -> Client:
        return self.api.client

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

    async def on_step(self, step: int) -> None:
        t0 = perf_counter()
        await self._handle_chat()
        if self.show.get(DebugLayers.GRID):
            self._show_grid()
        if self.show.get(DebugLayers.TASKS):
            self._show_tasks()
        if self.show.get(DebugLayers.EXTRA):
            self._show_extra()
        if self.show.get(DebugLayers.ORDERS):
            self._show_orders()
        if self.show.get(DebugLayers.SQUADS):
            self._show_squads()
        if self.show.get(DebugLayers.COMBAT):
            self._show_combat()
        if self.show.get(DebugLayers.EXP):
            self._show_expansions()
        if self.show.get(DebugLayers.EXP_DIST):
            self._show_expansion_distances()
        if self.show.get(DebugLayers.PLACEMENT):
            self._draw_field(self.map.placement_grid)
        if self.show.get(DebugLayers.PATHING):
            self._draw_field(self.map.pathing_grid)
        if self.show.get(DebugLayers.BLOCKING):
            self._draw_field(self.building.blocking_grid)
        if self.show.get(DebugLayers.CREEP):
            self._draw_field(self.map.creep)
        if self.show.get(DebugLayers.RESERVED):
            self._draw_field(self.building.reserved_grid)
        if self.show.get(DebugLayers.HEIGHT):
            self._draw_field(self.map.terrain_height, with_text=True, text_format=".0f")

        #self.damage_taken.clear()

        for item in reversed(self.debug_items):
            if isinstance(item, DebugWorldText):
                self._show_text(item)
            elif isinstance(item, DebugLine):
                self._show_line(item)
            elif isinstance(item, DebugSphere):
                self._show_sphere(item)
            if self.api.time >= item.created + item.duration:
                self.debug_items.remove(item)

        #if self.bot.map is not None:
        #    #for idx, expansion in enumerate(self.bot.map.enemy_expansions):
        #    #    self.box_with_text(expansion, f"Enemy expansion {idx}")
        #    for idx, expansion in enumerate(self.bot.map.expansions):
        #        self.box_with_text(expansion[0], f"Expansion {idx}: {expansion[1]}")
        self.timings['step'].add(t0)

    # ---

    def text_screen(self,
                    lines: list[str] | str,
                    *,
                    position: tuple[float, float] = (0.005, 0.01),
                    size: int = 16, color: tuple[int, int, int] = Color.YELLOW,
                    max_lines: int = 10):
        y = position[1]
        if isinstance(lines, str):
            lines = [lines]
        for line in lines[-max_lines:]:
            self.client.debug_text_screen(line, (position[0], y), size=size, color=color)
            y += size / 1000

    def text(self,
             text: str,
             position: Unit | Point3 | Point2,
             *,
             size: Optional[int] = None,
             z_offset: float = 1.0,
             color: tuple[int, int, int] | str = Color.YELLOW,
             duration: float = 0) -> DebugWorldText:
        position = self._normalize_point3(position, z_offset=z_offset)
        color = normalize_color(color)
        item = DebugWorldText(position, text, size=size or self.text_size, color=color,
                              created=self.api.time, duration=duration)
        self.debug_items.append(item)
        return item

    def _show_text(self, item: DebugWorldText) -> None:
        self.client.debug_text_world(item.text, item.position, size=item.size, color=item.color)

    def box(self, center: Unit | Point3 | Point2, size: Optional[float] = None, *,
            z_offset: float = 1.0,
            color: ColorType = Color.YELLOW) -> None:
        center = self._normalize_point3(center, z_offset=z_offset)
        color = normalize_color(color)
        if size is None:
            if isinstance(center, Unit):
                if center.is_structure:
                    size = 2*center.footprint_radius
                else:
                    size = 2*center.radius
            else:
                size = 1
        self.client.debug_box2_out(center, half_vertex_length=size/2, color=color)

    def sphere(self, center: Unit | Point3 | Point2 | Circle, radius: Optional[float] = None, *,
               color: tuple[int, int, int] | str = Color.YELLOW,
               duration: float = 0) -> DebugSphere:
        if isinstance(center, Circle):
            radius = center.radius
            center = center.center
        elif radius is None:
            radius = 1
        center = self._normalize_point3(center)
        color = normalize_color(color)
        item = DebugSphere(center, radius, color=color, created=self.api.time, duration=duration)
        self.debug_items.append(item)
        return item

    def _show_sphere(self, item: DebugSphere) -> None:
        self.client.debug_sphere_out(item.center, item.radius, color=item.color)

    def sphere_with_text(self, center: Unit | Point3 | Point2, text: str | list[str], size: Optional[float] = None, *,
                         color: tuple[int, int, int] | str = Color.YELLOW) -> None:
        color = normalize_color(color)
        self.sphere(center, size, color=color)
        self.text(text, center, color=color)

    def box_with_text(self, center: Unit | Point3 | Point2, text: str | list[str], size: Optional[float] = None, *,
                      color: tuple[int, int, int] | str = Color.YELLOW) -> None:
        color = normalize_color(color)
        self.box(center, size, color=color)
        self.text(text, center, color=color)

    def line(self, start: Point2 | Point3 | Unit | int, end: Point2 | Point3 | Unit | int, *,
             text_center: Optional[str] = None,
             text_start: Optional[str] = None,
             text_end: Optional[str] = None,
             text_offset: int = 5,
             text_size: Optional[int] = None,
             color: tuple[int, int, int] | str = Color.YELLOW,
             duration: float = 0) -> DebugLine:
        start = self._normalize_point3(start)
        end = self._normalize_point3(end)
        color = normalize_color(color)
        item = DebugLine(start, end, text_center=text_center, text_start=text_start, text_end=text_end,
                         text_offset=text_offset, text_size=text_size, color=color, created=self.api.time,
                         duration=duration)
        self.debug_items.append(item)
        return item

    def _show_line(self, item: DebugLine) -> None:
        self.client.debug_line_out(item.start, item.end, color=item.color)
        if item.text_center:
            added = (item.start + item.end)
            mid = Point3((added.x/2, added.y/2, added.z/2))
            self.text(item.text_center, mid, color=item.color, size=item.text_size)
        if item.text_start:
            self.text(item.text_start, item.start.towards(item.end, item.text_offset), color=item.color,
                      size=item.text_size)
        if item.text_end:
            self.text(item.text_end, item.end.towards(item.start, item.text_offset), color=item.color,
                      size=item.text_size)

    def arrow(self, start: Point2 | Point3 | Unit | int, end: Point2 | Point3 | Unit | int, *,
              color: tuple[int, int, int] = Color.YELLOW) -> None:
        self.line(start, end, color=color)
        # TODO
        #self.line(end, end, color=color)

    async def _handle_chat(self):
        cheats = {'!control_enemy', '!food', '!free', '!all_resources', '!god', '!minerals', '!gas',
                  '!cooldown', '!tech_tree', '!upgrade', '!fast_build', '!show_map', '!create_unit'}
        for chat_message in self.api.state.chat:
            self.logger.debug("Chat message: {}", chat_message.message)
            if chat_message.message.startswith('!'):
                cmd, *args = chat_message.message.split()

                if cmd == '!show' and len(args) == 1 and args[0] in list(DebugLayers) :
                    self.show[args[0]] = True
                if cmd == '!hide' and len(args) == 1 and args[0] in list(DebugLayers):
                    self.show[args[0]] = False

                elif cmd == '!grid' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_grid = bool(int(args[0]))

                elif cmd == '!cmd' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_tasks = bool(int(args[0]))

                elif cmd == '!orders' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.show_orders = bool(int(args[0]))

                elif cmd == '!debug' and len(args) == 1 and args[0] in {'0', '1'}:
                    self.api.debug_enabled = bool(int(args[0]))

                elif cmd in cheats:
                    func = getattr(self.client, f'debug_{cmd[1:]}', None)
                    if func is None:
                        continue
                    try:
                        if cmd[1:] == 'create_unit':
                                func_args = ([[UnitTypeId(int(args[0])), 1,
                                               Point2((float(args[1]), float(args[2]))), int(args[3])]],)
                        else:
                            func_args = ()
                        await func(*func_args)
                    except Exception as exc:
                        self.logger.error("Exception: {}", exc)

                elif cmd == '!slow':
                    if len(args) == 0:
                        slowdown = 40
                    else:
                        try:
                            slowdown = float(args[0])
                        except ValueError:
                            continue
                    self.logger.info("Setting slowdown time to: {}", slowdown)
                    self.api.slowdown = slowdown

    def _normalize_point3(self, point: Unit | Point3 | Point2, *, z_offset: float = 1.0) -> Point3:
        if isinstance(point, Unit):
            point = point.position3d
        if isinstance(point, Point3):
            return point + Point3((0, 0, z_offset))
        if isinstance(point, Point2):
            return Point3((point[0], point[1], self.api.get_terrain_z_height(point) + z_offset))
        raise TypeError(f"invalid argument: {point}")

    def _show_tasks(self) -> None:
        lines = [repr(task) for task in self.api.bot.objectives]
        self.text_screen(lines, position=(0.005, 0.006))

    def _show_combat(self, *, show_weapon_cooldown: bool = False) -> None:
        for unit in self.api.bot.units:
            if show_weapon_cooldown and unit.weapon_cooldown != 0:
                text = f'({math.ceil(unit.weapon_cooldown)})'
                self.text(text, unit.position3d + Point3((0, 0, -0.5)), size=12, color=Color.CYAN)

            if unit.orders:
                order = unit.orders[0]
                if isinstance(order.target, int):
                    target = self.api.all_units.find_by_tag(order.target)
                else:
                    target = order.target
                if target is not None:
                    self.line(unit, target, color=get_color_for_order(order))
        # for unit, damage in self.damage_taken.items():
        #     color = Color.RED if damage > 0 else Color.GREEN
        #     self.text_world(f"[{self.api.state.game_loop}] -{damage:.2f}", unit.position3d + Point3((0, 0, 1.2)),
        #                     size=12, color=color)

    def _show_orders(self) -> None:
        for tag, orders in self.api.bot.order.orders.items():
            if not orders:
                continue
            unit = (self.api.units + self.api.structures).find_by_tag(tag)
            if unit is None:
                continue
            order = orders[0]
            self.box_with_text(unit, order.short_repr)

    def _show_squads(self, color: tuple[int, int, int] | str = Color.PINK) -> None:
        for squad in self.squads:
            if len(squad) == 0:
                continue
            radius = math.sqrt(squad.radius_squared)
            self.sphere(squad.center, radius, color=color)
            self.sphere(squad.center, squad.leash_range, color=color)
            if isinstance(squad.task, SquadAttackTask):
                task_code = 'ATK'
                self.sphere(squad.task.target, color='RED')
                self.line(squad.center, squad.task.target.center, color='RED')
            elif isinstance(squad.task, SquadDefendTask):
                task_code = 'DEF'
                self.sphere(squad.task.target, color='BLUE')
                self.line(squad.center, squad.task.target.center, color='BLUE')
            elif isinstance(squad.task, SquadJoinTask):
                task_code = 'JOI'
                self.sphere(squad.task.target.center, radius=1, color='GREEN')
                self.line(squad.center, squad.task.target.center, color='GREEN')
            elif isinstance(squad.task, SquadRetreatTask):
                task_code = 'RET'
                self.sphere(squad.task.target, color='RED')
                self.line(squad.center, squad.task.target.center, color='RED')
            else:
                task_code = 'NON'
            self.text(f"{squad.id}  {len(squad)}  {squad.status}  {squad.strength:.1f}  {task_code}"
                            f"  {squad.damage_taken_percentage:.1%}", squad.center, color=color)
            for unit in squad.units:
                #self.text_world(f"{squad.id}", unit, color=color)
                self.line(unit, squad.center, color=color)

    def _show_extra(self) -> None:
        mineral_rate, vespene_rate = self.ext.get_resource_collection_rates()
        self.text_screen(f"{mineral_rate=:.2f}, {vespene_rate=:.2f}", position=(0.78, 0.05))
        self.text_screen(f"worker target={self.objectives.worker_objective.number},"
                         f" supply target={self.objectives.supply_objective.number}", position=(0.78, 0.10))

        min_step, avg_step, max_step, last_step = self.api.step_time
        if last_step <= 10:
            color =Color.GREEN
        elif last_step <= 40:
            color = Color.YELLOW
        else:
            color = Color.RED
        self.text_screen(f"step time (ms): {last_step:.1f} (avg={avg_step:.1f}, min={min_step:.1f}"
                         f", max={max_step:.1f})", position=(0.73, 0.71), color=color)

    def _show_expansions(self) -> None:
        self.text("NAT", self.map.start_location.natural.center)
        self.text("LINE", self.map.start_location.line_third.center)
        self.text("TRIA", self.map.start_location.triangle_third.center)
        for idx, exp in enumerate(self.map.start_location.expansion_order, start=1):
            self.text(f"{idx} exp", exp.center, z_offset=2)
        for exp, time in self.intel.get_time_since_expansions_last_visible().items():
            self.text(f"{exp}, Viz: {time:.2f}", exp.center, color='CYAN', z_offset=3.0)

    def _show_expansion_distances(self) -> None:
        for idx1, exp1 in enumerate(self.map.expansions):
            for idx2, exp2 in enumerate(self.map.expansions[:idx1]):
                text = (f"d={self.map.expansion_distance_matrix[idx1, idx2]:.2f}, "
                        f"D={self.map.expansion_path_distance_matrix[idx1, idx2]:.2f}")
                self.line(exp1.center, exp2.center, text_start=text)
                text = (f"d={self.map.expansion_distance_matrix[idx2, idx1]:.2f}, "
                        f"D={self.map.expansion_path_distance_matrix[idx2, idx1]:.2f}")
                self.line(exp2.center, exp1.center, text_start=text)

    def _draw_field(self, field: Field, *,
                    colormap: tuple[ColorType, ColorType] = ('Green', 'Red'),
                    with_text: bool = False,
                    text_format: str = ".2f"
                    ) -> None:
        view_area = self._get_camera_view_area()
        if not view_area:
            return
        (x0, y0), (x1, y1) = view_area
        color0 = normalize_color(colormap[0])
        color1 = normalize_color(colormap[1])
        for x in range(int(x0), int(x1)):
            for y in range(int(y0), int(y1)):
                point = Point2((x + 0.5, y + 0.5))
                if point not in field:
                    continue
                value = field[point]
                color = mix_colors(color0, color1, value/(field.max() or 1))
                self.draw_tile(point, color=color, text=f"{value:{text_format}}" if with_text else None)

    def _draw_region(self, region: Region, *, color: ColorType = Color.YELLOW) -> None:
        for point in region:
            self.draw_tile(point, color=color)

    def _show_grid(self, *, color: ColorType = 'Blue') -> None:
        view_area = self._get_camera_view_area()
        if not view_area:
            return
        (x0, y0), (x1, y1) = view_area
        for x in range(int(x0), int(x1)):
            for y in range(int(y0), int(y1)):
                point = Point2((x + 0.5, y + 0.5))
                self.draw_tile(point, color=color)
                self.text(f"{x}, {y}", point, color=color)

    def draw_tile(self, point: Point2, *, color: ColorType = 'Yellow', size=0.95, text: Optional[str] = None) -> None:
        self.box(point, size=size, color=color, z_offset=-size/2 + 0.05)
        if text:
            self.text(text, point, color=color)

    def _get_camera_view_area(self, *,
                              #camera_size: tuple[float, float] = (34, 24)
                              camera_size: tuple[float, float] = (22, 16)
                              ) -> Optional[tuple[Point2, Point2]]:
        """Returns the approximate bounding box of the camera view."""
        camera_pos = self.api.state.observation_raw.player.camera
        if not camera_pos:
            return None

        half_width_left = camera_size[0] * -0.5
        half_width_right = camera_size[0] * 0.5
        half_height_top = camera_size[1] * 0.5 + 4
        half_height_bottom = camera_size[1] * -0.5 + 4

        # I change the order because the map start from bottom left (0, 0) to top right (max_x, max_y)
        mins = Point2((camera_pos.x + half_width_left, camera_pos.y + half_height_bottom))
        maxs = Point2((camera_pos.x + half_width_right, camera_pos.y + half_height_top))
        return mins, maxs
