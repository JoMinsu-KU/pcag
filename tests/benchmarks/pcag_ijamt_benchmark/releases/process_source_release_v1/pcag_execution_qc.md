# Process PCAG Execution Dataset v1 QC

Derived source release: `process_source_release_v1`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `process_only`
- Purpose: `Gateway-facing execution dataset derived from frozen process all_cases.json`
- Provenance source retained: `tep_process_curated`

## Counts

- Total cases: `36`
- Nominal: `12`
- Unsafe: `12`
- Fault: `12`
- Final status distribution: `COMMITTED=12, UNSAFE=12, REJECTED=7, ABORTED=4, ERROR=1`

## Libraries

- Action sequences: `36`
- Runtime contexts: `3`
- Initial states: `3`
- Sensor snapshots: `1`

## Execution-shaping rules

- All cases keep the frozen final label from `all_cases.json`.
- All cases are reshaped into a Gateway-facing case contract with runtime preload instructions and proof construction hints.
- No scenario-specific PCAG branch is introduced by this dataset format.

## Generic integration requirements observed in this release

- `generic_runtime_context_transport`: `36` cases
- `generic_runtime_preload`: `36` cases
- `generic_sensor_alignment`: `36` cases
- `benchmark_policy_sensor_divergence_thresholds`: `1` cases
- `generic_fault_injection_hook`: `5` cases

## Notes

- Sensor-divergence fault cases are preserved from the frozen process source release.
- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- Transaction and infrastructure fault cases remain part of the dataset as generic benchmark cases and require generic fault-injection hooks, not scenario-specific logic.

