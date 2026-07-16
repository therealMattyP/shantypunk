# Stockyard v2

Stockyard v2 is the first construction-plausible procedural timber platform prototype for Shantypunk.

## Design rules

- Blender units are treated as meters.
- `Chaos = 0` produces deterministic, square, structurally legible construction.
- Randomness is seeded and belongs only to explicit imperfection controls.
- Generated parts are independent named objects with semantic `stockyard_role` metadata.
- The prototype targets midground visual quality and downstream refinement rather than joinery-level fabrication detail.

## Included structure

- Post grid based on width/depth bay counts
- Primary beams
- Joists at adjustable real-world spacing
- Individual deck boards with adjustable gaps
- Optional diagonal or cross bracing
- Optional repair boards

## Explicit chaos controls

- Post lean
- Joist/member shift
- Joist twist
- Deck-board twist
- Deck-board end shift
- Deck-board height variation
- Missing-board probability
- Repair-board count

All chaos values are multiplied by the master `Chaos` slider. At zero, none of these deviations are applied.

## Installation

1. Copy the `stockyard_v2` folder into Blender's add-ons directory, or zip the folder and install it through Blender Preferences.
2. Enable **Shantypunk Stockyard v2**.
3. Open the 3D View sidebar.
4. Select the **Shantypunk** tab.
5. Adjust the controls and click **Generate Stockyard v2**.

The generator replaces the contents of the `STOCKYARD_V2` collection each time it runs.

## Current limitations

- No roof, railing, stairs, ladders, doors, walls, corrugated panels, or enclosed rooms yet.
- No material assignment or UV generation yet.
- No curve-driven footprint yet.
- Deck-board sag is represented only by per-board displacement/rotation; true curved sag is a later geometry pass.
- Braces are visual structural members and do not yet solve around collisions.

## Recommended next passes

1. Add platform modules and vertical stacking.
2. Add stairs, ladders, railings, and circulation rules.
3. Add wall and roof attachment hosts.
4. Add corrugated-sheet and scrap-board enclosure grammars.
5. Add material slots and deterministic material variation.
6. Add commit/bake workflow and Unreal-friendly export metadata.
