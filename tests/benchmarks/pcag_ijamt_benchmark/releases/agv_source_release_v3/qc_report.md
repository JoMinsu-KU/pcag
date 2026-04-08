# AGV Source Release v3 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `agv_only`
- Base release: `agv_source_release_v2`
- Added supplements: `merge_bottleneck`, `single_lane_corridor`, `dock_occupancy_conflict`

## Counts

- Nominal cases: `40`
- Unsafe cases: `52`
- Fault cases: `36`
- Total cases: `128`
- Final-status coverage: `COMMITTED=40, UNSAFE=52, REJECTED=19, ABORTED=13, ERROR=4`

## Expansion families

- `merge_bottleneck`: upstream queue release, safe following, and bottleneck collision/deadlock counterfactuals.
- `single_lane_corridor`: corridor release, yielding, head-on conflict, and deadlock-risk counterfactuals.
- `dock_occupancy_conflict`: queue-to-gate, gate-to-dock, and occupied-dock conflict counterfactuals.

## Notes

- v3 keeps the v2 fault families intact so full PCAG outcome coverage remains available.
- The new cases are semantic expansions over validated templates, which keeps the Gateway contract and runtime hooks unchanged.

