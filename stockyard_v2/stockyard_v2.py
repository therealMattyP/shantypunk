from __future__ import annotations

import math
import random
from dataclasses import dataclass

import bpy
from mathutils import Vector

COLLECTION_NAME = "STOCKYARD_V2"
EPS = 0.004


@dataclass(frozen=True)
class Rect:
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return self.xmin - margin <= x <= self.xmax + margin and self.ymin - margin <= y <= self.ymax + margin

    def overlaps_x(self, a: float, b: float, margin: float = 0.0) -> bool:
        lo, hi = sorted((a, b))
        return hi >= self.xmin - margin and lo <= self.xmax + margin

    def overlaps_y(self, a: float, b: float, margin: float = 0.0) -> bool:
        lo, hi = sorted((a, b))
        return hi >= self.ymin - margin and lo <= self.ymax + margin


@dataclass(frozen=True)
class StairPlan:
    opening: Rect
    axis: str
    sign: float
    risers: int
    treads: int
    rise: float
    run: float
    tread: float


POST = (0.16, 0.16)
BEAM = (0.16, 0.28)
JOIST = (0.05, 0.20)
BOARD = (0.14, 0.035)
BRACE = (0.075, 0.10)
STRINGER = (0.05, 0.24)
RAIL_POST = (0.075, 0.075)
RAIL = (0.055, 0.075)


def collection() -> bpy.types.Collection:
    c = bpy.data.collections.get(COLLECTION_NAME)
    if c is None:
        c = bpy.data.collections.new(COLLECTION_NAME)
        bpy.context.scene.collection.children.link(c)
    return c


