# Robot Source Release v1 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `robot_only`
- Upstream sources: `IsaacLab`, `MimicGen`
- Implemented runtime shells: `robot_pick_place_cell`, `robot_stack_cell`

## Counts

- Nominal cases: `10`
- Unsafe cases: `14`
- Fault cases: `12`
- Total cases: `36`
- Final-status coverage: `COMMITTED=10, UNSAFE=14, REJECTED=7, ABORTED=4, ERROR=1`

## Coverage

- Covered source families: `lift, pick_place, place, reach, stack`
- Deferred selected families: `deploy/gear_assembly`, `nut_assembly`, `threading`, `three_piece_assembly`
- Covered shells: `robot_pick_place_cell`, `robot_stack_cell`
- Outcome-complete release artifact: `all_cases.json`

## Consistency checks

- All cases use `scenario_family = robot_manipulation`.
- All cases use the executable subset `move_joint`.
- All source references exist in the frozen local acquisition targets.
- All shell references exist in the implemented scene pack.
- All label triplets satisfy the frozen label taxonomy.

## Unsafe mutation policy

- Release v1 uses two robot unsafe families: `joint_limit_violation` and `fixture_collision_probe`.
- Collision unsafe cases are threshold-calibrated against the implemented pick-place and stack shells.
- The calibrated collision profiles currently correspond to workbench-surface penetration near the fixture approach region.

## Fault mutation policy

- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`
- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`
- Infrastructure faults: `ot_interface_error`

## Notes for the paper

- IsaacLab is used as a frozen task-family and env-config provenance source, not as a raw copied dataset.
- MimicGen is used as a frozen single-arm manipulation provenance source, normalized into the same PCAG shell vocabulary.
- Robot cases are normalized into canonical Franka-compatible runtime shells even when the upstream source family uses a different robot embodiment.
- The release is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1`.

