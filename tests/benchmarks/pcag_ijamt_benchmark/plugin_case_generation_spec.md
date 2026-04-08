# PCAG IJAMT Plugin-Aware Case Generation Spec

Version: `v1`  
Status: benchmark authoring reference

## 1. Purpose

This file explains how benchmark cases should be authored with respect to the actual plugin combinations used by the current PCAG stack.

This matters because the paper benchmark must satisfy two goals at once:

- preserve manufacturing semantics at the supervisory-command level
- remain executable or at least validator-aligned with the current public PCAG implementation

For the next expansion phase, concrete family additions are fixed in:

- `family_expansion_spec_v1.json`
- `plans/IJAMT/PCAG_IJAMT_Single_Asset_Expansion_Roadmap.md`

In practice, this means benchmark authors must understand which sensor, simulation, and executor plugins are actually active for each asset family.

## 2. Asset-to-plugin matrix

| asset_id | sensor path | simulation plugin | executor path | current executable action subset |
| --- | --- | --- | --- | --- |
| `reactor_01` | `source: modbus` routed to `PLCAdapterSensorSource` | `ode_solver` | `PLCAdapterExecutor` | `set_heater_output`, `set_cooling_valve` |
| `agv_01` | `source: modbus` routed to `PLCAdapterSensorSource` | `discrete_event` | `PLCAdapterExecutor` | `move_to` |
| `robot_arm_01` | `IsaacSimSensorSource` | `isaac_backend` | `MockExecutor` | `move_joint` |

## 3. Important interpretation rule

The benchmark may preserve higher-level manufacturing semantics in:

- `scenario_family`
- `operation_context`
- `source_benchmark`
- `notes`

But the `action_sequence` used for direct execution or direct validator compatibility must respect the current public runtime subset shown above.

This is especially important for:

- AGV cases, where high-level intents often reduce to a `move_to` actuation command
- robot cases, where source tasks such as pick/place/insert must currently be represented as `move_joint` commands in the public stack

## 4. Reactor / process-interlock case generation

## 4.1 Active plugin path

### Sensor path

- config label: `modbus`
- effective implementation in the live stack: `PLCAdapterSensorSource`
- retrieved fields:
  - `temperature`
  - `pressure`
  - `heater_output`
  - `cooling_valve`
  - `reactor_status`

### Simulation path

- plugin: `ode_solver`
- purpose: thermal/process response projection under supervisory action
- important expected state keys:
  - `temperature`
  - `pressure`
  - `heater_output`
  - `cooling_valve`

### Execution path

- effective implementation: `PLCAdapterExecutor`
- PLC Adapter writes to the mapped register set
- benchmark-executable action subset:
  - `set_heater_output`
  - `set_cooling_valve`

## 4.2 Authoring rule

For the first benchmark release, process-interlock cases should use the executable subset directly in `action_sequence`.

Recommended direct action forms:

- `set_heater_output`
- `set_cooling_valve`

Higher-level intents such as:

- `open_cooling_valve`
- `close_cooling_valve`
- `hold_state`
- `set_process_mode`

may still appear in:

- `operation_context`
- `notes`
- provenance annotations

but should be lowered into executable forms when the case is intended for direct runner execution.

## 4.3 Normalization rule

### High-level to executable lowering

| supervisory intent | executable action |
| --- | --- |
| open cooling fully | `set_cooling_valve` with `value = 100` |
| close cooling | `set_cooling_valve` with `value = 0` |
| increase heat to target level | `set_heater_output` with target value |
| preserve process thermal state | a safe combination of heater/cooling values in context-specific executable form |

## 4.4 Nominal case recipe

Each nominal process case should:

- start from a plausible sensor snapshot
- keep `temperature` and `pressure` within ruleset range
- use modest heater output or a safe heater/cooling pairing
- expect `COMMITTED`

Example nominal pattern:

- current temperature is moderate
- pressure is within bounds
- action requests `set_heater_output` to a safe value
- cooling remains in a safe or compatible state

## 4.5 Unsafe case recipe

Unsafe process cases should be derived by plugin-relevant mutations such as:

- heater output too high
- heating without adequate cooling
- temperature or pressure projected to exceed safe bound
- forbidden command combination implied by the ruleset

These should normally terminate at:

- `SAFETY_UNSAFE`

## 4.6 Fault case recipe

Good process fault cases include:

- stale timestamp
- sensor hash mismatch
- sensor divergence
- reverify mismatch
- commit failure after prepare

These should target:

- `INTEGRITY_REJECTED`
- `REVERIFY_FAILED`
- `COMMIT_FAILED`
- `COMMIT_TIMEOUT`

## 5. AGV case generation

## 5.1 Active plugin path

### Sensor path

- config label: `modbus`
- effective implementation in the live stack: `PLCAdapterSensorSource`
- retrieved fields:
  - `position_x`
  - `position_y`
  - `heading`
  - `speed`

### Simulation path

- plugin: `discrete_event`
- purpose: path and occupancy conflict validation in a 2D grid model
- important expected action parameters:
  - `target_x`
  - `target_y`
  - optional explicit `path`

### Execution path

- effective implementation: `PLCAdapterExecutor`
- benchmark-executable action subset:
  - `move_to`

## 5.2 Authoring rule

