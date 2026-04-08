from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from generate_agv_source_release_v1 import (
    BENCHMARK_ROOT,
    PROJECT_ROOT,
    SHELL_ROOT,
    _dump_json,
    _make_nominal_case,
    _make_unsafe_case,
    _validate_cases,
)


RELEASE_DIR = BENCHMARK_ROOT / "releases" / "agv_source_release_v3"
V2_ALL_CASES_PATH = BENCHMARK_ROOT / "releases" / "agv_source_release_v2" / "all_cases.json"


CONCURRENT_BASE_SPECS = [
    {
        "case_id": "agv_nominal_concurrent_shared_zone_staggered_crossing_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_nominal",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::staggered_crossing_with_north_traffic",
        "station_id": "shared_zone",
        "mission_phase": "zone_crossing_concurrent",
        "load_id": "carrier_iota",
        "provenance_note": "Warehouse-world shared-zone motif lifted into a concurrent two-AGV staggered crossing command.",
        "semantic_role": "staggered crossing with dynamic north-lane traffic",
        "target": [9, 5],
        "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [6, 8],
                        "speed": 1.0,
                        "path": [[6, 8], [6, 8], [6, 8], [6, 7], [6, 6], [6, 5], [6, 4]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 6, "y": 8}},
        },
        "unsafe_variant": {
            "rule": "concurrent_same_cell_collision",
            "simulation_expectation": "same_cell_collision",
            "target": [9, 5],
            "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [6, 8],
                            "speed": 1.0,
                            "path": [[6, 7], [6, 6], [6, 5], [6, 5]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 6, "y": 8}},
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_transfer_safe_following_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_with_path_variant",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::safe_following_with_background_departure",
        "station_id": "transfer_mid",
        "mission_phase": "transfer_concurrent",
        "load_id": "carrier_kappa",
        "provenance_note": "Warehouse-world transfer motif lifted into a concurrent two-AGV corridor-following command.",
        "semantic_role": "safe following behind moving background traffic",
        "target": [6, 3],
        "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [4, 1],
                        "speed": 1.0,
                        "path": [[5, 1], [6, 1], [7, 1], [8, 1], [9, 1]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 4, "y": 1}},
        },
        "unsafe_variant": {
            "rule": "concurrent_head_on_collision",
            "simulation_expectation": "same_cell_collision",
            "target": [6, 3],
            "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [5, 1],
                            "speed": 1.0,
                            "path": [[4, 1], [3, 1], [2, 1]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 5, "y": 1}},
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_shared_zone_priority_sequence_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_clear_crossing",
        "task_family": "intersection_conflict",
        "source_unit": "intersection_conflict::three_agv_priority_release",
        "station_id": "shared_zone",
        "mission_phase": "zone_priority_release",
        "load_id": "carrier_lambda",
        "initial_state_override": {"position_x": 5, "position_y": 5, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world shared intersection motif lifted into a three-AGV priority-release coordination command.",
        "semantic_role": "three-AGV coordinated release with explicit yielding",
        "target": [7, 5],
        "path": [[5, 5], [5, 5], [6, 5], [7, 5]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [6, 5],
                        "speed": 1.0,
                        "path": [[7, 5], [8, 5], [9, 5]],
                    },
                    "agv_03": {
                        "position": [7, 5],
                        "speed": 1.0,
                        "path": [[7, 4], [7, 3], [7, 2]],
                    },
                }
            },
            "sensor_state_overlay": {
                "agv_02": {"x": 6, "y": 5},
                "agv_03": {"x": 7, "y": 5},
            },
        },
        "unsafe_variant": {
            "rule": "deadlock_cycle",
            "simulation_expectation": "deadlock_cycle",
            "target": [6, 5],
            "path": [[6, 5]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [6, 5],
                            "speed": 1.0,
                            "path": [[7, 5]],
                        },
                        "agv_03": {
                            "position": [7, 5],
                            "speed": 1.0,
                            "path": [[5, 5]],
                        },
                    }
                },
                "sensor_state_overlay": {
                    "agv_02": {"x": 6, "y": 5},
                    "agv_03": {"x": 7, "y": 5},
                },
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_docking_release_yield_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_alignment_variant",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::docking_release_with_neighbor_departure",
        "station_id": "handoff_dock",
        "mission_phase": "dock_release_concurrent",
        "load_id": "carrier_mu",
        "initial_state_override": {"position_x": 8, "position_y": 2, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world docking motif lifted into a concurrent dock-release command with a neighboring AGV departure.",
        "semantic_role": "dock release with explicit neighbor yield",
        "target": [9, 2],
        "path": [[8, 2], [8, 2], [9, 2]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [9, 2],
                        "speed": 1.0,
                        "path": [[9, 3], [9, 4]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 9, "y": 2}},
        },
        "unsafe_variant": {
            "rule": "edge_swap_conflict",
            "simulation_expectation": "edge_swap_conflict",
            "target": [9, 2],
            "path": [[9, 2]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [9, 2],
                            "speed": 1.0,
                            "path": [[8, 2]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 9, "y": 2}},
            },
        },
    },
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _upgrade_case(case: dict[str, Any]) -> dict[str, Any]:
    upgraded = deepcopy(case)
    upgraded["benchmark_release"] = "agv_source_release_v3"
    upgraded["benchmark_version"] = "v3.0"
    return upgraded


