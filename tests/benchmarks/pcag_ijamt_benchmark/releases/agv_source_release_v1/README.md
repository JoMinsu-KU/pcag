# AGV Source Release v1

This folder contains the first frozen AGV benchmark release generated from the
IJAMT benchmark rules.

The release is grounded in the frozen provenance anchor:

- `warehouse_world_curated`

It intentionally limits itself to the currently implemented AGV shells:

- `agv_transfer_map`
- `agv_docking_map`
- `agv_shared_zone_map`

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

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_source_release_v1.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_agv_pcag_execution_dataset_v1.py`

## Policy alignment

This release is now aligned to the unified benchmark policy:

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

## Scope notes

- All executable cases are lowered to `move_to`.
- The release is grounded in warehouse-world logistics motifs rather than a
  copied raw AGV action dataset.
- The unsafe split mixes:
  - `grid_boundary_violation`
  - `obstacle_intrusion`
  - `shared_occupancy_conflict`
- Shared-zone unsafe cases are expressed through runtime-context background-AGV
  placement rather than scenario-specific PCAG branches.

## Execution semantics

The current AGV stack is PLC-adapter-backed:

- sensor snapshots come through the PLC adapter path
- safety simulation runs through the discrete-event backend
- final execution commit runs through the PLC-adapter-backed public executor

Case-specific AGV runtime state is preloaded into the PLC adapter's virtual
runtime before the normal Gateway request is sent.

## Historical status note

- this v1 release remains valid and runnable
- the paper-facing AGV baseline should now prefer `agv_source_release_v2`
- v1 is best understood as the lighter single-command AGV release without the
  concurrent-motion supplement

## Optional visualization

Single-case AGV viewer example:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_agv_pcag_benchmark.py --case-id agv_nominal_warehouse_transfer_source_to_mid_001 --show-agv-gui`

If Safety Cluster is started with `PCAG_ENABLE_BENCHMARK_TWIN_GUIS=true`, the
persistent AGV viewer can be booted centrally and this runner can be used
without AGV-specific GUI flags.
