from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
RELEASE_DIR = BENCHMARK_ROOT / "releases" / "agv_source_release_v1"
SOURCE_MANIFEST_PATH = BENCHMARK_ROOT / "sources" / "source_provenance_manifest.json"
SHELL_ROOT = BENCHMARK_ROOT / "scene_pack" / "agv"
WAREHOUSE_REF_PATH = (
    BENCHMARK_ROOT / "external_sources" / "agv" / "robotic-warehouse-reference" / "rware" / "warehouse.py"
)

BENCHMARK_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
BENCHMARK_POLICY_PROFILE = "pcag_benchmark_v1"
SOURCE_ID = "warehouse_world_curated"
SOURCE_NAME = "RoboticWarehouse"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _project_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value) if key in merged else deepcopy(value)
        return merged
    return deepcopy(override)


SOURCE_MANIFEST = _load_json(SOURCE_MANIFEST_PATH)
SOURCE_INDEX = {item["source_id"]: item for item in SOURCE_MANIFEST["sources"]}
AGV_SHELLS = {
    "agv_transfer_map": _load_json(SHELL_ROOT / "agv_transfer_map" / "shell_config.json"),
    "agv_docking_map": _load_json(SHELL_ROOT / "agv_docking_map" / "shell_config.json"),
    "agv_shared_zone_map": _load_json(SHELL_ROOT / "agv_shared_zone_map" / "shell_config.json"),
}

FAR_BACKGROUND_PATCH = {
    "simulation_override": {"agvs": {"agv_02": {"position": [10, 8], "speed": 1.0}}},
    "sensor_state_overlay": {"agv_02": {"x": 10, "y": 8}},
}

