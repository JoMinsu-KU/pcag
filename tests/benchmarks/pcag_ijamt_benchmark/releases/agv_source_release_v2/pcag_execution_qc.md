# AGV PCAG Execution Dataset v2 QC

Derived source release: `agv_source_release_v2`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `agv_only`
- Purpose: `Gateway-facing execution dataset derived from frozen AGV v2 all_cases.json`

## Counts

- Total cases: `44`
- Nominal: `16`
- Unsafe: `16`
- Fault: `12`
- Final status distribution: `COMMITTED=16, UNSAFE=16, REJECTED=7, ABORTED=4, ERROR=1`

## Notes

- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- PLC adapter preload is still used so the sensor gateway can observe the case-specific AGV runtime before Gateway submission.
- Concurrent AGV traffic is injected through runtime_context.simulation_override.agvs[*].path and remains compatible with the same full PCAG path used by v1.

