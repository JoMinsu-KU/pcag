# PCAG IJAMT Benchmark Scene Pack Strategy

Status: frozen scene/world standardization strategy before dataset authoring  
Version: `v1-scene-strategy`

## 1. Why this document exists

The benchmark cannot stop at source provenance and action normalization.

PCAG ultimately validates commands against runtime representations:

- Isaac scenes for robot cases
- grid or map configurations for AGV cases
- process parameter profiles for reactor/process cases

Therefore, the benchmark must define **how source-aligned scenarios are turned
into canonical runtime scenes** before case JSON files are drafted.

This document exists to answer three practical questions:

1. Do we need to rebuild the entire PCAG simulation stack?
2. Which assets need new benchmark scene scripts?
3. What runtime representation should each asset family use in the first frozen
   release?

## 2. Core decision

The benchmark does **not** require rebuilding the full PCAG simulation stack.

Instead, it requires a new **benchmark scene/world layer** that sits on top of
the current runtime structure.

### What is reused as-is

- the Safety Cluster orchestration
- the Isaac worker / proxy split
- the Isaac backend validation flow
- the AGV discrete-event backend
- the reactor ODE backend
- the sensor / executor / gateway pipeline

### What must be added

- benchmark-specific robot scene definitions
- benchmark-specific AGV map configurations
- benchmark-specific process parameter profiles
- a scene/profile registry that benchmark cases can reference

In short:

> We do not rebuild PCAG. We extend PCAG with a benchmark scene-pack layer.

## 3. Current state of the codebase

## 3.1 Robot path

The current robot validation path already supports scene references.

Evidence in the code:

- `pcag/apps/safety_cluster/isaac_worker.py`
- `pcag/plugins/simulation/isaac_backend.py`

Both modules can reload a scene when a `world_ref` points to a `.usd` file.
When no `world_ref` is given, the current public path falls back to a generic
Franka robot with a ground plane.

That means the robot runtime is already **scene-capable**, but the repository
does not yet contain a benchmark-ready robot scene pack.

## 3.2 AGV path

The AGV simulation path does not use USD scenes.

The current runtime representation is already map-like:

- grid width and height
- obstacles
- intersections
- AGV positions
- minimum-distance constraints

Evidence in the code:

- `pcag/plugins/simulation/discrete_event.py`

Therefore, AGV benchmark "scene" design should be implemented as a **map/config
pack**, not as a USD scene pack.

## 3.3 Process/reactor path

The reactor/process simulation path also does not use USD scenes.

The runtime representation is:

- process state
- process parameters
- safety ruleset
- action sequence

Evidence in the code:

- `pcag/plugins/simulation/ode_solver.py`

Therefore, process benchmark "scene" design should be implemented as a
**parameter/profile pack**, not as 3D scenes.

## 4. Asset-specific runtime representation strategy

The benchmark uses different runtime scene representations for different asset
families.

## 4.1 Robot -> USD scene pack

Robot cases require a visual and physics-backed runtime scene.

For the first release, robot source families should be grouped into a small set
of canonical benchmark scenes rather than building one scene per upstream task.

### Why not one USD per source task?

- too expensive to maintain
- weakens reproducibility if every task creates a slightly different scene
- unnecessary for PCAG, which validates supervisory execution rather than
  replaying entire upstream learning environments

### Recommended canonical robot scenes

#### `robot_pick_place_cell`

Used for:

- `reach`
- `lift`
- `pick_place`
- `place`

Typical contents:

- Franka or equivalent robot
- table or workbench
- source tray / source zone
- target fixture / target zone
- simple part objects

#### `robot_stack_cell`

Used for:

- `stack`
- placement and multi-object positioning variants

Typical contents:

- robot
- workspace table
- stackable blocks or parts
- target stacking fixture

#### `robot_gear_assembly_cell`

Used for:

- IsaacLab `deploy/gear_assembly`
- MimicGen `nut_assembly`
- MimicGen `threading`
- MimicGen `three_piece_assembly`

Typical contents:

- robot
- assembly fixture
- gear / nut / threaded-part proxies
- alignment pose and insertion zone

### Robot benchmark runtime rule

Every robot case should eventually contain:

- `scene_id`
- `world_ref`
- `source_benchmark`
- `action_sequence` with `move_joint` and `target_positions`

The source task family remains provenance.
The canonical USD scene is the benchmark runtime environment.

## 4.2 AGV -> map/config pack

AGV cases should not use USD in release `v1`.

