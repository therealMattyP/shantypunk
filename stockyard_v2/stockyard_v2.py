from __future__ import annotations

import math
import random
from dataclasses import dataclass

import bpy
from mathutils import Vector


COLLECTION_NAME = "STOCKYARD_V2"


@dataclass(frozen=True)
class TimberSpec:
    width: float
    depth: float


POST = TimberSpec(0.14, 0.14)
BEAM = TimberSpec(0.14, 0.24)
JOIST = TimberSpec(0.05, 0.20)
BOARD = TimberSpec(0.14, 0.035)
BRACE = TimberSpec(0.075, 0.10)


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
    return obj


def _beam_between(
    collection: bpy.types.Collection,
    name: str,
    start: Vector,
    end: Vector,
    width: float,
    depth: float,
) -> bpy.types.Object:
    delta = end - start
    length = delta.length
    midpoint = (start + end) * 0.5
    angle = math.atan2(delta.y, delta.x)
    return _cube(
        collection,
        name,
        midpoint,
        Vector((length, width, depth)),
        Vector((0.0, 0.0, angle)),
    )


def _noise(rng: random.Random, amount: float) -> float:
    return rng.uniform(-amount, amount) if amount > 0.0 else 0.0


def generate_stockyard(settings: "StockyardV2Properties") -> None:
    collection = _ensure_collection()
    _clear_collection(collection)

    rng = random.Random(settings.seed)
    width = settings.width
    depth = settings.depth
    deck_z = settings.deck_height
    chaos = settings.chaos

    x_positions = [(-width * 0.5) + (width * i / settings.bays_x) for i in range(settings.bays_x + 1)]
    y_positions = [(-depth * 0.5) + (depth * i / settings.bays_y) for i in range(settings.bays_y + 1)]

    # Structural posts: deterministic and square at chaos=0.
    for ix, x in enumerate(x_positions):
        for iy, y in enumerate(y_positions):
            lean_x = math.radians(_noise(rng, settings.post_lean_deg * chaos))
            lean_y = math.radians(_noise(rng, settings.post_lean_deg * chaos))
            z = deck_z * 0.5
            obj = _cube(
                collection,
                f"SYV2_POST_{ix:02d}_{iy:02d}",
                Vector((x, y, z)),
                Vector((POST.width, POST.depth, deck_z)),
                Vector((lean_x, lean_y, 0.0)),
            )
            obj["stockyard_role"] = "post"
            obj["stockyard_id"] = f"post:{ix}:{iy}"

    beam_z = deck_z - (BEAM.depth * 0.5)
    for iy, y in enumerate(y_positions):
        _cube(
            collection,
            f"SYV2_BEAM_X_{iy:02d}",
            Vector((0.0, y, beam_z)),
            Vector((width + POST.width, BEAM.width, BEAM.depth)),
        )["stockyard_role"] = "primary_beam"

    joist_count = max(2, math.floor(width / settings.joist_spacing) + 1)
    joist_z = deck_z + JOIST.depth * 0.5
    for index in range(joist_count):
        t = index / (joist_count - 1)
        x = -width * 0.5 + width * t
        x += _noise(rng, settings.member_shift * chaos)
        _cube(
            collection,
            f"SYV2_JOIST_{index:03d}",
            Vector((x, 0.0, joist_z)),
            Vector((JOIST.width, depth + POST.width, JOIST.depth)),
            Vector((0.0, 0.0, math.radians(_noise(rng, settings.member_twist_deg * chaos)))),
        )["stockyard_role"] = "joist"

    board_count = max(2, math.floor(depth / (BOARD.width + settings.board_gap)) + 1)
    board_z = deck_z + JOIST.depth + BOARD.depth * 0.5
    for index in range(board_count):
        if chaos > 0.0 and rng.random() < settings.missing_board_chance * chaos:
            continue

        t = index / (board_count - 1)
        y = -depth * 0.5 + depth * t
        z = board_z + _noise(rng, settings.board_height_variation * chaos)
        rotation_z = math.radians(_noise(rng, settings.board_twist_deg * chaos))
        board = _cube(
            collection,
            f"SYV2_DECK_BOARD_{index:03d}",
            Vector((_noise(rng, settings.board_end_shift * chaos), y, z)),
            Vector((width, BOARD.width, BOARD.depth)),
            Vector((0.0, 0.0, rotation_z)),
        )
        board["stockyard_role"] = "deck_board"
        board["stockyard_id"] = f"deck_board:{index}"

    # Perimeter and X braces provide an immediately readable, plausible structure.
    if settings.add_bracing:
        brace_top = deck_z - BEAM.depth
        for side_y, label in ((-depth * 0.5, "S"), (depth * 0.5, "N")):
            for bay in range(settings.bays_x):
                x0 = x_positions[bay]
                x1 = x_positions[bay + 1]
                z0 = settings.brace_clearance
                z1 = brace_top
                _beam_between(
                    collection,
                    f"SYV2_BRACE_{label}_{bay:02d}_A",
                    Vector((x0, side_y, z0)),
                    Vector((x1, side_y, z1)),
                    BRACE.width,
                    BRACE.depth,
                )["stockyard_role"] = "brace"
                if settings.cross_bracing:
                    _beam_between(
                        collection,
                        f"SYV2_BRACE_{label}_{bay:02d}_B",
                        Vector((x0, side_y, z1)),
                        Vector((x1, side_y, z0)),
                        BRACE.width,
                        BRACE.depth,
                    )["stockyard_role"] = "brace"

    if settings.add_repair_boards and chaos > 0.0:
        repair_count = round(settings.repair_board_count * chaos)
        for index in range(repair_count):
            x = rng.uniform(-width * 0.4, width * 0.4)
            y = rng.choice((-depth * 0.5 - 0.02, depth * 0.5 + 0.02))
            z = rng.uniform(deck_z * 0.35, deck_z * 0.8)
            repair = _cube(
                collection,
                f"SYV2_REPAIR_{index:02d}",
                Vector((x, y, z)),
                Vector((rng.uniform(0.7, 1.5), 0.025, 0.12)),
                Vector((math.radians(rng.uniform(-8, 8)), 0.0, math.radians(rng.uniform(-12, 12)))),
            )
            repair["stockyard_role"] = "repair"


