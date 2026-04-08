# PCAG IJAMT Benchmark

This directory stores the active benchmark workspace used for the IJAMT paper
preparation flow.

It now contains:

- per-asset frozen benchmark releases for robot, AGV, and process
- one unified benchmark policy spanning all three asset families
- one integrated cross-asset benchmark release assembled from the validated
  asset releases
- one machine-readable single-asset family expansion spec for the next
  benchmark-growth phase
- Gateway-facing runners for per-asset and integrated execution

These files remain the normative source for:

- supervisory action naming
- scenario-family assignment
- expected final-status, stop-stage, and reason-code labels
- source provenance and acquisition state
- runtime shell or profile normalization
- benchmark policy alignment
- full-PCAG execution expectations

## Current validated execution status

The currently validated live benchmark status is:

- robot benchmark v1:
  - `36/36 pass`
  - result file:
    `tests/benchmarks/pcag_ijamt_benchmark/results/robot_pcag_benchmark_latest.json`
- robot benchmark v4 expansion:
  - `120/120 pass`
  - result file:
    `tests/benchmarks/pcag_ijamt_benchmark/results/robot_pcag_benchmark_latest.json`
- AGV benchmark v2:
  - `44/44 pass`
  - result file:
    `tests/benchmarks/pcag_ijamt_benchmark/results/agv_pcag_benchmark_latest.json`
- AGV benchmark v3 expansion:
  - `128/128 pass`
  - dataset:
    `tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v3/pcag_execution_dataset.json`
- process benchmark v1:
  - `36/36 pass`
  - result file:
    `tests/benchmarks/pcag_ijamt_benchmark/results/process_pcag_benchmark_latest.json`
- process benchmark v2 expansion:
  - `120/120 pass`
  - dataset:
    `tests/benchmarks/pcag_ijamt_benchmark/releases/process_source_release_v2/pcag_execution_dataset.json`

The integrated cross-asset release is now assembled and ready for live
execution:

- integrated benchmark release v2:
  - `368 total cases`
  - source release:
    `tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2`
  - live runner:
    `tests/benchmarks/pcag_ijamt_benchmark/run_integrated_pcag_benchmark.py`

At the current paper-writing stage:

- `robot_source_release_v1` is the validated robot release
- `robot_source_release_v2` is the draft robot expansion release with the
  first phase-A narrow-clearance family expanded on top of the validated v1
  core
- `robot_source_release_v3` is the next robot expansion draft layered on top
  of v2 with the initial fixture-insertion family
- `robot_source_release_v4` is the expanded robot draft that reaches the
  planned `120`-case robot target by expanding `fixture_insertion` and adding
  `conveyor_timing_pick`
- `agv_source_release_v2` is the validated AGV baseline release
- `agv_source_release_v3` is the expanded AGV draft release with
  `merge_bottleneck`, `single_lane_corridor`, and
  `dock_occupancy_conflict`
- `process_source_release_v1` is the validated process release
- `process_source_release_v2` is the expanded process draft release with
  `startup_ramp`, `cooling_failure_management`, and
  `pressure_relief_margin`
- `integrated_benchmark_release_v2` is the unified cross-asset benchmark
  release assembled from the expanded robot v4, AGV v3, and process v2
  releases

## Unified benchmark policy

The active benchmark registration target is now the unified policy artifact:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

Compatibility wrappers are retained for convenience:

- `python scripts/seed_robot_benchmark_policy.py`
- `python scripts/seed_agv_benchmark_policy.py`
- `python scripts/seed_process_benchmark_policy.py`

These wrappers now seed the same unified benchmark policy rather than
re-activating asset-specific policy documents.

## Current implemented runtime artifacts

The benchmark workspace now includes ten concrete runtime artifacts:

- `scene_pack/robot/robot_pick_place_cell/`
- `scene_pack/robot/robot_stack_cell/`
- `scene_pack/robot/robot_narrow_clearance_cell/`
- `scene_pack/robot/robot_fixture_insertion_cell/`
- `scene_pack/agv/agv_transfer_map/`
- `scene_pack/agv/agv_docking_map/`
- `scene_pack/agv/agv_shared_zone_map/`
- `scene_pack/process/reactor_nominal_profile/`
- `scene_pack/process/reactor_high_heat_profile/`
- `scene_pack/process/reactor_disturbance_profile/`

## Centralized digital-twin GUI mode

The public benchmark stack can now run in a centralized server-driven GUI mode.

If Safety Cluster is started with:

- `PCAG_ENABLE_ISAAC=true`
- `PCAG_ENABLE_BENCHMARK_TWIN_GUIS=true`

then Safety Cluster startup will:

- boot Isaac Sim through the Isaac worker path
- open the persistent AGV grid viewer
- open the persistent process reactor viewer

In that mode, benchmark runners only need to submit dataset cases.

Configuration can be managed through:

- the root `.env`
- `config/services.yaml -> benchmark_runtime`

## Current frozen dataset releases

### Robot release

- `releases/robot_source_release_v1/`
- live runner:
  `run_robot_pcag_benchmark.py`
- live status:
  `36/36 pass`

Robot benchmark execution is hybrid in the current public stack:

- state acquisition is Isaac-backed
- safety validation is Isaac-backed
- final commit acknowledgement is mock-backed

### Robot expansion release

- `releases/robot_source_release_v2/`
- live runner:
  `run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v2/pcag_execution_dataset.json`
- current state:
  `family-validated expansion release`
- generated size:
  `64 total = 18 COMMITTED / 26 UNSAFE / 11 REJECTED / 6 ABORTED / 3 ERROR`

Robot v2 preserves the validated v1 core cases and adds the first phase-A
single-asset family:

- `narrow_clearance_approach`
- canonical shell:
  `scene_pack/robot/robot_narrow_clearance_cell/`
