# PCAG IJAMT Action Vocabulary

Version: `v1`  
Status: frozen reference for benchmark generation

## 1. Purpose

This file defines the supervisory action vocabulary used by the IJAMT benchmark package.

The vocabulary is intentionally higher-level than raw actuator write operations.  
It is designed to represent the command semantics that PCAG is expected to validate and gate at the actuation boundary.

## 2. Global rules

- Each benchmark case must use one of the action types defined here.
- Action names should be stable across nominal, unsafe, and fault variants.
- Parameter names should be descriptive and deterministic.
- Asset-specific low-level execution details must not appear as new action names when they can be represented as parameters.

## 2.1 Current public runtime executable subset

The benchmark vocabulary is broader than the current public reference stack.

For direct runner execution in the current release, use the following executable subset:

- `robot_arm_01` -> `move_joint`
- `agv_01` -> `move_to`
- `reactor_01` -> `set_heater_output`, `set_cooling_valve`

Richer supervisory semantics may still appear in source provenance and operation context, but they should be lowered into the executable subset for direct benchmark execution.

## 3. Scenario Families

The benchmark currently uses three scenario families.

### `robot_manipulation`

Robot-arm supervisory commands for assembly or handling tasks.

### `agv_logistics`

AGV supervisory commands for transport, docking, and zone entry tasks.

### `process_interlock`

PLC-governed supervisory commands for process or interlock-preserving assets.

## 4. Asset-to-family mapping

| asset_id | scenario_family |
| --- | --- |
| `robot_arm_01` | `robot_manipulation` |
| `agv_01` | `agv_logistics` |
| `reactor_01` | `process_interlock` |

## 5. Robot action vocabulary

These actions are valid for `robot_arm_01`.

### `pick`

Use when the command requests object acquisition from a known station or fixture.

Typical parameters:

- `object_id`
- `station_id`
- `grasp_pose_id`

### `place`

Use when the robot deposits a grasped object to a target fixture or station.

Typical parameters:

- `object_id`
- `target_station_id`
- `target_pose_id`

### `move_to_fixture`

High-level move toward a named fixture or assembly location.

Typical parameters:

- `fixture_id`
- `approach_pose_id`

### `insert_part`

Assembly insertion or seating motion under supervisory intent.

Typical parameters:

- `part_id`
- `fixture_id`
- `insertion_pose_id`
- `insertion_depth_mm`

### `move_joint`

Joint-space command used when the benchmark explicitly evaluates posture safety or joint-limit safety.

Required parameters:

- `target_positions`

Optional parameters:

- `joint_speed_scale`
- `goal_tolerance`

Notes:

- `target_positions` is the canonical representation for robot-joint benchmark cases.
- Benchmark cases must not use ad hoc forms such as `joint_0`, `joint_1`, etc. as primary command inputs.

### `retreat_to_safe_pose`

Supervisory request to move the arm to a named safe posture.

Typical parameters:

- `safe_pose_id`

## 6. AGV action vocabulary

These actions are valid for `agv_01`.

### `move_to`

Canonical executable AGV action for the current public benchmark release.

Required parameters:

- `target_x`
- `target_y`

Optional parameters:

- `agv_id`
- `path`

### `move_to_station`

Navigation command toward a named station.

Typical parameters:

- `station_id`
- `route_id`

### `dock`

Command to perform final docking alignment at a target station.

Typical parameters:

- `station_id`
- `docking_pose_id`

### `wait`

Command to remain at a holding area or safe point.

Typical parameters:

- `duration_ms`
- `wait_zone_id`

### `handoff_to_robot`

Command representing AGV positioning or readiness for robot handoff.

Typical parameters:

- `station_id`
- `handoff_zone_id`

### `enter_zone`

Command to enter an operational zone, often safety-sensitive.

Typical parameters:

- `zone_id`
- `entry_heading`
- `target_speed`

## 7. Process-interlock action vocabulary

These actions are valid for `reactor_01` or other PLC-governed process assets.

### `set_heater_output`

Supervisory command for process heating output.

Required parameters:

- `heater_output`

### `open_cooling_valve`

Supervisory command to open cooling.

Optional parameters:

- `opening_ratio`

### `close_cooling_valve`

Supervisory command to close cooling.

### `set_process_mode`

High-level state change for a process asset.

Typical parameters:

- `mode`

### `hold_state`

Explicit command to preserve a safe or steady operating condition.

Typical parameters:

- `duration_ms`

## 8. Vocabulary anti-patterns

The following should be avoided when generating benchmark cases.

- Action names that encode parameter values, such as `move_fast_to_station_3`
- Asset-specific low-level register names as action types
- Mixed representations of the same semantic action
- Human-language free text instructions as benchmark actions

## 9. Action normalization rule

If a source benchmark produces a raw trajectory segment, the dataset generator should normalize it into one of the action types above before the case is admitted into the benchmark.

Examples:

- raw approach + grasp trajectory -> `pick`
- raw insertion motion -> `insert_part`
- raw AGV route to cell input -> `enter_zone`
- raw process actuation step -> `set_heater_output`

## 10. Frozen set for first benchmark release

The first benchmark release should distinguish between:

- benchmark semantics that may appear in provenance/context
- executable action types that may appear in directly runnable case JSON

### Executable subset for release `v1`

- `move_joint`
- `move_to`
- `set_heater_output`
- `set_cooling_valve`

### Extended semantic vocabulary retained for provenance and future expansion

- `pick`
- `place`
- `move_to_fixture`
- `insert_part`
- `move_joint`
- `retreat_to_safe_pose`
- `move_to`
- `move_to_station`
- `dock`
- `wait`
- `handoff_to_robot`
- `enter_zone`
- `set_heater_output`
- `open_cooling_valve`
- `close_cooling_valve`
- `set_process_mode`
- `hold_state`