For the first benchmark release, AGV cases should use `move_to` in `action_sequence` when the case must be directly executable.

Higher-level logistics semantics such as:

- `move_to_station`
- `dock`
- `handoff_to_robot`
- `enter_zone`
- `wait`

should be encoded in:

- `operation_context`
- `source_benchmark`
- `notes`

and then lowered into the executable `move_to` action.

## 5.3 Normalization rule

| supervisory intent | executable action form |
| --- | --- |
| move to a named station | `move_to` with station coordinates |
| dock at a station | `move_to` with docking coordinates |
| enter a shared zone | `move_to` with zone entry coordinates |
| handoff to robot | `move_to` with handoff pose coordinates |

If a higher-level AGV intent cannot be reduced to coordinates and path semantics, it should not enter the first frozen release.

## 5.4 Nominal case recipe

Each nominal AGV case should:

- start from a valid current position
- move to an in-bounds target
- avoid obstacles and boundary violations
- avoid simulated conflicts
- expect `COMMITTED`

## 5.5 Unsafe case recipe

Unsafe AGV cases should be derived by plugin-relevant mutations such as:

- out-of-bounds target
- obstacle collision path
- unsafe zone entry
- conflict-prone route under discrete-event simulation

These should normally terminate at:

- `SAFETY_UNSAFE`

## 5.6 Fault case recipe

Good AGV fault cases include:

- stale timestamp
- sensor hash mismatch
- prepare lock denial
- reverify mismatch after prepare
- commit timeout or commit failure

## 6. Robot case generation

## 6.1 Active plugin path

### Sensor path

- plugin: `IsaacSimSensorSource`
- source endpoint: Safety Cluster simulation-state endpoint
- retrieved fields include:
  - `joint_positions`
  - `joint_velocities`
  - `joint_efforts`
  - expanded `joint_0 ... joint_6`
  - expanded finger joint fields

### Simulation path

- plugin: `isaac_backend`
- purpose: Isaac-backed motion safety validation
- key expected action form:
  - `move_joint` with `target_positions`

### Execution path

- current public reference stack: `MockExecutor`
- interpretation:
  - safety validation is Isaac-backed
  - commit semantics exist
  - physical actuation is still mock-backed in the public stack

## 6.2 Authoring rule

For the first benchmark release, all robot cases that are intended for direct execution must use:

- `action_type = move_joint`
- `params.target_positions = [...]`

Higher-level source semantics such as:

- pick
- place
- move to fixture
- insert part
- retreat to safe pose

should be preserved in provenance and context, but lowered to joint-space target commands for the public benchmark release.

## 6.3 Normalization rule

| source semantics | executable action form |
| --- | --- |
| pick motion episode | `move_joint` to pick posture |
| place motion episode | `move_joint` to place posture |
| insertion motion | `move_joint` to insertion posture |
| retreat motion | `move_joint` to safe posture |

## 6.4 Nominal case recipe

Each nominal robot case should:

- start from a valid Isaac-readable joint configuration
- use `target_positions` inside configured joint limits
- remain within workspace limits
- expect `COMMITTED`

Important note:

- the paper must disclose that the robot path is a hybrid path
- safety validation is live Isaac-backed, but execution remains mock-backed in the public reference stack

## 6.5 Unsafe case recipe

Unsafe robot cases should be derived by plugin-relevant mutations such as:

- joint limit violation
- workspace limit violation
- pre-check unsafe posture
- unsafe target positions that Isaac cannot validate as safe

These should normally terminate at:

- `SAFETY_UNSAFE`

## 6.6 Fault case recipe

Good robot fault cases include:

- stale timestamp
- hash mismatch
- Safety Cluster unavailable
- simulation timeout or indeterminate behavior

## 7. Cross-plugin fault families

Some fault families should be generated identically across all three asset groups.

### Integrity-layer faults

- policy mismatch
- timestamp expired
- sensor hash mismatch
- sensor divergence where applicable

### Transaction-layer faults

- lock denied
- reverify mismatch
- commit timeout
- commit failure

### Infrastructure faults

- sensor source unavailable
- simulation backend unavailable
- evidence ledger unavailable

## 8. Benchmark authoring workflow by plugin family

## Step A. Choose source semantics

- robot: public manipulation or assembly episode
- AGV: public warehouse/logistics layout reference
- process asset: process benchmark constraint or operating envelope reference

## Step B. Write supervisory intent

Record:

- scenario family
- mission phase
- station or zone context
- provenance note

## Step C. Lower into executable form

Convert the source semantics into the current asset-specific executable subset.

## Step D. Attach labels

Add:

- expected final status
- expected stop stage
- expected reason code

## Step E. Check plugin compatibility

Verify that the action fields actually match the plugin expectations.

Examples:

- robot must use `target_positions`
- AGV executable cases must use coordinate-based `move_to`
- process executable cases must use `set_heater_output` or `set_cooling_valve`

## 9. Release-v1 executable subset

To avoid mismatch between benchmark semantics and runnable public code, the first benchmark release should limit executable case authoring to:

- `robot_arm_01`: `move_joint`
- `agv_01`: `move_to`
- `reactor_01`: `set_heater_output`, `set_cooling_valve`

Any richer supervisory semantics should be stored as context and provenance unless a verified lowering rule already exists.
