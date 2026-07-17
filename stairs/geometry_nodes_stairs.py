"""Create a procedural flight of stairs with Blender Geometry Nodes.

Designed for Blender 4.0+. Run this file from Blender's Scripting workspace.
The script uses the active mesh object, or creates one when necessary.
"""

import bpy


NODE_GROUP_NAME = "GN_Procedural_Stairs"
MODIFIER_NAME = "Procedural Stairs"


def new_interface_socket(node_group, name, in_out, socket_type, **kwargs):
    """Create and configure a Blender 4.x node-group interface socket."""
    socket = node_group.interface.new_socket(
        name=name, in_out=in_out, socket_type=socket_type
    )
    for attribute, value in kwargs.items():
        if hasattr(socket, attribute):
            setattr(socket, attribute, value)
    return socket


def make_stair_node_group():
    """Build the complete Geometry Nodes graph and return it."""
    old_group = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if old_group:
        bpy.data.node_groups.remove(old_group, do_unlink=True)

    group = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")
    # Blender 5.x requires this flag for interface sockets to become live
    # per-object controls in a Geometry Nodes modifier.
    if hasattr(group, "is_modifier"):
        group.is_modifier = True

    # Modifier controls, in the order they appear in Blender's modifier panel.
    new_interface_socket(group, "Geometry", "OUTPUT", "NodeSocketGeometry")
    new_interface_socket(
        group, "Step Count", "INPUT", "NodeSocketInt",
        default_value=12, min_value=1, max_value=200, force_non_field=True,
        description="Number of stair treads"
    )
    new_interface_socket(
        group, "Width", "INPUT", "NodeSocketFloat",
        default_value=2.0, min_value=0.01, max_value=100.0,
        force_non_field=True,
        description="Overall stair width"
    )
    new_interface_socket(
        group, "Rise (in)", "INPUT", "NodeSocketFloat",
        default_value=7.5, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Vertical distance between steps, entered in inches"
    )
    new_interface_socket(
        group, "Run (in)", "INPUT", "NodeSocketFloat",
        default_value=10.0, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Horizontal tread depth, entered in inches"
    )
    new_interface_socket(
        group, "Tread Thickness (in)", "INPUT", "NodeSocketFloat",
        default_value=1.5, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Tread slab thickness, entered in inches"
    )
    new_interface_socket(
        group, "Railings", "INPUT", "NodeSocketBool",
        default_value=True, force_non_field=True,
        description="Show posts and handrails on both sides"
    )
    new_interface_socket(
        group, "Left Railing", "INPUT", "NodeSocketBool",
        default_value=True, force_non_field=True,
        description="Show the left railing when looking up the stairs"
    )
    new_interface_socket(
        group, "Right Railing", "INPUT", "NodeSocketBool",
        default_value=True, force_non_field=True,
        description="Show the right railing when looking up the stairs"
    )
    new_interface_socket(
        group, "Railing Spacing (in)", "INPUT", "NodeSocketFloat",
        default_value=48.0, min_value=1.0, max_value=1000.0,
        force_non_field=True,
        description="Desired post spacing; posts snap to the nearest tread center"
    )
    new_interface_socket(
        group, "Lower Overhang (in)", "INPUT", "NodeSocketFloat",
        default_value=4.0, min_value=0.0, max_value=120.0,
        force_non_field=True,
        description="Handrail extension beyond the lower ground post"
    )
    new_interface_socket(
        group, "Upper Landing Bays", "INPUT", "NodeSocketInt",
        default_value=0, min_value=0, max_value=3,
        force_non_field=True,
        description="Number of horizontal railing bays beyond the upper tread"
    )
    new_interface_socket(
        group, "Railings Outside Stringers", "INPUT", "NodeSocketBool",
        default_value=False, force_non_field=True,
        description="Mount railings outside the stringers instead of on the treads"
    )
    new_interface_socket(
        group, "Outside Clearance (in)", "INPUT", "NodeSocketFloat",
        default_value=0.5, min_value=0.0, max_value=120.0,
        force_non_field=True,
        description="Gap between an outside railing and its stringer or tread edge"
    )
    new_interface_socket(
        group, "Outside Rails Require Stringers", "INPUT", "NodeSocketBool",
        default_value=True, force_non_field=True,
        description="Hide outside railings when stringers are switched off"
    )
    new_interface_socket(
        group, "Stringers", "INPUT", "NodeSocketBool",
        default_value=False, force_non_field=True,
        description="Show two sloped stringers"
    )
    new_interface_socket(
        group, "Stringer Thickness (in)", "INPUT", "NodeSocketFloat",
        default_value=1.5, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Side-to-side stringer thickness"
    )
    new_interface_socket(
        group, "Stringer Height (in)", "INPUT", "NodeSocketFloat",
        default_value=11.25, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Vertical depth of each sloped stringer"
    )
    new_interface_socket(
        group, "Stringer Inset (in)", "INPUT", "NodeSocketFloat",
        default_value=0.0, min_value=0.0, max_value=1000.0,
        force_non_field=True,
        description="Pull both stringers inward from the tread edges toward center"
    )
    new_interface_socket(
        group, "Sawtooth Supports", "INPUT", "NodeSocketBool",
        default_value=False, force_non_field=True,
        description="Show stepped supports on both sides"
    )
    new_interface_socket(
        group, "Sawtooth Thickness (in)", "INPUT", "NodeSocketFloat",
        default_value=1.5, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Side-to-side thickness of each sawtooth support"
    )
    new_interface_socket(
        group, "Sawtooth Width (in)", "INPUT", "NodeSocketFloat",
        default_value=11.25, min_value=0.01, max_value=1000.0,
        force_non_field=True,
        description="Vertical board width below the tread profile"
    )

    nodes = group.nodes
    links = group.links
    nodes.clear()

    group_in = nodes.new("NodeGroupInput")
    group_in.name = "Stair Controls"
    group_in.label = "Stair Controls"
    group_in.location = (-900, 100)

    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (650, 100)

    mesh_line = nodes.new("GeometryNodeMeshLine")
    mesh_line.name = "Step Points"
    mesh_line.label = "One Point Per Step"
    mesh_line.mode = "OFFSET"
    mesh_line.location = (-620, 220)

    step_offset = nodes.new("ShaderNodeCombineXYZ")
    step_offset.name = "Step Offset"
    step_offset.label = "Run and Rise"
    step_offset.location = (-620, -80)

    run_inches = nodes.new("ShaderNodeMath")
    run_inches.name = "Run Inches to Meters"
    run_inches.label = "in to m"
    run_inches.operation = "MULTIPLY"
    run_inches.inputs[1].default_value = 0.0254
    run_inches.location = (-860, -180)

    rise_inches = nodes.new("ShaderNodeMath")
    rise_inches.name = "Rise Inches to Meters"
    rise_inches.label = "in to m"
    rise_inches.operation = "MULTIPLY"
    rise_inches.inputs[1].default_value = 0.0254
    rise_inches.location = (-860, -300)

    thickness_inches = nodes.new("ShaderNodeMath")
    thickness_inches.name = "Thickness Inches to Meters"
    thickness_inches.label = "in to m"
    thickness_inches.operation = "MULTIPLY"
    thickness_inches.inputs[1].default_value = 0.0254
    thickness_inches.location = (-620, -390)

    cube_size = nodes.new("ShaderNodeCombineXYZ")
    cube_size.name = "Tread Dimensions"
    cube_size.location = (-330, -210)

    tread = nodes.new("GeometryNodeMeshCube")
    tread.name = "Tread"
    tread.location = (-80, -190)

    instances = nodes.new("GeometryNodeInstanceOnPoints")
    instances.name = "Place Treads"
    instances.location = (170, 180)

    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (430, 180)

    # Point spacing: the flight travels along +Y and rises along +Z.
    links.new(group_in.outputs["Step Count"], mesh_line.inputs["Count"])
    links.new(group_in.outputs["Run (in)"], run_inches.inputs[0])
    links.new(group_in.outputs["Rise (in)"], rise_inches.inputs[0])
    links.new(group_in.outputs["Tread Thickness (in)"], thickness_inches.inputs[0])
    links.new(run_inches.outputs[0], step_offset.inputs["Y"])
    links.new(rise_inches.outputs[0], step_offset.inputs["Z"])
    links.new(step_offset.outputs["Vector"], mesh_line.inputs["Offset"])

    # A generated cube becomes the tread slab copied onto each point.
    links.new(group_in.outputs["Width"], cube_size.inputs["X"])
    links.new(run_inches.outputs[0], cube_size.inputs["Y"])
    links.new(thickness_inches.outputs[0], cube_size.inputs["Z"])
    links.new(cube_size.outputs["Vector"], tread.inputs["Size"])

    links.new(mesh_line.outputs["Mesh"], instances.inputs["Points"])
    links.new(tread.outputs["Mesh"], instances.inputs["Instance"])
    links.new(instances.outputs["Instances"], realize.inputs["Geometry"])

    # ------------------------------------------------------------------
    # Optional construction systems
    # ------------------------------------------------------------------
    def math_node(name, operation, x, y):
        node = nodes.new("ShaderNodeMath")
        node.name = name
        node.label = name
        node.operation = operation
        node.location = (x, y)
        return node

    def inch_converter(socket_name, x, y):
        node = math_node(socket_name + " to Meters", "MULTIPLY", x, y)
        node.inputs[1].default_value = 0.0254
        links.new(group_in.outputs[socket_name], node.inputs[0])
        return node

    def geometry_switch(name, control_name, geometry, x, y):
        node = nodes.new("GeometryNodeSwitch")
        node.name = name
        node.label = name
        node.input_type = "GEOMETRY"
        node.location = (x, y)
        links.new(group_in.outputs[control_name], node.inputs["Switch"])
        links.new(geometry, node.inputs["True"])
        return node

    def transformed_copy(name, geometry, translation, rotation, x, y):
        node = nodes.new("GeometryNodeTransform")
        node.name = name
        node.label = name
        node.location = (x, y)
        links.new(geometry, node.inputs["Geometry"])
        if translation is not None:
            links.new(translation, node.inputs["Translation"])
        if rotation is not None:
            links.new(rotation, node.inputs["Rotation"])
        return node

    # Shared flight dimensions.
    count_minus_one = math_node("Last Step Index", "SUBTRACT", -360, -520)
    count_minus_one.inputs[1].default_value = 1.0
    links.new(group_in.outputs["Step Count"], count_minus_one.inputs[0])

    total_run = math_node("Flight Run", "MULTIPLY", -120, -500)
    links.new(count_minus_one.outputs[0], total_run.inputs[0])
    links.new(run_inches.outputs[0], total_run.inputs[1])

    total_rise = math_node("Flight Rise", "MULTIPLY", -120, -620)
    links.new(count_minus_one.outputs[0], total_rise.inputs[0])
    links.new(rise_inches.outputs[0], total_rise.inputs[1])

    half_width = math_node("Half Stair Width", "MULTIPLY", -360, -760)
    half_width.inputs[1].default_value = 0.5
    links.new(group_in.outputs["Width"], half_width.inputs[0])

    # Shared stringer placement also drives optional outside railings.
    stringer_thickness = inch_converter("Stringer Thickness (in)", -900, -1240)
    stringer_height = inch_converter("Stringer Height (in)", -900, -1340)
    stringer_inset = inch_converter("Stringer Inset (in)", -900, -1440)
    outside_clearance = inch_converter("Outside Clearance (in)", -900, -520)
    lower_overhang = inch_converter("Lower Overhang (in)", -900, -420)

    half_stringer_thickness = math_node("Half Stringer Thickness", "MULTIPLY", -620, -1430)
    half_stringer_thickness.inputs[1].default_value = 0.5
    links.new(stringer_thickness.outputs[0], half_stringer_thickness.inputs[0])
    stringer_edge_x = math_node("Stringer At Tread Edge", "SUBTRACT", -400, -1430)
    links.new(half_width.outputs[0], stringer_edge_x.inputs[0])
    links.new(half_stringer_thickness.outputs[0], stringer_edge_x.inputs[1])
    inset_stringer_x = math_node("Apply Stringer Inset", "SUBTRACT", -180, -1430)
    links.new(stringer_edge_x.outputs[0], inset_stringer_x.inputs[0])
    links.new(stringer_inset.outputs[0], inset_stringer_x.inputs[1])
    stringer_x = math_node("Clamp Stringers At Center", "MAXIMUM", 40, -1430)
    stringer_x.inputs[1].default_value = 0.0
    links.new(inset_stringer_x.outputs[0], stringer_x.inputs[0])

    # ----------------------------- Railings ----------------------------
    rail_spacing = inch_converter("Railing Spacing (in)", -900, -620)
    three_inches = 0.0762
    rail_height = 0.9144       # 36 inches above each tread.
    post_size = 0.0381         # 1.5-inch square posts.
    handrail_radius = 0.01905  # 1.5-inch diameter handrail.

    step_length = nodes.new("ShaderNodeVectorMath")
    step_length.name = "Distance Between Treads"
    step_length.operation = "LENGTH"
    step_length.location = (-620, -620)
    links.new(step_offset.outputs["Vector"], step_length.inputs[0])

    spacing_steps = math_node("Spacing in Treads", "DIVIDE", -390, -640)
    links.new(rail_spacing.outputs[0], spacing_steps.inputs[0])
    links.new(step_length.outputs["Value"], spacing_steps.inputs[1])
    rounded_spacing = math_node("Nearest Tread Interval", "ROUND", -170, -740)
    links.new(spacing_steps.outputs[0], rounded_spacing.inputs[0])
    safe_spacing = math_node("At Least One Tread", "MAXIMUM", 40, -740)
    safe_spacing.inputs[1].default_value = 1.0
    links.new(rounded_spacing.outputs[0], safe_spacing.inputs[0])

    index = nodes.new("GeometryNodeInputIndex")
    index.location = (-160, -850)
    modulo = math_node("Post Interval", "MODULO", 40, -850)
    links.new(index.outputs["Index"], modulo.inputs[0])
    links.new(safe_spacing.outputs[0], modulo.inputs[1])
    is_post = math_node("Use This Tread", "COMPARE", 250, -850)
    is_post.inputs[1].default_value = 0.0
    is_post.inputs[2].default_value = 0.001
    links.new(modulo.outputs[0], is_post.inputs[0])

    is_last_post = math_node("Always Use Last Tread", "COMPARE", 250, -760)
    is_last_post.inputs[2].default_value = 0.001
    links.new(index.outputs["Index"], is_last_post.inputs[0])
    links.new(count_minus_one.outputs[0], is_last_post.inputs[1])
    post_selection = nodes.new("FunctionNodeBooleanMath")
    post_selection.operation = "OR"
    post_selection.location = (460, -820)
    links.new(is_post.outputs[0], post_selection.inputs[0])
    links.new(is_last_post.outputs[0], post_selection.inputs[1])

    rail_inset = math_node("Inside Railing Position", "SUBTRACT", -120, -880)
    rail_inset.inputs[1].default_value = three_inches
    links.new(half_width.outputs[0], rail_inset.inputs[0])
    outside_stringer_x = math_node("Outside Stringer Face", "ADD", -120, -960)
    links.new(stringer_x.outputs[0], outside_stringer_x.inputs[0])
    links.new(half_stringer_thickness.outputs[0], outside_stringer_x.inputs[1])
    outside_stringer_clearance_x = math_node("Outside Stringer Clearance", "ADD", 90, -1000)
    links.new(outside_stringer_x.outputs[0], outside_stringer_clearance_x.inputs[0])
    links.new(outside_clearance.outputs[0], outside_stringer_clearance_x.inputs[1])
    outside_tread_x = math_node("Outside Tread Clearance", "ADD", -120, -1040)
    links.new(half_width.outputs[0], outside_tread_x.inputs[0])
    links.new(outside_clearance.outputs[0], outside_tread_x.inputs[1])
    outside_source = nodes.new("GeometryNodeSwitch")
    outside_source.input_type = "FLOAT"
    outside_source.name = "Stringer or Tread Outside Position"
    outside_source.location = (300, -1030)
    links.new(group_in.outputs["Stringers"], outside_source.inputs["Switch"])
    links.new(outside_tread_x.outputs[0], outside_source.inputs["False"])
    links.new(outside_stringer_clearance_x.outputs[0], outside_source.inputs["True"])
    rail_position = nodes.new("GeometryNodeSwitch")
    rail_position.input_type = "FLOAT"
    rail_position.name = "Inside or Outside Rail Position"
    rail_position.location = (500, -960)
    links.new(group_in.outputs["Railings Outside Stringers"], rail_position.inputs["Switch"])
    links.new(rail_inset.outputs[0], rail_position.inputs["False"])
    links.new(outside_source.outputs["Output"], rail_position.inputs["True"])
    negative_rail_inset = math_node("Opposite Railing Inset", "MULTIPLY", 90, -960)
    negative_rail_inset.inputs[1].default_value = -1.0
    links.new(rail_position.outputs["Output"], negative_rail_inset.inputs[0])

    post_bottom_offset = math_node("Post Center Height", "MULTIPLY", 40, -1070)
    post_bottom_offset.inputs[1].default_value = 0.5
    post_height_plus_tread = math_node("Post plus Tread", "ADD", -170, -1070)
    post_height_plus_tread.inputs[0].default_value = rail_height
    links.new(thickness_inches.outputs[0], post_height_plus_tread.inputs[1])
    links.new(post_height_plus_tread.outputs[0], post_bottom_offset.inputs[0])

    post_size_vector = nodes.new("ShaderNodeCombineXYZ")
    post_size_vector.location = (250, -1080)
    post_size_vector.inputs["X"].default_value = post_size
    post_size_vector.inputs["Y"].default_value = post_size
    post_size_vector.inputs["Z"].default_value = rail_height
    post_cube = nodes.new("GeometryNodeMeshCube")
    post_cube.location = (460, -1070)
    links.new(post_size_vector.outputs["Vector"], post_cube.inputs["Size"])

    post_translation_a = nodes.new("ShaderNodeCombineXYZ")
    post_translation_a.location = (250, -940)
    links.new(rail_position.outputs["Output"], post_translation_a.inputs["X"])
    links.new(post_bottom_offset.outputs[0], post_translation_a.inputs["Z"])
    post_translation_b = nodes.new("ShaderNodeCombineXYZ")
    post_translation_b.location = (250, -820)
    links.new(negative_rail_inset.outputs[0], post_translation_b.inputs["X"])
    links.new(post_bottom_offset.outputs[0], post_translation_b.inputs["Z"])
    post_a = transformed_copy("Right Post", post_cube.outputs["Mesh"], post_translation_a.outputs["Vector"], None, 670, -1000)
    post_b = transformed_copy("Left Post", post_cube.outputs["Mesh"], post_translation_b.outputs["Vector"], None, 670, -850)
    place_posts_a = nodes.new("GeometryNodeInstanceOnPoints")
    place_posts_a.name = "Right Stair Posts"
    place_posts_a.location = (880, -1000)
    links.new(mesh_line.outputs["Mesh"], place_posts_a.inputs["Points"])
    links.new(post_selection.outputs["Boolean"], place_posts_a.inputs["Selection"])
    links.new(post_a.outputs["Geometry"], place_posts_a.inputs["Instance"])
    place_posts_b = nodes.new("GeometryNodeInstanceOnPoints")
    place_posts_b.name = "Left Stair Posts"
    place_posts_b.location = (880, -850)
    links.new(mesh_line.outputs["Mesh"], place_posts_b.inputs["Points"])
    links.new(post_selection.outputs["Boolean"], place_posts_b.inputs["Selection"])
    links.new(post_b.outputs["Geometry"], place_posts_b.inputs["Instance"])

    rail_base_z = math_node("Handrail Start Height", "ADD", 250, -650)
    rail_base_z.inputs[0].default_value = rail_height
    half_tread_thickness = math_node("Half Tread Thickness", "MULTIPLY", 40, -620)
    half_tread_thickness.inputs[1].default_value = 0.5
    links.new(thickness_inches.outputs[0], half_tread_thickness.inputs[0])
    links.new(half_tread_thickness.outputs[0], rail_base_z.inputs[1])
    rail_end_z = math_node("Handrail End Height", "ADD", 460, -650)
    links.new(total_rise.outputs[0], rail_end_z.inputs[0])
    links.new(rail_base_z.outputs[0], rail_end_z.inputs[1])
    step_slope = math_node("Rise Run Slope", "DIVIDE", 250, -500)
    links.new(rise_inches.outputs[0], step_slope.inputs[0])
    links.new(run_inches.outputs[0], step_slope.inputs[1])
    overhang_drop = math_node("Lower Overhang Drop", "MULTIPLY", 460, -500)
    links.new(lower_overhang.outputs[0], overhang_drop.inputs[0])
    links.new(step_slope.outputs[0], overhang_drop.inputs[1])
    rail_start_z = math_node("Lower Overhang Height", "SUBTRACT", 670, -500)
    links.new(rail_base_z.outputs[0], rail_start_z.inputs[0])
    links.new(overhang_drop.outputs[0], rail_start_z.inputs[1])
    negative_overhang = math_node("Lower Overhang Back", "MULTIPLY", 460, -420)
    negative_overhang.inputs[1].default_value = -1.0
    links.new(lower_overhang.outputs[0], negative_overhang.inputs[0])
    rail_start = nodes.new("ShaderNodeCombineXYZ")
    rail_start.location = (460, -560)
    links.new(negative_overhang.outputs[0], rail_start.inputs["Y"])
    links.new(rail_start_z.outputs[0], rail_start.inputs["Z"])
    rail_end = nodes.new("ShaderNodeCombineXYZ")
    rail_end.location = (670, -560)
    links.new(total_run.outputs[0], rail_end.inputs["Y"])
    links.new(rail_end_z.outputs[0], rail_end.inputs["Z"])
    rail_curve = nodes.new("GeometryNodeCurvePrimitiveLine")
    rail_curve.mode = "POINTS"
    rail_curve.location = (880, -580)
    links.new(rail_start.outputs["Vector"], rail_curve.inputs["Start"])
    links.new(rail_end.outputs["Vector"], rail_curve.inputs["End"])
    rail_profile = nodes.new("GeometryNodeCurvePrimitiveCircle")
    rail_profile.mode = "RADIUS"
    rail_profile.location = (880, -420)
    rail_profile.inputs["Resolution"].default_value = 8
    rail_profile.inputs["Radius"].default_value = handrail_radius
    rail_mesh = nodes.new("GeometryNodeCurveToMesh")
    rail_mesh.location = (1090, -520)
    links.new(rail_curve.outputs["Curve"], rail_mesh.inputs["Curve"])
    links.new(rail_profile.outputs["Curve"], rail_mesh.inputs["Profile Curve"])
    rail_translation_a = nodes.new("ShaderNodeCombineXYZ")
    rail_translation_a.location = (1090, -380)
    links.new(rail_position.outputs["Output"], rail_translation_a.inputs["X"])
    rail_translation_b = nodes.new("ShaderNodeCombineXYZ")
    rail_translation_b.location = (1090, -290)
    links.new(negative_rail_inset.outputs[0], rail_translation_b.inputs["X"])
    handrail_a = transformed_copy("Right Handrail", rail_mesh.outputs["Mesh"], rail_translation_a.outputs["Vector"], None, 1300, -500)
    handrail_b = transformed_copy("Left Handrail", rail_mesh.outputs["Mesh"], rail_translation_b.outputs["Vector"], None, 1300, -350)

    # Lower end posts extend all the way to the ground at the first tread.
    ground_post_size = nodes.new("ShaderNodeCombineXYZ")
    ground_post_size.location = (1090, -1160)
    ground_post_size.inputs["X"].default_value = post_size
    ground_post_size.inputs["Y"].default_value = post_size
    links.new(rail_base_z.outputs[0], ground_post_size.inputs["Z"])
    ground_post_cube = nodes.new("GeometryNodeMeshCube")
    ground_post_cube.location = (1300, -1160)
    links.new(ground_post_size.outputs["Vector"], ground_post_cube.inputs["Size"])
    ground_half_z = math_node("Ground Post Center", "MULTIPLY", 880, -1160)
    ground_half_z.inputs[1].default_value = 0.5
    links.new(rail_base_z.outputs[0], ground_half_z.inputs[0])
    ground_pos_a = nodes.new("ShaderNodeCombineXYZ")
    ground_pos_a.location = (1300, -1050)
    links.new(rail_position.outputs["Output"], ground_pos_a.inputs["X"])
    links.new(ground_half_z.outputs[0], ground_pos_a.inputs["Z"])
    ground_pos_b = nodes.new("ShaderNodeCombineXYZ")
    ground_pos_b.location = (1300, -950)
    links.new(negative_rail_inset.outputs[0], ground_pos_b.inputs["X"])
    links.new(ground_half_z.outputs[0], ground_pos_b.inputs["Z"])
    ground_post_a = transformed_copy("Right Ground Post", ground_post_cube.outputs["Mesh"], ground_pos_a.outputs["Vector"], None, 1510, -1080)
    ground_post_b = transformed_copy("Left Ground Post", ground_post_cube.outputs["Mesh"], ground_pos_b.outputs["Vector"], None, 1510, -930)

    # Optional horizontal guard bays at the upper floor.
    landing_length = math_node("Upper Landing Length", "MULTIPLY", 880, -1230)
    links.new(group_in.outputs["Upper Landing Bays"], landing_length.inputs[0])
    links.new(rail_spacing.outputs[0], landing_length.inputs[1])
    landing_end_y = math_node("Upper Landing End", "ADD", 1090, -1260)
    links.new(total_run.outputs[0], landing_end_y.inputs[0])
    links.new(landing_length.outputs[0], landing_end_y.inputs[1])
    landing_start_vector = nodes.new("ShaderNodeCombineXYZ")
    landing_start_vector.location = (1090, -1360)
    links.new(total_run.outputs[0], landing_start_vector.inputs["Y"])
    links.new(rail_end_z.outputs[0], landing_start_vector.inputs["Z"])
    landing_end_vector = nodes.new("ShaderNodeCombineXYZ")
    landing_end_vector.location = (1300, -1360)
    links.new(landing_end_y.outputs[0], landing_end_vector.inputs["Y"])
    links.new(rail_end_z.outputs[0], landing_end_vector.inputs["Z"])
    landing_curve = nodes.new("GeometryNodeCurvePrimitiveLine")
    landing_curve.mode = "POINTS"
    landing_curve.location = (1510, -1360)
    links.new(landing_start_vector.outputs["Vector"], landing_curve.inputs["Start"])
    links.new(landing_end_vector.outputs["Vector"], landing_curve.inputs["End"])
    landing_rail_mesh = nodes.new("GeometryNodeCurveToMesh")
    landing_rail_mesh.location = (1720, -1360)
    links.new(landing_curve.outputs["Curve"], landing_rail_mesh.inputs["Curve"])
    links.new(rail_profile.outputs["Curve"], landing_rail_mesh.inputs["Profile Curve"])
    landing_handrail_a = transformed_copy("Right Landing Handrail", landing_rail_mesh.outputs["Mesh"], rail_translation_a.outputs["Vector"], None, 1930, -1400)
    landing_handrail_b = transformed_copy("Left Landing Handrail", landing_rail_mesh.outputs["Mesh"], rail_translation_b.outputs["Vector"], None, 1930, -1250)

    first_landing_y = math_node("First Landing Post", "ADD", 880, -1490)
    links.new(total_run.outputs[0], first_landing_y.inputs[0])
    links.new(rail_spacing.outputs[0], first_landing_y.inputs[1])
    landing_point_start = nodes.new("ShaderNodeCombineXYZ")
    landing_point_start.location = (1090, -1490)
    links.new(first_landing_y.outputs[0], landing_point_start.inputs["Y"])
    links.new(total_rise.outputs[0], landing_point_start.inputs["Z"])
    landing_point_offset = nodes.new("ShaderNodeCombineXYZ")
    landing_point_offset.location = (1090, -1590)
    links.new(rail_spacing.outputs[0], landing_point_offset.inputs["Y"])
    landing_points = nodes.new("GeometryNodeMeshLine")
    landing_points.mode = "OFFSET"
    landing_points.location = (1300, -1510)
    links.new(group_in.outputs["Upper Landing Bays"], landing_points.inputs["Count"])
    links.new(landing_point_start.outputs["Vector"], landing_points.inputs["Start Location"])
    links.new(landing_point_offset.outputs["Vector"], landing_points.inputs["Offset"])
    landing_posts_a = nodes.new("GeometryNodeInstanceOnPoints")
    landing_posts_a.location = (1510, -1570)
    links.new(landing_points.outputs["Mesh"], landing_posts_a.inputs["Points"])
    links.new(post_a.outputs["Geometry"], landing_posts_a.inputs["Instance"])
    landing_posts_b = nodes.new("GeometryNodeInstanceOnPoints")
    landing_posts_b.location = (1510, -1720)
    links.new(landing_points.outputs["Mesh"], landing_posts_b.inputs["Points"])
    links.new(post_b.outputs["Geometry"], landing_posts_b.inputs["Instance"])
    has_landing = math_node("Has Upper Landing", "GREATER_THAN", 1300, -1810)
    has_landing.inputs[1].default_value = 0.0
    links.new(group_in.outputs["Upper Landing Bays"], has_landing.inputs[0])

    landing_right_join = nodes.new("GeometryNodeJoinGeometry")
    landing_right_join.location = (1930, -1580)
    links.new(landing_handrail_a.outputs["Geometry"], landing_right_join.inputs["Geometry"])
    links.new(landing_posts_a.outputs["Instances"], landing_right_join.inputs["Geometry"])
    landing_left_join = nodes.new("GeometryNodeJoinGeometry")
    landing_left_join.location = (1930, -1740)
    links.new(landing_handrail_b.outputs["Geometry"], landing_left_join.inputs["Geometry"])
    links.new(landing_posts_b.outputs["Instances"], landing_left_join.inputs["Geometry"])
    landing_right_switch = nodes.new("GeometryNodeSwitch")
    landing_right_switch.input_type = "GEOMETRY"
    landing_right_switch.location = (2140, -1580)
    links.new(has_landing.outputs[0], landing_right_switch.inputs["Switch"])
    links.new(landing_right_join.outputs["Geometry"], landing_right_switch.inputs["True"])
    landing_left_switch = nodes.new("GeometryNodeSwitch")
    landing_left_switch.input_type = "GEOMETRY"
    landing_left_switch.location = (2140, -1740)
    links.new(has_landing.outputs[0], landing_left_switch.inputs["Switch"])
    links.new(landing_left_join.outputs["Geometry"], landing_left_switch.inputs["True"])

    right_railing_join = nodes.new("GeometryNodeJoinGeometry")
    right_railing_join.location = (2360, -850)
    links.new(place_posts_a.outputs["Instances"], right_railing_join.inputs["Geometry"])
    links.new(handrail_a.outputs["Geometry"], right_railing_join.inputs["Geometry"])
    links.new(ground_post_a.outputs["Geometry"], right_railing_join.inputs["Geometry"])
    links.new(landing_right_switch.outputs["Output"], right_railing_join.inputs["Geometry"])
    left_railing_join = nodes.new("GeometryNodeJoinGeometry")
    left_railing_join.location = (2360, -1050)
    links.new(place_posts_b.outputs["Instances"], left_railing_join.inputs["Geometry"])
    links.new(handrail_b.outputs["Geometry"], left_railing_join.inputs["Geometry"])
    links.new(ground_post_b.outputs["Geometry"], left_railing_join.inputs["Geometry"])
    links.new(landing_left_switch.outputs["Output"], left_railing_join.inputs["Geometry"])

    right_side_switch = geometry_switch("Right Railing On Off", "Right Railing", right_railing_join.outputs["Geometry"], 2570, -850)
    left_side_switch = geometry_switch("Left Railing On Off", "Left Railing", left_railing_join.outputs["Geometry"], 2570, -1050)
    railing_join = nodes.new("GeometryNodeJoinGeometry")
    railing_join.location = (2780, -950)
    links.new(right_side_switch.outputs["Output"], railing_join.inputs["Geometry"])
    links.new(left_side_switch.outputs["Output"], railing_join.inputs["Geometry"])

    not_outside = nodes.new("FunctionNodeBooleanMath")
    not_outside.operation = "NOT"
    not_outside.location = (2360, -620)
    links.new(group_in.outputs["Railings Outside Stringers"], not_outside.inputs[0])
    not_require = nodes.new("FunctionNodeBooleanMath")
    not_require.operation = "NOT"
    not_require.location = (2360, -520)
    links.new(group_in.outputs["Outside Rails Require Stringers"], not_require.inputs[0])
    outside_allowed = nodes.new("FunctionNodeBooleanMath")
    outside_allowed.operation = "OR"
    outside_allowed.location = (2570, -570)
    links.new(group_in.outputs["Stringers"], outside_allowed.inputs[0])
    links.new(not_require.outputs["Boolean"], outside_allowed.inputs[1])
    placement_allowed = nodes.new("FunctionNodeBooleanMath")
    placement_allowed.operation = "OR"
    placement_allowed.location = (2780, -620)
    links.new(not_outside.outputs["Boolean"], placement_allowed.inputs[0])
    links.new(outside_allowed.outputs["Boolean"], placement_allowed.inputs[1])
    rail_master = nodes.new("FunctionNodeBooleanMath")
    rail_master.operation = "AND"
    rail_master.location = (2990, -620)
    links.new(group_in.outputs["Railings"], rail_master.inputs[0])
    links.new(placement_allowed.outputs["Boolean"], rail_master.inputs[1])
    railing_switch = nodes.new("GeometryNodeSwitch")
    railing_switch.input_type = "GEOMETRY"
    railing_switch.name = "Railings Master On Off"
    railing_switch.location = (3200, -850)
    links.new(rail_master.outputs["Boolean"], railing_switch.inputs["Switch"])
    links.new(railing_join.outputs["Geometry"], railing_switch.inputs["True"])

    # ----------------------------- Stringers ---------------------------
    flight_vector = nodes.new("ShaderNodeCombineXYZ")
    flight_vector.location = (-620, -1240)
    links.new(total_run.outputs[0], flight_vector.inputs["Y"])
    links.new(total_rise.outputs[0], flight_vector.inputs["Z"])
    flight_length = nodes.new("ShaderNodeVectorMath")
    flight_length.operation = "LENGTH"
    flight_length.location = (-400, -1240)
    links.new(flight_vector.outputs["Vector"], flight_length.inputs[0])
    stringer_size = nodes.new("ShaderNodeCombineXYZ")
    stringer_size.location = (-180, -1260)
    links.new(stringer_thickness.outputs[0], stringer_size.inputs["X"])
    links.new(flight_length.outputs["Value"], stringer_size.inputs["Y"])
    links.new(stringer_height.outputs[0], stringer_size.inputs["Z"])
    stringer_cube = nodes.new("GeometryNodeMeshCube")
    stringer_cube.location = (40, -1260)
    links.new(stringer_size.outputs["Vector"], stringer_cube.inputs["Size"])
    stringer_angle = math_node("Stringer Slope", "ARCTAN2", -180, -1400)
    links.new(total_rise.outputs[0], stringer_angle.inputs[0])
    links.new(total_run.outputs[0], stringer_angle.inputs[1])
    stringer_rotation = nodes.new("ShaderNodeCombineXYZ")
    stringer_rotation.location = (40, -1400)
    links.new(stringer_angle.outputs[0], stringer_rotation.inputs["X"])
    half_total_run = math_node("Half Flight Run", "MULTIPLY", -180, -1500)
    half_total_run.inputs[1].default_value = 0.5
    links.new(total_run.outputs[0], half_total_run.inputs[0])
    half_total_rise = math_node("Half Flight Rise", "MULTIPLY", -180, -1580)
    half_total_rise.inputs[1].default_value = 0.5
    links.new(total_rise.outputs[0], half_total_rise.inputs[0])
    half_stringer_height = math_node("Half Stringer Height", "MULTIPLY", 40, -1580)
    half_stringer_height.inputs[1].default_value = 0.5
    links.new(stringer_height.outputs[0], half_stringer_height.inputs[0])
    stringer_center_z = math_node("Stringer Below Treads", "SUBTRACT", 250, -1580)
    links.new(half_total_rise.outputs[0], stringer_center_z.inputs[0])
    links.new(half_stringer_height.outputs[0], stringer_center_z.inputs[1])
    negative_stringer_x = math_node("Opposite Stringer Edge", "MULTIPLY", 460, -1500)
    negative_stringer_x.inputs[1].default_value = -1.0
    links.new(stringer_x.outputs[0], negative_stringer_x.inputs[0])
    stringer_pos_a = nodes.new("ShaderNodeCombineXYZ")
    stringer_pos_a.location = (460, -1360)
    links.new(stringer_x.outputs[0], stringer_pos_a.inputs["X"])
    links.new(half_total_run.outputs[0], stringer_pos_a.inputs["Y"])
    links.new(stringer_center_z.outputs[0], stringer_pos_a.inputs["Z"])
    stringer_pos_b = nodes.new("ShaderNodeCombineXYZ")
    stringer_pos_b.location = (460, -1250)
    links.new(negative_stringer_x.outputs[0], stringer_pos_b.inputs["X"])
    links.new(half_total_run.outputs[0], stringer_pos_b.inputs["Y"])
    links.new(stringer_center_z.outputs[0], stringer_pos_b.inputs["Z"])
    stringer_a = transformed_copy("Right Stringer", stringer_cube.outputs["Mesh"], stringer_pos_a.outputs["Vector"], stringer_rotation.outputs["Vector"], 690, -1370)
    stringer_b = transformed_copy("Left Stringer", stringer_cube.outputs["Mesh"], stringer_pos_b.outputs["Vector"], stringer_rotation.outputs["Vector"], 690, -1220)
    stringer_join = nodes.new("GeometryNodeJoinGeometry")
    stringer_join.location = (920, -1300)
    links.new(stringer_a.outputs["Geometry"], stringer_join.inputs["Geometry"])
    links.new(stringer_b.outputs["Geometry"], stringer_join.inputs["Geometry"])
    stringer_switch = geometry_switch("Stringers On Off", "Stringers", stringer_join.outputs["Geometry"], 1150, -1300)

    # -------------------------- Sawtooth supports ----------------------
    saw_thickness = inch_converter("Sawtooth Thickness (in)", -900, -1740)
    saw_width = inch_converter("Sawtooth Width (in)", -900, -1840)
    saw_size = nodes.new("ShaderNodeCombineXYZ")
    saw_size.location = (-620, -1760)
    links.new(saw_thickness.outputs[0], saw_size.inputs["X"])
    links.new(run_inches.outputs[0], saw_size.inputs["Y"])
    links.new(saw_width.outputs[0], saw_size.inputs["Z"])
    saw_cube = nodes.new("GeometryNodeMeshCube")
    saw_cube.location = (-400, -1760)
    links.new(saw_size.outputs["Vector"], saw_cube.inputs["Size"])
    saw_drop_sum = math_node("Sawtooth Below Tread", "ADD", -620, -1920)
    links.new(saw_width.outputs[0], saw_drop_sum.inputs[0])
    links.new(thickness_inches.outputs[0], saw_drop_sum.inputs[1])
    saw_drop_half = math_node("Sawtooth Center Drop", "MULTIPLY", -400, -1920)
    saw_drop_half.inputs[1].default_value = -0.5
    links.new(saw_drop_sum.outputs[0], saw_drop_half.inputs[0])
    saw_local_position = nodes.new("ShaderNodeCombineXYZ")
    saw_local_position.location = (-180, -1920)
    links.new(saw_drop_half.outputs[0], saw_local_position.inputs["Z"])
    positioned_saw = transformed_copy("Support Below Tread", saw_cube.outputs["Mesh"], saw_local_position.outputs["Vector"], None, 40, -1760)
    saw_instances = nodes.new("GeometryNodeInstanceOnPoints")
    saw_instances.location = (270, -1760)
    links.new(mesh_line.outputs["Mesh"], saw_instances.inputs["Points"])
    links.new(positioned_saw.outputs["Geometry"], saw_instances.inputs["Instance"])
    half_saw_thickness = math_node("Half Sawtooth Thickness", "MULTIPLY", -180, -2080)
    half_saw_thickness.inputs[1].default_value = 0.5
    links.new(saw_thickness.outputs[0], half_saw_thickness.inputs[0])
    saw_x = math_node("Sawtooth Edge Position", "SUBTRACT", 40, -2080)
    links.new(half_width.outputs[0], saw_x.inputs[0])
    links.new(half_saw_thickness.outputs[0], saw_x.inputs[1])
    negative_saw_x = math_node("Opposite Sawtooth Edge", "MULTIPLY", 270, -2080)
    negative_saw_x.inputs[1].default_value = -1.0
    links.new(saw_x.outputs[0], negative_saw_x.inputs[0])
    saw_pos_a = nodes.new("ShaderNodeCombineXYZ")
    saw_pos_a.location = (500, -1980)
    links.new(saw_x.outputs[0], saw_pos_a.inputs["X"])
    saw_pos_b = nodes.new("ShaderNodeCombineXYZ")
    saw_pos_b.location = (500, -2080)
    links.new(negative_saw_x.outputs[0], saw_pos_b.inputs["X"])
    saw_a = transformed_copy("Right Sawtooth", saw_instances.outputs["Instances"], saw_pos_a.outputs["Vector"], None, 720, -1900)
    saw_b = transformed_copy("Left Sawtooth", saw_instances.outputs["Instances"], saw_pos_b.outputs["Vector"], None, 720, -2070)
    saw_join = nodes.new("GeometryNodeJoinGeometry")
    saw_join.location = (950, -1980)
    links.new(saw_a.outputs["Geometry"], saw_join.inputs["Geometry"])
    links.new(saw_b.outputs["Geometry"], saw_join.inputs["Geometry"])
    saw_switch = geometry_switch("Sawtooth On Off", "Sawtooth Supports", saw_join.outputs["Geometry"], 1180, -1980)

    final_join = nodes.new("GeometryNodeJoinGeometry")
    final_join.name = "Assemble Stair System"
    final_join.location = (1960, 100)
    links.new(realize.outputs["Geometry"], final_join.inputs["Geometry"])
    links.new(railing_switch.outputs["Output"], final_join.inputs["Geometry"])
    links.new(stringer_switch.outputs["Output"], final_join.inputs["Geometry"])
    links.new(saw_switch.outputs["Output"], final_join.inputs["Geometry"])
    links.new(final_join.outputs["Geometry"], group_out.inputs["Geometry"])

    group_out.location = (2180, 100)

    # Keep the graph readable when opened in the Geometry Nodes editor.
    for node in nodes:
        node.select = False
    group_in.select = True
    nodes.active = group_in

    return group


