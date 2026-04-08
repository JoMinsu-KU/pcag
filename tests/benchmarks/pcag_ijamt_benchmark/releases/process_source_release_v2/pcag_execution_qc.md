# Process PCAG Execution Dataset v2 QC

Derived source release: `process_source_release_v2`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `process_only`
- Purpose: `Gateway-facing execution dataset derived from frozen process v2 all_cases.json`
- Provenance source retained: `tep_process_curated`

## Counts

- Total cases: `120`
- Nominal: `36`
- Unsafe: `48`
- Fault: `36`
- Final status distribution: `COMMITTED=36, UNSAFE=48, REJECTED=17, ABORTED=15, ERROR=4`

## Libraries

- Action sequences: `120`
- Runtime contexts: `3`
- Initial states: `120`
- Sensor snapshots: `2`

## Execution-shaping rules

- All cases keep the frozen final label from `all_cases.json`.
- All cases are reshaped into a Gateway-facing case contract with runtime preload instructions and proof construction hints.
- No scenario-specific PCAG branch is introduced by this dataset format.

## Generic integration requirements observed in this release

- `generic_runtime_context_transport`: `120` cases
- `generic_runtime_preload`: `120` cases
- `generic_sensor_alignment`: `120` cases
- `benchmark_policy_sensor_divergence_thresholds`: `2` cases
- `generic_fault_injection_hook`: `19` cases

## Notes

- Sensor-divergence fault cases are preserved from the frozen process source release.
- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- Transaction and infrastructure fault cases remain part of the dataset as generic benchmark cases and require generic fault-injection hooks, not scenario-specific logic.