def _clone_case(
    template: dict[str, Any],
    *,
    case_id: str,
    task_family: str,
    mission_phase: str,
    semantic_role: str,
    qc_role: str,
) -> dict[str, Any]:
    cloned = _upgrade_case(template)
    cloned["case_id"] = case_id
    cloned["source_benchmark"]["task_family"] = task_family
    cloned["source_benchmark"]["source_unit"] = f"{task_family}::{mission_phase}"
    cloned["source_benchmark"]["provenance_note"] = (
        f"Existing AGV v2 template {template['case_id']} was remapped into the {task_family} expansion family."
    )
    cloned["source_benchmark"]["source_semantics"]["motif"] = task_family
    cloned["source_benchmark"]["source_semantics"]["semantic_role"] = semantic_role
    cloned["operation_context"]["task_family"] = task_family
    cloned["operation_context"]["mission_phase"] = mission_phase
    cloned["notes"]["qc_status"] = "templated_from_agv_source_release_v2"
    cloned["notes"]["paper_role"] = qc_role
    cloned["notes"]["derived_from_case_id"] = template["case_id"]
    cloned["notes"]["expansion_family"] = task_family
    return cloned


FAMILY_EXPANSION_MAP: dict[str, dict[str, list[tuple[str, str, str]]]] = {
    "merge_bottleneck": {
        "nominal": [
            ("entry_release", "agv_nominal_warehouse_transfer_source_to_mid_001", "source queue releases into merge lane"),
            ("throughput_handoff", "agv_nominal_warehouse_transfer_mid_to_drop_001", "merged carrier clears downstream transfer lane"),
            ("reverse_release", "agv_nominal_warehouse_transfer_drop_to_mid_001", "reverse-lane merge release remains collision free"),
            ("buffer_lane_shift", "agv_nominal_warehouse_transfer_lane_variant_001", "buffer lane variant avoids merge obstruction"),
            ("safe_following", "agv_nominal_concurrent_transfer_safe_following_001", "trailing AGV keeps safe merge-following distance"),
            ("queue_hold", "agv_nominal_warehouse_docking_queue_to_gate_001", "upstream queue hold prevents merge contention"),
            ("priority_hold", "agv_nominal_warehouse_shared_zone_west_hold_short_001", "priority hold resolves the bottleneck without conflict"),
            ("staggered_crossing", "agv_nominal_concurrent_shared_zone_staggered_crossing_001", "staggered crossing emulates phased merge release"),
        ],
        "unsafe": [
            ("same_cell_entry", "agv_unsafe_warehouse_transfer_source_to_mid_001", "merge entry attempts same-cell occupation"),
            ("same_cell_throughput", "agv_unsafe_warehouse_transfer_mid_to_drop_001", "throughput lane violates safe merge occupancy"),
            ("reverse_conflict", "agv_unsafe_warehouse_transfer_drop_to_mid_001", "reverse release collides in the merge lane"),
            ("buffer_collision", "agv_unsafe_warehouse_transfer_lane_variant_001", "buffer lane variant re-enters the merge conflict zone"),
            ("head_on_following", "agv_unsafe_concurrent_transfer_safe_following_001", "background AGV creates head-on merge conflict"),
            ("queue_gate_conflict", "agv_unsafe_warehouse_docking_queue_to_gate_001", "queued release violates narrow merge clearance"),
            ("gate_dock_conflict", "agv_unsafe_warehouse_docking_gate_to_dock_001", "gate-to-dock transition collides at the bottleneck"),
            ("west_to_east_conflict", "agv_unsafe_warehouse_shared_zone_west_to_east_001", "shared lane occupancy spills into merge bottleneck"),
            ("shared_crossing_conflict", "agv_unsafe_warehouse_shared_zone_clear_crossing_001", "clear-crossing timing collapses into merge conflict"),
            ("staggered_same_cell", "agv_unsafe_concurrent_shared_zone_staggered_crossing_001", "staggered merge collapses into same-cell collision"),
            ("priority_deadlock", "agv_unsafe_concurrent_shared_zone_priority_sequence_001", "priority release forms merge deadlock"),
            ("dock_edge_swap", "agv_unsafe_concurrent_docking_release_yield_001", "neighbor release induces edge-swap at merge exit"),
        ],
        "fault": [
            ("entry_release_policy_mismatch", "agv_fault_warehouse_transfer_source_to_mid_policy_mismatch_001", "integrity mismatch before bottleneck release"),
            ("throughput_handoff_timestamp_expired", "agv_fault_warehouse_transfer_mid_to_drop_timestamp_expired_001", "expired proof for downstream merge handoff"),
            ("reverse_release_sensor_hash_mismatch", "agv_fault_warehouse_transfer_drop_to_mid_sensor_hash_mismatch_001", "sensor hash mismatch on reverse merge release"),
            ("buffer_lane_shift_sensor_divergence", "agv_fault_warehouse_transfer_lane_variant_sensor_divergence_001", "sensor divergence on buffered merge lane shift"),
            ("queue_hold_lock_denied", "agv_fault_warehouse_docking_queue_to_gate_lock_denied_001", "prepare lock denial at upstream bottleneck queue"),
            ("gate_dock_reverify_hash_mismatch", "agv_fault_warehouse_docking_gate_to_dock_reverify_hash_mismatch_001", "reverify mismatch before final merge commit"),
            ("dock_clearance_commit_timeout", "agv_fault_warehouse_docking_dock_to_clearance_commit_timeout_001", "commit timeout while clearing merge dock"),
            ("throughput_handoff_ot_interface_error", "agv_fault_warehouse_shared_zone_west_to_east_ot_interface_error_001", "OT interface failure after bottleneck validation"),
        ],
    },
    "single_lane_corridor": {
        "nominal": [
            ("westbound_release", "agv_nominal_warehouse_shared_zone_west_to_east_001", "single-lane westbound release clears corridor"),
            ("clear_crossing", "agv_nominal_warehouse_shared_zone_clear_crossing_001", "corridor clears before opposing traffic enters"),
            ("north_to_west_yield", "agv_nominal_warehouse_shared_zone_north_to_west_001", "northbound vehicle yields before corridor turn"),
            ("hold_short_release", "agv_nominal_warehouse_shared_zone_west_hold_short_001", "short hold releases corridor safely"),
            ("staggered_crossing", "agv_nominal_concurrent_shared_zone_staggered_crossing_001", "staggered corridor crossing preserves spacing"),
            ("priority_sequence", "agv_nominal_concurrent_shared_zone_priority_sequence_001", "priority sequence avoids single-lane deadlock"),
            ("dock_clearance_return", "agv_nominal_warehouse_docking_dock_to_clearance_001", "dock clearance return re-enters the single lane safely"),
            ("reverse_buffer", "agv_nominal_warehouse_transfer_drop_to_mid_001", "reverse buffer transfer vacates the corridor before re-entry"),
        ],
        "unsafe": [
            ("westbound_head_on", "agv_unsafe_warehouse_shared_zone_west_to_east_001", "head-on occupation in the single lane"),
            ("clear_crossing_overlap", "agv_unsafe_warehouse_shared_zone_clear_crossing_001", "opposing traffic overlaps at the lane center"),
            ("north_to_west_overlap", "agv_unsafe_warehouse_shared_zone_north_to_west_001", "northbound turn conflicts with corridor traffic"),
            ("hold_short_violation", "agv_unsafe_warehouse_shared_zone_west_hold_short_001", "premature release collapses corridor spacing"),
            ("staggered_same_cell", "agv_unsafe_concurrent_shared_zone_staggered_crossing_001", "staggered release collapses into same-cell conflict"),
            ("priority_deadlock", "agv_unsafe_concurrent_shared_zone_priority_sequence_001", "priority ordering forms a lane deadlock"),
            ("safe_following_head_on", "agv_unsafe_concurrent_transfer_safe_following_001", "corridor following becomes head-on collision"),
            ("dock_release_swap", "agv_unsafe_concurrent_docking_release_yield_001", "dock release swaps cells at the corridor mouth"),
            ("queue_gate_overlap", "agv_unsafe_warehouse_docking_queue_to_gate_001", "queue-to-gate motion blocks corridor entry"),
            ("gate_dock_overlap", "agv_unsafe_warehouse_docking_gate_to_dock_001", "gate-to-dock motion violates corridor clearance"),
            ("source_to_mid_overlap", "agv_unsafe_warehouse_transfer_source_to_mid_001", "source-to-mid transfer reuses occupied corridor cell"),
            ("mid_to_drop_overlap", "agv_unsafe_warehouse_transfer_mid_to_drop_001", "mid-to-drop transfer blocks the single-lane exit"),
        ],
        "fault": [
            ("westbound_policy_mismatch", "agv_fault_warehouse_shared_zone_clear_crossing_policy_mismatch_001", "integrity mismatch before westbound corridor release"),
            ("northbound_timestamp_expired", "agv_fault_warehouse_shared_zone_north_to_west_timestamp_expired_001", "expired proof for north-to-west corridor turn"),
            ("hold_short_sensor_hash_mismatch", "agv_fault_warehouse_shared_zone_west_hold_short_sensor_hash_mismatch_001", "sensor hash mismatch while holding corridor entry"),
            ("entry_policy_mismatch", "agv_fault_warehouse_transfer_source_to_mid_policy_mismatch_001", "policy mismatch at upstream corridor entry"),
            ("reverse_sensor_hash_mismatch", "agv_fault_warehouse_transfer_drop_to_mid_sensor_hash_mismatch_001", "reverse corridor sensor hash mismatch"),
            ("queue_lock_denied", "agv_fault_warehouse_docking_queue_to_gate_lock_denied_001", "lock denied while reserving the single lane"),
            ("dock_reverify_hash_mismatch", "agv_fault_warehouse_docking_gate_to_dock_reverify_hash_mismatch_001", "reverify mismatch before lane commit"),
            ("westbound_ot_interface_error", "agv_fault_warehouse_shared_zone_west_to_east_ot_interface_error_001", "OT interface failure after corridor validation"),
        ],
    },
    "dock_occupancy_conflict": {
        "nominal": [
            ("queue_to_gate", "agv_nominal_warehouse_docking_queue_to_gate_001", "queue advances toward an unoccupied dock gate"),
            ("gate_to_dock", "agv_nominal_warehouse_docking_gate_to_dock_001", "gate-to-dock ingress occurs after occupancy release"),
            ("dock_to_clearance", "agv_nominal_warehouse_docking_dock_to_clearance_001", "docked AGV clears the bay before the next arrival"),
            ("alignment_hold", "agv_nominal_warehouse_docking_alignment_hold_001", "alignment hold preserves dock occupancy margin"),
            ("release_yield", "agv_nominal_concurrent_docking_release_yield_001", "neighboring AGV yields while dock is released"),
            ("clear_crossing_gate", "agv_nominal_warehouse_shared_zone_clear_crossing_001", "gate-side crossing stays outside dock occupancy zone"),
            ("transfer_buffer", "agv_nominal_warehouse_transfer_mid_to_drop_001", "transfer buffer arrival waits until dock occupancy clears"),
            ("shared_hold_release", "agv_nominal_warehouse_shared_zone_west_hold_short_001", "shared hold emulates controlled dock handoff timing"),
        ],
        "unsafe": [
            ("queue_gate_overlap", "agv_unsafe_warehouse_docking_queue_to_gate_001", "queue reaches the gate while dock remains occupied"),
            ("gate_dock_overlap", "agv_unsafe_warehouse_docking_gate_to_dock_001", "gate-to-dock ingress collides with occupied bay"),
            ("dock_clearance_overlap", "agv_unsafe_warehouse_docking_dock_to_clearance_001", "dock clearance path overlaps with incoming occupancy"),
            ("alignment_hold_overlap", "agv_unsafe_warehouse_docking_alignment_hold_001", "alignment hold violates dock clearance margin"),
            ("release_edge_swap", "agv_unsafe_concurrent_docking_release_yield_001", "neighboring release causes dock edge-swap conflict"),
            ("shared_gate_overlap", "agv_unsafe_warehouse_shared_zone_clear_crossing_001", "shared-zone gate approach intrudes into occupied dock"),
            ("west_to_east_overlap", "agv_unsafe_warehouse_shared_zone_west_to_east_001", "dock-side eastbound traffic enters occupied docking zone"),
            ("queue_priority_deadlock", "agv_unsafe_concurrent_shared_zone_priority_sequence_001", "priority sequence deadlocks the dock queue"),
            ("staggered_overlap", "agv_unsafe_concurrent_shared_zone_staggered_crossing_001", "staggered crossing collapses into occupied dock cell"),
            ("transfer_source_overlap", "agv_unsafe_warehouse_transfer_source_to_mid_001", "upstream transfer arrives before dock occupancy clears"),
            ("transfer_mid_overlap", "agv_unsafe_warehouse_transfer_mid_to_drop_001", "downstream transfer enters the occupied dock corridor"),
            ("transfer_reverse_overlap", "agv_unsafe_warehouse_transfer_drop_to_mid_001", "reverse transfer reclaims the dock lane too early"),
        ],
        "fault": [
            ("queue_lock_denied", "agv_fault_warehouse_docking_queue_to_gate_lock_denied_001", "dock queue reservation is denied before prepare"),
            ("gate_reverify_hash_mismatch", "agv_fault_warehouse_docking_gate_to_dock_reverify_hash_mismatch_001", "reverify mismatch while entering dock"),
            ("clearance_commit_timeout", "agv_fault_warehouse_docking_dock_to_clearance_commit_timeout_001", "dock clearance commit times out"),
            ("alignment_commit_failed", "agv_fault_warehouse_docking_alignment_hold_commit_failed_recovered_001", "alignment recovery ends in commit failure"),
            ("gate_policy_mismatch", "agv_fault_warehouse_shared_zone_clear_crossing_policy_mismatch_001", "policy mismatch before dock gate handoff"),
            ("hold_sensor_hash_mismatch", "agv_fault_warehouse_shared_zone_west_hold_short_sensor_hash_mismatch_001", "sensor hash mismatch while holding occupied dock"),
            ("transfer_timestamp_expired", "agv_fault_warehouse_transfer_mid_to_drop_timestamp_expired_001", "expired transfer proof before dock occupancy release"),
            ("dock_ot_interface_error", "agv_fault_warehouse_shared_zone_west_to_east_ot_interface_error_001", "OT interface failure during dock occupancy handoff"),
        ],
    },
}


