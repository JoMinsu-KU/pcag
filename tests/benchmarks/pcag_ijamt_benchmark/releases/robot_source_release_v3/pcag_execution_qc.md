# Robot PCAG Execution Dataset v3.0 QC

Derived source release: `robot_source_release_v3`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `robot_only`
- Purpose: `Gateway-facing execution dataset derived from frozen robot all_cases.json`
- Provenance sources retained: `IsaacLab`, `MimicGen`

## Counts

- Total cases: `76`
- Nominal: `22`
- Unsafe: `30`
- Fault: `24`
- Final status distribution: `COMMITTED=22, UNSAFE=30, REJECTED=13, ABORTED=7, ERROR=4`

## Libraries

- Action sequences: `76`
- Runtime contexts: `4`
- Initial states: `76`
- Sensor snapshots: `1`

## Execution-shaping rules

- All cases keep the frozen final label from `all_cases.json`.
- All cases are reshaped into a Gateway-facing case contract with:
  - runtime preload instructions
  - proof construction hints
  - expected Gateway outcome
- No scenario-specific PCAG branch is introduced by this dataset format.

## Generic integration requirements observed in this release

- `generic_runtime_context_transport`: `76` cases
- `generic_runtime_preload`: `76` cases
- `generic_sensor_alignment`: `76` cases
- `benchmark_policy_sensor_divergence_thresholds`: `1` cases
- `generic_fault_injection_hook`: `11` cases

## Notes

- Sensor-divergence fault cases are preserved from the frozen robot source release.
- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- Transaction and infrastructure fault cases remain part of the dataset as generic benchmark cases and require generic fault-injection hooks, not scenario-specific logic.

