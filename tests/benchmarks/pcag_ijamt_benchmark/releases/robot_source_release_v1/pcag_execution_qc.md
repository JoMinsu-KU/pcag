# Robot PCAG Execution Dataset v1 QC

Derived source release: `robot_source_release_v1`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `robot_only`
- Purpose: `Gateway-facing execution dataset derived from frozen robot all_cases.json`
- Provenance sources retained: `IsaacLab`, `MimicGen`

## Counts

- Total cases: `36`
- Nominal: `10`
- Unsafe: `14`
- Fault: `12`
- Final status distribution: `COMMITTED=10, UNSAFE=14, REJECTED=7, ABORTED=4, ERROR=1`

## Libraries

- Action sequences: `36`
- Runtime contexts: `2`
- Initial states: `2`
- Sensor snapshots: `1`

## Execution-shaping rules

- All cases keep the frozen final label from `all_cases.json`.
- All cases are reshaped into a Gateway-facing case contract with:
  - runtime preload instructions
  - proof construction hints
  - expected Gateway outcome
- No scenario-specific PCAG branch is introduced by this dataset format.

## Generic integration requirements observed in this release

- `generic_runtime_context_transport`: `36` cases
- `generic_runtime_preload`: `36` cases
- `generic_sensor_alignment`: `36` cases
- `benchmark_policy_sensor_divergence_thresholds`: `1` cases
- `generic_fault_injection_hook`: `5` cases

## Notes

- Sensor-divergence fault cases are preserved from the frozen robot source release.
- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- Transaction and infrastructure fault cases remain part of the dataset as generic benchmark cases and require generic fault-injection hooks, not scenario-specific logic.

