# Integrated Benchmark Release v1

This folder contains the unified cross-asset benchmark release assembled from
the already validated asset releases:

- `robot_source_release_v1`
- `agv_source_release_v2`
- `process_source_release_v1`

It is a non-destructive merge that preserves per-case provenance, runtime
context, action sequence, proof hints, and expected final PCAG outcome.

## Files

- `all_cases.json`
- `dataset_manifest.json`
- `pcag_execution_dataset.json`
- `pcag_execution_manifest.json`

## Policy alignment

This integrated release is aligned to:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`
- policy profile:
  `pcag_benchmark_v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

Integrity `policy_mismatch` fault cases intentionally preserve an explicit
mismatched `policy_version_id` so they still evaluate to
`INTEGRITY_POLICY_MISMATCH` under the unified-policy regime.

## Composition

Integrated execution manifest:

- `116 total`
- `38 nominal`
- `42 unsafe`
- `36 fault`

Expected final statuses:

- `COMMITTED 38`
- `UNSAFE 42`
- `REJECTED 21`
- `ABORTED 12`
- `ERROR 3`

Asset split:

- `robot_arm_01 36`
- `agv_01 44`
- `reactor_01 36`

Scenario-family split:

- `robot_manipulation 36`
- `agv_logistics 44`
- `process_interlock 36`

## Live runner

- `tests/benchmarks/pcag_ijamt_benchmark/run_integrated_pcag_benchmark.py`

Recommended command:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_integrated_pcag_benchmark.py`

Useful filters:

- `--asset-id robot_arm_01`
- `--asset-id agv_01`
- `--asset-id reactor_01`
- `--scenario-family agv_logistics`
- `--case-group unsafe`
- `--case-id <exact_case_id>`

## Status note

This integrated release is assembled from asset releases that have already been
validated live:

- robot `36/36 pass`
- AGV v2 `44/44 pass`
- process `36/36 pass`

The integrated release is therefore ready for unified-policy execution without
asset-by-asset policy reseeding.
