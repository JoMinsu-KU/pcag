# AGV PCAG Execution Dataset v3 QC

Derived source release: `agv_source_release_v3`
Source entrypoint: `all_cases.json`

## Scope

- Asset scope: `agv_only`
- Purpose: `Gateway-facing execution dataset derived from frozen AGV v2 all_cases.json`

## Counts

- Total cases: `128`
- Nominal: `40`
- Unsafe: `52`
- Fault: `36`
- Final status distribution: `COMMITTED=40, UNSAFE=52, REJECTED=19, ABORTED=13, ERROR=4`

## Notes

- This execution dataset is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1` and profile hint `pcag_benchmark_v1`.
- PLC adapter preload is still used so the sensor gateway can observe the case-specific AGV runtime before Gateway submission.
- AGV v3 keeps the same execution contract while broadening semantic families to merge, corridor, and dock-occupancy scenarios.