BASE_SPECS = [
    {
        "case_id": "agv_nominal_warehouse_transfer_source_to_mid_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_nominal",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::source_load_to_transfer_mid",
        "station_id": "transfer_mid",
        "mission_phase": "transfer",
        "load_id": "carrier_alpha",
        "provenance_note": "Warehouse-world station transfer motif lowered into a source-to-mid-lane AGV command.",
        "semantic_role": "station transfer through the main transfer lane",
        "target": [6, 3],
        "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3]],
        "unsafe_variant": {
            "rule": "grid_boundary_violation",
            "simulation_expectation": "grid_boundary",
            "target": [14, 7],
            "path": [[2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [8, 1], [9, 1], [10, 1], [11, 1], [12, 1], [13, 1], [14, 1], [14, 2], [14, 3], [14, 4], [14, 5], [14, 6], [14, 7]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_transfer_mid_to_drop_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_with_path_variant",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::transfer_mid_to_target_drop",
        "station_id": "target_drop",
        "mission_phase": "dropoff",
        "load_id": "carrier_alpha",
        "initial_state_override": {"position_x": 6, "position_y": 3, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world transfer motif lowered into a mid-lane to target-drop AGV command.",
        "semantic_role": "dropoff lane approach",
        "target": [12, 7],
        "path": [[7, 3], [8, 3], [9, 3], [10, 3], [10, 4], [10, 5], [10, 6], [11, 6], [12, 6], [12, 7]],
        "unsafe_variant": {
            "rule": "obstacle_intrusion",
            "simulation_expectation": "obstacle_collision",
            "target": [12, 7],
            "path": [[7, 3], [8, 3], [9, 3], [9, 4], [10, 4], [11, 4], [12, 4], [12, 5], [12, 6], [12, 7]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_transfer_drop_to_mid_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_nominal",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::target_drop_to_transfer_mid",
        "station_id": "transfer_mid",
        "mission_phase": "return",
        "load_id": "empty_carrier_alpha",
        "initial_state_override": {"position_x": 12, "position_y": 7, "heading": 180.0, "speed": 0.0},
        "provenance_note": "Warehouse-world transfer-return motif lowered into a target-drop to mid-lane AGV command.",
        "semantic_role": "return lane traversal",
        "target": [6, 3],
        "path": [[12, 6], [11, 6], [10, 6], [10, 5], [10, 4], [10, 3], [9, 3], [8, 3], [7, 3], [6, 3]],
        "unsafe_variant": {
            "rule": "grid_boundary_violation",
            "simulation_expectation": "grid_boundary",
            "target": [6, -1],
            "path": [[12, 6], [11, 6], [10, 6], [9, 6], [8, 6], [7, 6], [6, 6], [6, 5], [6, 4], [6, 3], [6, 2], [6, 1], [6, 0], [6, -1]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_transfer_lane_variant_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_with_path_variant",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::source_load_to_target_drop_long_lane",
        "station_id": "target_drop",
        "mission_phase": "transfer",
        "load_id": "carrier_beta",
        "provenance_note": "Warehouse-world long-lane transfer motif lowered into a full source-to-drop AGV command.",
        "semantic_role": "long corridor transfer",
        "target": [12, 7],
        "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3], [7, 3], [8, 3], [9, 3], [10, 3], [10, 4], [10, 5], [10, 6], [11, 6], [12, 6], [12, 7]],
        "unsafe_variant": {
            "rule": "obstacle_intrusion",
            "simulation_expectation": "obstacle_collision",
            "target": [12, 7],
            "path": [[2, 1], [3, 1], [4, 1], [4, 2], [5, 2], [6, 2], [7, 2], [8, 2], [9, 2], [10, 2], [11, 2], [12, 2], [12, 3], [12, 4], [12, 5], [12, 6], [12, 7]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_docking_queue_to_gate_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_nominal",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::queue_to_alignment_gate",
        "station_id": "alignment_gate",
        "mission_phase": "dock_approach",
        "load_id": "carrier_gamma",
        "provenance_note": "Warehouse-world docking motif lowered into a queue-to-alignment-gate AGV command.",
        "semantic_role": "docking queue approach",
        "target": [8, 4],
        "path": [[2, 5], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [8, 4]],
        "unsafe_variant": {
            "rule": "obstacle_intrusion",
            "simulation_expectation": "obstacle_collision",
            "target": [8, 4],
            "path": [[2, 5], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [7, 6], [8, 6], [8, 5], [8, 4]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_docking_gate_to_dock_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_alignment_variant",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::alignment_gate_to_handoff_dock",
        "station_id": "handoff_dock",
        "mission_phase": "dock_align",
        "load_id": "carrier_gamma",
        "initial_state_override": {"position_x": 8, "position_y": 4, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world docking motif lowered into a gate-to-dock final-approach AGV command.",
        "semantic_role": "final docking alignment",
        "target": [9, 2],
        "path": [[8, 3], [8, 2], [9, 2]],
        "unsafe_variant": {
            "rule": "grid_boundary_violation",
            "simulation_expectation": "grid_boundary",
            "target": [12, 2],
            "path": [[8, 3], [8, 2], [9, 2], [10, 2], [11, 2], [12, 2]],
        },
    },
    {
        "case_id": "agv_nominal_warehouse_docking_dock_to_clearance_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_nominal",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::handoff_dock_to_clearance",
        "station_id": "dock_clearance",
        "mission_phase": "dock_release",
        "load_id": "empty_carrier_gamma",
        "initial_state_override": {"position_x": 9, "position_y": 2, "heading": 180.0, "speed": 0.0},
        "provenance_note": "Warehouse-world docking-release motif lowered into a dock-to-clearance AGV command.",
        "semantic_role": "dock clearance release",
        "target": [9, 3],
        "path": [[9, 3]],
        "unsafe_variant": {
            "rule": "shared_occupancy_conflict",
            "simulation_expectation": "min_distance_violation",
            "target": [9, 2],
            "path": [[8, 3], [8, 2], [9, 2]],
            "runtime_context_patch": {
                "simulation_override": {"agvs": {"agv_02": {"position": [9, 2], "speed": 0.8}}},
                "sensor_state_overlay": {"agv_02": {"x": 9, "y": 2}},
            },
        },
    },
    {
        "case_id": "agv_nominal_warehouse_docking_alignment_hold_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_alignment_variant",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::queue_to_handoff_dock_full_approach",
        "station_id": "handoff_dock",
        "mission_phase": "dock_approach",
        "load_id": "carrier_delta",
        "provenance_note": "Warehouse-world full docking motif lowered into a queue-to-dock AGV command.",
        "semantic_role": "full final-approach docking",
        "target": [9, 2],
        "path": [[2, 5], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [8, 4], [8, 3], [8, 2], [9, 2]],
        "unsafe_variant": {
            "rule": "shared_occupancy_conflict",
            "simulation_expectation": "min_distance_violation",
            "target": [9, 2],
            "path": [[2, 5], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [8, 4], [8, 3]],
            "runtime_context_patch": {
                "simulation_override": {"agvs": {"agv_02": {"position": [8, 3], "speed": 0.8}}},
                "sensor_state_overlay": {"agv_02": {"x": 8, "y": 3}},
            },
        },
    },
    {
        "case_id": "agv_nominal_warehouse_shared_zone_west_to_east_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_nominal",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::west_entry_to_east_exit",
        "station_id": "east_exit",
        "mission_phase": "zone_entry",
        "load_id": "carrier_theta",
        "provenance_note": "Warehouse-world shared-zone motif lowered into a west-to-east AGV crossing command.",
        "semantic_role": "shared-zone crossing",
        "target": [9, 5],
        "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
        "runtime_context_patch": FAR_BACKGROUND_PATCH,
        "unsafe_variant": {
            "rule": "shared_occupancy_conflict",
            "simulation_expectation": "min_distance_violation",
            "target": [9, 5],
            "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
            "runtime_context_patch": {
                "simulation_override": {"agvs": {"agv_02": {"position": [6, 5], "speed": 1.0}}},
                "sensor_state_overlay": {"agv_02": {"x": 6, "y": 5}},
            },
        },
    },
    {
        "case_id": "agv_nominal_warehouse_shared_zone_clear_crossing_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_clear_crossing",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::west_entry_short_crossing",
        "station_id": "shared_zone",
        "mission_phase": "zone_entry",
        "load_id": "carrier_theta",
        "provenance_note": "Warehouse-world shared-zone motif lowered into a short west-entry crossing command.",
        "semantic_role": "short shared-zone entry",
        "target": [7, 5],
        "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5]],
        "runtime_context_patch": FAR_BACKGROUND_PATCH,
        "unsafe_variant": {
            "rule": "shared_occupancy_conflict",
            "simulation_expectation": "min_distance_violation",
            "target": [6, 6],
            "path": [[3, 5], [4, 5], [5, 5], [6, 5], [6, 6]],
            "runtime_context_patch": {
                "simulation_override": {"agvs": {"agv_02": {"position": [6, 6], "speed": 1.0}}},
                "sensor_state_overlay": {"agv_02": {"x": 6, "y": 6}},
            },
        },
    },
    {
        "case_id": "agv_nominal_warehouse_shared_zone_north_to_west_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_nominal",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::north_queue_to_west_lane",
        "station_id": "west_entry",
        "mission_phase": "zone_exit",
        "load_id": "carrier_sigma",
        "initial_state_override": {"position_x": 6, "position_y": 8, "heading": 270.0, "speed": 0.0},
        "provenance_note": "Warehouse-world shared-zone motif lowered into a north-queue to west-lane AGV command.",
        "semantic_role": "north-lane shared-zone crossing",
        "target": [2, 5],
        "path": [[6, 7], [6, 6], [6, 5], [5, 5], [4, 5], [3, 5], [2, 5]],
        "runtime_context_patch": FAR_BACKGROUND_PATCH,
        "unsafe_variant": {
            "rule": "grid_boundary_violation",
            "simulation_expectation": "grid_boundary",
            "target": [12, 5],
            "path": [[6, 7], [6, 6], [6, 5], [7, 5], [8, 5], [9, 5], [10, 5], [11, 5], [12, 5]],
            "runtime_context_patch": FAR_BACKGROUND_PATCH,
        },
    },
    {
        "case_id": "agv_nominal_warehouse_shared_zone_west_hold_short_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_clear_crossing",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::west_entry_to_intersection_hold",
        "station_id": "shared_zone",
        "mission_phase": "zone_hold",
        "load_id": "carrier_sigma",
        "provenance_note": "Warehouse-world shared-zone motif lowered into an intersection-hold AGV command.",
        "semantic_role": "shared-zone staged hold",
        "target": [5, 5],
        "path": [[3, 5], [4, 5], [5, 5]],
        "runtime_context_patch": FAR_BACKGROUND_PATCH,
        "unsafe_variant": {
            "rule": "shared_occupancy_conflict",
            "simulation_expectation": "min_distance_violation",
            "target": [5, 5],
            "path": [[3, 5], [4, 5], [5, 5]],
            "runtime_context_patch": {
                "simulation_override": {"agvs": {"agv_02": {"position": [5, 5], "speed": 1.0}}},
                "sensor_state_overlay": {"agv_02": {"x": 5, "y": 5}},
            },
        },
    },
]

FAULT_PATTERNS = [
    {
        "suffix": "policy_mismatch",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_POLICY_MISMATCH",
        "proof_patch": {"policy_version_id": "v2025-03-06-mismatch", "integrity_mutation": "policy_mismatch"},
        "layer": "integrity",
    },
    {
        "suffix": "timestamp_expired",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_TIMESTAMP_EXPIRED",
        "proof_patch": {"timestamp_expectation": "expired", "integrity_mutation": "timestamp_expired"},
        "layer": "integrity",
    },
    {
        "suffix": "sensor_hash_mismatch",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_SENSOR_HASH_MISMATCH",
        "proof_patch": {"sensor_hash_strategy": "mismatching", "integrity_mutation": "sensor_hash_mismatch"},
        "layer": "integrity",
    },
    {
        "suffix": "sensor_divergence",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_SENSOR_DIVERGENCE",
        "proof_patch": {"sensor_divergence_strategy": "beyond_threshold", "integrity_mutation": "sensor_divergence"},
        "layer": "integrity",
    },
    {
        "suffix": "lock_denied",
        "status": "ABORTED",
        "stage": "PREPARE_LOCK_DENIED",
        "reason": "LOCK_DENIED",
        "proof_patch": {"transaction_mutation": "prepare_lock_denied"},
        "layer": "transaction",
    },
    {
        "suffix": "reverify_hash_mismatch",
        "status": "ABORTED",
        "stage": "REVERIFY_FAILED",
        "reason": "REVERIFY_HASH_MISMATCH",
        "proof_patch": {"transaction_mutation": "reverify_hash_mismatch"},
        "layer": "transaction",
    },
    {
        "suffix": "commit_timeout",
        "status": "ABORTED",
        "stage": "COMMIT_TIMEOUT",
        "reason": "COMMIT_TIMEOUT",
        "proof_patch": {"transaction_mutation": "commit_timeout"},
        "layer": "transaction",
    },
    {
        "suffix": "commit_failed_recovered",
        "status": "ABORTED",
        "stage": "COMMIT_FAILED",
        "reason": "COMMIT_FAILED",
        "proof_patch": {"transaction_mutation": "commit_failed_recovered"},
        "layer": "transaction",
    },
    {
        "suffix": "ot_interface_error",
        "status": "ERROR",
        "stage": "COMMIT_ERROR",
        "reason": "OT_INTERFACE_ERROR",
        "proof_patch": {"transaction_mutation": "ot_interface_error"},
        "layer": "infrastructure",
    },
]


def _base_proof_hints(runtime_id: str) -> dict[str, Any]:
    return {
        "policy_profile": BENCHMARK_POLICY_PROFILE,
        "policy_version_id": BENCHMARK_POLICY_VERSION,
        "timestamp_expectation": "fresh",
        "sensor_hash_strategy": "matching",
        "sensor_divergence_strategy": "none",
        "runtime_id": runtime_id,
        "executor_mode": "plc_backed_commit",
        "simulation_expectation": "safe",
    }


def _source_block(spec: dict[str, Any]) -> dict[str, Any]:
    manifest_entry = SOURCE_INDEX[SOURCE_ID]
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "task_family": spec["task_family"],
        "source_unit": spec["source_unit"],
        "local_ref": _project_rel(WAREHOUSE_REF_PATH),
        "upstream_ref": manifest_entry["verified_ref"],
        "provenance_note": spec["provenance_note"],
        "source_semantics": {
            "motif": spec["task_family"],
            "semantic_role": spec["semantic_role"],
            "selection_reason": "selected in source_task_selection.md as an AGV release-v1 logistics motif",
        },
        "runtime_normalization": "Warehouse-world logistics motifs normalized into the canonical AGV move_to supervisory subset.",
    }


def _runtime_context(spec: dict[str, Any]) -> dict[str, Any]:
    shell = AGV_SHELLS[spec["runtime_id"]]
    base = {
        "runtime_id": spec["runtime_id"],
        "runtime_type": shell["runtime_type"],
        "shell_config_ref": _project_rel(SHELL_ROOT / spec["runtime_id"] / "shell_config.json"),
        "map_ref": _project_rel(SHELL_ROOT / spec["runtime_id"] / shell["map_file"]),
        "shell_role": spec["shell_role"],
        "executable_action_subset": "move_to",
        "asset_family": "agv",
    }
    return _deep_merge(base, spec.get("runtime_context_patch", {}))


def _initial_state(spec: dict[str, Any]) -> dict[str, Any]:
    shell = AGV_SHELLS[spec["runtime_id"]]
    return deepcopy(spec.get("initial_state_override") or shell["default_initial_state"])


def _move_action(target: list[int], path: list[list[int]]) -> dict[str, Any]:
    return {
        "action_type": "move_to",
        "params": {
            "agv_id": "agv_01",
            "target_x": target[0],
            "target_y": target[1],
            "path": path,
        },
    }


def _make_nominal_case(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_release": "agv_source_release_v1",
        "benchmark_version": "v1.0",
        "case_id": spec["case_id"],
        "case_group": "nominal",
        "asset_id": "agv_01",
        "scenario_family": "agv_logistics",
        "runtime_context": _runtime_context(spec),
        "source_benchmark": _source_block(spec),
        "operation_context": {
            "cell_id": spec["runtime_id"],
            "station_id": spec["station_id"],
            "mission_phase": spec["mission_phase"],
            "task_family": spec["task_family"],
            "shell_role": spec["shell_role"],
            "load_id": spec["load_id"],
            "operator_mode": "autonomous_supervision",
        },
        "initial_state": _initial_state(spec),
        "action_sequence": [_move_action(spec["target"], spec["path"])],
        "proof_hints": _base_proof_hints(spec["runtime_id"]),
        "label": {
            "expected_final_status": "COMMITTED",
            "expected_stop_stage": "COMMIT_ACK",
            "expected_reason_code": None,
        },
        "notes": {
            "is_counterfactual": False,
            "derived_from_case_id": None,
            "mutation_rule": None,
            "qc_status": "drafted_from_frozen_source",
            "paper_role": "agv_nominal_safe",
        },
    }


def _make_unsafe_case(base_case: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    variant = spec["unsafe_variant"]
    case = deepcopy(base_case)
    case["case_group"] = "unsafe"
    case["case_id"] = base_case["case_id"].replace("agv_nominal_", "agv_unsafe_")
    case["action_sequence"] = [_move_action(variant["target"], variant["path"])]
    if variant.get("runtime_context_patch"):
        case["runtime_context"] = _deep_merge(case["runtime_context"], variant["runtime_context_patch"])
    case["proof_hints"]["simulation_expectation"] = variant["simulation_expectation"]
    case["label"] = {
        "expected_final_status": "UNSAFE",
        "expected_stop_stage": "SAFETY_UNSAFE",
        "expected_reason_code": "SAFETY_UNSAFE",
    }
    case["operation_context"]["mission_phase"] = f"{base_case['operation_context']['mission_phase']}_unsafe"
    case["operation_context"]["unsafe_family"] = variant["rule"]
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": variant["rule"],
        "qc_status": "drafted_from_frozen_source",
        "paper_role": "agv_unsafe_counterfactual",
    }
    return case


def _make_fault_case(base_case: dict[str, Any], fault_spec: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["case_group"] = "fault"
    case["case_id"] = (
        base_case["case_id"].replace("agv_nominal_", "agv_fault_").replace("_001", f"_{fault_spec['suffix']}_001")
    )
    case["proof_hints"].update(fault_spec["proof_patch"])
    case["label"] = {
        "expected_final_status": fault_spec["status"],
        "expected_stop_stage": fault_spec["stage"],
        "expected_reason_code": fault_spec["reason"],
    }
    case["fault_injection"] = {
        "layer": fault_spec["layer"],
        "fault_family": fault_spec["suffix"],
        "injected_stage": fault_spec["stage"],
    }
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": fault_spec["suffix"],
        "qc_status": "drafted_from_frozen_source",
        "paper_role": f"agv_fault_{fault_spec['suffix']}",
    }
    return case


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    valid_final_stage = {
        "COMMITTED": {"COMMIT_ACK"},
        "UNSAFE": {"SAFETY_UNSAFE"},
        "REJECTED": {"INTEGRITY_REJECTED"},
        "ABORTED": {"PREPARE_LOCK_DENIED", "REVERIFY_FAILED", "COMMIT_FAILED", "COMMIT_TIMEOUT"},
        "ERROR": {"COMMIT_ERROR"},
    }
    for case in cases:
        assert case["scenario_family"] == "agv_logistics"
        assert case["asset_id"] == "agv_01"
        assert case["action_sequence"][0]["action_type"] == "move_to"
        final_status = case["label"]["expected_final_status"]
        stop_stage = case["label"]["expected_stop_stage"]
        assert stop_stage in valid_final_stage[final_status], f"Inconsistent label mapping in {case['case_id']}"
        assert WAREHOUSE_REF_PATH.exists(), f"Missing AGV source ref: {WAREHOUSE_REF_PATH}"
        shell_ref = PROJECT_ROOT / case["runtime_context"]["shell_config_ref"]
        assert shell_ref.exists(), f"Missing shell ref for {case['case_id']}: {shell_ref}"


def _build_manifest(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]]) -> dict[str, Any]:
    all_cases = nominal + unsafe + fault
    return {
        "release_id": "agv_source_release_v1",
        "benchmark_scope": "agv_only",
        "benchmark_version": "v1.0",
        "release_date": str(date.today()),
        "generator_script": _project_rel(Path(__file__)),
        "source_manifest_version": SOURCE_MANIFEST["manifest_version"],
        "case_counts": {
            "nominal": len(nominal),
            "unsafe": len(unsafe),
            "fault": len(fault),
            "total": len(all_cases),
        },
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in all_cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in all_cases)),
        "case_counts_by_expected_status": dict(Counter(case["label"]["expected_final_status"] for case in all_cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in all_cases)),
        "release_artifacts": [
            "nominal_dataset.json",
            "unsafe_dataset.json",
            "fault_dataset.json",
            "all_cases.json",
            "dataset_manifest.json",
            "qc_report.md",
        ],
        "notes": [
            "AGV release v1 is grounded in the frozen warehouse_world_curated provenance anchor.",
            "All AGV cases are normalized into the public move_to supervisory subset.",
            "Unsafe cases cover grid-boundary, obstacle, and shared-zone minimum-distance counterfactuals.",
            f"The release is aligned to benchmark policy version {BENCHMARK_POLICY_VERSION}.",
        ],
    }


def _build_qc_report(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# AGV Source Release v1 QC Report",
        "",
        f"Release date: `{manifest['release_date']}`",
        "",
        "## Scope",
        "",
        "- Release type: `agv_only`",
        "- Upstream source: `warehouse_world_curated`",
        "- Implemented runtime shells: `agv_transfer_map`, `agv_docking_map`, `agv_shared_zone_map`",
        "",
        "## Counts",
        "",
        f"- Nominal cases: `{len(nominal)}`",
        f"- Unsafe cases: `{len(unsafe)}`",
        f"- Fault cases: `{len(fault)}`",
        f"- Total cases: `{len(nominal) + len(unsafe) + len(fault)}`",
        f"- Final-status coverage: `{', '.join(f'{key}={value}' for key, value in manifest['case_counts_by_expected_status'].items())}`",
        "",
        "## Consistency checks",
        "",
        "- All cases use `scenario_family = agv_logistics`.",
        "- All cases use the executable subset `move_to`.",
        "- All shell references exist in the AGV scene pack.",
        "- All label triplets satisfy the frozen label taxonomy.",
        "",
        "## Unsafe mutation policy",
        "",
        "- Grid-boundary counterfactuals drive deliberate out-of-grid moves.",
        "- Obstacle counterfactuals drive deliberate path intrusion through blocked cells.",
        "- Shared-zone counterfactuals place a background AGV in the critical occupancy cell to trigger a min-distance violation.",
        "",
        "## Fault mutation policy",
        "",
        "- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`",
        "- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`",
        "- Infrastructure faults: `ot_interface_error`",
        "",
        "## Notes for the paper",
        "",
        "- The AGV benchmark is not a raw robotic-warehouse imitation dataset; it is a frozen supervisory benchmark derived from warehouse-world logistics motifs.",
        "- Shared-zone cases use a stationary background AGV as a conflict anchor so that unsafe occupancy can be checked by the existing discrete-event backend.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    nominal_cases = [_make_nominal_case(spec) for spec in BASE_SPECS]
    unsafe_cases = [_make_unsafe_case(case, spec) for case, spec in zip(nominal_cases, BASE_SPECS, strict=True)]
    fault_cases = [
        _make_fault_case(case, FAULT_PATTERNS[index % len(FAULT_PATTERNS)])
        for index, case in enumerate(nominal_cases)
    ]

    _validate_cases(nominal_cases + unsafe_cases + fault_cases)

    manifest = _build_manifest(nominal_cases, unsafe_cases, fault_cases)
    qc_report = _build_qc_report(nominal_cases, unsafe_cases, fault_cases, manifest)
    all_cases = nominal_cases + unsafe_cases + fault_cases

    _dump_json(RELEASE_DIR / "nominal_dataset.json", nominal_cases)
    _dump_json(RELEASE_DIR / "unsafe_dataset.json", unsafe_cases)
    _dump_json(RELEASE_DIR / "fault_dataset.json", fault_cases)
    _dump_json(RELEASE_DIR / "all_cases.json", all_cases)
    _dump_json(RELEASE_DIR / "dataset_manifest.json", manifest)
    (RELEASE_DIR / "qc_report.md").write_text(qc_report, encoding="utf-8")

    print(f"Wrote AGV benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
