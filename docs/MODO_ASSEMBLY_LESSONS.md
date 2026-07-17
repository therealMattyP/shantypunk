# Lessons Recovered from the Modo Procedural Assemblies

## Purpose

This document records the architectural ideas recovered from Matt's older Modo assemblies so they can guide the Blender/Geometry Nodes implementation of Shantypunk and related procedural architecture tools.

The goal is **not** to reproduce the Modo schematic graphs node-for-node. The goal is to preserve the design intelligence behind them and rebuild that intelligence natively in Blender.

---

## Core discovery

The Modo systems consistently follow this pattern:

```text
Controller
    ↓
Parameter translation / math
    ↓
Construction logic
    ↓
Curves, points, profiles, or primitive geometry
    ↓
Replication / assembly
    ↓
Finishing operations
    ↓
Output
```

The important distinction is that these generators are not simply parameterized meshes. They are **construction interpreters**.

A user control rarely drives only one object. A control such as board width, stringer width, support width, or column diameter often drives:

- source geometry dimensions
- spacing calculations
- offsets
- profile sizes
- related components
- finishing dimensions

This means the exposed controller is the design interface, while the graph below it translates design intent into construction.

---

## Three foundational breakthroughs

### 1. Tuscan column: proportion

The Tuscan column generator predates the stair system and is primarily driven by column diameter. Pedestal and capital options are exposed, while the rest of the assembly derives from classical proportional relationships.

The core lesson is:

```text
Primary dimension
    ↓
Proportional rules
    ↓
Complete architectural assembly
```

This establishes **proportion as a generator** rather than a collection of unrelated dimensions.

### 2. Stairs: construction

The stair breakthrough came from the CS50 Mario exercise and the realization that a stair can begin as a simple repeated three-point construction:

- start
- rise
- run

A repeated top-and-front profile produces the basis for treads and risers. Removing or thickening different faces changes the interpretation:

- thin top surfaces become planks
- thickened units become stone steps
- front faces can become risers or be removed
- the same circulation logic can feed stringers, railings, and supports

The core lesson is:

```text
Circulation logic
    ↓
Step frames
    ↓
Construction interpreters
```

The stair should therefore be separated into reusable subsystems rather than implemented as one monolithic node graph.

### 3. Brick wall: material grammar

The brick wall generator uses start, end, and height controls to establish a construction frame, then fills that frame using brick dimensions, spacing, turbulence, jitter, and related rules.

The core lesson is:

```text
Construction host
    ↓
Material-sized units
    ↓
Bonding / spacing / variation rules
```

This is not merely texture placement. It is a material system expressed through geometry.

---

## Curve Point Generator was a key procedural primitive

Curve Point Generator appears repeatedly across the Modo assemblies and was one of the most important nodes in the procedural vocabulary.

It provided a clean separation:

```text
Curve = path or design intent
Points = placement logic
Prototype = construction part
Replicator = assembly
```

It was used or implied for:

- walkway planks
- joists
- railing posts
- nails aligned to planks
- stair balusters
- supports
- repeated masonry or trim elements

The closest Blender pattern is:

```text
Curve
    ↓
Resample Curve / Curve to Points
    ↓
Selection, spacing, endpoint masks, or randomization
    ↓
Instance on Points
```

A reusable Geometry Nodes group should expose both the host curve and its distribution data:

```text
Host Curve Distribution
├── curve geometry
├── uniformly spaced points
├── tangent
├── normal
├── spline parameter
├── start mask
└── end mask
```

This should become shared infrastructure for walls, stairs, walkways, railings, bridges, pipes, supports, and trim.

---

## Walkway assembly lessons

The walkway generator is not one system. It is an assembly of independent subsystems:

```text
Walkway
├── Plank Generator
├── Stringer / Joist Generator
├── Railing Generator
├── Support Generator
└── Randomization / Damage
```

### Planks

Controls include width, length, thickness, chamfer, positional jitter, rotational jitter, scale variation, seed, and random deletion.

Modo patterns:

- cube primitive as source board
- Curve Point Generator for placement
- Replicator for board and nail distribution
- random rotation and scale on replicators
- random selection for missing boards
- chamfer as finishing