Instead, they should use canonical map/config files that match the current
discrete-event backend.

### Recommended canonical AGV maps

#### `agv_transfer_map`

Used for:

- station-to-station transport
- in-bounds nominal movement

Typical contents:

- grid size
- loading and unloading stations
- static obstacles
- initial AGV position

#### `agv_docking_map`

Used for:

- final approach
- docking alignment
- handoff preparation

Typical contents:

- docking pose
- station boundary
- approach corridor

#### `agv_shared_zone_map`

Used for:

- shared-zone entry
- congestion or collision conflict
- wait-versus-proceed supervision logic

Typical contents:

- shared critical zone
- intersections
- possible conflicting paths

### AGV benchmark runtime rule

Every AGV case should eventually contain:

- `scene_id`
- `map_ref`
- `source_benchmark`
- `action_sequence` lowered to `move_to`

The public warehouse source remains provenance.
The canonical map config is the benchmark runtime environment.

## 4.3 Process/reactor -> parameter/profile pack

Process cases should use canonical parameter profiles rather than scenes.

### Recommended canonical process profiles

#### `reactor_nominal_profile`

Used for:

- nominal envelope-preserving cases
- moderate heating and cooling settings

Typical contents:

- mass, heat capacity, heater power, cooling coefficient
- initial safe temperature and pressure
- nominal ruleset

#### `reactor_high_heat_profile`

Used for:

- unsafe over-heating mutations
- insufficient cooling scenarios

Typical contents:

- same structure as nominal profile
- stricter or stressed thermal operating point

#### `reactor_disturbance_profile`

Used for:

- disturbance-inspired cases
- fault-style supervision or correction logic

Typical contents:

- perturbed initial conditions
- benchmark-style process envelope references

### Process benchmark runtime rule

Every process case should eventually contain:

- `scene_id` or `profile_id`
- `profile_ref`
- `source_benchmark`
- executable process actions such as `set_heater_output` and
  `set_cooling_valve`

The TE-style reference remains provenance.
The canonical process profile is the benchmark runtime environment.

## 5. What must be built next

The benchmark should proceed in the following order.

### Phase 1. Freeze the scene-pack design

This document completes that phase by fixing:

- which runtime representation is used per asset family
- which canonical packs are needed first
- how cases should reference them

### Phase 2. Build the benchmark scene pack

This phase creates the actual benchmark runtime artifacts.

Required outputs:

- robot USD or USD-building scripts
- AGV map JSON or YAML files
- process profile JSON files
- a registry document that maps `scene_id` to runtime file references

### Phase 3. Draft dataset cases against frozen scene/profile IDs

Only after the runtime scene/profile layer exists should the first nominal
dataset batch be drafted.

This avoids the common failure mode where cases are written first and later have
no stable scene representation to execute against.

## 6. Why dataset authoring should wait until this phase is complete

The benchmark should not draft nominal cases before scene/profile IDs are frozen,
because otherwise:

- case metadata must be rewritten later
- source-to-runtime provenance becomes ambiguous
- paper reproducibility becomes weak
- some robot cases may reference motion semantics with no corresponding scene

For the first release, the correct order is:

1. freeze sources
2. freeze selected task families
3. freeze scene/profile strategy
4. build scene pack
5. draft dataset cases
6. derive unsafe and fault variants

## 7. Recommended registry fields

When the scene pack is implemented, each runtime artifact should be registered
with fields such as:

- `scene_id`
- `asset_family`
- `runtime_type` (`usd`, `map_config`, `process_profile`)
- `source_alignment`
- `local_ref`
- `notes`

Examples:

- `robot_pick_place_cell`
- `robot_stack_cell`
- `robot_gear_assembly_cell`
- `agv_transfer_map`
- `agv_docking_map`
- `agv_shared_zone_map`
- `reactor_nominal_profile`
- `reactor_high_heat_profile`
- `reactor_disturbance_profile`

## 8. Paper wording guidance

The paper should not claim that upstream datasets are replayed verbatim in the
PCAG runtime.

Instead, the paper should say:

- public source task families were frozen as provenance
- source families were normalized into canonical benchmark runtime scenes or
  profiles
- supervisory command cases were authored against those canonical runtime
  representations

This wording is both accurate and defensible.

## 9. Immediate next step

The next benchmark implementation task should be:

1. create the benchmark scene-pack workspace
2. define the scene/profile registry
3. implement robot canonical scene scripts
4. implement AGV map configs
5. implement process profile files

Only then should `nominal_dataset_first_batch.json` be drafted.
