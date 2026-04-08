# PCAG IJAMT Benchmark Scene Pack

This directory contains the canonical runtime shells used by the IJAMT
benchmark workflow.

The scene pack is intentionally asset-specific.

- `robot/` stores USD shells or scene-building scripts
- `agv/` stores map or grid configuration shells
- `process/` stores process parameter profile shells
- `registry/` stores the frozen shell catalog and, later, the executable
  registry manifest

## Current implementation status

The first canonical shells are already implemented as runnable builder
scripts with generated runtime artifacts.

- `robot/robot_pick_place_cell/`
  - `scene_builder.py`
  - `robot_pick_place_cell.usd`
  - `shell_config.json`
- `robot/robot_stack_cell/`
  - `scene_builder.py`
  - `robot_stack_cell.usd`
  - `shell_config.json`
- `robot/robot_narrow_clearance_cell/`
  - `scene_builder.py`
  - `robot_narrow_clearance_cell.usd`
  - `shell_config.json`
- `robot/robot_fixture_insertion_cell/`
  - `scene_builder.py`
  - `robot_fixture_insertion_cell.usd`
  - `shell_config.json`
- `agv/agv_transfer_map/`
  - `map_builder.py`
  - `agv_transfer_map.json`
  - `shell_config.json`
- `agv/agv_docking_map/`
  - `map_builder.py`
  - `agv_docking_map.json`
  - `shell_config.json`
- `agv/agv_shared_zone_map/`
  - `map_builder.py`
  - `agv_shared_zone_map.json`
  - `shell_config.json`
- `process/reactor_nominal_profile/`
  - `profile_builder.py`
  - `reactor_nominal_profile.json`
  - `shell_config.json`
- `process/reactor_high_heat_profile/`
  - `profile_builder.py`
  - `reactor_high_heat_profile.json`
  - `shell_config.json`
- `process/reactor_disturbance_profile/`
  - `profile_builder.py`
  - `reactor_disturbance_profile.json`
  - `shell_config.json`

`robot_pick_place_cell` and `robot_stack_cell` are now both benchmark-safe
robot shells validated in the public robot benchmark. Each includes:

- a canonical Franka spawn pose
- collider-backed runtime objects
- safety-probe metadata for fixture-aware unsafe detection
- shell-declared safety motion profiles for manual smoke validation

These implemented folders are now the reference implementation pattern for the
remaining canonical shells.

`robot_narrow_clearance_cell` is the first robot expansion shell added after
the validated v1 release. It is intended for phase-A narrow-clearance approach
and insertion-adjacent benchmark cases and currently serves as the runtime
envelope for `robot_source_release_v2`.

`robot_fixture_insertion_cell` is the next robot expansion shell added for the
draft fixture-insertion family in `robot_source_release_v3`. It reuses the
pick-place layout but replaces the target zone with a deeper insertion
corridor. The current family-level validation status is:

- `robot_narrow_clearance_cell` -> `28/28 pass`
- `robot_fixture_insertion_cell` -> `12/12 pass`

The AGV benchmark now has three runtime-ready map shells:

- `agv_transfer_map` for transfer-lane logistics cases
- `agv_docking_map` for docking, station-approach, and bay-alignment cases
- `agv_shared_zone_map` for shared-intersection and occupancy-conflict cases

The process benchmark now has three runtime-ready profile shells:

- `reactor_nominal_profile` for baseline envelope-preservation cases
- `reactor_high_heat_profile` for high-heat recovery and pressure-risk cases
- `reactor_disturbance_profile` for disturbance-amplified pressure-risk cases

## Normative references

The canonical first-release shell definitions are recorded in:

- [canonical_shell_catalog.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/scene_pack/registry/canonical_shell_catalog.md)

The scene-pack strategy is defined in:

- [scene_pack_strategy.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/generation/scene_pack_strategy.md)

The Safety Cluster integration strategy is defined in:

- [safety_cluster_scene_integration_strategy.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/benchmarks/pcag_ijamt_benchmark/generation/safety_cluster_scene_integration_strategy.md)

## Important interpretation note

The robot shell is already materialized as a benchmark USD environment shell,
but full benchmark execution still requires the runtime resolver and preload
flow described in the Safety Cluster integration strategy.

The AGV and process shells are closer to immediate runtime use because their
simulation backends already accept map/profile patches directly.

For process benchmarking, the ODE solver can also drive the persistent reactor
GUI viewer used by `run_process_pcag_benchmark.py`.

No benchmark case should reference runtime scenes or profiles that are not
listed in the frozen registry once the registry is created.