def clear(c: bpy.types.Collection) -> None:
    for obj in list(c.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def cube(c, name, loc, dims, rot=None, role="part", sid="", level=-1, material="WOOD_FRAME"):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    obj.rotation_euler = rot or Vector((0, 0, 0))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    c.objects.link(obj)
    obj["stockyard_role"] = role
    obj["stockyard_id"] = sid or name
    obj["stockyard_level"] = level
    obj["stockyard_material_class"] = material
    obj["stockyard_version"] = "2.2"
    return obj


def beam_between(c, name, a, b, width, depth, role, sid, level):
    delta = b - a
    if delta.length <= EPS:
        return None
    angle_y = -math.atan2(delta.z, math.hypot(delta.x, delta.y))
    angle_z = math.atan2(delta.y, delta.x)
    return cube(c, name, (a + b) * 0.5, Vector((delta.length, width, depth)), Vector((0, angle_y, angle_z)), role, sid, level)


def noise(rng, amount):
    return rng.uniform(-amount, amount) if amount else 0.0


def floor_z(s, level):
    return s.deck_height + level * s.story_height


def stair_plan(s, upper_level):
    lower = floor_z(s, upper_level - 1)
    upper = floor_z(s, upper_level)
    total_rise = upper - lower
    risers = max(2, math.ceil(total_rise / s.max_riser))
    treads = risers - 1
    axis = "X" if s.stair_direction in {"POS_X", "NEG_X"} else "Y"
    sign = 1.0 if s.stair_direction in {"POS_X", "POS_Y"} else -1.0
    if s.alternate_stairs and upper_level % 2 == 0:
        sign *= -1.0
    span = s.width if axis == "X" else s.depth
    cross = s.depth if axis == "X" else s.width
    available = max(0.5, span - 2 * s.edge_clearance)
    tread = min(s.tread_depth, available / treads)
    run = tread * treads
    length = min(available, max(s.opening_length, run + 2 * s.opening_end_clearance))
    width = min(cross - 2 * s.edge_clearance, max(s.opening_width, s.stair_width + 2 * s.stair_side_clearance))
    hx, hy = (length * 0.5, width * 0.5) if axis == "X" else (width * 0.5, length * 0.5)
    cx = max(-s.width * 0.5 + hx + s.edge_clearance, min(s.width * 0.5 - hx - s.edge_clearance, s.opening_x))
    cy = max(-s.depth * 0.5 + hy + s.edge_clearance, min(s.depth * 0.5 - hy - s.edge_clearance, s.opening_y))
    return StairPlan(Rect(cx - hx, cx + hx, cy - hy, cy + hy), axis, sign, risers, treads, total_rise / risers, run, tread)


def segments_avoiding(a, b, cut_a, cut_b, gap):
    lo, hi = sorted((a, b))
    pieces = []
    if cut_a - gap > lo:
        pieces.append((lo, cut_a - gap))
    if cut_b + gap < hi:
        pieces.append((cut_b + gap, hi))
    return pieces


def add_opening_frame(c, s, level, z, plan):
    r = plan.opening
    d = JOIST[1]
    w = JOIST[0] * 2
    for tag, y in (("S", r.ymin), ("N", r.ymax)):
        cube(c, f"SYV22_HEADER_{tag}_L{level:02d}", Vector(((r.xmin+r.xmax)/2, y, z)), Vector((r.xmax-r.xmin, w, d)), role="opening_header", sid=f"header:{level}:{tag}", level=level)
    for tag, x in (("W", r.xmin), ("E", r.xmax)):
        cube(c, f"SYV22_TRIMMER_{tag}_L{level:02d}", Vector((x, (r.ymin+r.ymax)/2, z)), Vector((w, r.ymax-r.ymin, d)), role="opening_trimmer", sid=f"trimmer:{level}:{tag}", level=level)


def add_structure(c, s, rng, level, plan):
    base = level * s.story_height
    deck = floor_z(s, level)
    beam_z = deck - BEAM[1] * 0.5
    joist_z = deck + JOIST[1] * 0.5 + EPS
    board_z = deck + JOIST[1] + BOARD[1] * 0.5 + 2 * EPS
    xs = [-s.width/2 + s.width*i/s.bays_x for i in range(s.bays_x+1)]
    ys = [-s.depth/2 + s.depth*i/s.bays_y for i in range(s.bays_y+1)]

    for ix, x in enumerate(xs):
        for iy, y in enumerate(ys):
            if plan and plan.opening.contains(x, y, POST[0]):
                continue
            h = s.deck_height - BEAM[1] - s.connection_gap
            cube(c, f"SYV22_POST_L{level:02d}_{ix:02d}_{iy:02d}", Vector((x, y, base+h/2)), Vector((POST[0], POST[1], h)), Vector((math.radians(noise(rng, s.post_lean*s.chaos)), math.radians(noise(rng, s.post_lean*s.chaos)), 0)), "post", f"post:{level}:{ix}:{iy}", level)

    for iy, y in enumerate(ys):
        segs = [(-s.width/2-POST[0]/2, s.width/2+POST[0]/2)]
        if plan and plan.opening.overlaps_y(y-BEAM[0]/2, y+BEAM[0]/2):
            segs = segments_avoiding(-s.width/2-POST[0]/2, s.width/2+POST[0]/2, plan.opening.xmin, plan.opening.xmax, s.connection_gap)
        for j, (a, b) in enumerate(segs):
            cube(c, f"SYV22_BEAM_L{level:02d}_{iy:02d}_{j}", Vector(((a+b)/2, y, beam_z)), Vector((b-a, BEAM[0], BEAM[1])), role="primary_beam", sid=f"beam:{level}:{iy}:{j}", level=level)

    count = max(2, math.floor(s.width/s.joist_spacing)+1)
    for i in range(count):
        x = -s.width/2 + s.width*i/(count-1) + noise(rng, s.member_shift*s.chaos)
        segs = [(-s.depth/2-POST[1]/2, s.depth/2+POST[1]/2)]
        if plan and plan.opening.xmin-JOIST[0] <= x <= plan.opening.xmax+JOIST[0]:
            segs = segments_avoiding(-s.depth/2-POST[1]/2, s.depth/2+POST[1]/2, plan.opening.ymin, plan.opening.ymax, s.connection_gap)
        for j, (a, b) in enumerate(segs):
            cube(c, f"SYV22_JOIST_L{level:02d}_{i:03d}_{j}", Vector((x, (a+b)/2, joist_z)), Vector((JOIST[0], b-a, JOIST[1])), Vector((0,0,math.radians(noise(rng,s.member_twist*s.chaos)))), "joist", f"joist:{level}:{i}:{j}", level)
    if plan:
        add_opening_frame(c, s, level, joist_z, plan)

    count = max(2, math.floor(s.depth/(BOARD[0]+s.board_gap))+1)
    for i in range(count):
        if s.chaos and rng.random() < s.missing_board*s.chaos:
            continue
        y = -s.depth/2 + s.depth*i/(count-1)
        segs = [(-s.width/2, s.width/2)]
        if plan and plan.opening.ymin-BOARD[0]/2 <= y <= plan.opening.ymax+BOARD[0]/2:
            segs = segments_avoiding(-s.width/2, s.width/2, plan.opening.xmin, plan.opening.xmax, s.connection_gap)
        for j, (a, b) in enumerate(segs):
            if b-a < 0.05:
                continue
            cube(c, f"SYV22_DECK_L{level:02d}_{i:03d}_{j}", Vector(((a+b)/2+noise(rng,s.board_shift*s.chaos), y, board_z+noise(rng,s.board_height*s.chaos))), Vector((b-a, BOARD[0], BOARD[1])), Vector((0,0,math.radians(noise(rng,s.board_twist*s.chaos)))), "deck_board", f"deck:{level}:{i}:{j}", level, "WOOD_DECK")

    add_bracing(c, s, level, xs, ys, base, beam_z, plan)
    if s.guardrails:
        add_guardrails(c, s, level, board_z+BOARD[1]/2, plan)


def add_bracing(c, s, level, xs, ys, base, beam_z, plan):
    if not s.bracing:
        return
    top = beam_z - BEAM[1]/2 - s.connection_gap
    for side_y, label, outward in ((ys[0], "S", -1), (ys[-1], "N", 1)):
        y = side_y + outward*(POST[1]/2+BRACE[0]/2+s.connection_gap)
        for bay in range(s.bays_x):
            x0, x1 = xs[bay], xs[bay+1]
            if plan and plan.opening.overlaps_x(x0, x1, BRACE[0]) and plan.opening.ymin-0.25 <= side_y <= plan.opening.ymax+0.25:
                continue
            a = Vector((x0+POST[0]/2+s.connection_gap, y, base+s.brace_clearance))
            b = Vector((x1-POST[0]/2-s.connection_gap, y, top))
            beam_between(c, f"SYV22_BRACE_{label}_L{level:02d}_{bay:02d}_A", a, b, BRACE[0], BRACE[1], "brace", f"brace:{level}:{label}:{bay}:a", level)
            if s.cross_bracing:
                beam_between(c, f"SYV22_BRACE_{label}_L{level:02d}_{bay:02d}_B", Vector((a.x,a.y,b.z)), Vector((b.x,b.y,a.z)), BRACE[0], BRACE[1], "brace", f"brace:{level}:{label}:{bay}:b", level)


def stair_point(plan, lower_z, step):
    cx = (plan.opening.xmin+plan.opening.xmax)/2
    cy = (plan.opening.ymin+plan.opening.ymax)/2
    dist = -plan.run/2 + plan.tread*(step+0.5)
    if plan.axis == "X":
        return Vector((cx+plan.sign*dist, cy, lower_z+plan.rise*(step+1)))
    return Vector((cx, cy+plan.sign*dist, lower_z+plan.rise*(step+1)))


def add_stairs(c, s, upper_level, plan):
    lower = floor_z(s, upper_level-1) + JOIST[1] + BOARD[1]
    upper = floor_z(s, upper_level) + JOIST[1] + BOARD[1]
    cx = (plan.opening.xmin+plan.opening.xmax)/2
    cy = (plan.opening.ymin+plan.opening.ymax)/2
    half = s.stair_width/2-STRINGER[0]/2
    start_d = -plan.run/2
    end_d = plan.run/2
    for side, off in (("L",-half),("R",half)):
        if plan.axis == "X":
            a = Vector((cx+plan.sign*start_d, cy+off, lower+plan.rise/2))
            b = Vector((cx+plan.sign*end_d, cy+off, upper-plan.rise/2))
        else:
            a = Vector((cx+off, cy+plan.sign*start_d, lower+plan.rise/2))
            b = Vector((cx+off, cy+plan.sign*end_d, upper-plan.rise/2))
        beam_between(c, f"SYV22_STRINGER_L{upper_level:02d}_{side}", a, b, STRINGER[0], STRINGER[1], "stair_stringer", f"stringer:{upper_level}:{side}", upper_level)
    for i in range(plan.treads):
        p = stair_point(plan, lower, i)
        dims = Vector((plan.tread, s.stair_width, 0.04)) if plan.axis == "X" else Vector((s.stair_width, plan.tread, 0.04))
        cube(c, f"SYV22_TREAD_L{upper_level:02d}_{i:03d}", p, dims, role="stair_tread", sid=f"tread:{upper_level}:{i}", level=upper_level, material="WOOD_DECK")
    if s.stair_handrails:
        for side, off in (("L",-s.stair_width/2),("R",s.stair_width/2)):
            if plan.axis == "X":
                a = Vector((cx+plan.sign*start_d, cy+off, lower+s.rail_height))
                b = Vector((cx+plan.sign*end_d, cy+off, upper+s.rail_height))
            else:
                a = Vector((cx+off, cy+plan.sign*start_d, lower+s.rail_height))
                b = Vector((cx+off, cy+plan.sign*end_d, upper+s.rail_height))
            beam_between(c, f"SYV22_HANDRAIL_L{upper_level:02d}_{side}", a, b, RAIL[0], RAIL[1], "handrail", f"handrail:{upper_level}:{side}", upper_level)


def add_ladder(c, s, upper_level, plan):
    lower = floor_z(s, upper_level-1)+JOIST[1]+BOARD[1]
    upper = floor_z(s, upper_level)+JOIST[1]+BOARD[1]
    x = (plan.opening.xmin+plan.opening.xmax)/2
    y = (plan.opening.ymin+plan.opening.ymax)/2
    for side, yy in (("L", y-s.ladder_width/2),("R",y+s.ladder_width/2)):
        cube(c, f"SYV22_LADDER_RAIL_L{upper_level:02d}_{side}", Vector((x,yy,(lower+upper)/2)), Vector((0.07,0.07,upper-lower)), role="ladder_rail", sid=f"ladder:{upper_level}:{side}", level=upper_level)
    n = max(2, math.floor((upper-lower)/s.rung_spacing))
    for i in range(n+1):
        z = lower+(upper-lower)*i/n
        cube(c, f"SYV22_LADDER_RUNG_L{upper_level:02d}_{i:03d}", Vector((x,y,z)), Vector((0.04,s.ladder_width,0.04)), role="ladder_rung", sid=f"rung:{upper_level}:{i}", level=upper_level)


def rail_segment(c, level, axis, fixed, a, b, z, tag, skip=None):
    intervals = [(a,b)]
    if skip:
        cut = (skip.xmin, skip.xmax) if axis == "X" else (skip.ymin, skip.ymax)
        intervals = segments_avoiding(a,b,cut[0],cut[1],0.08)
    for j,(lo,hi) in enumerate(intervals):
        if hi-lo < 0.1:
            continue
        for pos in (lo,hi):
            loc = Vector((pos,fixed,z+0.5)) if axis=="X" else Vector((fixed,pos,z+0.5))
            cube(c,f"SYV22_RAILPOST_{tag}_L{level:02d}_{j}_{pos:.2f}",loc,Vector((RAIL_POST[0],RAIL_POST[1],1.0)),role="rail_post",sid=f"railpost:{level}:{tag}:{j}:{pos}",level=level)
        loc = Vector(((lo+hi)/2,fixed,z+1.0)) if axis=="X" else Vector((fixed,(lo+hi)/2,z+1.0))
        dims = Vector((hi-lo,RAIL[0],RAIL[1])) if axis=="X" else Vector((RAIL[0],hi-lo,RAIL[1]))
        cube(c,f"SYV22_RAIL_{tag}_L{level:02d}_{j}",loc,dims,role="guardrail",sid=f"rail:{level}:{tag}:{j}",level=level)


def add_guardrails(c,s,level,z,plan):
    hw,hd=s.width/2,s.depth/2
    rail_segment(c,level,"X",-hd,-hw,hw,z,"S",plan.opening if plan and plan.opening.ymin<=-hd+0.2 else None)
    rail_segment(c,level,"X", hd,-hw,hw,z,"N",plan.opening if plan and plan.opening.ymax>= hd-0.2 else None)
    rail_segment(c,level,"Y",-hw,-hd,hd,z,"W",plan.opening if plan and plan.opening.xmin<=-hw+0.2 else None)
    rail_segment(c,level,"Y", hw,-hd,hd,z,"E",plan.opening if plan and plan.opening.xmax>= hw-0.2 else None)
    if plan and level>0:
        r=plan.opening
        rail_segment(c,level,"X",r.ymin,r.xmin,r.xmax,z,"OPEN_S")
        rail_segment(c,level,"X",r.ymax,r.xmin,r.xmax,z,"OPEN_N")
        rail_segment(c,level,"Y",r.xmin,r.ymin,r.ymax,z,"OPEN_W")
        rail_segment(c,level,"Y",r.xmax,r.ymin,r.ymax,z,"OPEN_E")


def add_sockets(c,s,level,z):
    for tag,x,y in (("N",0,s.depth/2),("S",0,-s.depth/2),("E",s.width/2,0),("W",-s.width/2,0),("CENTER",0,0)):
        obj=bpy.data.objects.new(f"SYV22_SOCKET_L{level:02d}_{tag}",None)
        obj.empty_display_type="ARROWS"; obj.empty_display_size=0.2; obj.location=(x,y,z)
        obj["stockyard_role"]="attachment_socket"; obj["stockyard_level"]=level; obj["socket_direction"]=tag; obj["stockyard_version"]="2.2"
        c.objects.link(obj)


def generate_stockyard(s):
    c=collection(); clear(c); rng=random.Random(s.seed)
    plans={level:stair_plan(s,level) for level in range(1,s.level_count) if s.circulation!="NONE"}
    for level in range(s.level_count):
        plan=plans.get(level)
        add_structure(c,s,rng,level,plan)
        surface=floor_z(s,level)+JOIST[1]+BOARD[1]
        if s.sockets: add_sockets(c,s,level,surface)
        if level>0 and plan:
            if s.circulation=="STAIRS": add_stairs(c,s,level,plan)
            elif s.circulation=="LADDER": add_ladder(c,s,level,plan)


class StockyardV2Properties(bpy.types.PropertyGroup):
    width:bpy.props.FloatProperty(name="Width",default=6,min=2,max=50,unit="LENGTH")
    depth:bpy.props.FloatProperty(name="Depth",default=5,min=2,max=50,unit="LENGTH")
    deck_height:bpy.props.FloatProperty(name="First Deck Height",default=2.4,min=.3,max=15,unit="LENGTH")
    level_count:bpy.props.IntProperty(name="Levels",default=2,min=1,max=12)
    story_height:bpy.props.FloatProperty(name="Story Height",default=3,min=1.8,max=8,unit="LENGTH")
    bays_x:bpy.props.IntProperty(name="Width Bays",default=3,min=1,max=24)
    bays_y:bpy.props.IntProperty(name="Depth Bays",default=2,min=1,max=24)
    joist_spacing:bpy.props.FloatProperty(name="Joist Spacing",default=.4,min=.2,max=1.2,unit="LENGTH")
    board_gap:bpy.props.FloatProperty(name="Board Gap",default=.008,min=0,max=.08,unit="LENGTH")
    connection_gap:bpy.props.FloatProperty(name="Connection Gap",default=.006,min=.001,max=.05,unit="LENGTH")
    circulation:bpy.props.EnumProperty(name="Circulation",items=(("NONE","None",""),("STAIRS","Straight Stairs",""),("LADDER","Ladder","")),default="STAIRS")
    stair_direction:bpy.props.EnumProperty(name="Stair Direction",items=(("POS_X","+X",""),("NEG_X","-X",""),("POS_Y","+Y",""),("NEG_Y","-Y","")),default="POS_X")
    alternate_stairs:bpy.props.BoolProperty(name="Alternate Direction / Story",default=True)
    opening_width:bpy.props.FloatProperty(name="Opening Width",default=1.25,min=.7,max=4,unit="LENGTH")
    opening_length:bpy.props.FloatProperty(name="Opening Length",default=4.5,min=1,max=12,unit="LENGTH")
    opening_x:bpy.props.FloatProperty(name="Opening X",default=0,unit="LENGTH")
    opening_y:bpy.props.FloatProperty(name="Opening Y",default=0,unit="LENGTH")
    edge_clearance:bpy.props.FloatProperty(name="Edge Clearance",default=.25,min=.05,max=2,unit="LENGTH")
    opening_end_clearance:bpy.props.FloatProperty(name="Opening End Clearance",default=.15,min=0,max=1,unit="LENGTH")
    stair_side_clearance:bpy.props.FloatProperty(name="Stair Side Clearance",default=.1,min=0,max=1,unit="LENGTH")
    stair_width:bpy.props.FloatProperty(name="Stair Width",default=1,min=.6,max=3,unit="LENGTH")
    tread_depth:bpy.props.FloatProperty(name="Target Tread",default=.27,min=.18,max=.4,unit="LENGTH")
    max_riser:bpy.props.FloatProperty(name="Max Riser",default=.19,min=.12,max=.25,unit="LENGTH")
    ladder_width:bpy.props.FloatProperty(name="Ladder Width",default=.55,min=.35,max=1.2,unit="LENGTH")
    rung_spacing:bpy.props.FloatProperty(name="Rung Spacing",default=.3,min=.2,max=.5,unit="LENGTH")
    guardrails:bpy.props.BoolProperty(name="Guardrails",default=True)
    stair_handrails:bpy.props.BoolProperty(name="Stair Handrails",default=True)
    rail_height:bpy.props.FloatProperty(name="Rail Height",default=1,min=.7,max=1.4,unit="LENGTH")
    sockets:bpy.props.BoolProperty(name="Attachment Sockets",default=False)
    bracing:bpy.props.BoolProperty(name="Bracing",default=True)
    cross_bracing:bpy.props.BoolProperty(name="Cross Bracing",default=False)
    brace_clearance:bpy.props.FloatProperty(name="Brace Ground Clearance",default=.25,min=0,max=3,unit="LENGTH")
    seed:bpy.props.IntProperty(name="Seed",default=1,min=0)
    chaos:bpy.props.FloatProperty(name="Chaos",default=0,min=0,max=1,subtype="FACTOR")
    post_lean:bpy.props.FloatProperty(name="Post Lean",default=2,min=0,max=15)
    member_shift:bpy.props.FloatProperty(name="Member Shift",default=.035,min=0,max=.5,unit="LENGTH")
    member_twist:bpy.props.FloatProperty(name="Joist Twist",default=1.5,min=0,max=15)
    board_twist:bpy.props.FloatProperty(name="Board Twist",default=1.5,min=0,max=15)
    board_shift:bpy.props.FloatProperty(name="Board End Shift",default=.06,min=0,max=.5,unit="LENGTH")
    board_height:bpy.props.FloatProperty(name="Board Height Variation",default=.015,min=0,max=.2,unit="LENGTH")
    missing_board:bpy.props.FloatProperty(name="Missing Board Chance",default=.08,min=0,max=.8,subtype="FACTOR")


class STOCKYARD_OT_generate_v2(bpy.types.Operator):
    bl_idname="stockyard.generate_v2"; bl_label="Generate Stockyard v2.2"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        generate_stockyard(context.scene.stockyard_v2); return {"FINISHED"}


class STOCKYARD_PT_v2(bpy.types.Panel):
    bl_label="Stockyard v2.2"; bl_idname="STOCKYARD_PT_v2"; bl_space_type="VIEW_3D"; bl_region_type="UI"; bl_category="Shantypunk"
    def draw(self,context):
        s=context.scene.stockyard_v2; layout=self.layout
        box=layout.box(); box.label(text="Multistory Structure")
        for p in ("width","depth","deck_height","level_count","story_height","bays_x","bays_y","joist_spacing","board_gap","connection_gap"): box.prop(s,p)
        box=layout.box(); box.label(text="Circulation First")
        for p in ("circulation","stair_direction","alternate_stairs","opening_width","opening_length","opening_x","opening_y","edge_clearance"): box.prop(s,p)
        if s.circulation=="STAIRS":
            for p in ("stair_width","tread_depth","max_riser","opening_end_clearance","stair_side_clearance","stair_handrails"): box.prop(s,p)
        elif s.circulation=="LADDER":
            for p in ("ladder_width","rung_spacing"): box.prop(s,p)
        box=layout.box(); box.label(text="Safety / Hosts")
        for p in ("guardrails","rail_height","sockets"): box.prop(s,p)
        box=layout.box(); box.label(text="Bracing")
        for p in ("bracing","cross_bracing","brace_clearance"): box.prop(s,p)
        box=layout.box(); box.label(text="Explicit Chaos")
        for p in ("seed","chaos","post_lean","member_shift","member_twist","board_twist","board_shift","board_height","missing_board"): box.prop(s,p)
        layout.operator("stockyard.generate_v2",icon="MOD_BUILD")


CLASSES=(StockyardV2Properties,STOCKYARD_OT_generate_v2,STOCKYARD_PT_v2)