def get_or_create_target_object():
    """Return the active mesh object, creating an empty mesh object if needed."""
    active = bpy.context.active_object
    if active and active.type == "MESH":
        return active

    mesh = bpy.data.meshes.new("Procedural_Stairs_Mesh")
    obj = bpy.data.objects.new("Procedural Stairs", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def capture_modifier_inputs(modifier):
    """Remember existing Blender 5.x modifier values by their visible names."""
    saved = {}
    group = getattr(modifier, "node_group", None) if modifier else None
    property_inputs = getattr(getattr(modifier, "properties", None), "inputs", None)
    if not group or property_inputs is None:
        return saved
    for item in group.interface.items_tree:
        if getattr(item, "item_type", "") != "SOCKET" or item.in_out != "INPUT":
            continue
        value_holder = getattr(property_inputs, item.identifier, None)
        if value_holder is not None and hasattr(value_holder, "value"):
            saved[item.name] = value_holder.value
    return saved


def restore_modifier_inputs(modifier, saved):
    """Restore values whose controls still exist in the rebuilt node group."""
    group = modifier.node_group
    property_inputs = modifier.properties.inputs
    for item in group.interface.items_tree:
        if item.name not in saved or getattr(item, "in_out", "") != "INPUT":
            continue
        value_holder = getattr(property_inputs, item.identifier, None)
        if value_holder is not None and hasattr(value_holder, "value"):
            value_holder.value = saved[item.name]


def install_stair_generator():
    obj = get_or_create_target_object()

    # Rerunning updates the existing named modifier instead of stacking copies.
    modifier = obj.modifiers.get(MODIFIER_NAME)
    saved_inputs = capture_modifier_inputs(modifier)
    if modifier and modifier.type != "NODES":
        obj.modifiers.remove(modifier)
        modifier = None
    if modifier is None:
        modifier = obj.modifiers.new(MODIFIER_NAME, "NODES")

    modifier.node_group = make_stair_node_group()
    restore_modifier_inputs(modifier, saved_inputs)
    obj.update_tag(refresh={"OBJECT", "DATA", "TIME"})
    obj.name = "Procedural Stairs"

    print(
        "Procedural stairs created. Adjust Step Count and Width normally; "
        "Rise, Run, and Tread Thickness are entered in inches."
    )
    return obj


if __name__ == "__main__":
    install_stair_generator()