Blender interpretation:

```text
Host curve
    ↓
Curve to Points
    ↓
Instance board prototype
    ↓
Random rotation / scale / deletion
    ↓
Optional realization and bevel
```

### Stringers and joists

Stringer width affects many downstream calculations, sweeps, and offsets. This demonstrates that a single exposed construction dimension should feed a dedicated translation group rather than be manually wired throughout a giant graph.

Blender interpretation:

- independent Stringer node group
- independent Joist node group
- shared host-curve data
- feature toggles through Switch nodes

### Railings

Left and right railings are separate feature branches. Post spacing is generated from a curve. Handrails are sweeps. Random rotation, deletion, and seeded variation can be applied independently.

The railing system should be reusable by:

- walkways
- stairs
- decks
- bridges
- balconies
- fire escapes

### Supports

Supports are located by percentages along the main and side/stringer curves. Start and end supports are independently enabled. H-bracing and X-bracing are separate feature branches.

This is an important host concept:

```text
Main curve
    ↓
Sample at normalized position
    ↓
Construct support frame
    ↓
Interpret frame as posts, beams, or braces
```

---

## Floorboard generator lessons

The floorboard generator accepts an **input mesh whose polygons define floorboard regions**.

This is a crucial example of plan interpretation:

```text
Input floor polygons
    ↓
Interpret region
    ↓
Generate boards
```

The input mesh is not merely geometry to decorate. It is construction intent.

The Modo controller exposes:

- board width
- board length
- two board offsets
- board thickness
- chamfer
- length jitter
- vertical offset jitter
- rotation jitter
- X/Z scale jitter
- random deletion chance and seed

The recovered implementation suggests:

```text
Floor region
    ↓
Axis slicing / course generation
    ↓
Board segmentation and offsets
    ↓
Curve sweep or strip construction
    ↓
Thicken
    ↓
Chamfer
    ↓
Jitter and random deletion
```

The two board offsets likely control staggered seams or alternating course offsets. Board length drives slicing rather than merely scaling one board prototype.

A native Blender implementation should be treated as a **region interpreter**, not as a board scatter tool:

```text
Floor region
    ↓
Determine board direction
    ↓
Generate parallel courses
    ↓
Intersect courses with region boundary
    ↓
Segment by realistic board length
    ↓
Stagger seams
    ↓
Create individual boards
    ↓
Thickness, bevel, variation, damage
```

This abstraction can later support:

- timber flooring
- deck boards
- brick paving
- stone slabs
- tile
- parquet
- metal grating

The region remains the same while the construction interpreter changes.

---

## Architectural abstraction emerging from the assemblies

The larger system should be organized around a small number of style-agnostic concepts:

```text
Plans / regions / curves
    ↓
Hosts
    ↓
Interpretation
    ↓
Construction assemblies
    ↓
Materials and finishing
```

### Plans and regions

Plans define areas, boundaries, room relationships, and intended use. They should remain editable and understandable as design documents.

### Hosts

Generated architecture should expose valid hosts for future generation. A floor, wall, tower, bridge, rock, cliff, or ruin can become a host for another assembly.

Hosts should expose useful data such as:

- boundary curves
- centerlines
- surfaces
- normals
- levels
- attachment edges
- support positions
- openings
- circulation interfaces

### Interpreters

Interpreters convert abstract intent into construction:

```text
Curve Interpreter
├── wall
├── railing
├── walkway
├── pipe
└── trim

Region Interpreter
├── floorboards
├── tile
├── paving
├── ceiling
└── room system

Circulation Interpreter
├── stairs
├── ramps
├── ladders
├── landings
└── bridges

Wall Interpreter
├── brick
├── stone
├── timber
├── sheet material
└── framed wall
```

### Construction assemblies

Assemblies should be reusable node groups with clear responsibilities:

- Deck / Plank Builder
- Joist Builder
- Stringer Builder
- Railing Builder
- Support Builder
- Brace Builder
- Floor Region Builder
- Stair Frame Builder
- Masonry Builder
- Opening / Fenestration Builder