def _build_expanded_cases(source_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for family, groups in FAMILY_EXPANSION_MAP.items():
        for group, entries in groups.items():
            for slug, source_case_id, semantic_role in entries:
                template = source_index[source_case_id]
                prefix = {"nominal": "agv_nominal_warehouse_", "unsafe": "agv_unsafe_warehouse_", "fault": "agv_fault_warehouse_"}[group]
                mission_phase = slug
                case_id = f"{prefix}{family}_{slug}_001"
                qc_role = {"nominal": "agv_nominal_safe", "unsafe": "agv_unsafe_counterfactual", "fault": "agv_fault_expanded"}[group]
                expanded.append(
                    _clone_case(
                        template,
                        case_id=case_id,
                        task_family=family,
                        mission_phase=mission_phase,
                        semantic_role=semantic_role,
                        qc_role=qc_role,
                    )
                )
    return expanded


def _build_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "release_id": "agv_source_release_v3",
        "benchmark_scope": "agv_only",
        "benchmark_version": "v3.0",
        "release_date": str(date.today()),
        "generator_script": str(Path(__file__).relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "derived_from_release": "agv_source_release_v2",
        "case_counts": {
            "nominal": sum(1 for case in cases if case["case_group"] == "nominal"),
            "unsafe": sum(1 for case in cases if case["case_group"] == "unsafe"),
            "fault": sum(1 for case in cases if case["case_group"] == "fault"),
            "total": len(cases),
        },
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in cases)),
        "case_counts_by_expected_status": dict(Counter(case["label"]["expected_final_status"] for case in cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in cases)),
        "release_artifacts": [
            "nominal_dataset.json",
            "unsafe_dataset.json",
            "fault_dataset.json",
            "all_cases.json",
            "dataset_manifest.json",
            "qc_report.md",
        ],
        "notes": [
            "AGV release v3 preserves the validated v2 outcome-complete benchmark and adds three single-asset expansion families.",
            "The expansion families are merge_bottleneck, single_lane_corridor, and dock_occupancy_conflict.",
            "v3 is built by templating validated v2 cases into richer supervisory families without introducing scenario-specific PCAG branching.",
        ],
    }


