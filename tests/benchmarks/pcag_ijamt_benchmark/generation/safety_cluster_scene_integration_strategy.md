# PCAG IJAMT Safety Cluster Scene Integration Strategy

Status: benchmark runtime integration strategy before scene-pack implementation  
Version: `v1-integration`

## 1. Why this document exists

Defining benchmark scene packs is not enough by itself.

Once robot USD scenes, AGV map configs, and process profiles are created, the
benchmark still needs a way to connect those runtime artifacts to the current
PCAG execution flow.

This document explains:

- how the current Safety Cluster already supports parts of this flow
- what is still missing
- how benchmark scene packs should be integrated without rebuilding PCAG

## 2. Current integration hooks already present in the codebase

The current stack is not scene-pack-ready, but it is also not starting from
zero.

## 2.1 SimulationConfig already exposes `world_ref`

The policy model already contains:

- `simulation.engine`
- `simulation.world_ref`

Evidence:

- `pcag/core/models/policy.py`

This means the data model already has a place to carry a robot-scene reference.

## 2.2 Safety Cluster already forwards simulation configuration

The Safety Cluster service:

- loads the asset policy profile
- extracts `simulation`
- selects the backend
- passes simulation constraints to the selected backend

Evidence:

- `pcag/apps/safety_cluster/service.py`

## 2.3 Isaac backends already support scene reload

Both the Isaac worker and the Isaac backend already contain logic for scene
reload when a `world_ref` points to a `.usd` file.

Evidence:

- `pcag/apps/safety_cluster/isaac_worker.py`
- `pcag/plugins/simulation/isaac_backend.py`

This is the most important reason we do **not** need to redesign the Safety
Cluster from scratch.

## 2.4 AGV and process backends already use non-USD runtime representations

The AGV backend already runs on grid or map-like configuration.

Evidence:

- `pcag/plugins/simulation/discrete_event.py`

The process backend already runs on parameter profiles and current-state values.

Evidence:

- `pcag/plugins/simulation/ode_solver.py`

This means AGV and process integration should not mimic the robot USD flow.

## 3. Why the current structure is still not enough

The present runtime is only partially scene-aware.

Three key limitations remain.

## 3.1 Policy-level `world_ref` is too static

Right now `simulation.world_ref` belongs to the asset policy profile.

That works if:

- one asset always uses one scene

But it does **not** work well for a benchmark where:

- `robot_arm_01` must be evaluated across multiple canonical scenes
- AGV cases may require multiple map configurations
- reactor cases may require multiple process profiles

So a benchmark cannot rely on one static per-asset scene reference.

## 3.2 The Safety contract does not yet carry runtime-scene context

The current Safety request contract contains:

- `transaction_id`
- `asset_id`
- `policy_version_id`
- `action_sequence`
- `current_sensor_snapshot`

Evidence:

- `pcag/core/contracts/safety.py`

There is currently no explicit field for:

- `scene_id`
- `map_id`
- `profile_id`
- benchmark runtime override

## 3.3 Robot sensor reads depend on Safety Cluster scene state

The robot sensor path is special:

- the robot sensor source reads simulation state from Safety Cluster
- that means the current Isaac scene must already match the intended benchmark
  case when the snapshot is collected

Evidence:

- `pcag/plugins/sensor/isaac_sim_sensor.py`
- `pcag/apps/safety_cluster/routes.py`

This means benchmark runtime integration must solve **both**:

- simulation-scene selection during validation
- scene preload before robot sensor snapshot generation

## 4. Integration principles

The benchmark integration should follow four principles.

### Principle 1. Do not fork the main validation architecture

The benchmark should reuse:

- Gateway
- Safety Cluster
- Sensor Gateway
- OT Interface
- Evidence Ledger

The benchmark should not create a separate parallel validation stack just for
paper experiments.

### Principle 2. Runtime scene selection must be explicit and per-case

Benchmark scenes, maps, and process profiles should be selected:

- per case
- through stable registry-controlled IDs
- not through hidden implicit defaults

### Principle 3. Runtime overrides must remain optional

Production-like flows should still work with ordinary policy-driven defaults.

The benchmark integration should add optional runtime override paths rather than
replacing normal behavior.

### Principle 4. Provenance and runtime representation must stay linked

Each case must preserve both:

- source provenance
- canonical runtime representation

The paper should be able to explain how a source family maps to a concrete
runtime artifact.

## 5. Recommended integration architecture

The recommended strategy is:

> add a benchmark runtime registry and allow per-request runtime overrides that
> are resolved inside the Gateway/Safety path.

This involves four layers.

## 5.1 Scene pack registry layer

Create a frozen registry under:

- `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/registry/`

Each entry should describe a canonical runtime artifact.

Recommended fields:

- `runtime_id`
- `asset_family`
- `runtime_type`
  - `usd`
  - `map_config`
  - `process_profile`
- `local_ref`
- `simulation_patch`
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

## 5.2 Benchmark runtime override layer

The benchmark case should carry a runtime selector such as:

- `runtime_id`

This should not replace policy metadata.
It should act as a benchmark-only override.

