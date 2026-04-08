# AGV Source Release v3

This folder contains the expanded AGV benchmark release built on top of the
validated v2 baseline.

`agv_source_release_v3` preserves the full validated v2 release and adds three
single-asset expansion families closer to the logistics scenarios targeted in
the paper.

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

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_source_release_v3.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_pcag_execution_dataset_v3.py`

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

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v3/pcag_execution_dataset.json`

## Key differences from v2

- three new semantic families are added on top of the validated v2 release
- `merge_bottleneck`
- `single_lane_corridor`
- `dock_occupancy_conflict`
- the same Gateway contract, runtime preload path, and discrete-event backend
  are preserved

## Release size

- `nominal=40`
- `unsafe=52`
- `fault=36`
- `total=128`

## Execution semantics

- AGV runtime state is preloaded into the PLC adapter virtual runtime
- sensor snapshots come through the PLC adapter path
- safety simulation runs through the discrete-event backend
- the normal Gateway / Integrity / Safety / 2PC / Evidence path is used

## Visualization

Single AGV v3 family example:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/agv_source_release_v3/pcag_execution_dataset.json --case-id agv_nominal_warehouse_merge_bottleneck_entry_release_001 --show-agv-gui`

If Safety Cluster is started with `PCAG_ENABLE_BENCHMARK_TWIN_GUIS=true`, the
persistent AGV viewer can be booted centrally and the runner can be used with
dataset submission only.

## Current live check status

- release generation completed
- representative scenario-wise live runs passed for:
  - `merge_bottleneck` nominal / unsafe / fault
  - `single_lane_corridor` nominal / unsafe / fault
  - `dock_occupancy_conflict` nominal / unsafe / fault

## Interpretation

- v3 broadens AGV benchmark semantics while keeping the same single-primary-AGV
  transaction model
- it still commits one primary AGV asset per transaction, so it should not be
  described as a simultaneous multi-actuator commit benchmark