This is the modularity that the Modo schematic system could not adequately provide.

---

## Translation vocabulary: Modo to Blender

| Modo concept | Blender / Geometry Nodes interpretation |
|---|---|
| User Channels | Node group interface / custom properties |
| Basic Math | Math / Vector Math / Map Range |
| Curve Point Generator | Resample Curve / Curve to Points |
| Replicator | Instance on Points |
| Curve Sweep | Curve to Mesh |
| Path Constraint | Sample Curve / Spline Parameter / transform logic |
| Cube primitive | Cube node or prototype object |
| Thicken | Extrude Mesh or Solidify |
| Edge Chamfer | Bevel node or modifier |
| Random Jitter | Random Value + Set Position / Rotate Instances / Scale Instances |
| Random Selection | Random Value + Compare + selection mask |
| MeshOp Stack Enable | Switch / independent feature node group |
| Merge Meshes | Join Geometry |
| Axis Slice | Procedural course/segment generation, clipping, or mesh cutting |

The translation should preserve behavior and intent, not necessarily the original implementation.

---

## Recommended Blender architecture

```text
Input Layer
├── plans
├── region meshes
├── curves
├── section controls
└── host objects

Host Analysis Layer
├── boundaries
├── directions
├── normals
├── levels
├── attachment points
└── circulation interfaces

Construction Logic Layer
├── spacing
├── proportions
├── realistic material lengths
├── seams
├── supports
├── openings
└── structural relationships

Assembly Layer
├── boards
├── beams
├── walls
├── railings
├── stairs
├── supports
└── masonry

Finishing Layer
├── bevels
├── UVs
├── materials
├── seeded variation
├── aging
└── damage

Output Layer
├── editable Blender hierarchy
├── construction metadata
├── Unreal-ready naming and pivots
├── collision
└── export preparation
```

---

## Design rules to preserve

1. **Construction before surface appearance.**
   Geometry should be generated from believable material and assembly rules.

2. **Do not stretch materials beyond realistic lengths.**
   Longer spans require another piece, seam, lap, splice, bracket, or brace.

3. **Use seeded randomness.**
   Variation must be reproducible and art-directable.

4. **Separate placement from interpretation.**
   Curves, points, and regions define where. Assemblies define what gets built there.

5. **Expose a small number of meaningful controls.**
   Internal calculations should derive related dimensions rather than forcing the artist to manage every value independently.

6. **Make feature branches modular.**
   Railings, supports, braces, joists, and damage should be independent reusable groups.

7. **Generated objects should become future hosts.**
   Architecture must support recursive building on, into, and around previous generated results.

8. **Do not copy Modo spaghetti.**
   Recover intent, validate behavior, and rebuild using Blender's native strengths.

---

## Diagnostic lessons

Whole-scene Modo graph traversal can crash on complex assemblies, especially when recursively inspecting MeshOps, replicators, deformers, or third-party nodes.

The safe diagnostic strategy is:

- select only the controller
- inspect custom user channels
- read current values
- record only direct channel-link endpoints
- do not expand connected items
- checkpoint before and after every channel
- infer semantic subsystems from controller sections and target operator types

The diagnostics are now best used to answer focused questions such as:

- What does this exposed control affect?
- Is this feature curve-driven, primitive-driven, or instance-driven?
- Which controls toggle independent subassemblies?
- Which dimensions fan out into multiple construction calculations?

They should not be used to reproduce every low-level node.

---

## Current conclusion

The Modo assemblies reveal a consistent procedural grammar:

```text
Design intent
    ↓
Host
    ↓
Construction rules
    ↓
Reusable assembly
    ↓
Variation and finishing
```

The long-term project is therefore not just a collection of generators. It is an **artist-first procedural architectural environment built on Blender**, centered on:

- Section Controls
- plans and regions
- construction hosts
- circulation
- interpretation
- reusable assemblies
- construction-aware UVs and materials
- Unreal-ready output

The old Modo work is valuable not because it should be copied, but because it proves these ideas were already working in practical generators. Blender gives them the modular system they were missing.