Recommended location:

- inside the benchmark dataset case metadata
- then translated by the benchmark runner into request metadata

## 5.3 Gateway forwarding layer

The current ProofPackage model allows extra fields.

Evidence:

- `pcag/core/contracts/proof_package.py`

That means the benchmark can safely attach structured runtime metadata without
breaking the existing proof schema.

Recommended benchmark extension field:

- `runtime_context`

Suggested contents:

- `runtime_id`
- `runtime_type`
- `scene_id` / `map_id` / `profile_id`
- optional provenance echo

The Gateway should preserve this field and forward it to Safety Cluster in an
explicit request field such as:

- `runtime_context`

This requires a small contract extension to:

- `pcag/core/contracts/safety.py`

## 5.4 Safety Cluster resolver layer

Inside Safety Cluster, add a registry resolver step before validator fan-out.

Recommended location:

- `pcag/apps/safety_cluster/service.py`

The resolver should:

1. inspect the incoming optional `runtime_context`
2. load the matching registry entry
3. merge the registry's `simulation_patch` into the policy-derived simulation
   config
4. pass the merged config to the selected simulation backend

This lets the benchmark override runtime representation per case while keeping
policy defaults as the baseline.

## 6. Asset-specific integration behavior

## 6.1 Robot integration

Robot integration is the most demanding because runtime state and sensor state
share the same Isaac environment.

### Required behavior

For robot cases, the benchmark runtime patch should typically set:

- `simulation.engine = isaac_sim`
- `simulation.world_ref = <scene usd path>`
- optional scene-specific `joint_limits`
- optional `workspace_limits`
- optional `torque_limits`

### Additional requirement: scene preload

Robot benchmark cases should preload the target scene **before** sensor snapshot
generation.

Without this step:

- Safety validation may use the intended benchmark scene
- but Sensor Gateway may still read state from the previous scene

### Recommended preload strategy

Add a benchmark-only scene preload endpoint or preload hook that:

1. resolves `runtime_id`
2. asks Safety Cluster to load the target Isaac scene
3. waits until the scene is ready
4. only then triggers Sensor Gateway snapshot collection

This preload should be handled by the benchmark runner, not by production
traffic.

## 6.2 AGV integration

AGV integration should not preload a USD scene.

Instead, the registry entry should inject a map configuration into the
simulation config.

Recommended patch contents:

- `grid.width`
- `grid.height`
- `grid.obstacles`
- `grid.intersections`
- `agvs`
- `min_distance`

Safety Cluster should merge these values into the discrete-event backend config
before validation.

Sensor behavior is simpler here because AGV sensor state is not tied to a
visual Isaac scene.

## 6.3 Process/reactor integration

Process integration should use parameter-profile overrides rather than scenes.

Recommended patch contents:

- `simulation.engine = ode_solver`
- `simulation.params`
- optional `horizon_ms`
- optional `dt_ms`
- optional envelope-related profile metadata

Safety Cluster should merge these values into the ODE backend config before
validation.

## 7. Recommended implementation order

This order keeps the integration incremental and low-risk.

### Phase 1. Registry and artifacts

- create scene/profile artifacts
- create registry files
- assign stable runtime IDs

### Phase 2. Contract extension

- extend benchmark runner metadata
- add optional `runtime_context` to the Safety request contract
- forward this field from Gateway to Safety Cluster

### Phase 3. Safety resolver

- add runtime registry resolver in Safety Cluster
- merge registry patches into simulation config

### Phase 4. Robot preload support

- add benchmark-only scene preload mechanism
- make robot benchmark runs preload the scene before snapshot capture

### Phase 5. Benchmark dataset drafting

- only after Phases 1-4 should the first robot benchmark dataset batch be
  drafted

AGV and process drafting can begin slightly earlier because they do not need
Isaac scene preload, but keeping one common workflow is cleaner for the paper
artifact.

## 8. Minimal viable integration for the first paper release

If implementation time is limited, the first paper release should aim for:

### Required

- frozen registry
- runtime-context forwarding
- Safety Cluster simulation-config merge
- robot scene preload support

### Nice to have

- generic benchmark preload API
- automatic registry validation
- scene warm-cache optimization

## 9. What should not be done

The benchmark should avoid:

- hardcoding benchmark scene paths into policy profiles
- creating one-off benchmark scripts that bypass Gateway and Safety Cluster
- storing runtime scene selection only in external notes instead of request
  metadata
- coupling AGV and process cases to robot-style USD assumptions

## 10. Paper wording guidance

The paper should describe this as:

- a benchmark-specific runtime scene/profile registry
- per-case runtime standardization for heterogeneous assets
- integration through optional runtime-context overrides resolved by the Safety
  Cluster

The paper should avoid claiming that all scenes are statically embedded in the
production policy store.

## 11. Immediate next step

The next implementation task should be:

1. define the scene/profile registry schema
2. define the benchmark `runtime_context` schema
3. create the first runtime artifact for each asset family
4. implement the Safety Cluster registry resolver
5. implement robot scene preload support
