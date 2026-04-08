# PCAG IJAMT Canonical Shell Catalog

Status: frozen specification of the first nine benchmark shells  
Version: `v1-shell-catalog`

Expansion note:

- `robot_narrow_clearance_cell` now exists as a phase-A robot expansion shell
  in `scene_pack/robot/robot_narrow_clearance_cell/`
- it is intentionally outside the original frozen nine-shell catalog and is
  currently consumed by `robot_source_release_v2`

## 1. Purpose

This document defines the first nine canonical benchmark shells used by the
PCAG IJAMT benchmark.

In this benchmark, a **shell** means the standardized runtime envelope that a
case executes against.

Depending on the asset family, a shell may be:

- a robot USD scene
- an AGV map/config scene
- a process parameter profile

The benchmark does not create one custom environment per upstream source task.
Instead, upstream source families are mapped into a small number of canonical
runtime shells. Individual cases then fill those shells with case-specific
parameters, target states, and labels.

This document should be read together with:

- [source_task_selection.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/sources/source_task_selection.md)
- [scene_pack_strategy.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/generation/scene_pack_strategy.md)
- [safety_cluster_scene_integration_strategy.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/generation/safety_cluster_scene_integration_strategy.md)
- [plugin_case_generation_spec.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/plugin_case_generation_spec.md)

## 2. Global design rules

All nine shells follow the same design rules.

### Rule 1. Shell first, case second

The shell is frozen before nominal cases are drafted.

### Rule 2. Upstream provenance is preserved in metadata

The shell does not replace the source benchmark.
It standardizes the runtime environment used by PCAG.

### Rule 3. Each shell must define validator-facing semantics

Each shell must state how it connects to:

- Rules Validator
- barrier-based validator
- simulation backend
- consensus path

### Rule 4. Shells must remain benchmark-sized

The shell is not a full reproduction of the upstream dataset environment.
It is the minimal canonical runtime environment needed for execution-assurance
benchmarking.

## 3. Shell overview

| shell_id | asset family | runtime type | simulation backend | main source families |
| --- | --- | --- | --- | --- |
| `robot_pick_place_cell` | robot | USD scene | `isaac_sim` | `reach`, `lift`, `pick_place`, `place` |
| `robot_stack_cell` | robot | USD scene | `isaac_sim` | `stack` |
| `robot_gear_assembly_cell` | robot | USD scene | `isaac_sim` | `gear_assembly`, `nut_assembly`, `threading`, `three_piece_assembly` |
| `agv_transfer_map` | AGV | map config | `discrete_event` | station transfer |
| `agv_docking_map` | AGV | map config | `discrete_event` | docking approach |
| `agv_shared_zone_map` | AGV | map config | `discrete_event` | shared-zone entry, congestion conflict |
| `reactor_nominal_profile` | process | parameter profile | `ode_solver` | normal operating envelope |
| `reactor_high_heat_profile` | process | parameter profile | `ode_solver` | manipulated-variable stress |
| `reactor_disturbance_profile` | process | parameter profile | `ode_solver` | disturbance-inspired supervision |

## 4. Robot shells

Robot shells are the only shells that require Isaac scene preload before sensor
capture and validation.

All robot shells share:

- `asset_id = robot_arm_01`
- sensor plugin: `IsaacSimSensorSource`
- simulation backend: `isaac_sim`
- executable action subset: `move_joint` with `target_positions`
- public executor path: `MockExecutor`

## 4.1 `robot_pick_place_cell`

### Scenario meaning

This shell represents a generic manufacturing pick-and-place workstation.

It is the default shell for:

- approach motions
- pickup motions
- transport-to-fixture motions
- placement motions

### Intended source families

- IsaacLab `reach`
- IsaacLab `lift`
- IsaacLab `pick_place`
- IsaacLab `place`
- MimicGen `pick_place`

### Planned scene contents

- a single arm robot mounted at a workbench
- one source tray or pickup zone
- one target fixture or placement zone
- one or more simple parts represented by box or part proxies
- a clear reachable workspace envelope

### What changes per dataset case

- initial joint state
- active source object or target fixture metadata
- target posture in `target_positions`
- mission phase such as `approach`, `pick`, `transfer`, `place`, `retreat`

### Recommended runtime artifacts

- `scene_pack/robot/robot_pick_place_cell/scene_builder.py`
- `scene_pack/robot/robot_pick_place_cell/robot_pick_place_cell.usd`
- `scene_pack/robot/robot_pick_place_cell/shell_config.json`

### Safety-validator connection

#### Rules Validator