- supplemental family count:
  `28`

The full `28`-case `narrow_clearance_approach` family has now been validated
through the live PCAG stack:

- family result:
  `28/28 pass`
- result file:
  `tests/benchmarks/pcag_ijamt_benchmark/results/robot_narrow_clearance_family_latest.json`

### Robot expansion release v3

- `releases/robot_source_release_v3/`
- live runner:
  `run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v3/pcag_execution_dataset.json`
- current state:
  `family-validated draft release`
- generated size:
  `76 total = 22 COMMITTED / 30 UNSAFE / 14 REJECTED / 7 ABORTED / 3 ERROR`

Robot v3 preserves the validated v2 cases and adds the next robot family:

- `fixture_insertion`
- canonical shell:
  `scene_pack/robot/robot_fixture_insertion_cell/`
- supplemental family count:
  `12`

The full initial `12`-case `fixture_insertion` family has now been validated
through the live PCAG stack:

- family result:
  `12/12 pass`
- result file:
  `tests/benchmarks/pcag_ijamt_benchmark/results/robot_fixture_insertion_family_latest.json`

### Robot expansion release v4

- `releases/robot_source_release_v4/`
- live runner:
  `run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json`
- current state:
  `120-case expanded robot draft release`
- generated size:
  `120 total = 34 COMMITTED / 50 UNSAFE / 19 REJECTED / 10 ABORTED / 7 ERROR`

Robot v4 preserves the generated v3 cases and completes the planned robot
single-asset expansion target:

- `narrow_clearance_approach`: `28`
- `fixture_insertion`: `28`
- `conveyor_timing_pick`: `28`

Current v4 status:

- full live sweep completed
- final result:
  `120/120 pass`

### AGV historical release

- `releases/agv_source_release_v1/`

AGV v1 remains useful as a lighter historical baseline release for
single-command AGV evaluation and quick debugging.

### AGV concurrent-motion release

- `releases/agv_source_release_v2/`
- live runner:
  `run_agv_pcag_benchmark.py`
- live status:
  `44/44 pass`

AGV v2 preserves the v1 coverage and adds concurrent-motion difficulty:

- simultaneous shared-zone crossing
- head-on corridor conflict
- edge-swap conflict
- three-AGV deadlock-cycle risk

### AGV expansion release v3

- `releases/agv_source_release_v3/`
- live runner:
  `run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v3/pcag_execution_dataset.json`
- generated size:
  `128 total = 40 COMMITTED / 52 UNSAFE / 19 REJECTED / 13 ABORTED / 4 ERROR`

AGV v3 preserves the validated v2 release and adds the planned single-asset
families:

- `merge_bottleneck`: `28`
- `single_lane_corridor`: `28`
- `dock_occupancy_conflict`: `28`

Representative live scenario-wise runs now pass for each family's nominal,
unsafe, and fault paths.

### Process release

- `releases/process_source_release_v1/`
- live runner:
  `run_process_pcag_benchmark.py`
- live status:
  `36/36 pass`

### Process expansion release v2

- `releases/process_source_release_v2/`
- live runner:
  `run_process_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/process_source_release_v2/pcag_execution_dataset.json`
- generated size:
  `120 total = 36 COMMITTED / 48 UNSAFE / 17 REJECTED / 15 ABORTED / 4 ERROR`

Process v2 preserves the validated v1 release and adds the planned
single-asset families:

- `startup_ramp`: `28`
- `cooling_failure_management`: `28`
- `pressure_relief_margin`: `28`

Representative live scenario-wise runs now pass for each family's nominal,
unsafe, and fault paths.

### Integrated release

- `releases/integrated_benchmark_release_v2/`
- live runner:
  `run_integrated_pcag_benchmark.py`

Integrated execution manifest:

- `368 total`
- `110 COMMITTED`
- `150 UNSAFE`
- `55 REJECTED`
- `38 ABORTED`
- `15 ERROR`

This release is designed to run under the unified benchmark policy without
asset-by-asset reseeding.

## Recommended commands

Register the unified benchmark policy:

- `python scripts/seed_pcag_benchmark_policy.py`

Run robot benchmark:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py`

Run robot benchmark v2 draft expansion:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v2/pcag_execution_dataset.json`

Run robot benchmark v3 fixture-insertion draft:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v3/pcag_execution_dataset.json`

Run robot benchmark v4 expanded draft:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json`

Run AGV benchmark v2:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v2/pcag_execution_dataset.json`

Run AGV benchmark v3 expansion:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v3/pcag_execution_dataset.json`

Run process benchmark:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_process_pcag_benchmark.py`

Run process benchmark v2 expansion:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_process_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/process_source_release_v2/pcag_execution_dataset.json`

Run integrated cross-asset benchmark:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_integrated_pcag_benchmark.py`

## Usage rule

If a new case or baseline result uses an action name, stage label, or reason
code that is not present in the benchmark reference files, update the
specification first before freezing the case.

## Next expansion reference

The next benchmark-growth phase is fixed around nine harder single-asset
families rather than cross-asset coordinated commit.

Reference files:

- `family_expansion_spec_v1.json`
- `plans/IJAMT/PCAG_IJAMT_Single_Asset_Expansion_Roadmap.md`

## Unified structure reference

The cross-asset schema and final-labeling rule are defined in:

- [PCAG_IJAMT_Integrated_Benchmark_Dataset_Structure.md](C:/Users/choiLee/Dropbox/寃쎈궓??숆탳/AI%20agent%20湲곕컲?쇰줈%20臾쇰━%20?섍꼍%20?쒖뼱/plans/IJAMT/PCAG_IJAMT_Integrated_Benchmark_Dataset_Structure.md)

Use that document as the top-level reference for robot, AGV, process, and
integrated benchmark updates.
