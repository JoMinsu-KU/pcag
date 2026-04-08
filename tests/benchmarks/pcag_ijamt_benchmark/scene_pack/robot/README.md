# Robot Scene Pack

This folder stores the canonical robot runtime shells used by the IJAMT
benchmark.

## Implemented shells

- `robot_pick_place_cell`
  - validated public robot shell for generic pick, place, reach, and transfer
    motions
- `robot_stack_cell`
  - validated public robot shell for stack and constrained placement motions
- `robot_narrow_clearance_cell`
  - first phase-A expansion shell for narrow-clearance approach and
    insertion-adjacent motions
  - introduced to increase DT collision difficulty without changing the
    single-asset PCAG contract
- `robot_fixture_insertion_cell`
  - first plugin-light expansion shell for deeper insertion-corridor motions
  - introduced to make insertion depth, orientation margin, and side-wall
    contact explicit DT concerns

## Deferred shells

- `robot_gear_assembly_cell`
  - still planned
  - not yet implemented in the active benchmark workspace

## Runtime contract

All implemented robot shells follow the same benchmark contract:

- `asset_id = robot_arm_01`
- `runtime_type = usd_scene`
- `robot_model = franka_fallback`
- executable action subset: `move_joint`
- sensor path: Isaac-backed
- simulation backend: `isaac_sim`

## Builder pattern

Each implemented shell should be reproducible from:

- `scene_builder.py`
- generated `.usd`
- `shell_config.json`

This keeps the robot benchmark artifact reproducible while remaining light
enough for public benchmark distribution.

## Current interpretation

`robot_pick_place_cell` and `robot_stack_cell` are already part of the
validated robot benchmark v1.

`robot_narrow_clearance_cell` is the first expansion shell used by
`robot_source_release_v2`.

`robot_fixture_insertion_cell` is the next robot expansion shell used by the
draft `robot_source_release_v3`. Both expansion shells have now been validated
at the current family level:

- `robot_narrow_clearance_cell` -> `28/28` family pass
- `robot_fixture_insertion_cell` -> `12/12` family pass
