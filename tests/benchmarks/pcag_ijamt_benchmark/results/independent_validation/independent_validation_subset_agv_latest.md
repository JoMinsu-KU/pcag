# Independent Validation Subset Report

- Generated at: 2026-03-23 17:50:50
- Dataset: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\releases\integrated_benchmark_release_v2\pcag_execution_dataset.json`
- Policy: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\policies\pcag_benchmark_policy_v1.json`
- Subset size: `40`
- Matches: `40`
- Mismatches: `0`
- Match rate: `1.0`

## Asset-wise Summary

| Asset | Total | Matches | Mismatches | Match Rate |
| --- | ---: | ---: | ---: | ---: |
| agv_01 | 40 | 40 | 0 | 1.0000 |

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
| `agv_nominal_warehouse_dock_occupancy_conflict_alignment_hold_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::dock_alignment_variant::alignment_hold` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_gate_to_dock_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::dock_alignment_variant::gate_to_dock` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_release_yield_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::dock_alignment_variant::release_yield` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_dock_to_clearance_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::dock_nominal::dock_to_clearance` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_queue_to_gate_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::dock_nominal::queue_to_gate` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_clear_crossing_gate_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::shared_zone_clear_crossing::clear_crossing_gate` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_shared_hold_release_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::shared_zone_clear_crossing::shared_hold_release` | SAFE | True |
| `agv_nominal_warehouse_dock_occupancy_conflict_transfer_buffer_001` | agv_01 | COMMITTED | `dock_occupancy_conflict::transfer_with_path_variant::transfer_buffer` | SAFE | True |
| `agv_nominal_warehouse_docking_gate_to_dock_001` | agv_01 | COMMITTED | `docking_approach::dock_alignment_variant::dock_align` | SAFE | True |
| `agv_nominal_warehouse_docking_alignment_hold_001` | agv_01 | COMMITTED | `docking_approach::dock_alignment_variant::dock_approach` | SAFE | True |
| `agv_nominal_concurrent_docking_release_yield_001` | agv_01 | COMMITTED | `docking_approach::dock_alignment_variant::dock_release_concurrent` | SAFE | True |
| `agv_nominal_warehouse_docking_queue_to_gate_001` | agv_01 | COMMITTED | `docking_approach::dock_nominal::dock_approach` | SAFE | True |
| `agv_nominal_warehouse_docking_dock_to_clearance_001` | agv_01 | COMMITTED | `docking_approach::dock_nominal::dock_release` | SAFE | True |
| `agv_nominal_concurrent_shared_zone_priority_sequence_001` | agv_01 | COMMITTED | `intersection_conflict::shared_zone_clear_crossing::zone_priority_release` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_queue_hold_001` | agv_01 | COMMITTED | `merge_bottleneck::dock_nominal::queue_hold` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_priority_hold_001` | agv_01 | COMMITTED | `merge_bottleneck::shared_zone_clear_crossing::priority_hold` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_staggered_crossing_001` | agv_01 | COMMITTED | `merge_bottleneck::shared_zone_nominal::staggered_crossing` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_entry_release_001` | agv_01 | COMMITTED | `merge_bottleneck::transfer_nominal::entry_release` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_reverse_release_001` | agv_01 | COMMITTED | `merge_bottleneck::transfer_nominal::reverse_release` | SAFE | True |
| `agv_nominal_warehouse_merge_bottleneck_buffer_lane_shift_001` | agv_01 | COMMITTED | `merge_bottleneck::transfer_with_path_variant::buffer_lane_shift` | SAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_alignment_hold_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::dock_alignment_variant::alignment_hold_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_gate_dock_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::dock_alignment_variant::gate_dock_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_release_edge_swap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::dock_alignment_variant::release_edge_swap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_dock_clearance_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::dock_nominal::dock_clearance_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_queue_gate_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::dock_nominal::queue_gate_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_queue_priority_deadlock_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::shared_zone_clear_crossing::queue_priority_deadlock` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_shared_gate_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::shared_zone_clear_crossing::shared_gate_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_staggered_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::shared_zone_nominal::staggered_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_west_to_east_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::shared_zone_nominal::west_to_east_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_transfer_reverse_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::transfer_nominal::transfer_reverse_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_transfer_source_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::transfer_nominal::transfer_source_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_dock_occupancy_conflict_transfer_mid_overlap_001` | agv_01 | UNSAFE | `dock_occupancy_conflict::transfer_with_path_variant::transfer_mid_overlap` | UNSAFE | True |
| `agv_unsafe_warehouse_docking_gate_to_dock_001` | agv_01 | UNSAFE | `docking_approach::dock_alignment_variant::dock_align_unsafe` | UNSAFE | True |
| `agv_unsafe_warehouse_docking_alignment_hold_001` | agv_01 | UNSAFE | `docking_approach::dock_alignment_variant::dock_approach_unsafe` | UNSAFE | True |
| `agv_unsafe_concurrent_docking_release_yield_001` | agv_01 | UNSAFE | `docking_approach::dock_alignment_variant::dock_release_concurrent_unsafe` | UNSAFE | True |
| `agv_unsafe_warehouse_docking_queue_to_gate_001` | agv_01 | UNSAFE | `docking_approach::dock_nominal::dock_approach_unsafe` | UNSAFE | True |
| `agv_unsafe_warehouse_docking_dock_to_clearance_001` | agv_01 | UNSAFE | `docking_approach::dock_nominal::dock_release_unsafe` | UNSAFE | True |
| `agv_unsafe_concurrent_shared_zone_priority_sequence_001` | agv_01 | UNSAFE | `intersection_conflict::shared_zone_clear_crossing::zone_priority_release_unsafe` | UNSAFE | True |
| `agv_unsafe_warehouse_merge_bottleneck_dock_edge_swap_001` | agv_01 | UNSAFE | `merge_bottleneck::dock_alignment_variant::dock_edge_swap` | UNSAFE | True |
| `agv_unsafe_warehouse_merge_bottleneck_gate_dock_conflict_001` | agv_01 | UNSAFE | `merge_bottleneck::dock_alignment_variant::gate_dock_conflict` | UNSAFE | True |

## Notes

- The same simulation engines were invoked outside the Gateway/Safety-Cluster admission path as independent oracles.
- No benchmark cases or expected labels were mutated during this validation run.