def _build_qc_report(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# AGV Source Release v3 QC Report",
        "",
        f"Release date: `{manifest['release_date']}`",
        "",
        "## Scope",
        "",
        "- Release type: `agv_only`",
        "- Base release: `agv_source_release_v2`",
        "- Added supplements: `merge_bottleneck`, `single_lane_corridor`, `dock_occupancy_conflict`",
        "",
        "## Counts",
        "",
        f"- Nominal cases: `{manifest['case_counts']['nominal']}`",
        f"- Unsafe cases: `{manifest['case_counts']['unsafe']}`",
        f"- Fault cases: `{manifest['case_counts']['fault']}`",
        f"- Total cases: `{manifest['case_counts']['total']}`",
        f"- Final-status coverage: `{', '.join(f'{key}={value}' for key, value in manifest['case_counts_by_expected_status'].items())}`",
        "",
        "## Expansion families",
        "",
        "- `merge_bottleneck`: upstream queue release, safe following, and bottleneck collision/deadlock counterfactuals.",
        "- `single_lane_corridor`: corridor release, yielding, head-on conflict, and deadlock-risk counterfactuals.",
        "- `dock_occupancy_conflict`: queue-to-gate, gate-to-dock, and occupied-dock conflict counterfactuals.",
        "",
        "## Notes",
        "",
        "- v3 keeps the v2 fault families intact so full PCAG outcome coverage remains available.",
        "- The new cases are semantic expansions over validated templates, which keeps the Gateway contract and runtime hooks unchanged.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    v2_cases = [_upgrade_case(case) for case in _load_json(V2_ALL_CASES_PATH)]
    source_index = {case["case_id"]: case for case in v2_cases}
    expanded_cases = _build_expanded_cases(source_index)
    all_cases = v2_cases + expanded_cases
    _validate_cases(all_cases)

    nominal_cases = [case for case in all_cases if case["case_group"] == "nominal"]
    unsafe_cases = [case for case in all_cases if case["case_group"] == "unsafe"]
    fault_cases = [case for case in all_cases if case["case_group"] == "fault"]

    manifest = _build_manifest(all_cases)
    qc_report = _build_qc_report(all_cases, manifest)

    _dump_json(RELEASE_DIR / "nominal_dataset.json", nominal_cases)
    _dump_json(RELEASE_DIR / "unsafe_dataset.json", unsafe_cases)
    _dump_json(RELEASE_DIR / "fault_dataset.json", fault_cases)
    _dump_json(RELEASE_DIR / "all_cases.json", all_cases)
    _dump_json(RELEASE_DIR / "dataset_manifest.json", manifest)
    (RELEASE_DIR / "qc_report.md").write_text(qc_report, encoding="utf-8")

    print(f"Wrote AGV benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
