# Independent Validation Subset Report

- Generated at: 2026-03-22 05:37:52
- Dataset: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\releases\integrated_benchmark_release_v2\pcag_execution_dataset.json`
- Policy: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\policies\pcag_benchmark_policy_v1.json`
- Subset size: `40`
- Matches: `40`
- Mismatches: `0`
- Match rate: `1.0`

## Asset-wise Summary

| Asset | Total | Matches | Mismatches | Match Rate |
| --- | ---: | ---: | ---: | ---: |
| robot_arm_01 | 40 | 40 | 0 | 1.0000 |

## Status-wise Summary

| Expected Status | Total | Matches | Mismatches | Match Rate |
| --- | ---: | ---: | ---: | ---: |
| COMMITTED | 20 | 20 | 0 | 1.0000 |
| UNSAFE | 20 | 20 | 0 | 1.0000 |

## Mismatches

- None

## Selected Cases

| Case ID | Asset | Expected Status | Stratum | Oracle Verdict | Match |
| --- | --- | --- | --- | --- | --- |
| `robot_nominal_isaaclab_lift_source_pick_001` | robot_arm_01 | COMMITTED | `lift::pick::pick` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_fixture_insertion_insert_001` | robot_arm_01 | COMMITTED | `pick_place::insert::insert` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_fixture_insertion_insert_mid_depth_001` | robot_arm_01 | COMMITTED | `pick_place::insert::insert_mid_depth` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_narrow_clearance_insert_mid_slot_001` | robot_arm_01 | COMMITTED | `pick_place::insert::insert_mid_slot` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_milk_pick_001` | robot_arm_01 | COMMITTED | `pick_place::pick::pick` | SAFE | True |
| `robot_nominal_isaaclab_pick_place_conveyor_timing_pick_source_capture_001` | robot_arm_01 | COMMITTED | `pick_place::pick::source_capture` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_conveyor_timing_pick_clear_reset_001` | robot_arm_01 | COMMITTED | `pick_place::place::clear_reset` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_milk_place_001` | robot_arm_01 | COMMITTED | `pick_place::place::place` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_narrow_clearance_retreat_001` | robot_arm_01 | COMMITTED | `pick_place::retreat::retreat` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_narrow_clearance_retreat_short_001` | robot_arm_01 | COMMITTED | `pick_place::retreat::retreat_short` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_conveyor_timing_pick_handoff_window_001` | robot_arm_01 | COMMITTED | `pick_place::transfer::handoff_window` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_conveyor_timing_pick_mid_transfer_001` | robot_arm_01 | COMMITTED | `pick_place::transfer::mid_transfer` | SAFE | True |
| `robot_nominal_isaaclab_pick_place_transfer_001` | robot_arm_01 | COMMITTED | `pick_place::transfer::transfer` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_fixture_insertion_withdraw_001` | robot_arm_01 | COMMITTED | `pick_place::withdraw::withdraw` | SAFE | True |
| `robot_nominal_mimicgen_pick_place_fixture_insertion_withdraw_short_001` | robot_arm_01 | COMMITTED | `pick_place::withdraw::withdraw_short` | SAFE | True |
| `robot_nominal_isaaclab_place_output_fixture_001` | robot_arm_01 | COMMITTED | `place::place::place` | SAFE | True |
| `robot_nominal_isaaclab_place_fixture_insertion_pre_insert_001` | robot_arm_01 | COMMITTED | `place::pre_insert::pre_insert` | SAFE | True |
| `robot_nominal_isaaclab_place_fixture_insertion_pre_insert_shallow_001` | robot_arm_01 | COMMITTED | `place::pre_insert::pre_insert_shallow` | SAFE | True |
| `robot_nominal_isaaclab_reach_fixture_insertion_align_001` | robot_arm_01 | COMMITTED | `reach::align::align` | SAFE | True |
| `robot_nominal_isaaclab_reach_fixture_insertion_align_left_bias_001` | robot_arm_01 | COMMITTED | `reach::align::align_left_bias` | SAFE | True |
| `robot_unsafe_isaaclab_lift_source_pick_001` | robot_arm_01 | UNSAFE | `lift::pick::pick_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_fixture_insertion_insert_mid_depth_depth_margin_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::insert::insert_mid_depth_depth_margin_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_fixture_insertion_insert_mid_depth_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::insert::insert_mid_depth_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_narrow_clearance_insert_mid_slot_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::insert::insert_mid_slot_fixture_collision` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_narrow_clearance_insert_mid_slot_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::insert::insert_mid_slot_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_fixture_insertion_insert_001` | robot_arm_01 | UNSAFE | `pick_place::insert::insert_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_milk_pick_001` | robot_arm_01 | UNSAFE | `pick_place::pick::pick_unsafe` | UNSAFE | True |
| `robot_unsafe_isaaclab_pick_place_conveyor_timing_pick_source_capture_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::pick::source_capture_fixture_collision` | UNSAFE | True |
| `robot_unsafe_isaaclab_pick_place_conveyor_timing_pick_source_capture_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::pick::source_capture_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_conveyor_timing_pick_clear_reset_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::place::clear_reset_fixture_collision` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_milk_place_001` | robot_arm_01 | UNSAFE | `pick_place::place::place_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_narrow_clearance_retreat_short_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::retreat::retreat_short_fixture_collision` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_narrow_clearance_retreat_short_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::retreat::retreat_short_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_narrow_clearance_retreat_001` | robot_arm_01 | UNSAFE | `pick_place::retreat::retreat_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_conveyor_timing_pick_handoff_window_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::transfer::handoff_window_fixture_collision` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_conveyor_timing_pick_handoff_window_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::transfer::handoff_window_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_conveyor_timing_pick_mid_transfer_fixture_collision_001` | robot_arm_01 | UNSAFE | `pick_place::transfer::mid_transfer_fixture_collision` | UNSAFE | True |
| `robot_unsafe_isaaclab_pick_place_transfer_001` | robot_arm_01 | UNSAFE | `pick_place::transfer::transfer_unsafe` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_fixture_insertion_withdraw_short_depth_margin_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::withdraw::withdraw_short_depth_margin_joint_limit` | UNSAFE | True |
| `robot_unsafe_mimicgen_pick_place_fixture_insertion_withdraw_short_joint_limit_001` | robot_arm_01 | UNSAFE | `pick_place::withdraw::withdraw_short_unsafe` | UNSAFE | True |

## Notes

- The same simulation engines were invoked outside the Gateway/Safety-Cluster admission path as independent oracles.
- No benchmark cases or expected labels were mutated during this validation run.