Rules should focus on:

- joint limits
- allowed action type (`move_joint`)
- optional workspace-related target constraints encoded in sensor/target fields

#### Barrier-based validator

The barrier layer should interpret:

- current joint positions
- projected target posture
- configured workspace margin fields

This shell should expose barrier-relevant constraints such as:

- joint-space range bounds
- optional end-effector workspace box

#### Simulation Validator

The shell connects to `isaac_sim` through:

- `simulation.world_ref = robot_pick_place_cell.usd`
- optional shell-specific `workspace_limits`
- optional shell-specific `joint_limits`

#### Consensus

This shell is expected to contribute strong signal in all three validators for:

- safe postures
- unsafe target posture
- workspace escape

### Typical case families

- nominal pick approach
- nominal pick posture
- nominal transfer posture
- nominal placement posture
- unsafe joint-limit target
- unsafe workspace overshoot

## 4.2 `robot_stack_cell`

### Scenario meaning

This shell represents a multi-object placement or stacking workstation.

It is intended for cases where the benchmark should reason about:

- precise placement order
- constrained stacking region
- repeated posture transitions in a structured workspace

### Intended source families

- IsaacLab `stack`
- MimicGen `stack`

### Planned scene contents

- robot mount and industrial workbench
- infeed conveyor carrying block proxies into the cell
- a stack nest plate with side guides and backstop
- an outfeed pallet zone representing downstream handling
- operator-side HMI/control cabinet and stack light
- floor safety stripes and perimeter fence segments
- two or more stackable object proxies
- constrained stacking zone with narrow placement tolerance

### What changes per dataset case

- object role metadata
- source pickup location on the infeed conveyor
- stack layer or target level
- optional outfeed-clearance intent metadata
- target posture
- safe or unsafe approach posture

### Recommended runtime artifacts

- `scene_pack/robot/robot_stack_cell/scene_builder.py`
- `scene_pack/robot/robot_stack_cell/robot_stack_cell.usd`
- `scene_pack/robot/robot_stack_cell/shell_config.json`

### Safety-validator connection

#### Rules Validator

Rules should encode:

- joint limit compliance
- allowed pickup/place regions relative to conveyor and stack nest
- stack-zone reach constraints where representable
- permitted motion subset

#### Barrier-based validator

The barrier layer should detect:

- posture changes that move outside the conveyor-to-nest transfer corridor
- posture changes that move outside the constrained stack region
- large posture shifts that imply unstable or unsafe placement approach

#### Simulation Validator

The shell connects through:

- `simulation.world_ref = robot_stack_cell.usd`
- stack-zone-specific workspace limits
- conveyor, pallet, and fence-informed workspace envelope
- optional more restrictive approach-area constraints

#### Consensus

This shell is useful for showing that:

- Rules alone may be too weak for certain constrained placements
- barrier and simulation paths help reject posture families that are technically
  within joint limits but not acceptable for safe stacking

### Typical case families

- nominal conveyor pickup
- nominal first-layer place
- nominal stacked placement
- nominal pallet-clearance retreat
- unsafe overreach into side boundary
- unsafe target posture near stack collapse region

## 4.3 `robot_gear_assembly_cell`

### Scenario meaning

This shell represents an industrial assembly or insertion workstation.

It is the most manufacturing-specific robot shell in the release.

### Intended source families

- IsaacLab `deploy/gear_assembly`
- MimicGen `nut_assembly`
- MimicGen `threading`
- MimicGen `three_piece_assembly`

### Planned scene contents

- robot arm and fixture
- alignment feature or insertion fixture
- one or more part proxies such as gear, nut, shaft, or assembly pin
- constrained insertion zone

### What changes per dataset case

- target insertion posture
- source family provenance
- insertion phase or retreat phase metadata
- unsafe overshoot or alignment-violation targets

### Recommended runtime artifacts

- `scene_pack/robot/robot_gear_assembly_cell/scene_builder.py`
- `scene_pack/robot/robot_gear_assembly_cell/robot_gear_assembly_cell.usd`
- `scene_pack/robot/robot_gear_assembly_cell/shell_config.json`

### Safety-validator connection

#### Rules Validator

Rules should include:

- joint limits
- optional insertion-depth or target-zone logic if encoded in metadata-derived
  features

#### Barrier-based validator

The barrier layer should focus on:

- constrained posture margins
- alignment-sensitive workspace envelope

#### Simulation Validator

The shell connects through:

- `simulation.world_ref = robot_gear_assembly_cell.usd`
- shell-specific workspace limits
- optional more restrictive contact-zone assumptions

