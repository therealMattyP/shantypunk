"""
SHANTYPUNK MODULAR STOCKYARD GENERATOR v1.9
======================================

Creates an expansion-ready stock, assembly, opening-proxy, and site-structure library for Blender and Unreal.
The objects are modeled at real-world size, use applied scale, receive useful
construction pivots, descriptive names, material families, metadata, and are
laid out in a compact, dimension-aware visible stockyard.

EXPORT WORKFLOW
---------------
Every asset's geometry is authored relative to its useful pivot. The script moves
objects into the stockyard using Object Location only. To prepare an asset for
export, select it and set Location to 0,0,0 (Alt-G). Rotation and Scale remain
clean unless the asset itself requires a designed orientation.

Designed for Blender 4.x / 5.x using stable bpy APIs.
UV generation is intentionally deferred. Version 1.9 adds reusable midground
opening, storefront, dock, retaining, foundation, flashing, and trim assets for
building and settlement generators.

Run:
1. Open Blender's Scripting workspace.
2. Create a new Text block.
3. Paste this script.
4. Press Run Script.

The script deletes and recreates only the collection named:
    SHANTYPUNK_STOCKYARD
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix
from pathlib import Path

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

ROOT_COLLECTION = "SHANTYPUNK_STOCKYARD"
ASSET_PREFIX = "SPK"
INCH = 0.0254
FOOT = 0.3048

# Stockyard placement.
# Assets are packed by their actual footprint instead of occupying a fixed grid.
STOCKYARD_MAX_ROW_WIDTH = 27.0
ASSET_PADDING_X = 0.55
ASSET_PADDING_Y = 0.65
MIN_FOOTPRINT_X = 0.70
MIN_FOOTPRINT_Y = 1.00
CATEGORY_GAP = 1.15
LABEL_GAP = 0.70
AISLE_HEADER_WIDTH = 2.8
AISLE_STRIP_DEPTH = 0.45
HERO_SHELF_GAP = 2.0
PREVIEW_GROUND_CLEARANCE = 0.035

# Metadata target only. UVs are not generated in this version.
TEXEL_DENSITY_PX_PER_M = 1024
TEXTURE_TARGET = "4K"

# Global modeling detail.
DEFAULT_BEVEL = 0.006
BEVEL_SEGMENTS = 2

# -----------------------------------------------------------------------------
# MATERIAL PALETTE
# -----------------------------------------------------------------------------

MATERIAL_SPECS = {
    "MAT_WOOD_STRUCTURAL":       (0.32, 0.15, 0.055, 1.0),
    "MAT_WOOD_SALVAGED":         (0.20, 0.085, 0.025, 1.0),
    "MAT_WOOD_TREATED":          (0.09, 0.055, 0.025, 1.0),
    "MAT_PLYWOOD_SHEET":         (0.47, 0.28, 0.095, 1.0),
    "MAT_LATH_PLASTER":          (0.72, 0.61, 0.46, 1.0),
    "MAT_METAL_GALVANIZED":      (0.42, 0.47, 0.50, 1.0),
    "MAT_METAL_PAINTED":         (0.12, 0.27, 0.34, 1.0),
    "MAT_METAL_RUST":            (0.33, 0.075, 0.025, 1.0),
    "MAT_STEEL_STRUCTURAL":      (0.10, 0.12, 0.14, 1.0),
    "MAT_STEEL_DIAMOND_PLATE":   (0.20, 0.23, 0.25, 1.0),
    "MAT_CONCRETE":              (0.34, 0.34, 0.32, 1.0),
    "MAT_CMU":                   (0.42, 0.42, 0.39, 1.0),
    "MAT_BRICK":                 (0.43, 0.12, 0.055, 1.0),
    "MAT_PLASTIC":               (0.055, 0.19, 0.24, 1.0),
    "MAT_CLOTH_CANVAS":          (0.22, 0.25, 0.17, 1.0),
    "MAT_CLOTH_TARP":            (0.03, 0.17, 0.26, 1.0),
    "MAT_GLASS":                 (0.12, 0.28, 0.34, 0.45),
    "MAT_RUBBER":                (0.018, 0.018, 0.018, 1.0),
    "MAT_LIGHT_WARM":            (1.0, 0.35, 0.06, 1.0),
    "MAT_LIGHT_COOL":            (0.22, 0.65, 1.0, 1.0),
    "MAT_PIPE_PVC":              (0.78, 0.78, 0.74, 1.0),
    "MAT_SIGNAGE":               (0.68, 0.18, 0.04, 1.0),
}

# -----------------------------------------------------------------------------
# SCENE / COLLECTION HELPERS
# -----------------------------------------------------------------------------

def remove_collection_recursive(name: str) -> None:
    coll = bpy.data.collections.get(name)
    if not coll:
        return
    for child in list(coll.children):
        remove_collection_recursive(child.name)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(coll)


def ensure_collection(name: str, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    target_parent = parent or bpy.context.scene.collection
    if coll.name not in [c.name for c in target_parent.children]:
        target_parent.children.link(coll)
    return coll


def unlink_from_all_collections(obj):
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)


def move_to_collection(obj, coll):
    unlink_from_all_collections(obj)
    coll.objects.link(obj)


def create_materials():
    mats = {}
    for name, rgba in MATERIAL_SPECS.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.diffuse_color = rgba
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = 0.64
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = rgba[3]
            if name.startswith("MAT_METAL") or name.startswith("MAT_STEEL"):
                bsdf.inputs["Metallic"].default_value = 0.72
            if name.startswith("MAT_LIGHT"):
                bsdf.inputs["Emission Color"].default_value = rgba
                bsdf.inputs["Emission Strength"].default_value = 3.0
        if rgba[3] < 1.0:
            mat.surface_render_method = 'DITHERED'
        mats[name] = mat
    return mats


def assign_material(obj, material, slot=0):
    if not hasattr(obj.data, "materials"):
        return
    while len(obj.data.materials) <= slot:
        obj.data.materials.append(material)
    obj.data.materials[slot] = material


def add_metadata(obj, asset_type, category, material_family, cuttable=False,
                 joinable=False, notes="", front_back=False):
    obj["spk_asset_id"] = obj.name
    obj["spk_asset_type"] = asset_type
    obj["spk_category"] = category
    obj["spk_material_family"] = material_family
    obj["spk_cuttable"] = bool(cuttable)
    obj["spk_joinable"] = bool(joinable)
    obj["spk_front_back_shader_ready"] = bool(front_back)
    obj["spk_texel_density_px_per_m"] = TEXEL_DENSITY_PX_PER_M
    obj["spk_texture_target"] = TEXTURE_TARGET
    obj["spk_origin_usage"] = "Construction/export pivot"
    obj["spk_notes"] = notes


def apply_scale(obj):
    view_layer = bpy.context.view_layer
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def apply_rotation(obj):
    view_layer = bpy.context.view_layer
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)


def shade_smooth_by_angle(obj, angle=math.radians(40)):
    if obj.type != 'MESH':
        return
    for poly in obj.data.polygons:
        poly.use_smooth = False
    # Bevels carry the readable edge detail; avoid fragile version-specific autosmooth calls.


def add_bevel(obj, width=DEFAULT_BEVEL, segments=BEVEL_SEGMENTS):
    if obj.type != 'MESH' or width <= 0:
        return
    mod = obj.modifiers.new("SPK_Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'


def finalize(obj, name, collection, material, asset_type, category,
             cuttable=False, joinable=False, notes="", bevel=DEFAULT_BEVEL,
             front_back=False):
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_MESH"
    move_to_collection(obj, collection)
    apply_scale(obj)
    assign_material(obj, material)
    add_bevel(obj, bevel)
    shade_smooth_by_angle(obj)
    add_metadata(
        obj, asset_type, category, material.name,
        cuttable=cuttable, joinable=joinable,
        notes=notes, front_back=front_back
    )
    return obj


# -----------------------------------------------------------------------------
# PRIMITIVE BUILDERS — GEOMETRY IS CREATED AROUND USEFUL PIVOTS
# -----------------------------------------------------------------------------

def cube_from_bounds(name, min_xyz, max_xyz, collection, material,
                     asset_type, category, **kwargs):
    """
    Create a cube whose LOCAL mesh bounds exactly match min_xyz / max_xyz.

    Critical pivot rule:
    - Object Location remains 0,0,0.
    - Mesh data is translated TO the requested local-space center.
    - No preview or world-space location is baked into the mesh.

    Previous versions translated by -obj.location after creating the primitive
    at the requested center. That inverted endpoint and bottom pivots, producing
    meshes from -X..0 or -Z..0 while metadata claimed +X / +Z.
    """
    min_v = Vector(min_xyz)
    max_v = Vector(max_xyz)
    dims = max_v - min_v
    center = (min_v + max_v) * 0.5

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    obj = bpy.context.object
    obj.dimensions = dims
    apply_scale(obj)

    # Move mesh data into the requested LOCAL bounds.
    obj.data.transform(Matrix.Translation(center))
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)

    result = finalize(
        obj, name, collection, material,
        asset_type, category, **kwargs
    )
    result["spk_axis_standard"] = "+X width; +Y depth; +Z height"
    return result


def box_bottom_center(name, width, depth, height, collection, material,
                      asset_type, category, **kwargs):
    return cube_from_bounds(
        name,
        (-width/2, -depth/2, 0),
        ( width/2,  depth/2, height),
        collection, material, asset_type, category, **kwargs
    )


def box_end_center_x(name, length, width, height, collection, material,
                     asset_type, category, **kwargs):
    # Long axis +X. Pivot at center of one cut end.
    result = cube_from_bounds(
        name,
        (0, -width/2, -height/2),
        (length, width/2, height/2),
        collection, material, asset_type, category, **kwargs
    )
    result["spk_axis_standard"] = "+X length; endpoint pivot"
    return result


def box_end_center_z(name, width, depth, height, collection, material,
                     asset_type, category, **kwargs):
    # Long axis +Z. Pivot at bottom center.
    return box_bottom_center(
        name, width, depth, height, collection, material,
        asset_type, category, **kwargs
    )


def cylinder_bottom(name, radius, height, vertices, collection, material,
                    asset_type, category, taper=1.0, bevel=DEFAULT_BEVEL, **kwargs):
    """
    Create a cylinder/cone with LOCAL bounds starting at Z=0.

    Object origin is the true bottom-center construction pivot.
    """
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius,
        radius2=radius * taper,
        depth=height,
        location=(0, 0, 0)
    )
    obj = bpy.context.object

    # Primitive cone is centered around local Z=0; lift mesh by half height.
    obj.data.transform(Matrix.Translation((0, 0, height * 0.5)))
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)

    result = finalize(
        obj, name, collection, material,
        asset_type, category,
        bevel=bevel, **kwargs
    )
    result["spk_axis_standard"] = "+Z height; bottom-center pivot"
    return result


def plane_vertical(name, width, height, collection, material,
                   asset_type, category, subdivisions_x=1, subdivisions_z=1,
                   y=0.0, **kwargs):
    # Plane lies in XZ; pivot bottom-center.
    verts = []
    faces = []
    for iz in range(subdivisions_z + 1):
        z = height * iz / subdivisions_z
        for ix in range(subdivisions_x + 1):
            x = -width/2 + width * ix / subdivisions_x
            verts.append((x, y, z))
    row = subdivisions_x + 1
    for iz in range(subdivisions_z):
        for ix in range(subdivisions_x):
            a = iz * row + ix
            faces.append((a, a+1, a+1+row, a+row))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return finalize(
        obj, name, collection, material, asset_type, category,
        bevel=0.0, **kwargs
    )


def corrugated_sheet(name, width, height, depth, pitch, collection, material,
                     category="SHEET_METAL", ribs_direction="VERTICAL",
                     front_back=True, **kwargs):
    # Geometric corrugation with actual faces; pivot at bottom center.
    # Local Y is sheet depth, local Z is height.
    samples = max(8, int(width / pitch * 8))
    verts = []
    faces = []
    if ribs_direction == "VERTICAL":
        for z in (0.0, height):
            for i in range(samples + 1):
                x = -width/2 + width * i / samples
                phase = 2 * math.pi * (x + width/2) / pitch
                y = math.sin(phase) * depth
                verts.append((x, y, z))
        row = samples + 1
        for i in range(samples):
            faces.append((i, i+1, i+1+row, i+row))
    else:
        samples = max(8, int(height / pitch * 8))
        for x in (-width/2, width/2):
            for i in range(samples + 1):
                z = height * i / samples
                phase = 2 * math.pi * z / pitch
                y = math.sin(phase) * depth
                verts.append((x, y, z))
        row = samples + 1
        for i in range(samples):
            faces.append((i, row+i, row+i+1, i+1))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    solid = obj.modifiers.new("SPK_SheetThickness", 'SOLIDIFY')
    solid.thickness = 0.0015
    solid.offset = 0.0
    return finalize(
        obj, name, collection, material, "CORRUGATED_SHEET", category,
        bevel=0.0, front_back=front_back, **kwargs
    )



def orient_vertical_sheet_as_flat_roof(obj):
    """
    Convert an XZ-authored vertical sheet into an XY roof/deck sheet.
    Keeps a useful edge-center pivot and applies rotation.
    """
    obj.rotation_euler.x = math.radians(90)
    apply_rotation(obj)

    # Put the lowest Z at zero after orientation.
    zs = [v.co.z for v in obj.data.vertices]
    obj.data.transform(Matrix.Translation((0, 0, -min(zs))))
    obj.location = (0, 0, 0)
    obj["spk_axis_standard"] = "+X width; +Y run; edge-center pivot"
    return obj


def pipe_segment(name, radius, length, collection, material,
                 category="UTILITIES", vertices=16, **kwargs):
    """
    Pipe standard:
        +X = length
        origin = one endpoint center
        rotation = 0
        scale = 1
    """
    obj = cylinder_bottom(
        name, radius, length, vertices, collection, material,
        "PIPE_SEGMENT", category, taper=1.0, bevel=0.0015, **kwargs
    )
    obj.rotation_euler.y = math.radians(90)
    apply_rotation(obj)

    # After rotation, translate mesh so its minimum X is exactly zero.
    xs = [v.co.x for v in obj.data.vertices]
    obj.data.transform(Matrix.Translation((-min(xs), 0, 0)))
    obj.location = (0, 0, 0)
    obj["spk_axis_standard"] = "+X length; endpoint pivot"
    return obj


def torus_object(name, major_radius, minor_radius, collection, material,
                 asset_type, category, **kwargs):
    """
    Create a torus centered on the object's local origin.

    No hidden Z offset is baked into the mesh. Callers place the ring using
    object.location.z equal to the desired ring-center height.

    This avoids the previous double-offset bug that caused barrel hoops,
    tank ribs, tire rings, and grilles to float above their parent assets.
    """
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=24,
        minor_segments=8,
        location=(0, 0, 0)
    )
    obj = bpy.context.object

    # Bake any primitive rotation/scale while keeping the local origin centered.
    apply_scale(obj)
    obj.location = (0, 0, 0)

    result = finalize(
        obj, name, collection, material,
        asset_type, category, **kwargs
    )
    result["spk_axis_standard"] = "Torus centered on local origin"
    return result


def create_text_label(text, location, collection, size=0.45, upright=True):
    curve = bpy.data.curves.new(f"LABEL_{text}", 'FONT')
    curve.body = text
    curve.align_x = 'LEFT'
    curve.align_y = 'BOTTOM'
    curve.size = size
    curve.extrude = 0.008
    obj = bpy.data.objects.new(f"LABEL_{text}", curve)
    collection.objects.link(obj)
    obj.location = location
    if upright:
        obj.rotation_euler = (math.radians(90), 0, 0)
    return obj



# -----------------------------------------------------------------------------
# DIRECT MESH CONSTRUCTION HELPERS
# -----------------------------------------------------------------------------

def append_box_geometry(verts, faces, min_xyz, max_xyz):
    """Append an axis-aligned box to shared vertex/face buffers."""
    x0, y0, z0 = min_xyz
    x1, y1, z1 = max_xyz
    base = len(verts)
    verts.extend([
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ])
    faces.extend([
        (base+0, base+1, base+2, base+3),
        (base+4, base+7, base+6, base+5),
        (base+0, base+4, base+5, base+1),
        (base+1, base+5, base+6, base+2),
        (base+2, base+6, base+7, base+3),
        (base+4, base+0, base+3, base+7),
    ])


def append_oriented_box_between(verts, faces, p0, p1, width, depth):
    """
    Append a rectangular prism running from p0 to p1.

    Local long axis is built between the points. Width/depth are perpendicular
    dimensions. Used for stair stringers and diagonal structural members.
    """
    p0 = Vector(p0)
    p1 = Vector(p1)
    direction = p1 - p0
    length = direction.length
    if length < 1e-8:
        return

    # Build a local cube from x=0..length, centered around local Y/Z.
    local_verts = [
        Vector((0, -width/2, -depth/2)),
        Vector((length, -width/2, -depth/2)),
        Vector((length, width/2, -depth/2)),
        Vector((0, width/2, -depth/2)),
        Vector((0, -width/2, depth/2)),
        Vector((length, -width/2, depth/2)),
        Vector((length, width/2, depth/2)),
        Vector((0, width/2, depth/2)),
    ]

    rot = direction.to_track_quat('X', 'Z').to_matrix()
    base = len(verts)
    for v in local_verts:
        verts.append(tuple(p0 + rot @ v))

    faces.extend([
        (base+0, base+1, base+2, base+3),
        (base+4, base+7, base+6, base+5),
        (base+0, base+4, base+5, base+1),
        (base+1, base+5, base+6, base+2),
        (base+2, base+6, base+7, base+3),
        (base+4, base+0, base+3, base+7),
    ])


def mesh_object_from_buffers(name, verts, faces, collection):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    return obj


# -----------------------------------------------------------------------------
# COMPOUND ASSET HELPERS
# -----------------------------------------------------------------------------

def join_objects(objects, name, collection):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    move_to_collection(result, collection)
    return result



def make_i_beam(name, length, flange_w, overall_h, flange_t, web_t,
                collection, material):
    """I-beam, long axis +X, endpoint pivot."""
    parts = [
        cube_from_bounds(
            f"{name}_TOP_TMP",
            (0, -flange_w/2, overall_h/2 - flange_t),
            (length, flange_w/2, overall_h/2),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_BOTTOM_TMP",
            (0, -flange_w/2, -overall_h/2),
            (length, flange_w/2, -overall_h/2 + flange_t),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_WEB_TMP",
            (0, -web_t/2, -overall_h/2 + flange_t),
            (length, web_t/2, overall_h/2 - flange_t),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
    ]
    obj = join_objects(parts, name, collection)
    obj.location = (0, 0, 0)
    return finalize(
        obj, name, collection, material,
        "STEEL_I_BEAM", "INDUSTRIAL",
        cuttable=True, joinable=True, bevel=0.0025,
        notes="Compound I-beam; +X length; endpoint pivot."
    )


def make_channel(name, length, width, height, thickness, collection, material):
    """C-channel, long axis +X, endpoint pivot."""
    parts = [
        cube_from_bounds(
            f"{name}_WEB_TMP",
            (0, -width/2, -height/2),
            (length, -width/2 + thickness, height/2),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_TOP_TMP",
            (0, -width/2, height/2 - thickness),
            (length, width/2, height/2),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_BOTTOM_TMP",
            (0, -width/2, -height/2),
            (length, width/2, -height/2 + thickness),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
    ]
    obj = join_objects(parts, name, collection)
    obj.location = (0, 0, 0)
    return finalize(
        obj, name, collection, material,
        "STEEL_CHANNEL", "INDUSTRIAL",
        cuttable=True, joinable=True, bevel=0.002,
        notes="Compound C-channel; +X length; endpoint pivot."
    )


def make_angle_iron(name, length, leg_a, leg_b, thickness, collection, material):
    """L-angle, long axis +X, endpoint pivot."""
    parts = [
        cube_from_bounds(
            f"{name}_LEG_A_TMP",
            (0, 0, 0),
            (length, leg_a, thickness),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_LEG_B_TMP",
            (0, 0, 0),
            (length, thickness, leg_b),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
    ]
    obj = join_objects(parts, name, collection)
    obj.location = (0, 0, 0)
    return finalize(
        obj, name, collection, material,
        "STEEL_ANGLE", "INDUSTRIAL",
        cuttable=True, joinable=True, bevel=0.0015,
        notes="Compound angle iron; +X length; endpoint corner pivot."
    )


def make_square_tube(name, length, outer, wall, collection, material):
    """Readable square hollow section, +X length."""
    parts = [
        cube_from_bounds(
            f"{name}_TOP_TMP",
            (0, -outer/2, outer/2-wall),
            (length, outer/2, outer/2),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_BOTTOM_TMP",
            (0, -outer/2, -outer/2),
            (length, outer/2, -outer/2+wall),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_SIDE_A_TMP",
            (0, -outer/2, -outer/2+wall),
            (length, -outer/2+wall, outer/2-wall),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
        cube_from_bounds(
            f"{name}_SIDE_B_TMP",
            (0, outer/2-wall, -outer/2+wall),
            (length, outer/2, outer/2-wall),
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0
        ),
    ]
    obj = join_objects(parts, name, collection)
    obj.location = (0, 0, 0)
    return finalize(
        obj, name, collection, material,
        "STEEL_SQUARE_TUBE", "INDUSTRIAL",
        cuttable=True, joinable=True, bevel=0.0015,
        notes="Square hollow section; +X length; endpoint pivot."
    )


def make_pipe_column(name, radius, height, collection, material):
    obj = cylinder_bottom(
        name, radius, height, 20,
        collection, material,
        "STEEL_PIPE_COLUMN", "INDUSTRIAL",
        bevel=0.002,
        cuttable=True,
        joinable=True,
        notes="Vertical steel pipe column; bottom-center pivot."
    )
    return obj


def make_steel_truss(name, span, height, bays, chord_size,
                     collection, material):
    """
    Simple Warren-style truss in XZ plane.
    Origin at lower-left chord endpoint.
    """
    parts = []

    def beam_between(p0, p1, member_name):
        p0 = Vector(p0)
        p1 = Vector(p1)
        vec = p1 - p0
        length = vec.length
        obj = box_end_center_x(
            member_name, length, chord_size, chord_size,
            collection, material, "TEMP", "INDUSTRIAL", bevel=0.0015
        )
        obj.location = p0
        obj.rotation_euler = vec.to_track_quat('X', 'Z').to_euler()
        apply_rotation(obj)
        return obj

    # Chords.
    parts.append(beam_between((0,0,0), (span,0,0), f"{name}_LOWER_TMP"))
    parts.append(beam_between((0,0,height), (span,0,height), f"{name}_UPPER_TMP"))

    bay_w = span / bays
    for i in range(bays + 1):
        x = i * bay_w
        parts.append(beam_between(
            (x,0,0), (x,0,height), f"{name}_VERT_{i:02d}_TMP"
        ))

    for i in range(bays):
        x0 = i * bay_w
        x1 = (i + 1) * bay_w
        if i % 2 == 0:
            p0, p1 = (x0,0,0), (x1,0,height)
        else:
            p0, p1 = (x0,0,height), (x1,0,0)
        parts.append(beam_between(p0, p1, f"{name}_DIAG_{i:02d}_TMP"))

    obj = join_objects(parts, name, collection)
    obj.location = (0,0,0)
    return finalize(
        obj, name, collection, material,
        "STEEL_TRUSS", "INDUSTRIAL",
        cuttable=False, joinable=True, bevel=0.0015,
        notes="Warren-style steel truss; lower-left endpoint pivot."
    )


def make_frame_panel(name, width, height, stud, collection, material,
                     category, opening=None):
    """
    Build a wall frame in one shared local coordinate system.

    Standard:
        origin = wall bottom-center
        +X = wall width
        +Y = wall thickness
        +Z = wall height
    """
    parts = []
    half_w = width * 0.5
    half_s = stud * 0.5

    def member(member_name, min_xyz, max_xyz):
        return cube_from_bounds(
            member_name,
            min_xyz,
            max_xyz,
            collection,
            material,
            "TEMP",
            category,
            bevel=0.0
        )

    # Plates.
    parts.append(member(
        f"{name}_BOTTOM_TMP",
        (-half_w, -half_s, 0.0),
        ( half_w,  half_s, stud)
    ))
    parts.append(member(
        f"{name}_TOP_TMP",
        (-half_w, -half_s, height - stud),
        ( half_w,  half_s, height)
    ))

    # End studs.
    parts.append(member(
        f"{name}_LEFT_END_TMP",
        (-half_w, -half_s, 0.0),
        (-half_w + stud, half_s, height)
    ))
    parts.append(member(
        f"{name}_RIGHT_END_TMP",
        (half_w - stud, -half_s, 0.0),
        (half_w, half_s, height)
    ))

    if opening is None:
        usable = width - 2.0 * stud
        target_spacing = 16.0 * INCH
        count = max(1, int(usable / target_spacing))
        for i in range(1, count + 1):
            x = -half_w + stud + usable * i / (count + 1)
            parts.append(member(
                f"{name}_STUD_{i:02d}_TMP",
                (x - half_s, -half_s, stud),
                (x + half_s,  half_s, height - stud)
            ))
    else:
        opening_w, opening_h, sill_h = opening
        opening_left = -opening_w * 0.5
        opening_right = opening_w * 0.5
        header_bottom = min(height - 2.0 * stud, sill_h + opening_h)

        # King studs.
        for x0, x1, side in [
            (opening_left - 2*stud, opening_left - stud, "KING_L"),
            (opening_right + stud, opening_right + 2*stud, "KING_R"),
        ]:
            parts.append(member(
                f"{name}_{side}_TMP",
                (x0, -half_s, stud),
                (x1,  half_s, height - stud)
            ))

        # Jack studs supporting header.
        parts.append(member(
            f"{name}_JACK_L_TMP",
            (opening_left - stud, -half_s, stud),
            (opening_left, half_s, header_bottom)
        ))
        parts.append(member(
            f"{name}_JACK_R_TMP",
            (opening_right, -half_s, stud),
            (opening_right + stud, half_s, header_bottom)
        ))

        # Header.
        parts.append(member(
            f"{name}_HEADER_TMP",
            (opening_left - stud, -half_s, header_bottom),
            (opening_right + stud, half_s, header_bottom + stud)
        ))

        # Window sill and cripple studs.
        if sill_h > 0.0:
            parts.append(member(
                f"{name}_SILL_TMP",
                (opening_left, -half_s, sill_h),
                (opening_right, half_s, sill_h + stud)
            ))
            cripple_count = max(1, int(opening_w / (16.0 * INCH)))
            for i in range(1, cripple_count + 1):
                x = opening_left + opening_w * i / (cripple_count + 1)
                parts.append(member(
                    f"{name}_CRIPPLE_BOTTOM_{i:02d}_TMP",
                    (x - half_s, -half_s, stud),
                    (x + half_s,  half_s, sill_h)
                ))

        # Short studs above header.
        upper_clear = height - stud - (header_bottom + stud)
        if upper_clear > stud:
            cripple_count = max(1, int(opening_w / (16.0 * INCH)))
            for i in range(1, cripple_count + 1):
                x = opening_left + opening_w * i / (cripple_count + 1)
                parts.append(member(
                    f"{name}_CRIPPLE_TOP_{i:02d}_TMP",
                    (x - half_s, -half_s, header_bottom + stud),
                    (x + half_s,  half_s, height - stud)
                ))

    result = join_objects(parts, name, collection)
    result.location = (0, 0, 0)
    return finalize(
        result, name, collection, material,
        "FRAMED_PANEL", category,
        cuttable=False,
        joinable=True,
        bevel=0.004,
        notes="Wall frame built in shared bottom-center coordinate system."
    )


def make_lath_panel(name, width, height, slat_w, gap, collection, material,
                    broken=False):
    parts = []
    count = int(width / (slat_w + gap))
    used_w = count * (slat_w + gap) - gap
    x0 = -used_w/2
    for i in range(count):
        h = height
        z = 0
        if broken and i % 5 == 2:
            h *= 0.55
        if broken and i % 7 == 3:
            z = height * 0.28
            h *= 0.72
        part = box_bottom_center(
            f"{name}_SLAT_TMP", slat_w, 0.008, h,
            collection, material, "TEMP", "LATH", bevel=0.001
        )
        part.location.x = x0 + i*(slat_w+gap) + slat_w/2
        part.location.z = z
        parts.append(part)
    result = join_objects(parts, name, collection)
    result.data.transform(Matrix.Translation((-result.location.x, -result.location.y, -result.location.z)))
    result.location = (0, 0, 0)
    return finalize(
        result, name, collection, material, "LATH_PANEL", "LATH",
        cuttable=True, joinable=True, bevel=0.001,
        notes="Wood lath/slat infill panel."
    )


def make_cmu(name, length, width, height, collection, material, half=False):
    length = length * (0.5 if half else 1.0)
    outer = box_bottom_center(
        f"{name}_OUTER", length, width, height,
        collection, material, "TEMP", "MASONRY", bevel=0
    )
    # Build hollow geometry by booleaning two cells, then apply.
    cell_len = length * 0.32
    cell_width = width * 0.55
    cutters = []
    centers = [0.0] if half else [-length*0.22, length*0.22]
    for cx in centers:
        cutter = box_bottom_center(
            f"{name}_CUTTER", cell_len, cell_width, height*1.2,
            collection, material, "TEMP", "MASONRY", bevel=0
        )
        cutter.location = (cx, 0, -height*0.1)
        cutters.append(cutter)
        mod = outer.modifiers.new("SPK_HollowCell", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = cutter
        bpy.context.view_layer.objects.active = outer
        outer.select_set(True)
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except RuntimeError:
            pass
        outer.select_set(False)
    for cutter in cutters:
        bpy.data.objects.remove(cutter, do_unlink=True)
    outer.name = name
    return finalize(
        outer, name, collection, material, "CMU_BLOCK", "MASONRY",
        cuttable=False, joinable=True, bevel=0.006,
        notes="Hollow concrete masonry unit proxy."
    )


def make_barrel(name, radius, height, collection, material):
    """Simple barrel body only. Hoops and lids are separate modular assets."""
    obj = cylinder_bottom(
        name, radius, height, 32,
        collection, material,
        "BARREL_BODY", "SALVAGE",
        bevel=0.004,
        cuttable=True,
        notes="Barrel body only; bottom-center pivot. Use separate hoop/lid assets."
    )
    return obj


def make_water_tank(name, radius, height, collection, material):
    """Simple tank body only. Ribs and lids are separate modular assets."""
    obj = cylinder_bottom(
        name, radius, height, 32,
        collection, material,
        "WATER_TANK_BODY", "UTILITIES",
        bevel=0.005,
        notes="Tank body only; bottom-center pivot. Use separate rib/lid assets."
    )
    return obj


def make_stair_flight(name, rise, run, width, steps, collection, tread_mat, frame_mat):
    """
    Direct-mesh straight stair.

    Origin is lower-center. +Y is travel/run, +Z is rise.
    """
    verts, faces = [], []
    tread_depth = run / steps
    tread_thickness = 0.045

    # Treads.
    for i in range(steps):
        z = rise * (i + 1) / steps
        y0 = tread_depth * i
        y1 = y0 + tread_depth * 1.08
        append_box_geometry(
            verts, faces,
            (-width/2, y0, z-tread_thickness),
            ( width/2, y1, z)
        )

    # Two diagonal stringers.
    stringer_w = 0.075
    stringer_d = 0.16
    for x in (-width*0.38, width*0.38):
        append_oriented_box_between(
            verts, faces,
            (x, 0, 0),
            (x, run, rise),
            stringer_w,
            stringer_d
        )

    obj = mesh_object_from_buffers(name, verts, faces, collection)
    return finalize(
        obj, name, collection, tread_mat,
        "STAIR_FLIGHT", "CIRCULATION",
        bevel=0.003,
        notes="Direct-mesh stair; lower-center pivot; +Y run; +Z rise."
    )


def make_ladder(name, width, height, rungs, collection, material):
    """
    Direct-mesh ladder.

    Standard:
        origin = bottom center
        +X = ladder width
        +Z = ladder height
        no joins, no temporary transforms
    """
    verts, faces = [], []
    rail_w = 0.055
    rail_d = 0.045
    rung_h = 0.045
    rung_d = 0.045

    # Rails.
    append_box_geometry(
        verts, faces,
        (-width/2 - rail_w/2, -rail_d/2, 0),
        (-width/2 + rail_w/2,  rail_d/2, height)
    )
    append_box_geometry(
        verts, faces,
        (width/2 - rail_w/2, -rail_d/2, 0),
        (width/2 + rail_w/2,  rail_d/2, height)
    )

    # Rungs span cleanly between inner rail faces.
    inner_left = -width/2 + rail_w/2
    inner_right = width/2 - rail_w/2
    for i in range(rungs):
        z = height * (i + 1) / (rungs + 1)
        append_box_geometry(
            verts, faces,
            (inner_left, -rung_d/2, z-rung_h/2),
            (inner_right, rung_d/2, z+rung_h/2)
        )

    obj = mesh_object_from_buffers(name, verts, faces, collection)
    return finalize(
        obj, name, collection, material,
        "LADDER", "CIRCULATION",
        bevel=0.002,
        notes="Direct-mesh ladder; bottom-center pivot; +Z height."
    )


def make_railing(name, length, height, post_spacing, collection, material):
    """
    Direct-mesh railing.

    Standard:
        origin = bottom-left end
        +X = length
        +Z = height
    """
    verts, faces = [], []
    post = 0.05
    post_count = max(2, int(length / post_spacing) + 1)

    for i in range(post_count):
        x = length * i / (post_count - 1)
        append_box_geometry(
            verts, faces,
            (x-post/2, -post/2, 0),
            (x+post/2,  post/2, height)
        )

    rail_h = 0.05
    rail_d = 0.05
    for z in (height*0.5, height):
        append_box_geometry(
            verts, faces,
            (0, -rail_d/2, z-rail_h/2),
            (length, rail_d/2, z+rail_h/2)
        )

    obj = mesh_object_from_buffers(name, verts, faces, collection)
    return finalize(
        obj, name, collection, material,
        "RAILING", "CIRCULATION",
        bevel=0.002,
        notes="Direct-mesh railing; endpoint pivot; +X length."
    )


def make_window_cage(name, width, height, depth, collection, material):
    parts = []
    bar = 0.025
    # Front frame and projecting side bars.
    for x in (-width/2, width/2):
        p = box_bottom_center(
            f"{name}_V_TMP", bar, bar, height,
            collection, material, "TEMP", "FACADE_DETAILS", bevel=0.001
        )
        p.location.x = x
        p.location.y = -depth
        parts.append(p)
    for z in (0, height):
        h = box_end_center_x(
            f"{name}_H_TMP", width, bar, bar,
            collection, material, "TEMP", "FACADE_DETAILS", bevel=0.001
        )
        h.location = (-width/2, -depth, z)
        parts.append(h)
    for x in (-width/2, 0, width/2):
        for z in (0, height):
            d = cube_from_bounds(
                f"{name}_D_TMP",
                (x-bar/2, -depth, z-bar/2),
                (x+bar/2, 0, z+bar/2),
                collection, material, "TEMP", "FACADE_DETAILS", bevel=0.001
            )
            parts.append(d)
    result = join_objects(parts, name, collection)
    result.data.transform(Matrix.Translation((-result.location.x, -result.location.y, -result.location.z)))
    result.location = (0, 0, 0)
    return finalize(
        result, name, collection, material, "WINDOW_CAGE", "FACADE_DETAILS",
        bevel=0.001, notes="Window-sill bottom-center attachment pivot."
    )


def make_ac_unit(name, width, depth, height, collection, material):
    body = box_bottom_center(
        f"{name}_BODY", width, depth, height,
        collection, material, "TEMP", "FACADE_DETAILS", bevel=0.018
    )
    fan = cylinder_bottom(
        f"{name}_FAN", height*0.30, 0.02, 24,
        collection, material, "TEMP", "FACADE_DETAILS", bevel=0.001
    )
    fan.rotation_euler.x = math.radians(90)
    fan.location = (0, -depth/2-0.01, height*0.52)
    grille = torus_object(
        f"{name}_GRILLE", height*0.28, 0.012,
        collection, material, "TEMP", "FACADE_DETAILS", bevel=0
    )
    grille.rotation_euler.x = math.radians(90)
    grille.location = (0, -depth/2-0.02, height*0.52)
    result = join_objects([body, fan, grille], name, collection)
    result.data.transform(Matrix.Translation((-result.location.x, -result.location.y, -result.location.z)))
    result.location = (0, 0, 0)
    return finalize(
        result, name, collection, material, "AC_UNIT", "FACADE_DETAILS",
        bevel=0.006, notes="Wall-mount bottom-center attachment pivot."
    )


def make_light_fixture(name, style, collection, body_mat, glow_mat):
    parts = []
    if style == "BARE_BULB":
        cord = cylinder_bottom(
            f"{name}_CORD", 0.008, 0.65, 8,
            collection, body_mat, "TEMP", "LIGHTING", bevel=0
        )
        bulb = cylinder_bottom(
            f"{name}_BULB", 0.055, 0.11, 16,
            collection, glow_mat, "TEMP", "LIGHTING", taper=0.65, bevel=0.002
        )
        bulb.location.z = -0.11
        parts = [cord, bulb]
    elif style == "CAGE":
        stem = cylinder_bottom(
            f"{name}_STEM", 0.012, 0.28, 8,
            collection, body_mat, "TEMP", "LIGHTING", bevel=0
        )
        shade = cylinder_bottom(
            f"{name}_SHADE", 0.14, 0.16, 16,
            collection, body_mat, "TEMP", "LIGHTING", taper=0.55, bevel=0.002
        )
        shade.location.z = -0.16
        bulb = cylinder_bottom(
            f"{name}_BULB", 0.045, 0.10, 16,
            collection, glow_mat, "TEMP", "LIGHTING", taper=0.7, bevel=0.002
        )
        bulb.location.z = -0.22
        parts = [stem, shade, bulb]
    else:  # FLOOD
        bracket = box_bottom_center(
            f"{name}_BRACKET", 0.08, 0.08, 0.24,
            collection, body_mat, "TEMP", "LIGHTING", bevel=0.004
        )
        head = box_bottom_center(
            f"{name}_HEAD", 0.32, 0.16, 0.24,
            collection, body_mat, "TEMP", "LIGHTING", bevel=0.018
        )
        head.location.z = 0.2
        lens = box_bottom_center(
            f"{name}_LENS", 0.27, 0.012, 0.18,
            collection, glow_mat, "TEMP", "LIGHTING", bevel=0.004
        )
        lens.location = (0, -0.086, 0.23)
        parts = [bracket, head, lens]
    result = join_objects(parts, name, collection)
    result.data.transform(Matrix.Translation((-result.location.x, -result.location.y, -result.location.z)))
    result.location = (0, 0, 0)
    return finalize(
        result, name, collection, body_mat, "LIGHT_FIXTURE", "LIGHTING",
        bevel=0.003, notes=f"{style} fixture proxy; attachment pivot at mounting point."
    )



# -----------------------------------------------------------------------------
# PLACEHOLDER / SOCKET HELPERS
# -----------------------------------------------------------------------------

def create_placeholder_empty(
    name,
    collection,
    category,
    role,
    mount_type,
    display_size=0.22,
    notes="",
    replacement_family=""
):
    """
    Create an invisible/non-rendering construction socket.

    These empties preserve intent without committing to weak proxy geometry.
    Future modeled assets can replace them by matching `spk_role` or
    `spk_replacement_family`.
    """
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = display_size
    obj.hide_render = True
    obj.show_in_front = True

    obj["spk_asset_id"] = name
    obj["spk_asset_type"] = "PLACEHOLDER_SOCKET"
    obj["spk_category"] = category
    obj["spk_role"] = role
    obj["spk_mount_type"] = mount_type
    obj["spk_replacement_family"] = replacement_family or role
    obj["spk_material_family"] = "NONE"
    obj["spk_cuttable"] = False
    obj["spk_joinable"] = True
    obj["spk_texel_density_px_per_m"] = TEXEL_DENSITY_PX_PER_M
    obj["spk_texture_target"] = TEXTURE_TARGET
    obj["spk_origin_usage"] = "Attachment/socket pivot"
    obj["spk_notes"] = notes
    obj["spk_export_instruction"] = (
        "Placeholder only. Replace with modeled asset sharing spk_role."
    )
    return obj


# -----------------------------------------------------------------------------
# v1.9 BUILDING-VOCABULARY ASSET HELPERS
# -----------------------------------------------------------------------------

def finalize_v19_compound(parts, name, collection, material, asset_type,
                          category, role, notes, bevel=0.004,
                          replacement_family=""):
    """Join simple proxy parts and apply the shared v1.9 metadata contract."""
    obj = parts[0] if len(parts) == 1 else join_objects(parts, name, collection)
    obj.name = name
    move_to_collection(obj, collection)
    obj.location = (0, 0, 0)
    obj = finalize(
        obj, name, collection, material, asset_type, category,
        cuttable=False, joinable=True, notes=notes, bevel=bevel
    )
    obj["spk_role"] = role
    obj["spk_replacement_family"] = replacement_family or role
    obj["spk_stockyard_version"] = "1.9"
    obj["spk_quality_target"] = "MIDGROUND_PROXY"
    obj["spk_chaos_zero_clean"] = True
    obj["spk_axis_standard"] = (
        "+X width; +Y outward depth; +Z height; construction-boundary pivot"
    )
    return obj


def temp_box(name, bounds, collection, material):
    return cube_from_bounds(
        name, bounds[0], bounds[1], collection, material,
        "TEMP", "V1_9_PROXY", bevel=0.0
    )


def make_opening_frame(name, width, height, depth, member, collection,
                       material, asset_type, role, sill=False, center_post=False):
    parts = [
        temp_box(f"{name}_JAMB_L_TMP", ((-width/2, 0, 0), (-width/2+member, depth, height)), collection, material),
        temp_box(f"{name}_JAMB_R_TMP", ((width/2-member, 0, 0), (width/2, depth, height)), collection, material),
        temp_box(f"{name}_HEADER_TMP", ((-width/2, 0, height-member), (width/2, depth, height)), collection, material),
    ]
    if sill:
        parts.append(temp_box(
            f"{name}_SILL_TMP", ((-width/2, 0, 0), (width/2, depth, member)),
            collection, material
        ))
    if center_post:
        parts.append(temp_box(
            f"{name}_CENTER_TMP", ((-member/2, 0, 0), (member/2, depth, height-member)),
            collection, material
        ))
    obj = finalize_v19_compound(
        parts, name, collection, material, asset_type, "OPENINGS", role,
        "Clean open frame proxy; wall plane and bottom-center attachment pivot.",
        bevel=min(0.004, member*0.08)
    )
    obj["spk_clear_opening_width"] = width - member * (3 if center_post else 2)
    obj["spk_clear_opening_height"] = height - member * (2 if sill else 1)
    return obj


def make_window_unit(name, width, height, depth, frame, collection, frame_mat, glass_mat):
    parts = [
        temp_box(f"{name}_L_TMP", ((-width/2, 0, 0), (-width/2+frame, depth, height)), collection, frame_mat),
        temp_box(f"{name}_R_TMP", ((width/2-frame, 0, 0), (width/2, depth, height)), collection, frame_mat),
        temp_box(f"{name}_TOP_TMP", ((-width/2, 0, height-frame), (width/2, depth, height)), collection, frame_mat),
        temp_box(f"{name}_BOTTOM_TMP", ((-width/2, 0, 0), (width/2, depth, frame)), collection, frame_mat),
        temp_box(f"{name}_MULLION_TMP", ((-frame*0.35, 0, frame), (frame*0.35, depth, height-frame)), collection, frame_mat),
        temp_box(f"{name}_GLASS_TMP", ((-width/2+frame, depth*0.42, frame), (width/2-frame, depth*0.58, height-frame)), collection, glass_mat),
    ]
    obj = finalize_v19_compound(
        parts, name, collection, frame_mat, "WINDOW_UNIT", "WINDOWS",
        "WINDOW", "Basic two-light window proxy with separate glass material slot.",
        bevel=0.003, replacement_family="SPK_WINDOW"
    )
    obj["spk_glazing_type"] = "BASIC_PROXY"
    return obj


def make_rolling_door(name, width, height, depth, collection, metal_mat, frame_mat):
    rail = 0.10
    parts = [
        temp_box(f"{name}_RAIL_L_TMP", ((-width/2-rail, 0, 0), (-width/2, depth, height+0.18)), collection, frame_mat),
        temp_box(f"{name}_RAIL_R_TMP", ((width/2, 0, 0), (width/2+rail, depth, height+0.18)), collection, frame_mat),
        temp_box(f"{name}_HOOD_TMP", ((-width/2-rail, 0, height), (width/2+rail, depth*1.25, height+0.24)), collection, frame_mat),
    ]
    slat_h = height / 14.0
    for i in range(14):
        z0 = i * slat_h + 0.006
        parts.append(temp_box(
            f"{name}_SLAT_{i:02d}_TMP",
            ((-width/2, depth*0.20, z0), (width/2, depth*0.62, (i+1)*slat_h-0.006)),
            collection, metal_mat
        ))
    obj = finalize_v19_compound(
        parts, name, collection, frame_mat, "ROLLING_GARAGE_DOOR", "UTILITY_DOORS",
        "UTILITY_DOOR", "Simple closed rolling-door proxy with readable horizontal slats.",
        bevel=0.004, replacement_family="SPK_UTILITY_DOOR"
    )
    obj["spk_clear_opening_width"] = width
    obj["spk_clear_opening_height"] = height
    obj["spk_door_operation"] = "ROLL_UP"
    return obj


def make_awning(name, width, projection, collection, sheet_mat, frame_mat):
    thickness = 0.045
    parts = [
        temp_box(f"{name}_CANOPY_TMP", ((-width/2, 0, -thickness), (width/2, projection, 0)), collection, sheet_mat),
        temp_box(f"{name}_VALANCE_TMP", ((-width/2, projection-0.04, -0.22), (width/2, projection, 0)), collection, sheet_mat),
        temp_box(f"{name}_ARM_L_TMP", ((-width*0.38, 0, -0.07), (-width*0.38+0.035, projection, -0.035)), collection, frame_mat),
        temp_box(f"{name}_ARM_R_TMP", ((width*0.38-0.035, 0, -0.07), (width*0.38, projection, -0.035)), collection, frame_mat),
    ]
    obj = finalize_v19_compound(
        parts, name, collection, sheet_mat, "AWNING", "AWNINGS", "AWNING",
        "Simple wall-mounted awning; origin is rear wall attachment center.",
        bevel=0.003, replacement_family="SPK_AWNING"
    )
    obj["spk_mount_type"] = "WALL"
    obj["spk_origin_usage"] = "Rear wall attachment center"
    return obj


def make_loading_dock(name, width, depth, deck_height, collection, concrete_mat, steel_mat):
    deck_t = 0.18
    post = 0.12
    parts = [
        temp_box(f"{name}_DECK_TMP", ((-width/2, 0, deck_height-deck_t), (width/2, depth, deck_height)), collection, concrete_mat),
        temp_box(f"{name}_BEAM_TMP", ((-width/2, depth-post, deck_height-0.34), (width/2, depth, deck_height-deck_t)), collection, steel_mat),
    ]
    for x in (-width/2+post, width/2-post):
        for y in (post, depth-post):
            parts.append(temp_box(
                f"{name}_POST_TMP", ((x-post/2, y-post/2, 0), (x+post/2, y+post/2, deck_height-deck_t)),
                collection, steel_mat
            ))
    obj = finalize_v19_compound(
        parts, name, collection, concrete_mat, "LOADING_DOCK_PLATFORM", "DOCKS",
        "LOADING_DOCK", "Protected cargo apron/platform proxy; wall-side bottom-center pivot.",
        bevel=0.01, replacement_family="SPK_DOCK"
    )
    obj["spk_platform_height"] = deck_height
    obj["spk_load_edge"] = "+Y"
    return obj


def make_retaining_corner(name, length, height, thickness, collection, material):
    parts = [
        temp_box(f"{name}_A_TMP", ((0, 0, 0), (length, thickness, height)), collection, material),
        temp_box(f"{name}_B_TMP", ((0, 0, 0), (thickness, length, height)), collection, material),
        temp_box(f"{name}_FOOT_TMP", ((0, 0, 0), (length*0.55, length*0.55, 0.14)), collection, material),
    ]
    obj = finalize_v19_compound(
        parts, name, collection, material, "RETAINING_WALL_CORNER", "RETAINING",
        "RETAINING", "Ninety-degree concrete retaining corner with inside-corner pivot.",
        bevel=0.012, replacement_family="SPK_RETAINING"
    )
    obj["spk_origin_usage"] = "Inside corner at footing bottom"
    return obj


def make_cmu_pier(name, width, depth, height, collection, material):
    course = 7.625 * INCH
    parts = []
    count = max(1, round(height / course))
    for i in range(count):
        gap = 0.006
        parts.append(temp_box(
            f"{name}_COURSE_{i:02d}_TMP",
            ((-width/2, 0, i*course+gap/2), (width/2, depth, min(height, (i+1)*course)-gap/2)),
            collection, material
        ))
    obj = finalize_v19_compound(
        parts, name, collection, material, "CMU_PIER", "FOUNDATIONS", "SUPPORT",
        "Clean stacked-course CMU support pier; bottom wall-plane pivot.",
        bevel=0.004, replacement_family="SPK_CMU"
    )
    obj["spk_support_capacity"] = "PROXY_UNRATED"
    return obj


def make_l_trim(name, length, leg_y, leg_z, thickness, collection, material,
                asset_type, role, family):
    parts = [
        temp_box(f"{name}_H_TMP", ((0, 0, 0), (length, leg_y, thickness)), collection, material),
        temp_box(f"{name}_V_TMP", ((0, 0, 0), (length, thickness, leg_z)), collection, material),
    ]
    obj = finalize_v19_compound(
        parts, name, collection, material, asset_type, "FLASHING_TRIM", role,
        "Simple L-profile; +X run with endpoint construction pivot.",
        bevel=min(0.0015, thickness*0.25), replacement_family=family
    )
    obj["spk_axis_standard"] = "+X length; endpoint pivot"
    obj["spk_profile"] = "L"
    return obj


# -----------------------------------------------------------------------------
# ASSET CREATION
# -----------------------------------------------------------------------------

def generate_assets(root, mats):
    categories = {}

    def cat(key, label):
        coll = ensure_collection(f"{ASSET_PREFIX}_{key}", root)
        categories[key] = {"collection": coll, "label": label, "objects": []}
        return coll

    timber = cat("01_TIMBER_STOCK", "01  TIMBER STOCK")
    sheet = cat("02_SHEET_GOODS", "02  SHEET GOODS")
    wall = cat("03_WALL_MODULES", "03  WALL MODULES")
    masonry = cat("04_MASONRY_FOUNDATIONS", "04  MASONRY + FOUNDATIONS")
    salvage = cat("05_SALVAGE_CONTAINERS", "05  SALVAGE + CONTAINERS")
    circulation = cat("06_CIRCULATION", "06  STAIRS + CATWALKS")
    industrial = cat("07_INDUSTRIAL_STRUCTURE", "07  INDUSTRIAL STRUCTURE")
    facade = cat("08_FACADE_DETAILS", "08  FACADE DETAILS")
    utilities = cat("09_UTILITIES", "09  UTILITIES")
    lighting = cat("10_LIGHTING", "10  LIGHTING")
    waterfront = cat("11_WATERFRONT_FLOATING", "11  WATERFRONT + FLOATING")
    cloth = cat("12_CLOTH_FLEXIBLE", "12  CLOTH + FLEXIBLE")
    roof = cat("13_ROOFING", "13  ROOFING")
    site = cat("14_SITE_CLUTTER", "14  SITE + CLUTTER")
    openings = cat("15_OPENINGS_STOREFRONTS", "15  OPENINGS + STOREFRONTS")
    site_structure = cat("16_DOCKS_FOUNDATIONS", "16  DOCKS + FOUNDATIONS")
    trim = cat("17_FLASHING_TRIM", "17  FLASHING + END TRIM")

    def register(cat_key, obj):
        categories[cat_key]["objects"].append(obj)
        return obj

    # --- 01 TIMBER STOCK -----------------------------------------------------
    wood_dims = [
        ("2X4_8FT", 8*FOOT, 3.5*INCH, 1.5*INCH),
        ("2X4_10FT", 10*FOOT, 3.5*INCH, 1.5*INCH),
        ("2X4_12FT", 12*FOOT, 3.5*INCH, 1.5*INCH),
        ("2X6_8FT", 8*FOOT, 5.5*INCH, 1.5*INCH),
        ("2X6_12FT", 12*FOOT, 5.5*INCH, 1.5*INCH),
        ("2X8_12FT", 12*FOOT, 7.25*INCH, 1.5*INCH),
        ("4X4_8FT", 8*FOOT, 3.5*INCH, 3.5*INCH),
        ("6X6_8FT", 8*FOOT, 5.5*INCH, 5.5*INCH),
        ("ROUGH_PLANK_WIDE", 8*FOOT, 10*INCH, 1*INCH),
        ("ROUGH_PLANK_NARROW", 8*FOOT, 5*INCH, 0.75*INCH),
        ("PALLET_DECK_BOARD", 48*INCH, 3.5*INCH, 0.7*INCH),
        ("PALLET_STRINGER", 48*INCH, 3.5*INCH, 1.5*INCH),
        ("RAILROAD_TIE", 8.5*FOOT, 9*INCH, 7*INCH),
        ("RAILROAD_TIE_HALF", 4.25*FOOT, 9*INCH, 7*INCH),
    ]
    for ident, length, width, height in wood_dims:
        mat = mats["MAT_WOOD_TREATED"] if "TIE" in ident else (
            mats["MAT_WOOD_SALVAGED"] if "PALLET" in ident or "ROUGH" in ident
            else mats["MAT_WOOD_STRUCTURAL"]
        )
        obj = box_end_center_x(
            f"{ASSET_PREFIX}_WOOD_{ident}", length, width, height,
            timber, mat, "TIMBER_STOCK", "TIMBER",
            cuttable=True, joinable=True,
            notes="Long axis +X; pivot at cut end center.",
            bevel=min(DEFAULT_BEVEL, min(width, height)*0.10)
        )
        register("01_TIMBER_STOCK", obj)

    for ident, radius, h in [
        ("POWER_POLE_30FT", 0.15, 30*FOOT),
        ("ROUGH_LOG_12FT", 0.13, 12*FOOT),
        ("STUMP_SUPPORT", 0.18, 0.55),
    ]:
        obj = cylinder_bottom(
            f"{ASSET_PREFIX}_WOOD_{ident}", radius, h, 16,
            timber, mats["MAT_WOOD_TREATED"], "ROUND_TIMBER", "TIMBER",
            taper=0.72 if "POLE" in ident else 0.86,
            cuttable=True, joinable=True,
            notes="Bottom-center pivot; tapered rough round timber."
        )
        register("01_TIMBER_STOCK", obj)

    # Railroad tie discs / blocks.
    for i, thick in enumerate((0.18, 0.30, 0.45), 1):
        obj = box_bottom_center(
            f"{ASSET_PREFIX}_WOOD_TIE_BLOCK_{i:02d}", 0.23, 0.18, thick,
            timber, mats["MAT_WOOD_TREATED"], "TIMBER_BLOCK", "TIMBER",
            cuttable=True, joinable=True, bevel=0.012
        )
        register("01_TIMBER_STOCK", obj)

    # --- 02 SHEET GOODS ------------------------------------------------------
    sheet_specs = [
        ("PLYWOOD_4X8", 4*FOOT, 8*FOOT, 0.5*INCH, "MAT_PLYWOOD_SHEET"),
        ("PLYWOOD_4X8_THICK", 4*FOOT, 8*FOOT, 0.75*INCH, "MAT_PLYWOOD_SHEET"),
        ("OSB_4X8", 4*FOOT, 8*FOOT, 0.5*INCH, "MAT_PLYWOOD_SHEET"),
        ("LINOLIUM_4X8", 4*FOOT, 8*FOOT, 0.12*INCH, "MAT_PLASTIC"),
        ("FLAT_STEEL_3X8", 3*FOOT, 8*FOOT, 0.08*INCH, "MAT_METAL_RUST"),
        ("FLATTENED_BARREL_SHEET", 2.7, 0.82, 0.002, "MAT_METAL_PAINTED"),
        ("ROAD_SIGN_SHEET", 0.75, 0.75, 0.003, "MAT_SIGNAGE"),
        ("APPLIANCE_PANEL", 0.75, 1.3, 0.002, "MAT_METAL_PAINTED"),
    ]
    for ident, w, h, t, mat_name in sheet_specs:
        obj = cube_from_bounds(
            f"{ASSET_PREFIX}_SHEET_{ident}",
            (-w/2, -t/2, 0), (w/2, t/2, h),
            sheet, mats[mat_name], "SHEET_GOOD", "SHEET_GOODS",
            cuttable=True, joinable=True, front_back=True,
            notes="Vertical sheet; pivot bottom-center; front/back shader-ready.",
            bevel=min(0.003, t*0.25)
        )
        register("02_SHEET_GOODS", obj)

    for ident, w, h, pitch, dep, mat_name in [
        ("CORRUGATED_3X8", 3*FOOT, 8*FOOT, 0.076, 0.018, "MAT_METAL_GALVANIZED"),
        ("CORRUGATED_3X10", 3*FOOT, 10*FOOT, 0.076, 0.018, "MAT_METAL_RUST"),
        ("CORRUGATED_WIDE_4X8", 4*FOOT, 8*FOOT, 0.10, 0.020, "MAT_METAL_PAINTED"),
        ("CORRUGATED_SMALL_PATCH", 1.2, 0.8, 0.076, 0.018, "MAT_METAL_RUST"),
    ]:
        obj = corrugated_sheet(
            f"{ASSET_PREFIX}_SHEET_{ident}", w, h, dep, pitch,
            sheet, mats[mat_name],
            cuttable=True, joinable=True,
            notes="Geometric corrugation; bottom-center pivot."
        )
        register("02_SHEET_GOODS", obj)

    # --- 03 WALL MODULES -----------------------------------------------------
    for ident, opening in [
        ("FRAME_BLANK_8FT", None),
        ("FRAME_WINDOW_8FT", (1.05, 1.15, 0.85)),
        ("FRAME_DOOR_8FT", (0.92, 2.05, 0.0)),
    ]:
        obj = make_frame_panel(
            f"{ASSET_PREFIX}_WALL_{ident}", 8*FOOT, 8*FOOT, 3.5*INCH,
            wall, mats["MAT_WOOD_STRUCTURAL"], "WALL_MODULE", opening
        )
        register("03_WALL_MODULES", obj)

    for ident, broken in [("LATH_CLEAN", False), ("LATH_BROKEN", True)]:
        obj = make_lath_panel(
            f"{ASSET_PREFIX}_WALL_{ident}", 4*FOOT, 8*FOOT,
            1.25*INCH, 0.35*INCH, wall, mats["MAT_LATH_PLASTER"], broken
        )
        register("03_WALL_MODULES", obj)

    # Plank/pallet infill panels.
    for ident, count, plank_w, gap, mat_name in [
        ("PLANK_VERTICAL", 10, 0.12, 0.012, "MAT_WOOD_SALVAGED"),
        ("PALLET_INFILL", 8, 0.10, 0.055, "MAT_WOOD_SALVAGED"),
    ]:
        parts = []
        panel_w, panel_h = 4*FOOT, 8*FOOT
        x0 = -panel_w/2
        for i in range(count):
            p = box_bottom_center(
                f"{ident}_TMP", plank_w, 0.025, panel_h,
                wall, mats[mat_name], "TEMP", "WALL_MODULE", bevel=0.002
            )
            p.location.x = x0 + i*(plank_w+gap) + plank_w/2
            parts.append(p)
        obj = join_objects(parts, f"{ASSET_PREFIX}_WALL_{ident}", wall)
        obj.data.transform(Matrix.Translation((-obj.location.x, -obj.location.y, -obj.location.z)))
        obj.location = (0, 0, 0)
        obj = finalize(
            obj, obj.name, wall, mats[mat_name], "INFILL_PANEL", "WALL_MODULE",
            cuttable=True, joinable=True, bevel=0.002
        )
        register("03_WALL_MODULES", obj)

    # --- 04 MASONRY + FOUNDATIONS -------------------------------------------
    for ident, half in [("CMU_FULL", False), ("CMU_HALF", True)]:
        obj = make_cmu(
            f"{ASSET_PREFIX}_MASONRY_{ident}",
            15.625*INCH, 7.625*INCH, 7.625*INCH,
            masonry, mats["MAT_CMU"], half
        )
        register("04_MASONRY_FOUNDATIONS", obj)

    for ident, dims in [
        ("BRICK_FULL", (8*INCH, 3.625*INCH, 2.25*INCH)),
        ("BRICK_HALF", (4*INCH, 3.625*INCH, 2.25*INCH)),
        ("CONCRETE_PIER_SMALL", (0.30, 0.30, 0.55)),
        ("CONCRETE_PIER_LARGE", (0.45, 0.45, 0.90)),
        ("CONCRETE_FOOTING", (0.75, 0.75, 0.22)),
        ("BROKEN_SLAB", (1.2, 0.85, 0.12)),
    ]:
        mat = mats["MAT_BRICK"] if "BRICK" in ident else mats["MAT_CONCRETE"]
        obj = box_bottom_center(
            f"{ASSET_PREFIX}_MASONRY_{ident}", *dims,
            masonry, mat, "MASONRY_UNIT", "MASONRY",
            joinable=True, bevel=0.006 if "BRICK" in ident else 0.015
        )
        register("04_MASONRY_FOUNDATIONS", obj)

    # --- 05 SALVAGE + CONTAINERS --------------------------------------------
    barrel = make_barrel(
        f"{ASSET_PREFIX}_SALVAGE_BARREL_55GAL",
        0.286, 0.88, salvage, mats["MAT_METAL_PAINTED"]
    )
    register("05_SALVAGE_CONTAINERS", barrel)

    # Barrel components are separate modular assets with independent origins.
    barrel_lid = cylinder_bottom(
        f"{ASSET_PREFIX}_SALVAGE_BARREL_LID_55GAL",
        0.278, 0.025, 32,
        salvage, mats["MAT_METAL_PAINTED"],
        "BARREL_LID", "SALVAGE",
        bevel=0.002,
        notes="Separate barrel lid; bottom-center pivot."
    )
    register("05_SALVAGE_CONTAINERS", barrel_lid)

    barrel_hoop = torus_object(
        f"{ASSET_PREFIX}_SALVAGE_BARREL_HOOP_55GAL",
        0.274, 0.018,
        salvage, mats["MAT_METAL_PAINTED"],
        "BARREL_HOOP", "SALVAGE",
        bevel=0.001
    )
    # Put hoop bottom at local Z=0.
    barrel_hoop.data.transform(Matrix.Translation((0, 0, 0.018)))
    barrel_hoop["spk_origin_usage"] = "Bottom-center modular hoop pivot"
    register("05_SALVAGE_CONTAINERS", barrel_hoop)

    for ident, frac in [("BARREL_HALF_VERTICAL", 0.5), ("BARREL_HALF_SHORT", 0.42)]:
        obj = cylinder_bottom(
            f"{ASSET_PREFIX}_SALVAGE_{ident}", 0.286, 0.88*frac, 24,
            salvage, mats["MAT_METAL_RUST"], "BARREL_SECTION", "SALVAGE",
            bevel=0.003, cuttable=True
        )
        register("05_SALVAGE_CONTAINERS", obj)

    # Shipping container primitives with readable corrugated side panels.
    for ident, length in [("CONTAINER_20FT", 20*FOOT), ("CONTAINER_40FT", 40*FOOT)]:
        body = box_bottom_center(
            f"{ASSET_PREFIX}_SALVAGE_{ident}",
            8*FOOT, length, 8.5*FOOT,
            salvage, mats["MAT_METAL_PAINTED"], "SHIPPING_CONTAINER", "SALVAGE",
            bevel=0.03, joinable=True,
            notes="Container proxy; pivot centered at one floor end for snapping."
        )
        # Reorient so long axis is +X and shift pivot to one end.
        body.data.transform(Matrix.Rotation(math.radians(90), 4, 'Z'))
        # Body currently centered around local origin in XY with bottom z; shift X so min is 0.
        xs = [v.co.x for v in body.data.vertices]
        body.data.transform(Matrix.Translation((-min(xs), 0, 0)))
        register("05_SALVAGE_CONTAINERS", body)

    pallet = make_frame_panel(
        f"{ASSET_PREFIX}_SALVAGE_PALLET_48X40",
        48*INCH, 40*INCH, 2.5*INCH,
        salvage, mats["MAT_WOOD_SALVAGED"], "SALVAGE", None
    )
    pallet.scale.z = 0.18
    apply_scale(pallet)
    register("05_SALVAGE_CONTAINERS", pallet)

    for ident, dims, mat_name in [
        ("IBC_TOTE", (1.0, 1.2, 1.15), "MAT_PLASTIC"),
        ("PLASTIC_DRUM", (0.58, 0.58, 0.90), "MAT_PLASTIC"),
        ("WOOD_CRATE", (0.85, 0.65, 0.60), "MAT_WOOD_SALVAGED"),
    ]:
        obj = box_bottom_center(
            f"{ASSET_PREFIX}_SALVAGE_{ident}", *dims,
            salvage, mats[mat_name], "SALVAGE_CONTAINER", "SALVAGE",
            bevel=0.015
        )
        register("05_SALVAGE_CONTAINERS", obj)

    # --- 06 CIRCULATION ------------------------------------------------------
    for ident, rise, run, width, steps in [
        ("STAIR_8FT_RISE", 8*FOOT, 3.2, 0.9, 12),
        ("STAIR_10FT_RISE", 10*FOOT, 3.9, 1.0, 15),
    ]:
        obj = make_stair_flight(
            f"{ASSET_PREFIX}_CIRC_{ident}", rise, run, width, steps,
            circulation, mats["MAT_WOOD_SALVAGED"], mats["MAT_WOOD_STRUCTURAL"]
        )
        register("06_CIRCULATION", obj)

    for ident, h in [("LADDER_8FT", 8*FOOT), ("LADDER_12FT", 12*FOOT)]:
        obj = make_ladder(
            f"{ASSET_PREFIX}_CIRC_{ident}", 0.48, h, 10 if h < 3 else 15,
            circulation, mats["MAT_STEEL_STRUCTURAL"]
        )
        register("06_CIRCULATION", obj)

    for ident, length, width in [
        ("CATWALK_2M", 2.0, 0.9),
        ("CATWALK_4M", 4.0, 1.0),
        ("BALCONY_2X1", 2.0, 1.0),
    ]:
        obj = box_end_center_x(
            f"{ASSET_PREFIX}_CIRC_{ident}", length, width, 0.08,
            circulation, mats["MAT_STEEL_DIAMOND_PLATE"],
            "PLATFORM", "CIRCULATION", cuttable=True, joinable=True,
            notes="Long axis +X; pivot at one platform end."
        )
        register("06_CIRCULATION", obj)

    for ident, length in [("RAILING_2M", 2.0), ("RAILING_4M", 4.0)]:
        obj = make_railing(
            f"{ASSET_PREFIX}_CIRC_{ident}", length, 1.05, 1.0,
            circulation, mats["MAT_STEEL_STRUCTURAL"]
        )
        register("06_CIRCULATION", obj)

    # --- 07 INDUSTRIAL STRUCTURE --------------------------------------------
    industrial_assets = [
        make_i_beam(
            f"{ASSET_PREFIX}_IND_IBEAM_4M",
            4.0, 0.18, 0.28, 0.025, 0.016,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        make_i_beam(
            f"{ASSET_PREFIX}_IND_IBEAM_8M",
            8.0, 0.24, 0.38, 0.032, 0.020,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        make_channel(
            f"{ASSET_PREFIX}_IND_CHANNEL_4M",
            4.0, 0.16, 0.24, 0.018,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        make_angle_iron(
            f"{ASSET_PREFIX}_IND_ANGLE_IRON_3M",
            3.0, 0.10, 0.10, 0.012,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        make_square_tube(
            f"{ASSET_PREFIX}_IND_SQUARE_TUBE_4M",
            4.0, 0.15, 0.012,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        make_pipe_column(
            f"{ASSET_PREFIX}_IND_PIPE_COLUMN_4M",
            0.075, 4.0,
            industrial, mats["MAT_STEEL_STRUCTURAL"]
        ),
        box_end_center_x(
            f"{ASSET_PREFIX}_IND_TRUSS_6M",
            6.0, 0.18, 1.2,
            industrial, mats["MAT_STEEL_STRUCTURAL"],
            "TRUSS_BOUNDING_BOX", "INDUSTRIAL",
            cuttable=False,
            joinable=True,
            bevel=0.006,
            notes=(
                "Temporary truss bounding-box proxy. "
                "Replace later with authored truss using the same object name."
            )
        ),
    ]

    for obj in industrial_assets:
        register("07_INDUSTRIAL_STRUCTURE", obj)

    # --- 08 FACADE DETAILS ---------------------------------------------------
    # Intentionally represented as empties/sockets for the first shack-builder
    # milestone. These can be replaced later with authored hero models.
    facade_placeholders = [
        ("WINDOW_CAGE_SMALL", "window_cage_small", "WINDOW", 0.28),
        ("WINDOW_CAGE_LARGE", "window_cage_large", "WINDOW", 0.34),
        ("AC_WINDOW", "ac_window", "WINDOW", 0.30),
        ("AC_SPLIT_OUTDOOR", "ac_split_outdoor", "WALL", 0.34),
        ("WINDOW_BOX", "window_box", "WINDOW_SILL", 0.22),
        ("AWNING_SIMPLE", "awning_simple", "WALL_ABOVE_OPENING", 0.28),
        ("SHUTTER_PANEL", "shutter_panel", "WINDOW_SIDE", 0.26),
        ("UTILITY_METER_BOX", "utility_meter_box", "WALL", 0.20),
        ("JUNCTION_BOX", "junction_box", "WALL", 0.16),
        ("SATELLITE_DISH", "satellite_dish", "ROOF_OR_WALL", 0.32),
        ("MAILBOX", "mailbox", "WALL_OR_POST", 0.16),
        ("FLOWER_BOX", "flower_box", "WINDOW_SILL", 0.20),
        ("SIGN_PANEL", "sign_panel", "WALL", 0.22),
        ("GUTTER_OUTLET", "gutter_outlet", "ROOF_EDGE", 0.16),
        ("CLOTHESLINE_ANCHOR", "clothesline_anchor", "WALL_OR_POST", 0.14),
        ("CABLE_SPLICE", "cable_splice", "CABLE", 0.12),
    ]

    for ident, role, mount, size in facade_placeholders:
        obj = create_placeholder_empty(
            f"{ASSET_PREFIX}_PLACEHOLDER_{ident}",
            facade,
            "FACADE_DETAILS",
            role,
            mount,
            display_size=size,
            notes="Model later; currently used as an attachment/socket marker.",
            replacement_family=role
        )
        register("08_FACADE_DETAILS", obj)

    # --- 09 UTILITIES --------------------------------------------------------
    for ident, radius, length, mat_name in [
        ("PIPE_STEEL_1M", 0.035, 1.0, "MAT_STEEL_STRUCTURAL"),
        ("PIPE_STEEL_3M", 0.050, 3.0, "MAT_STEEL_STRUCTURAL"),
        ("PIPE_LARGE_4M", 0.16, 4.0, "MAT_STEEL_STRUCTURAL"),
        ("PVC_DRAIN_3M", 0.055, 3.0, "MAT_PIPE_PVC"),
        ("CONDUIT_2M", 0.018, 2.0, "MAT_METAL_GALVANIZED"),
    ]:
        obj = pipe_segment(
            f"{ASSET_PREFIX}_UTIL_{ident}", radius, length,
            utilities, mats[mat_name], cuttable=True, joinable=True,
            notes="Long axis +Z; pivot at pipe endpoint."
        )
        register("09_UTILITIES", obj)

    for ident, radius, h, mat_name in [
        ("WATER_TANK_SMALL", 0.55, 1.10, "MAT_PLASTIC"),
        ("WATER_TANK_LARGE", 0.85, 1.65, "MAT_PLASTIC"),
    ]:
        obj = make_water_tank(
            f"{ASSET_PREFIX}_UTIL_{ident}", radius, h,
            utilities, mats[mat_name]
        )
        register("09_UTILITIES", obj)

    # Separate reusable tank components.
    for ident, radius in [
        ("WATER_TANK_RIB_SMALL", 0.54),
        ("WATER_TANK_RIB_LARGE", 0.84),
    ]:
        rib = torus_object(
            f"{ASSET_PREFIX}_UTIL_{ident}",
            radius, 0.022,
            utilities, mats["MAT_PLASTIC"],
            "WATER_TANK_RIB", "UTILITIES",
            bevel=0.001
        )
        rib.data.transform(Matrix.Translation((0, 0, 0.022)))
        rib["spk_origin_usage"] = "Bottom-center modular rib pivot"
        register("09_UTILITIES", rib)

    for ident, radius in [
        ("WATER_TANK_LID_SMALL", 0.53),
        ("WATER_TANK_LID_LARGE", 0.82),
    ]:
        lid = cylinder_bottom(
            f"{ASSET_PREFIX}_UTIL_{ident}",
            radius, 0.08, 32,
            utilities, mats["MAT_PLASTIC"],
            "WATER_TANK_LID", "UTILITIES",
            taper=0.82,
            bevel=0.004,
            notes="Separate tank lid; bottom-center pivot."
        )
        register("09_UTILITIES", lid)

    for ident, dims, mat_name in [
        ("TRANSFORMER_BOX", (0.65, 0.48, 0.82), "MAT_STEEL_STRUCTURAL"),
        ("BREAKER_PANEL", (0.36, 0.12, 0.55), "MAT_METAL_GALVANIZED"),
        ("SOLAR_PANEL", (1.0, 0.04, 1.7), "MAT_GLASS"),
        ("CABLE_TRAY_2M", (2.0, 0.22, 0.08), "MAT_STEEL_STRUCTURAL"),
    ]:
        obj = box_bottom_center(
            f"{ASSET_PREFIX}_UTIL_{ident}", *dims,
            utilities, mats[mat_name], "UTILITY_ASSET", "UTILITIES",
            bevel=0.01, joinable=True
        )
        register("09_UTILITIES", obj)

    # --- 10 LIGHTING ---------------------------------------------------------
    lighting_placeholders = [
        ("BARE_BULB", "light_bare_bulb", "CEILING_OR_BEAM", 0.18),
        ("CAGE_LIGHT", "light_cage", "CEILING_OR_BEAM", 0.22),
        ("FLOOD_LIGHT", "light_flood", "WALL_OR_POLE", 0.26),
        ("FLUORESCENT_STRIP", "light_fluorescent", "CEILING", 0.24),
        ("WALL_UTILITY_LIGHT", "light_wall_utility", "WALL", 0.20),
        ("STRING_LIGHT_ANCHOR", "string_light_anchor", "WALL_OR_POLE", 0.14),
    ]

    for ident, role, mount, size in lighting_placeholders:
        obj = create_placeholder_empty(
            f"{ASSET_PREFIX}_PLACEHOLDER_{ident}",
            lighting,
            "LIGHTING",
            role,
            mount,
            display_size=size,
            notes="Lighting socket. Future fixture mesh and Blender light attach here.",
            replacement_family=role
        )
        register("10_LIGHTING", obj)

    # --- 11 WATERFRONT + FLOATING -------------------------------------------
    for ident, radius, length, mat_name in [
        ("FLOAT_BARREL", 0.286, 0.88, "MAT_PLASTIC"),
        ("PONTOON_SMALL", 0.32, 2.2, "MAT_METAL_GALVANIZED"),
        ("LOG_FLOAT", 0.16, 3.5, "MAT_WOOD_TREATED"),
    ]:
        obj = cylinder_bottom(
            f"{ASSET_PREFIX}_FLOAT_{ident}", radius, length, 20,
            waterfront, mats[mat_name], "FLOATATION", "WATERFRONT",
            taper=1.0, bevel=0.004, joinable=True
        )
        obj.rotation_euler.y = math.radians(90)
        # Rotation is intentionally part of design; apply it so export rotation stays zero.
        apply_scale(obj)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        register("11_WATERFRONT_FLOATING", obj)

    for ident, length, width, height, mat_name in [
        ("RAFT_DECK_3X3", 3.0, 3.0, 0.18, "MAT_WOOD_SALVAGED"),
        ("BARGE_DECK_6X3", 6.0, 3.0, 0.28, "MAT_STEEL_STRUCTURAL"),
        ("DOCK_MODULE_2X1", 2.0, 1.0, 0.16, "MAT_WOOD_SALVAGED"),
        ("GANGWAY_3M", 3.0, 0.85, 0.08, "MAT_STEEL_DIAMOND_PLATE"),
    ]:
        obj = box_end_center_x(
            f"{ASSET_PREFIX}_FLOAT_{ident}", length, width, height,
            waterfront, mats[mat_name], "FLOATING_PLATFORM", "WATERFRONT",
            cuttable=True, joinable=True
        )
        register("11_WATERFRONT_FLOATING", obj)

    tire = torus_object(
        f"{ASSET_PREFIX}_FLOAT_TIRE_BUMPER", 0.34, 0.11,
        waterfront, mats["MAT_RUBBER"], "TIRE_BUMPER", "WATERFRONT"
    )
    tire.data.transform(Matrix.Translation((0, 0, 0.11)))
    tire["spk_origin_usage"] = "Bottom-center display/construction pivot"
    register("11_WATERFRONT_FLOATING", tire)

    # --- 12 CLOTH + FLEXIBLE -------------------------------------------------
    for ident, w, h, sx, sz, mat_name in [
        ("TARP_DOOR", 1.05, 2.2, 8, 16, "MAT_CLOTH_TARP"),
        ("TARP_WALL", 2.4, 2.6, 16, 16, "MAT_CLOTH_TARP"),
        ("CANVAS_SHADE", 3.0, 2.0, 18, 12, "MAT_CLOTH_CANVAS"),
        ("LAUNDRY_SHEET", 1.4, 1.8, 10, 12, "MAT_CLOTH_CANVAS"),
        ("BILLBOARD_VINYL", 4.0, 2.5, 20, 14, "MAT_CLOTH_TARP"),
    ]:
        obj = plane_vertical(
            f"{ASSET_PREFIX}_CLOTH_{ident}", w, h,
            cloth, mats[mat_name], "CLOTH_PANEL", "CLOTH",
            subdivisions_x=sx, subdivisions_z=sz,
            front_back=True,
            notes="Subdivided cloth-ready plane; bottom-center pivot."
        )
        # Pin group: top row vertices.
        vg = obj.vertex_groups.new(name="PIN_TOP")
        top_verts = [v.index for v in obj.data.vertices if abs(v.co.z - h) < 1e-5]
        vg.add(top_verts, 1.0, 'REPLACE')
        obj["spk_pin_group"] = "PIN_TOP"
        register("12_CLOTH_FLEXIBLE", obj)

    # --- 13 ROOFING ----------------------------------------------------------
    for ident, w, length, mat_name in [
        ("CORR_ROOF_3X8", 3*FOOT, 8*FOOT, "MAT_METAL_RUST"),
        ("CORR_ROOF_3X12", 3*FOOT, 12*FOOT, "MAT_METAL_GALVANIZED"),
    ]:
        obj = corrugated_sheet(
            f"{ASSET_PREFIX}_ROOF_{ident}", w, length, 0.018, 0.076,
            roof, mats[mat_name], ribs_direction="VERTICAL",
            cuttable=True, joinable=True,
            notes="Roof sheet; flat XY orientation; edge-center pivot."
        )
        orient_vertical_sheet_as_flat_roof(obj)
        register("13_ROOFING", obj)

    for ident, w, length, thick, mat_name in [
        ("SHINGLE_STRIP", 1.0, 0.34, 0.012, "MAT_WOOD_SALVAGED"),
        ("TAR_PAPER_ROLL_OUT", 1.0, 3.0, 0.004, "MAT_RUBBER"),
        ("RIDGE_CAP_2M", 2.0, 0.24, 0.025, "MAT_METAL_GALVANIZED"),
        ("ROOF_BOARD_8FT", 8*FOOT, 0.20, 0.025, "MAT_WOOD_SALVAGED"),
    ]:
        obj = box_end_center_x(
            f"{ASSET_PREFIX}_ROOF_{ident}", length, w, thick,
            roof, mats[mat_name], "ROOF_COMPONENT", "ROOFING",
            cuttable=True, joinable=True
        )
        obj["spk_axis_standard"] = "+X length; flat XY; endpoint pivot"
        register("13_ROOFING", obj)

    # --- 14 SITE + CLUTTER ---------------------------------------------------
    for ident, dims, mat_name in [
        ("CINDER_BLOCK_STACK_PROXY", (0.85, 0.42, 0.55), "MAT_CMU"),
        ("BRICK_STACK_PROXY", (0.75, 0.55, 0.42), "MAT_BRICK"),
        ("SCRAP_PILE_PROXY", (1.4, 1.0, 0.75), "MAT_METAL_RUST"),
        ("TOOL_CRATE", (0.65, 0.42, 0.35), "MAT_WOOD_SALVAGED"),
        ("SANDBAG", (0.62, 0.28, 0.18), "MAT_CLOTH_CANVAS"),
        ("CONCRETE_BARRIER", (1.8, 0.50, 0.80), "MAT_CONCRETE"),
        ("SIGN_PANEL", (0.65, 0.035, 0.9), "MAT_SIGNAGE"),
    ]:
        obj = box_bottom_center(
            f"{ASSET_PREFIX}_SITE_{ident}", *dims,
            site, mats[mat_name], "SITE_ASSET", "SITE_CLUTTER",
            bevel=0.025
        )
        register("14_SITE_CLUTTER", obj)

    for ident, radius, height, mat_name in [
        ("BUCKET", 0.16, 0.28, "MAT_METAL_GALVANIZED"),
        ("FUEL_CAN", 0.16, 0.42, "MAT_METAL_PAINTED"),
        ("SMALL_TANK", 0.32, 0.75, "MAT_METAL_RUST"),
    ]:
        obj = cylinder_bottom(
            f"{ASSET_PREFIX}_SITE_{ident}", radius, height, 16,
            site, mats[mat_name], "SITE_ASSET", "SITE_CLUTTER",
            taper=0.92, bevel=0.004
        )
        register("14_SITE_CLUTTER", obj)

    # --- 15 OPENINGS + STOREFRONTS (v1.9) -----------------------------------
    door_slab = finalize_v19_compound(
        [temp_box(
            f"{ASSET_PREFIX}_OPENING_DOOR_SLAB_36X80_BODY_TMP",
            ((-18*INCH, 0, 0), (18*INCH, 1.75*INCH, 80*INCH)),
            openings, mats["MAT_WOOD_STRUCTURAL"]
        )],
        f"{ASSET_PREFIX}_OPENING_DOOR_SLAB_36X80",
        openings, mats["MAT_WOOD_STRUCTURAL"], "DOOR_SLAB", "OPENINGS",
        "DOOR", "Plain 36 x 80 inch personnel-door slab proxy.",
        bevel=0.006, replacement_family="SPK_OPENING"
    )
    door_slab["spk_hinge_side_default"] = "LEFT"
    door_slab["spk_door_operation"] = "SWING"
    register("15_OPENINGS_STOREFRONTS", door_slab)

    door_frame = make_opening_frame(
        f"{ASSET_PREFIX}_OPENING_DOOR_FRAME_36X80",
        38*INCH, 82*INCH, 4.5*INCH, 2.25*INCH,
        openings, mats["MAT_WOOD_STRUCTURAL"],
        "DOOR_FRAME", "DOOR_FRAME", sill=False
    )
    door_frame["spk_replacement_family"] = "SPK_OPENING"
    register("15_OPENINGS_STOREFRONTS", door_frame)

    window = make_window_unit(
        f"{ASSET_PREFIX}_WINDOW_BASIC_3X4",
        3*FOOT, 4*FOOT, 3.5*INCH, 2.0*INCH,
        openings, mats["MAT_METAL_PAINTED"], mats["MAT_GLASS"]
    )
    register("15_OPENINGS_STOREFRONTS", window)

    casing = make_opening_frame(
        f"{ASSET_PREFIX}_WINDOW_CASING_3X4",
        3*FOOT+7*INCH, 4*FOOT+7*INCH, 0.75*INCH, 3.5*INCH,
        openings, mats["MAT_WOOD_SALVAGED"],
        "WINDOW_CASING", "WINDOW_TRIM", sill=True
    )
    casing["spk_replacement_family"] = "SPK_WINDOW"
    register("15_OPENINGS_STOREFRONTS", casing)

    storefront = make_opening_frame(
        f"{ASSET_PREFIX}_STOREFRONT_OPEN_FRAME_12FT",
        12*FOOT, 9*FOOT, 5.5*INCH, 4*INCH,
        openings, mats["MAT_STEEL_STRUCTURAL"],
        "OPEN_AIR_STOREFRONT_FRAME", "STOREFRONT",
        sill=False, center_post=True
    )
    storefront["spk_replacement_family"] = "SPK_STOREFRONT"
    storefront["spk_storefront_entry_side"] = "FRONT"
    register("15_OPENINGS_STOREFRONTS", storefront)

    for ident, width, height in [
        ("ROLLING_8X8", 8*FOOT, 8*FOOT),
        ("ROLLING_10X10", 10*FOOT, 10*FOOT),
    ]:
        rolling = make_rolling_door(
            f"{ASSET_PREFIX}_UTILITY_DOOR_{ident}", width, height, 0.16,
            openings, mats["MAT_METAL_GALVANIZED"], mats["MAT_STEEL_STRUCTURAL"]
        )
        register("15_OPENINGS_STOREFRONTS", rolling)

    for ident, width, projection in [
        ("SIMPLE_6FT", 6*FOOT, 0.9),
        ("SIMPLE_10FT", 10*FOOT, 1.2),
    ]:
        awning = make_awning(
            f"{ASSET_PREFIX}_AWNING_{ident}", width, projection,
            openings, mats["MAT_METAL_PAINTED"], mats["MAT_STEEL_STRUCTURAL"]
        )
        register("15_OPENINGS_STOREFRONTS", awning)

    # --- 16 DOCKS + FOUNDATIONS (v1.9) --------------------------------------
    for ident, width, depth, height in [
        ("PLATFORM_8X6", 8*FOOT, 6*FOOT, 48*INCH),
        ("PLATFORM_12X8", 12*FOOT, 8*FOOT, 48*INCH),
    ]:
        dock = make_loading_dock(
            f"{ASSET_PREFIX}_DOCK_{ident}", width, depth, height,
            site_structure, mats["MAT_CONCRETE"], mats["MAT_STEEL_STRUCTURAL"]
        )
        register("16_DOCKS_FOUNDATIONS", dock)

    for ident, length, height, thickness in [
        ("STRAIGHT_2M", 2.0, 1.0, 0.20),
        ("STRAIGHT_4M", 4.0, 1.5, 0.25),
    ]:
        retaining = finalize_v19_compound(
            [
                temp_box(f"{ident}_WALL_TMP", ((-length/2, 0, 0), (length/2, thickness, height)), site_structure, mats["MAT_CONCRETE"]),
                temp_box(f"{ident}_FOOT_TMP", ((-length/2, 0, 0), (length/2, thickness*2.2, 0.16)), site_structure, mats["MAT_CONCRETE"]),
            ],
            f"{ASSET_PREFIX}_RETAINING_{ident}", site_structure,
            mats["MAT_CONCRETE"], "RETAINING_WALL_STRAIGHT", "RETAINING",
            "RETAINING", "Straight concrete retaining module with integrated footing.",
            bevel=0.012, replacement_family="SPK_RETAINING"
        )
        retaining["spk_nominal_length"] = length
        register("16_DOCKS_FOUNDATIONS", retaining)

    corner = make_retaining_corner(
        f"{ASSET_PREFIX}_RETAINING_CORNER_2M", 2.0, 1.0, 0.20,
        site_structure, mats["MAT_CONCRETE"]
    )
    register("16_DOCKS_FOUNDATIONS", corner)

    for ident, width, depth, height in [
        ("PAD_SMALL", 0.60, 0.60, 0.18),
        ("PAD_MEDIUM", 1.20, 1.20, 0.25),
        ("PAD_LARGE", 2.40, 1.80, 0.30),
    ]:
        pad = finalize_v19_compound(
            [temp_box(f"{ident}_TMP", ((-width/2, 0, 0), (width/2, depth, height)), site_structure, mats["MAT_CONCRETE"])],
            f"{ASSET_PREFIX}_FOUNDATION_{ident}", site_structure,
            mats["MAT_CONCRETE"], "CONCRETE_FOUNDATION_PAD", "FOUNDATIONS",
            "FOUNDATION", "Simple level concrete foundation pad; back-edge bottom-center pivot.",
            bevel=0.012, replacement_family="SPK_FOUNDATION"
        )
        pad["spk_support_surface"] = "TOP"
        register("16_DOCKS_FOUNDATIONS", pad)

    for ident, width, depth, height in [
        ("PIER_8X8_32", 8*INCH, 8*INCH, 32*INCH),
        ("PIER_16X16_48", 16*INCH, 16*INCH, 48*INCH),
    ]:
        pier = make_cmu_pier(
            f"{ASSET_PREFIX}_CMU_{ident}", width, depth, height,
            site_structure, mats["MAT_CMU"]
        )
        register("16_DOCKS_FOUNDATIONS", pier)

    # --- 17 FLASHING + END TRIM (v1.9) --------------------------------------
    for ident, length, leg_y, leg_z, family, role in [
        ("L_2M", 2.0, 0.10, 0.10, "SPK_FLASHING", "FLASHING"),
        ("L_4M", 4.0, 0.12, 0.12, "SPK_FLASHING", "FLASHING"),
    ]:
        flashing = make_l_trim(
            f"{ASSET_PREFIX}_FLASHING_{ident}", length, leg_y, leg_z, 0.002,
            trim, mats["MAT_METAL_GALVANIZED"], "FLASHING", role, family
        )
        register("17_FLASHING_TRIM", flashing)

    for prefix, ident, length, leg_y, leg_z, role in [
        ("TRIM", "ROOF_END_2M", 2.0, 0.08, 0.10, "ROOF_TRIM"),
        ("TRIM", "ROOF_END_4M", 4.0, 0.08, 0.10, "ROOF_TRIM"),
        ("TRIM", "WALL_END_8FT", 8*FOOT, 0.06, 0.08, "WALL_TRIM"),
    ]:
        end_trim = make_l_trim(
            f"{ASSET_PREFIX}_{prefix}_{ident}", length, leg_y, leg_z, 0.002,
            trim, mats["MAT_METAL_PAINTED"], "END_TRIM", role, "SPK_TRIM"
        )
        register("17_FLASHING_TRIM", end_trim)

    return categories


# -----------------------------------------------------------------------------
# HERO SHELF + VALIDATION
# -----------------------------------------------------------------------------

HERO_ASSET_NAMES = [
    "SPK_WOOD_2X4_8FT",
    "SPK_WOOD_2X6_8FT",
    "SPK_WOOD_PALLET_DECK_BOARD",
    "SPK_SHEET_CORRUGATED_3X8",
    "SPK_SHEET_PLYWOOD_4X8",
    "SPK_MASONRY_CMU_FULL",
    "SPK_SALVAGE_BARREL_55GAL",
    "SPK_UTIL_PIPE_STEEL_3M",
    "SPK_WALL_FRAME_WINDOW_8FT",
    "SPK_WALL_FRAME_DOOR_8FT",
    "SPK_OPENING_DOOR_SLAB_36X80",
    "SPK_WINDOW_BASIC_3X4",
    "SPK_UTILITY_DOOR_ROLLING_8X8",
    "SPK_DOCK_PLATFORM_8X6",
]


def make_display_link(source, name, collection):
    dup = source.copy()
    dup.data = source.data
    dup.name = name
    collection.objects.link(dup)
    dup["spk_display_only"] = True
    dup["spk_source_asset"] = source.name
    return dup


def create_hero_shelf(root, categories, y_position):
    shelf_coll = ensure_collection(f"{ASSET_PREFIX}_00_HERO_SHELF", root)
    create_text_label(
        "HERO SHELF  —  FIRST SHACK KIT",
        (0.0, y_position + 1.0, 0.03),
        shelf_coll,
        size=0.55,
        upright=True
    )

    x = 0.0
    max_depth = 1.0
    for asset_name in HERO_ASSET_NAMES:
        source = bpy.data.objects.get(asset_name)
        if not source:
            continue
        display = make_display_link(
            source,
            f"VIEW_{asset_name}",
            shelf_coll
        )
        fx, fy = object_stockyard_footprint(display)
        display.rotation_euler = source.rotation_euler.copy()
        display.scale = source.scale.copy()
        place_on_preview_ground(
            display,
            x + fx * 0.5,
            y_position,
            clearance=0.015
        )
        x += fx + 0.45
        max_depth = max(max_depth, fy)

    # Shelf base.
    shelf = box_bottom_center(
        f"{ASSET_PREFIX}_HERO_SHELF_BASE",
        max(x, 8.0),
        max_depth + 0.7,
        0.10,
        shelf_coll,
        bpy.data.materials["MAT_STEEL_STRUCTURAL"],
        "DISPLAY_GROUND",
        "STOCKYARD",
        bevel=0.015,
        notes="Display-only hero shelf."
    )
    shelf.location = (max(x, 8.0) * 0.5, y_position, -0.12)
    shelf["spk_display_only"] = True
    return max_depth + 1.8


def validate_stockyard(categories):
    report = []
    passed = 0
    failed = 0

    for data in categories.values():
        for obj in data["objects"]:
            issues = []

            if not obj.name.startswith(f"{ASSET_PREFIX}_"):
                issues.append("name prefix")

            if obj.type == 'MESH' and len(obj.data.materials) == 0:
                issues.append("material missing")
            if obj.type == 'EMPTY' and obj.get("spk_asset_type") != "PLACEHOLDER_SOCKET":
                issues.append("empty missing socket type")

            if any(abs(s - 1.0) > 1e-5 for s in obj.scale):
                issues.append(f"scale={tuple(round(v, 5) for v in obj.scale)}")

            if any(abs(r) > 1e-5 for r in obj.rotation_euler):
                issues.append("unapplied rotation")

            if "spk_asset_type" not in obj:
                issues.append("metadata missing")

            if obj.type == 'MESH':
                axis_standard = obj.get("spk_axis_standard", "")
                coords = [v.co for v in obj.data.vertices]
                if coords:
                    local_min_x = min(v.x for v in coords)
                    local_min_z = min(v.z for v in coords)
                    local_max_x = max(v.x for v in coords)
                    local_max_z = max(v.z for v in coords)

                    if "+X length; endpoint pivot" in axis_standard:
                        if abs(local_min_x) > 1e-4 or local_max_x <= 0.0:
                            issues.append("broken +X endpoint pivot")

                    if "+Z height; bottom-center pivot" in axis_standard:
                        if abs(local_min_z) > 1e-4 or local_max_z <= 0.0:
                            issues.append("broken +Z bottom pivot")

            if obj.type == 'MESH':
                # Construction pivots should generally touch or closely approach
                # one side of the mesh bounding box rather than float centrally.
                coords = [v.co for v in obj.data.vertices]
                if coords:
                    mins = Vector((
                        min(v.x for v in coords),
                        min(v.y for v in coords),
                        min(v.z for v in coords),
                    ))
                    maxs = Vector((
                        max(v.x for v in coords),
                        max(v.y for v in coords),
                        max(v.z for v in coords),
                    ))
                    near_boundary = (
                        abs(mins.x) < 1e-4 or abs(maxs.x) < 1e-4 or
                        abs(mins.y) < 1e-4 or abs(maxs.y) < 1e-4 or
                        abs(mins.z) < 1e-4 or abs(maxs.z) < 1e-4
                    )
                    if not near_boundary:
                        issues.append("pivot not on construction boundary")

            if issues:
                failed += 1
                report.append(f"FAIL  {obj.name}: " + ", ".join(issues))
                obj["spk_validation"] = "FAIL: " + ", ".join(issues)
            else:
                passed += 1
                report.append(f"PASS  {obj.name}")
                obj["spk_validation"] = "PASS"

    summary = [
        "SHANTYPUNK STOCKYARD VALIDATION",
        "=" * 72,
        f"Passed: {passed}",
        f"Failed: {failed}",
        "",
    ] + report

    text_name = f"{ASSET_PREFIX}_VALIDATION_REPORT"
    datablock = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
    datablock.clear()
    datablock.write("\n".join(summary))
    print("\n".join(summary[:5]))
    return passed, failed


# -----------------------------------------------------------------------------
# STOCKYARD LAYOUT
# -----------------------------------------------------------------------------

def place_on_preview_ground(obj, x, y, clearance=PREVIEW_GROUND_CLEARANCE):
    """
    Place an asset for stockyard display without changing its authored mesh,
    origin, rotation, or scale.

    The object's evaluated world-space bounding box is measured after its X/Y
    preview placement. Object Location Z is then raised just enough that the
    lowest evaluated point sits above Z=0 by `clearance`.

    Alt-G still returns the object to its true construction/export pivot at
    world 0,0,0.
    """
    obj.location = (x, y, 0.0)
    bpy.context.view_layer.update()

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)

    if obj.type == 'EMPTY':
        obj.location.z = max(clearance, obj.empty_display_size)
    elif evaluated.bound_box:
        world_corners = [
            evaluated.matrix_world @ Vector(corner)
            for corner in evaluated.bound_box
        ]
        min_world_z = min(corner.z for corner in world_corners)
        obj.location.z += clearance - min_world_z
    else:
        obj.location.z = clearance

    bpy.context.view_layer.update()
    obj["spk_preview_ground_clearance"] = clearance
    obj["spk_preview_location"] = tuple(obj.location)
    obj["spk_export_instruction"] = (
        "Preview transform only. Select object and press Alt-G "
        "to return to its authored construction/export pivot at world origin."
    )
    return obj.location.z


def object_stockyard_footprint(obj):
    """
    Return a compact but readable XY footprint for stockyard packing.
    Empties receive a small standardized footprint.
    """
    if obj.type == 'EMPTY':
        size = max(obj.empty_display_size * 2.2, MIN_FOOTPRINT_X)
        return size, max(size, MIN_FOOTPRINT_Y * 0.65)

    dims = obj.dimensions
    footprint_x = max(abs(dims.x), MIN_FOOTPRINT_X)
    footprint_y = max(abs(dims.y), MIN_FOOTPRINT_Y)
    return footprint_x, footprint_y


def layout_stockyard(categories, root):
    """
    Compact aisle layout.

    Each category forms a readable aisle with an upright placard and a narrow
    material-colored strip. Small assets are tightly packed; large assets reserve
    only their real footprint. Object Location is the only display transform.
    """
    hero_depth = create_hero_shelf(root, categories, y_position=0.0)
    current_y = -(hero_depth + HERO_SHELF_GAP)

    used_max_x = 0.0
    used_min_y = current_y

    material_cycle = [
        "MAT_WOOD_STRUCTURAL",
        "MAT_METAL_GALVANIZED",
        "MAT_CONCRETE",
        "MAT_STEEL_STRUCTURAL",
        "MAT_PLASTIC",
        "MAT_CLOTH_TARP",
    ]

    for category_index, cat_key in enumerate(sorted(categories.keys())):
        data = categories[cat_key]
        objects = data["objects"]

        aisle_top = current_y
        create_text_label(
            data["label"],
            (0.0, aisle_top + LABEL_GAP, 0.03),
            root,
            size=0.40,
            upright=True
        )

        # Colored aisle marker.
        strip = box_bottom_center(
            f"{ASSET_PREFIX}_AISLE_STRIP_{cat_key}",
            STOCKYARD_MAX_ROW_WIDTH,
            AISLE_STRIP_DEPTH,
            0.025,
            root,
            bpy.data.materials[material_cycle[category_index % len(material_cycle)]],
            "DISPLAY_GROUND",
            "STOCKYARD",
            bevel=0.0,
            notes="Display-only category aisle marker."
        )
        strip.location = (
            STOCKYARD_MAX_ROW_WIDTH * 0.5,
            aisle_top + 0.12,
            -0.035
        )
        strip["spk_display_only"] = True

        cursor_x = AISLE_HEADER_WIDTH
        row_y = current_y
        row_depth = MIN_FOOTPRINT_Y

        for obj in objects:
            footprint_x, footprint_y = object_stockyard_footprint(obj)

            if cursor_x > AISLE_HEADER_WIDTH and (
                cursor_x + footprint_x > STOCKYARD_MAX_ROW_WIDTH
            ):
                row_y -= row_depth + ASSET_PADDING_Y
                cursor_x = AISLE_HEADER_WIDTH
                row_depth = MIN_FOOTPRINT_Y

            x = cursor_x + footprint_x * 0.5
            y = row_y

            place_on_preview_ground(obj, x, y)
            obj["spk_stockyard_location"] = tuple(obj.location)

            cursor_x += footprint_x + ASSET_PADDING_X
            row_depth = max(row_depth, footprint_y)
            used_max_x = max(used_max_x, cursor_x)
            used_min_y = min(used_min_y, row_y - row_depth)

        current_y = row_y - row_depth - CATEGORY_GAP

    total_height = abs(used_min_y) + hero_depth + CATEGORY_GAP
    total_width = max(used_max_x, STOCKYARD_MAX_ROW_WIDTH)

    ground = box_bottom_center(
        f"{ASSET_PREFIX}_STOCKYARD_GROUND",
        total_width + 1.5,
        total_height + 1.5,
        0.04,
        root,
        bpy.data.materials["MAT_CONCRETE"],
        "DISPLAY_GROUND",
        "STOCKYARD",
        bevel=0.0,
        notes="Display-only ground; do not export."
    )
    ground.location = (
        total_width * 0.5,
        used_min_y * 0.5 + hero_depth * 0.5,
        -0.07
    )
    ground.hide_render = True
    ground.display_type = 'WIRE'
    ground["spk_display_only"] = True
    ground["spk_preview_ground_exempt"] = True

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    origin = bpy.context.object
    origin.name = f"{ASSET_PREFIX}_EXPORT_ORIGIN"
    origin.empty_display_size = 1.0
    move_to_collection(origin, root)

    return {
        "width": total_width,
        "height": total_height,
        "center_x": total_width * 0.5,
        "center_y": used_min_y * 0.5 + hero_depth * 0.5,
    }


# -----------------------------------------------------------------------------
# OPTIONAL CAMERA SETUP
# -----------------------------------------------------------------------------

def create_overview_camera(root, bounds):
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = f"{ASSET_PREFIX}_STOCKYARD_CAMERA"
    move_to_collection(cam, root)

    center_x = bounds["center_x"]
    center_y = bounds["center_y"]
    scene_span = max(bounds["width"], bounds["height"])
    cam.location = (
        center_x,
        center_y - max(24.0, scene_span * 0.42),
        max(28.0, scene_span * 0.50)
    )

    target = Vector((center_x, center_y, 0))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 48
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type='AREA', location=(center_x, center_y - 5, 28))
    key = bpy.context.object
    key.name = f"{ASSET_PREFIX}_STOCKYARD_KEY"
    key.data.energy = 3500
    key.data.shape = 'DISK'
    key.data.size = 18
    key.rotation_euler = (0, 0, 0)
    direction = Vector((center_x, center_y, 0)) - key.location
    key.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    move_to_collection(key, root)


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    # Ensure metric internally while displaying imperial-friendly units.
    scene = bpy.context.scene
    scene.unit_settings.system = 'IMPERIAL'
    scene.unit_settings.length_unit = 'FEET'
    scene.unit_settings.scale_length = 1.0

    remove_collection_recursive(ROOT_COLLECTION)
    root = ensure_collection(ROOT_COLLECTION)
    root["spk_stockyard_version"] = "1.9"
    root["spk_generator"] = "SHANTYPUNK_MODULAR_STOCKYARD"
    mats = create_materials()

    categories = generate_assets(root, mats)
    stockyard_bounds = layout_stockyard(categories, root)

    # Final preview-ground safety pass. This affects only Object Location.
    for data in categories.values():
        for obj in data["objects"]:
            obj["spk_stockyard_version"] = "1.9"
            place_on_preview_ground(obj, obj.location.x, obj.location.y)
            obj["spk_stockyard_location"] = tuple(obj.location)

    create_overview_camera(root, stockyard_bounds)
    passed, failed = validate_stockyard(categories)

    # Select all generated exportable assets, excluding display helpers.
    bpy.ops.object.select_all(action='DESELECT')
    asset_count = 0
    for data in categories.values():
        for obj in data["objects"]:
            obj.select_set(True)
            asset_count += 1

    print("=" * 72)
    print(f"SHANTYPUNK STOCKYARD COMPLETE: {asset_count} modular assets generated.")
    print(f"Validation: {passed} passed, {failed} flagged.")
    print("v1.9: added reusable opening, storefront, dock, foundation, flashing, and trim proxies.")
    print("To export an asset at its construction origin: select it and press Alt-G.")
    print(f"UV target metadata: {TEXEL_DENSITY_PX_PER_M} px/m on {TEXTURE_TARGET} sets.")
    print("=" * 72)


if __name__ == "__main__":
    main()
