# AGV PCAG Execution Dataset v1 QC

Derived source release: `agv_source_release_v1`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `agv_only`
- Purpose: `Gateway-facing execution dataset derived from frozen AGV all_cases.json`

## Counts

- Total cases: `36`
- Nominal: `12`
- Unsafe: `12`
- Fault: `12`
- Final status distribution: `COMMITTED=12, UNSAFE=12, REJECTED=7, ABORTED=4, ERROR=1`

## Libraries

- Action sequences: `36`
- Runtime contexts: `3`
- Initial states: `8`
- Sensor snapshots: `1`

## Notes

- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- PLC adapter preload is used so that the sensor gateway can observe the case-specific AGV runtime before Gateway submission.
- Transaction and infrastructure fault cases remain generic benchmark cases and require only the generic fault-injection hooks already used by the robot benchmark.