#### Consensus

This shell is ideal for demonstrating:

- manufacturing-specific assembly provenance
- unsafe target rejection before actuation
- TOCTOU-sensitive assembly posture control in the full PCAG path

### Typical case families

- nominal alignment posture
- nominal insertion posture
- nominal retreat to safe pose
- unsafe insertion overshoot
- unsafe target posture outside assembly zone

## 5. AGV shells

AGV shells use map or grid configurations rather than USD scenes.

All AGV shells share:

- `asset_id = agv_01`
- sensor path aligned with `PLCAdapterSensorSource`
- simulation backend: `discrete_event`
- executable action subset: `move_to`

## 5.1 `agv_transfer_map`

### Scenario meaning

This shell represents a normal material-transfer route between stations.

### Intended source motifs

- warehouse station transfer
- normal path-following between loading and unloading points

### Planned map contents

- bounded grid
- source and destination stations
- static obstacles such as racks or machines
- nominal corridor path

### What changes per dataset case

- initial AGV position
- destination coordinates
- path variant
- transfer mission metadata

### Recommended runtime artifacts

- `scene_pack/agv/agv_transfer_map.json`
- `scene_pack/agv/agv_transfer_map_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should validate:

- in-bounds motion target
- allowed target zone
- optional speed or heading consistency if modeled

#### Barrier-based validator

The barrier layer should interpret:

- current AGV pose
- projected `move_to` target
- distance-to-boundary or zone-margin fields

#### Simulation Validator

The shell connects through a discrete-event config patch containing:

- `grid.width`
- `grid.height`
- `grid.obstacles`
- `agvs`
- `min_distance`

#### Consensus

This shell is mainly used for:

- clean `COMMITTED` AGV transfer cases
- fault-driven cases where integrity or transaction control, not path safety,
  dominates the outcome

## 5.2 `agv_docking_map`

### Scenario meaning

This shell represents final approach and docking at a station or handoff point.

### Intended source motifs

- docking approach
- final alignment at handoff station
- approach to robot or reactor handoff area

### Planned map contents

- docking station geometry
- narrow approach corridor
- no-go boundary near the station edge

### What changes per dataset case

- docking destination
- approach path
- safe versus overshoot target
- handoff metadata

### Recommended runtime artifacts

- `scene_pack/agv/agv_docking_map.json`
- `scene_pack/agv/agv_docking_map_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should encode:

- docking target bounds
- zone entry permissions
- optional low-speed or final-approach policy assumptions

#### Barrier-based validator

The barrier layer should reflect:

- distance-to-dock limits
- near-boundary safety margins

#### Simulation Validator

The shell connects through a docking-specific map patch containing:

- narrow corridor geometry
- docking station coordinates
- boundary obstacles or exclusion cells

#### Consensus

This shell is ideal for:

- distinguishing acceptable final approach from overshoot
- generating unsafe docking target cases

## 5.3 `agv_shared_zone_map`

### Scenario meaning

This shell represents a safety-critical shared zone such as an intersection,
handoff zone, or congestion area.

### Intended source motifs

- shared-zone entry
- congestion conflict
- crossing or mutual exclusion scenarios

### Planned map contents

- one or more intersections
- a critical shared zone
- potential conflicting AGV paths

### What changes per dataset case

- initial positions of one or more AGVs
- target path for `agv_01`
- optional interfering traffic assumptions
- safe wait-versus-proceed context

### Recommended runtime artifacts

- `scene_pack/agv/agv_shared_zone_map.json`
- `scene_pack/agv/agv_shared_zone_map_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should encode:

- zone permission logic
- in-bounds requirements
- optional mutual-exclusion metadata

#### Barrier-based validator

The barrier layer should track:

- minimum distance margins
- boundary approach
- zone occupancy features if mapped

#### Simulation Validator

This shell is the strongest AGV shell for the discrete-event backend because it
can express:

- conflicting paths
- minimum-distance violations
- shared-zone occupancy collisions

#### Consensus

This shell is expected to produce the clearest AGV `UNSAFE` cases in the paper.

## 6. Process shells

Process shells use parameter profiles rather than visual scenes.

All process shells share:

- `asset_id = reactor_01`
- sensor path aligned with `PLCAdapterSensorSource`
- simulation backend: `ode_solver`
- executable action subset: `set_heater_output`, `set_cooling_valve`

## 6.1 `reactor_nominal_profile`

### Scenario meaning

This shell represents normal operating envelope preservation.

### Intended source motifs

- TE-style normal operation
- thermal regulation within safe range
- interlock-compatible nominal supervisory control

### Planned profile contents

- nominal process parameters
- safe initial temperature and pressure
- moderate heater and cooling dynamics
- nominal ruleset envelope

### What changes per dataset case

- initial state within the nominal envelope
- target heater or cooling command
- normal-operation provenance

### Recommended runtime artifacts

- `scene_pack/process/reactor_nominal_profile.json`
- `scene_pack/process/reactor_nominal_profile_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should encode:

