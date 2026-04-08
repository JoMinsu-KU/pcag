# AGV Source Release v1 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `agv_only`
- Upstream source: `warehouse_world_curated`
- Implemented runtime shells: `agv_transfer_map`, `agv_docking_map`, `agv_shared_zone_map`

## Counts

- Nominal cases: `12`
- Unsafe cases: `12`
- Fault cases: `12`
- Total cases: `36`
- Final-status coverage: `COMMITTED=12, UNSAFE=12, REJECTED=7, ABORTED=4, ERROR=1`

## Consistency checks

- All cases use `scenario_family = agv_logistics`.
- All cases use the executable subset `move_to`.
- All shell references exist in the AGV scene pack.
- All label triplets satisfy the frozen label taxonomy.

## Unsafe mutation policy

- Grid-boundary counterfactuals drive deliberate out-of-grid moves.
- Obstacle counterfactuals drive deliberate path intrusion through blocked cells.
- Shared-zone counterfactuals place a background AGV in the critical occupancy cell to trigger a min-distance violation.

## Fault mutation policy

- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`
- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`
- Infrastructure faults: `ot_interface_error`

## Notes for the paper

- The AGV benchmark is not a raw robotic-warehouse imitation dataset; it is a frozen supervisory benchmark derived from warehouse-world logistics motifs.
- Shared-zone cases use a stationary background AGV as a conflict anchor so that unsafe occupancy can be checked by the existing discrete-event backend.

