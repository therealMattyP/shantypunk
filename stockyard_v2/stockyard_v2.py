from __future__ import annotations

import math
import random
from dataclasses import dataclass

import bpy
from mathutils import Vector


COLLECTION_NAME = "STOCKYARD_V2"
EPSILON = 0.006


@dataclass(frozen=True)
class TimberSpec:
    width: float
    depth: float


POST = TimberSpec(0.14, 0.14)
BEAM = TimberSpec(0.14, 0.24)
JOIST = TimberSpec(0.05, 0.20)
BOARD = TimberSpec(0.14, 0.035)
BRACE = TimberSpec(0.075, 0.10)
STRINGER = TimberSpec(0.05, 0.20)
TREAD = TimberSpec(0.26, 0.04)
LADDER_RAIL = TimberSpec(0.07, 0.07)
LADDER_RUNG = TimberSpec(0.04, 0.04)


def _ensure_collection() -> bpy.types.Collection:
    scene_collection = bpy.context.scene.collection
    collection = bpy.data.collections.get(COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(COLLECTION_NAME)
        scene_collection.children.link(collection)
    return collection


def _clear_collection(collection: bpy.types.Collection) -> None:
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _cube(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    dimensions: Vector,
    rotation: Vector | None = None,
    role: str | None = None,
    stable_id: str | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    obj.rotation_euler = rotation or Vector((0.0, 0.0, 0.0))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)

    if role:
        obj["stockyard_role"] = role
    if stable_id:
        obj["stockyard_id"] = stable_id
    return obj


def _empty_socket(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    socket_type: str,
    level: int,
    direction: str,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.22
    obj.location = location
    obj["stockyard_role"] = "attachment_socket"
    obj["socket_type"] = socket_type
    obj["stockyard_level"] = level
    obj["socket_direction"] = direction
    collection.objects.link(obj)
    return obj


def _beam_between(
    collection: bpy.types.Collection,
    name: str,
    start: Vector,
    end: Vector,
    width: float,
    depth: float,
    role: str,
    stable_id: str,
) -> bpy.types.Object:
    delta = end - start
    length = delta.length
    midpoint = (start + end) * 0.5
    angle_y = -math.atan2(delta.z, math.hypot(delta.x, delta.y))
    angle_z = math.atan2(delta.y, delta.x)
    return _cube(
        collection,
        name,
        midpoint,
        Vector((length, width, depth)),
        Vector((0.0, angle_y, angle_z)),
        role,
        stable_id,
    )


def _noise(rng: random.Random, amount: float) -> float:
    return rng.uniform(-amount, amount) if amount > 0.0 else 0.0


def _opening_contains(settings: "StockyardV2Properties", x: float, y: float) -> bool:
    if settings.circulation_type == "NONE":
        return False
    half_x = settings.opening_width * 0.5
    half_y = settings.opening_depth * 0.5
    return (
        abs(x - settings.opening_offset_x) <= half_x
        and abs(y - settings.opening_offset_y) <= half_y
    )


def _add_sockets(
    collection: bpy.types.Collection,
    settings: "StockyardV2Properties",
    level: int,
    deck_surface_z: float,
) -> None:
    half_w = settings.width * 0.5
    half_d = settings.depth * 0.5
    sockets = (
        ("N", Vector((0.0, half_d, deck_surface_z))),
        ("S", Vector((0.0, -half_d, deck_surface_z))),
        ("E", Vector((half_w, 0.0, deck_surface_z))),
        ("W", Vector((-half_w, 0.0, deck_surface_z))),
        ("NE", Vector((half_w, half_d, deck_surface_z))),
        ("NW", Vector((-half_w, half_d, deck_surface_z))),
        ("SE", Vector((half_w, -half_d, deck_surface_z))),
        ("SW", Vector((-half_w, -half_d, deck_surface_z))),
        ("CENTER", Vector((0.0, 0.0, deck_surface_z))),
    )
    for direction, location in sockets:
        _empty_socket(
            collection,
            f"SYV21_SOCKET_L{level:02d}_{direction}",
            location,
            "floor_host",
            level,
            direction,
        )


def _add_stairs(
    collection: bpy.types.Collection,
    settings: "StockyardV2Properties",
    lower_z: float,
    upper_z: float,
    level: int,
) -> None:
    rise = upper_z - lower_z
    step_count = max(3, math.ceil(rise / settings.max_riser_height))
    actual_rise = rise / step_count
    run = step_count * settings.tread_depth
    x0 = settings.opening_offset_x - run * 0.5
    x1 = settings.opening_offset_x + run * 0.5
    y_center = settings.opening_offset_y
    rail_offset = settings.stair_width * 0.5 - STRINGER.width * 0.5

    for side, y in (("L", y_center - rail_offset), ("R", y_center + rail_offset)):
        _beam_between(
            collection,
            f"SYV21_STAIR_STRINGER_L{level:02d}_{side}",
            Vector((x0, y, lower_z + actual_rise * 0.5)),
            Vector((x1, y, upper_z - actual_rise * 0.5)),
            STRINGER.width,
            STRINGER.depth,
            "stair_stringer",
            f"stair_stringer:{level}:{side}",
        )

    for step in range(step_count):
        t = (step + 0.5) / step_count
        x = x0 + run * t
        z = lower_z + actual_rise * (step + 1)
        _cube(
            collection,
            f"SYV21_STAIR_TREAD_L{level:02d}_{step:03d}",
            Vector((x, y_center, z)),
            Vector((settings.tread_depth, settings.stair_width, TREAD.depth)),
            role="stair_tread",
            stable_id=f"stair_tread:{level}:{step}",
        )


def _add_ladder(
    collection: bpy.types.Collection,
    settings: "StockyardV2Properties",
    lower_z: float,
    upper_z: float,
    level: int,
) -> None:
    x = settings.opening_offset_x
    y = settings.opening_offset_y
    rail_half = settings.ladder_width * 0.5
    height = upper_z - lower_z
    rail_z = lower_z + height * 0.5

    for side, rail_y in (("L", y - rail_half), ("R", y + rail_half)):
        _cube(
            collection,
            f"SYV21_LADDER_RAIL_L{level:02d}_{side}",
            Vector((x, rail_y, rail_z)),
            Vector((LADDER_RAIL.width, LADDER_RAIL.depth, height)),
            role="ladder_rail",
            stable_id=f"ladder_rail:{level}:{side}",
        )

    rung_count = max(2, math.floor(height / settings.ladder_rung_spacing))
    for rung in range(rung_count + 1):
        z = lower_z + height * (rung / rung_count)
        _cube(
            collection,
            f"SYV21_LADDER_RUNG_L{level:02d}_{rung:03d}",
            Vector((x, y, z)),
            Vector((LADDER_RUNG.width, settings.ladder_width, LADDER_RUNG.depth)),
            role="ladder_rung",
            stable_id=f"ladder_rung:{level}:{rung}",
        )


def generate_stockyard(settings: "StockyardV2Properties") -> None:
    collection = _ensure_collection()
    _clear_collection(collection)

    rng = random.Random(settings.seed)
    width = settings.width
    depth = settings.depth
    chaos = settings.chaos
    x_positions = [(-width * 0.5) + (width * i / settings.bays_x) for i in range(settings.bays_x + 1)]
    y_positions = [(-depth * 0.5) + (depth * i / settings.bays_y) for i in range(settings.bays_y + 1)]

    for level in range(settings.level_count):
        level_base = level * settings.story_height
        beam_top = level_base + settings.deck_height
        beam_z = beam_top - BEAM.depth * 0.5
        joist_z = beam_top + JOIST.depth * 0.5 + EPSILON
        board_z = beam_top + JOIST.depth + BOARD.depth * 0.5 + EPSILON * 2.0
        deck_surface_z = board_z + BOARD.depth * 0.5

        for ix, x in enumerate(x_positions):
            for iy, y in enumerate(y_positions):
                lean_x = math.radians(_noise(rng, settings.post_lean_deg * chaos))
                lean_y = math.radians(_noise(rng, settings.post_lean_deg * chaos))
                post_height = settings.deck_height - BEAM.depth - EPSILON
                post_z = level_base + post_height * 0.5
                _cube(
                    collection,
                    f"SYV21_POST_L{level:02d}_{ix:02d}_{iy:02d}",
                    Vector((x, y, post_z)),
                    Vector((POST.width, POST.depth, post_height)),
                    Vector((lean_x, lean_y, 0.0)),
                    "post",
                    f"post:{level}:{ix}:{iy}",
                )

        for iy, y in enumerate(y_positions):
            _cube(
                collection,
                f"SYV21_BEAM_X_L{level:02d}_{iy:02d}",
                Vector((0.0, y, beam_z)),
                Vector((width + POST.width, BEAM.width, BEAM.depth)),
                role="primary_beam",
                stable_id=f"beam:{level}:x:{iy}",
            )

        joist_count = max(2, math.floor(width / settings.joist_spacing) + 1)
        for index in range(joist_count):
            t = index / (joist_count - 1)
            x = -width * 0.5 + width * t + _noise(rng, settings.member_shift * chaos)
            _cube(
                collection,
                f"SYV21_JOIST_L{level:02d}_{index:03d}",
                Vector((x, 0.0, joist_z)),
                Vector((JOIST.width, depth + POST.width, JOIST.depth)),
                Vector((0.0, 0.0, math.radians(_noise(rng, settings.member_twist_deg * chaos)))),
                "joist",
                f"joist:{level}:{index}",
            )

        board_count = max(2, math.floor(depth / (BOARD.width + settings.board_gap)) + 1)
        for index in range(board_count):
            if chaos > 0.0 and rng.random() < settings.missing_board_chance * chaos:
                continue
            t = index / (board_count - 1)
            y = -depth * 0.5 + depth * t
            if level > 0 and _opening_contains(settings, 0.0, y):
                continue
            z = board_z + _noise(rng, settings.board_height_variation * chaos)
            _cube(
                collection,
                f"SYV21_DECK_BOARD_L{level:02d}_{index:03d}",
                Vector((_noise(rng, settings.board_end_shift * chaos), y, z)),
                Vector((width, BOARD.width, BOARD.depth)),
                Vector((0.0, 0.0, math.radians(_noise(rng, settings.board_twist_deg * chaos)))),
                "deck_board",
                f"deck_board:{level}:{index}",
            )

        if settings.add_bracing:
            brace_top = beam_z - BEAM.depth * 0.5 - settings.connection_gap
            brace_side_offset = POST.depth * 0.5 + BRACE.width * 0.5 + settings.connection_gap
            for side_y, label, sign in ((-depth * 0.5, "S", -1.0), (depth * 0.5, "N", 1.0)):
                brace_y = side_y + sign * brace_side_offset
                for bay in range(settings.bays_x):
                    x0 = x_positions[bay] + POST.width * 0.5 + settings.connection_gap
                    x1 = x_positions[bay + 1] - POST.width * 0.5 - settings.connection_gap
                    z0 = level_base + settings.brace_clearance
                    z1 = brace_top
                    _beam_between(
                        collection,
                        f"SYV21_BRACE_L{level:02d}_{label}_{bay:02d}_A",
                        Vector((x0, brace_y, z0)),
                        Vector((x1, brace_y, z1)),
                        BRACE.width,
                        BRACE.depth,
                        "brace",
                        f"brace:{level}:{label}:{bay}:a",
                    )
                    if settings.cross_bracing:
                        _beam_between(
                            collection,
                            f"SYV21_BRACE_L{level:02d}_{label}_{bay:02d}_B",
                            Vector((x0, brace_y, z1)),
                            Vector((x1, brace_y, z0)),
                            BRACE.width,
                            BRACE.depth,
                            "brace",
                            f"brace:{level}:{label}:{bay}:b",
                        )

        if settings.show_attachment_sockets:
            _add_sockets(collection, settings, level, deck_surface_z)

        if level > 0:
            lower_deck_surface = deck_surface_z - settings.story_height
            if settings.circulation_type == "STAIRS":
                _add_stairs(collection, settings, lower_deck_surface, deck_surface_z, level)
            elif settings.circulation_type == "LADDER":
                _add_ladder(collection, settings, lower_deck_surface, deck_surface_z, level)

    if settings.add_repair_boards and chaos > 0.0:
        repair_count = round(settings.repair_board_count * chaos)
        top_level_base = (settings.level_count - 1) * settings.story_height
        for index in range(repair_count):
            x = rng.uniform(-width * 0.4, width * 0.4)
            y = rng.choice((-depth * 0.5 - 0.02, depth * 0.5 + 0.02))
            z = top_level_base + rng.uniform(settings.deck_height * 0.35, settings.deck_height * 0.8)
            _cube(
                collection,
                f"SYV21_REPAIR_{index:02d}",
                Vector((x, y, z)),
                Vector((rng.uniform(0.7, 1.5), 0.025, 0.12)),
                Vector((math.radians(rng.uniform(-8, 8)), 0.0, math.radians(rng.uniform(-12, 12)))),
                "repair",
                f"repair:{index}",
            )


class StockyardV2Properties(bpy.types.PropertyGroup):
    width: bpy.props.FloatProperty(name="Width", default=6.0, min=1.0, max=50.0, unit="LENGTH")
    depth: bpy.props.FloatProperty(name="Depth", default=4.0, min=1.0, max=50.0, unit="LENGTH")
    deck_height: bpy.props.FloatProperty(name="Deck Structure Height", default=2.4, min=0.3, max=15.0, unit="LENGTH")
    level_count: bpy.props.IntProperty(name="Levels", default=2, min=1, max=12)
    story_height: bpy.props.FloatProperty(name="Story Height", default=3.0, min=1.5, max=8.0, unit="LENGTH")
    bays_x: bpy.props.IntProperty(name="Width Bays", default=3, min=1, max=24)
    bays_y: bpy.props.IntProperty(name="Depth Bays", default=2, min=1, max=24)
    joist_spacing: bpy.props.FloatProperty(name="Joist Spacing", default=0.40, min=0.20, max=1.2, unit="LENGTH")
    board_gap: bpy.props.FloatProperty(name="Board Gap", default=0.008, min=0.0, max=0.08, unit="LENGTH")
    connection_gap: bpy.props.FloatProperty(name="Connection Gap", default=0.006, min=0.001, max=0.05, unit="LENGTH")

    circulation_type: bpy.props.EnumProperty(
        name="Circulation",
        items=(("NONE", "None", "No vertical circulation"), ("STAIRS", "Straight Stairs", "Straight stair between levels"), ("LADDER", "Ladder", "Vertical ladder between levels")),
        default="STAIRS",
    )
    opening_width: bpy.props.FloatProperty(name="Opening Width", default=1.2, min=0.5, max=4.0, unit="LENGTH")
    opening_depth: bpy.props.FloatProperty(name="Opening Depth", default=2.4, min=0.5, max=8.0, unit="LENGTH")
    opening_offset_x: bpy.props.FloatProperty(name="Opening X", default=0.0, min=-20.0, max=20.0, unit="LENGTH")
    opening_offset_y: bpy.props.FloatProperty(name="Opening Y", default=0.0, min=-20.0, max=20.0, unit="LENGTH")
    stair_width: bpy.props.FloatProperty(name="Stair Width", default=1.0, min=0.6, max=3.0, unit="LENGTH")
    tread_depth: bpy.props.FloatProperty(name="Tread Depth", default=0.27, min=0.18, max=0.5, unit="LENGTH")
    max_riser_height: bpy.props.FloatProperty(name="Max Riser", default=0.19, min=0.10, max=0.30, unit="LENGTH")
    ladder_width: bpy.props.FloatProperty(name="Ladder Width", default=0.55, min=0.35, max=1.2, unit="LENGTH")
    ladder_rung_spacing: bpy.props.FloatProperty(name="Rung Spacing", default=0.30, min=0.20, max=0.50, unit="LENGTH")
    show_attachment_sockets: bpy.props.BoolProperty(name="Attachment Sockets", default=True)

    seed: bpy.props.IntProperty(name="Seed", default=1, min=0)
    chaos: bpy.props.FloatProperty(name="Chaos", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    post_lean_deg: bpy.props.FloatProperty(name="Post Lean", default=2.0, min=0.0, max=15.0)
    member_shift: bpy.props.FloatProperty(name="Member Shift", default=0.035, min=0.0, max=0.5, unit="LENGTH")
    member_twist_deg: bpy.props.FloatProperty(name="Joist Twist", default=1.5, min=0.0, max=15.0)
    board_twist_deg: bpy.props.FloatProperty(name="Board Twist", default=1.5, min=0.0, max=15.0)
    board_end_shift: bpy.props.FloatProperty(name="Board End Shift", default=0.06, min=0.0, max=0.5, unit="LENGTH")
    board_height_variation: bpy.props.FloatProperty(name="Board Height Variation", default=0.015, min=0.0, max=0.2, unit="LENGTH")
    missing_board_chance: bpy.props.FloatProperty(name="Missing Board Chance", default=0.08, min=0.0, max=0.8, subtype="FACTOR")

    add_bracing: bpy.props.BoolProperty(name="Add Bracing", default=True)
    cross_bracing: bpy.props.BoolProperty(name="Cross Bracing", default=False)
    brace_clearance: bpy.props.FloatProperty(name="Brace Ground Clearance", default=0.25, min=0.0, max=3.0, unit="LENGTH")
    add_repair_boards: bpy.props.BoolProperty(name="Repair Boards", default=True)
    repair_board_count: bpy.props.IntProperty(name="Max Repair Boards", default=5, min=0, max=50)


class STOCKYARD_OT_generate_v2(bpy.types.Operator):
    bl_idname = "stockyard.generate_v2"
    bl_label = "Generate Stockyard v2.1"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        generate_stockyard(context.scene.stockyard_v2)
        return {"FINISHED"}


class STOCKYARD_PT_v2(bpy.types.Panel):
    bl_label = "Stockyard v2.1"
    bl_idname = "STOCKYARD_PT_v2"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Shantypunk"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.stockyard_v2

        structure = layout.box()
        structure.label(text="Multistory Structure")
        for prop in ("width", "depth", "deck_height", "level_count", "story_height", "bays_x", "bays_y", "joist_spacing", "board_gap", "connection_gap"):
            structure.prop(settings, prop)

        circulation = layout.box()
        circulation.label(text="Circulation")
        for prop in ("circulation_type", "opening_width", "opening_depth", "opening_offset_x", "opening_offset_y", "show_attachment_sockets"):
            circulation.prop(settings, prop)
        if settings.circulation_type == "STAIRS":
            for prop in ("stair_width", "tread_depth", "max_riser_height"):
                circulation.prop(settings, prop)
        elif settings.circulation_type == "LADDER":
            for prop in ("ladder_width", "ladder_rung_spacing"):
                circulation.prop(settings, prop)

        bracing = layout.box()
        bracing.label(text="Bracing")
        bracing.prop(settings, "add_bracing")
        bracing.prop(settings, "cross_bracing")
        bracing.prop(settings, "brace_clearance")

        imperfection = layout.box()
        imperfection.label(text="Explicit Chaos")
        for prop in ("seed", "chaos", "post_lean_deg", "member_shift", "member_twist_deg", "board_twist_deg", "board_end_shift", "board_height_variation", "missing_board_chance", "add_repair_boards", "repair_board_count"):
            imperfection.prop(settings, prop)

        layout.operator("stockyard.generate_v2", icon="MOD_BUILD")


CLASSES = (
    StockyardV2Properties,
    STOCKYARD_OT_generate_v2,
    STOCKYARD_PT_v2,
)
