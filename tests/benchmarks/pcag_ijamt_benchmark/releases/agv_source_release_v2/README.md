# AGV Source Release v2

This folder contains the recommended frozen AGV benchmark release.

`agv_source_release_v2` preserves the full outcome-complete v1 release and
adds a concurrency supplement closer to the original multi-AGV planning
scenario.

## Files

- `nominal_dataset.json`
- `unsafe_dataset.json`
- `fault_dataset.json`
- `all_cases.json`
- `pcag_execution_dataset.json`
- `pcag_execution_manifest.json`
- `pcag_execution_qc.md`
- `dataset_manifest.json`
- `qc_report.md`

## Generators

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_source_release_v2.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_pcag_execution_dataset_v2.py`

## Policy alignment

This release is aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`
- policy profile:
  `pcag_benchmark_v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

Compatibility wrapper:

- `python scripts/seed_agv_benchmark_policy.py`

## Live runner

- `tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py`

Recommended command:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v2/pcag_execution_dataset.json`

## Key differences from v1

- concurrent-motion supplement cases are added on top of the v1 release
- dynamic background AGV paths are expressed through
  `runtime_context.simulation_override.agvs[*].path`
- unsafe concurrency cases include:
  - same-cell collision during simultaneous crossing
  - head-on corridor conflict
  - edge-swap conflict
  - three-AGV deadlock-cycle risk

## Release size

- `nominal=16`
- `unsafe=16`
- `fault=12`
- `total=44`

## Execution semantics

- AGV runtime state is preloaded into the PLC adapter virtual runtime
- sensor snapshots come through the PLC adapter path
- safety simulation runs through the discrete-event backend
- the normal Gateway / Integrity / Safety / 2PC / Evidence path is used

## Visualization

Single concurrent-case GUI example:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v2/pcag_execution_dataset.json --case-id agv_nominal_concurrent_shared_zone_staggered_crossing_001 --show-agv-gui`

If Safety Cluster is started with `PCAG_ENABLE_BENCHMARK_TWIN_GUIS=true`, the
persistent AGV viewer can be booted centrally and the runner can be used with
dataset submission only.

## Current validated live result

- `44/44 pass`
- result file:
  `tests/benchmarks/pcag_ijamt_benchmark/results/agv_pcag_benchmark_latest.json`

## Interpretation

- v2 validates multi-AGV concurrent traffic prediction
- it includes dynamic peer-AGV motion, edge-swap conflict, and deadlock-cycle
  risk
- it still commits one primary AGV asset per transaction, so it should not be
  described as a simultaneous multi-actuator commit benchmark