class StockyardV2Properties(bpy.types.PropertyGroup):
    width: bpy.props.FloatProperty(name="Width", default=6.0, min=1.0, max=50.0, unit="LENGTH")
    depth: bpy.props.FloatProperty(name="Depth", default=4.0, min=1.0, max=50.0, unit="LENGTH")
    deck_height: bpy.props.FloatProperty(name="Deck Height", default=2.4, min=0.3, max=15.0, unit="LENGTH")
    bays_x: bpy.props.IntProperty(name="Width Bays", default=3, min=1, max=24)
    bays_y: bpy.props.IntProperty(name="Depth Bays", default=2, min=1, max=24)
    joist_spacing: bpy.props.FloatProperty(name="Joist Spacing", default=0.40, min=0.20, max=1.2, unit="LENGTH")
    board_gap: bpy.props.FloatProperty(name="Board Gap", default=0.008, min=0.0, max=0.08, unit="LENGTH")

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
    bl_label = "Generate Stockyard v2"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        generate_stockyard(context.scene.stockyard_v2)
        return {"FINISHED"}


class STOCKYARD_PT_v2(bpy.types.Panel):
    bl_label = "Stockyard v2"
    bl_idname = "STOCKYARD_PT_v2"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Shantypunk"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.stockyard_v2

        structure = layout.box()
        structure.label(text="Structure")
        structure.prop(settings, "width")
        structure.prop(settings, "depth")
        structure.prop(settings, "deck_height")
        structure.prop(settings, "bays_x")
        structure.prop(settings, "bays_y")
        structure.prop(settings, "joist_spacing")
        structure.prop(settings, "board_gap")

        bracing = layout.box()
        bracing.label(text="Bracing")
        bracing.prop(settings, "add_bracing")
        bracing.prop(settings, "cross_bracing")
        bracing.prop(settings, "brace_clearance")

        imperfection = layout.box()
        imperfection.label(text="Explicit Chaos")
        imperfection.prop(settings, "seed")
        imperfection.prop(settings, "chaos")
        imperfection.prop(settings, "post_lean_deg")
        imperfection.prop(settings, "member_shift")
        imperfection.prop(settings, "member_twist_deg")
        imperfection.prop(settings, "board_twist_deg")
        imperfection.prop(settings, "board_end_shift")
        imperfection.prop(settings, "board_height_variation")
        imperfection.prop(settings, "missing_board_chance")
        imperfection.prop(settings, "add_repair_boards")
        imperfection.prop(settings, "repair_board_count")

        layout.operator("stockyard.generate_v2", icon="MOD_BUILD")


CLASSES = (
    StockyardV2Properties,
    STOCKYARD_OT_generate_v2,
    STOCKYARD_PT_v2,
)
