# AGV Source Release v2 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `agv_only`
- Base release: `agv_source_release_v1`
- Added supplement: `concurrent multi-AGV motion, edge-swap conflict, deadlock-cycle risk`

## Counts

- Nominal cases: `16`
- Unsafe cases: `16`
- Fault cases: `12`
- Total cases: `44`
- Final-status coverage: `COMMITTED=16, UNSAFE=16, REJECTED=7, ABORTED=4, ERROR=1`

## Concurrency supplement

- `agv_nominal_concurrent_shared_zone_staggered_crossing_001`: two AGVs move concurrently with time separation.
- `agv_nominal_concurrent_transfer_safe_following_001`: background AGV moves ahead in the same corridor while the primary AGV follows safely.
- `agv_nominal_concurrent_shared_zone_priority_sequence_001`: three AGVs coordinate priority release through the shared zone.
- `agv_nominal_concurrent_docking_release_yield_001`: docking release waits for a neighboring AGV to clear.

## Unsafe concurrency mutations

- `concurrent_same_cell_collision` introduces dynamic center-cell occupancy collision.
- `concurrent_head_on_collision` introduces head-on same-cell collision in the transfer corridor.
- `deadlock_cycle` introduces a three-AGV wait-for cycle.
- `edge_swap_conflict` introduces simultaneous cell-swap conflict at the docking release point.

## Notes

- v2 keeps the v1 fault families intact so full PCAG outcome coverage remains available.
- The new concurrency cases are intended to align the benchmark more closely with the original multi-AGV planning scenario in the project document.