- temperature and pressure thresholds
- allowed actuation ranges
- incompatible command-combination rules when applicable

#### Barrier-based validator

The barrier layer should reflect:

- distance to thermal and pressure bounds
- actuation-driven projected state margins

#### Simulation Validator

The shell connects through:

- `simulation.engine = ode_solver`
- profile-specific `params`
- nominal horizon and step settings

#### Consensus

This shell is primarily for:

- nominal `COMMITTED` process cases
- low-risk safe-command baselines

## 6.2 `reactor_high_heat_profile`

### Scenario meaning

This shell represents stressed thermal operation where high heating or reduced
cooling can push the process toward an unsafe state.

### Intended source motifs

- manipulated-variable stress
- excessive thermal load
- insufficient cooling response

### Planned profile contents

- process parameters near thermal-risk conditions
- reduced safety margin to threshold
- stricter thermal envelope interpretation

### What changes per dataset case

- aggressive heater targets
- cooling reduction
- boundary-near initial state

### Recommended runtime artifacts

- `scene_pack/process/reactor_high_heat_profile.json`
- `scene_pack/process/reactor_high_heat_profile_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should strongly encode:

- maximum heater range
- temperature threshold safety
- cooling compatibility

#### Barrier-based validator

The barrier layer should show reduced distance to unsafe thermal states.

#### Simulation Validator

This shell is expected to produce:

- projected thermal overshoot
- pressure rise
- clear `UNSAFE` process traces

#### Consensus

This shell is the main process shell for unsafe action interception.

## 6.3 `reactor_disturbance_profile`

### Scenario meaning

This shell represents disturbance-inspired or fault-inspired process
supervision.

### Intended source motifs

- TE-style disturbance references
- process upset conditions
- interlock or corrective supervisory action context

### Planned profile contents

- perturbed initial conditions
- disturbance-aware parameter settings
- recovery or stabilization context

### What changes per dataset case

- initial disturbed state
- corrective or unsafe actuation command
- disturbance provenance metadata

### Recommended runtime artifacts

- `scene_pack/process/reactor_disturbance_profile.json`
- `scene_pack/process/reactor_disturbance_profile_notes.md`

### Safety-validator connection

#### Rules Validator

Rules should encode:

- disturbed-state envelope limits
- corrective action bounds

#### Barrier-based validator

The barrier layer should emphasize:

- reduced margin to unsafe operating zones
- corrective versus destabilizing actuation difference

#### Simulation Validator

This shell is useful for:

- disturbance recovery nominal cases
- unsafe disturbance-amplifying commands
- integrity and reverify stress cases layered on top of a realistic process
  upset context

#### Consensus

This shell provides the strongest process justification for fault-inspired
benchmarking in the paper.

## 7. How dataset values interact with these shells

The shell is fixed.
The case-specific benchmark values are variable.

For every shell, dataset cases may change:

- initial state
- actuation target
- mission phase
- proof-hint strategy
- label triplet
- mutation provenance

What does **not** change per case:

- the shell's runtime structure
- the shell's validator-facing assumptions
- the shell's provenance alignment class

This is the main reason the benchmark remains reproducible.

## 8. Safety Cluster integration expectation

When these shells are implemented as files, each one should be integrated
through the benchmark scene/profile registry and the runtime-context override
strategy described in:

- [safety_cluster_scene_integration_strategy.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/generation/safety_cluster_scene_integration_strategy.md)

Expected flow:

1. dataset case declares `runtime_id`
2. benchmark runner resolves `runtime_id`
3. Gateway forwards `runtime_context`
4. Safety Cluster resolves the registry entry
5. simulation config is patched
6. robot scenes are preloaded when needed

## 9. Recommended implementation order

The first actual shell implementation should proceed in this order:

1. `robot_pick_place_cell`
2. `agv_transfer_map`
3. `reactor_nominal_profile`
4. `robot_gear_assembly_cell`
5. `agv_shared_zone_map`
6. `reactor_high_heat_profile`
7. remaining shells

This order gives one nominal-ready shell per asset family early, which makes it
possible to start drafting the first benchmark batch sooner.
