from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
RELEASE_DIR = BENCHMARK_ROOT / "releases" / "robot_source_release_v1"
SOURCE_MANIFEST_PATH = BENCHMARK_ROOT / "sources" / "source_provenance_manifest.json"
SHELL_ROOT = BENCHMARK_ROOT / "scene_pack" / "robot"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _project_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


SOURCE_MANIFEST = _load_json(SOURCE_MANIFEST_PATH)
SOURCE_INDEX = {item["source_id"]: item for item in SOURCE_MANIFEST["sources"]}
BENCHMARK_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
BENCHMARK_POLICY_PROFILE = "pcag_benchmark_v1"

ROBOT_SHELLS = {
    "robot_pick_place_cell": _load_json(SHELL_ROOT / "robot_pick_place_cell" / "shell_config.json"),
    "robot_stack_cell": _load_json(SHELL_ROOT / "robot_stack_cell" / "shell_config.json"),
}

SAFE_POSES = {
    "pick_fixture_approach": [0.12, -0.88, 0.18, -2.20, 0.02, 1.72, 0.66],
    "pick_source_lift": [0.02, -0.68, 0.05, -2.12, -0.02, 1.66, 0.80],
    "transfer_to_fixture": [0.30, -0.52, 0.12, -2.00, 0.10, 1.56, 0.96],
    "place_output_fixture": [0.54, -0.38, 0.18, -1.86, 0.18, 1.48, 1.10],
    "retreat_safe_pose": [0.10, -0.76, 0.20, -1.96, 0.00, 1.82, 0.88],
    "alternate_station_transfer": [0.36, -0.26, 0.16, -1.92, 0.26, 1.44, 1.04],
    "conveyor_pick_approach": [0.28, -0.86, 0.22, -2.18, -0.18, 1.74, 0.58],
    "conveyor_pick_pose": [0.18, -0.54, 0.08, -2.06, 0.10, 1.70, 0.82],
    "first_layer_place": [0.46, -0.44, 0.22, -1.90, 0.18, 1.57, 1.08],
    "second_layer_place": [0.50, -0.38, 0.30, -1.82, 0.22, 1.50, 1.14],
    "retreat_clearance": [0.22, -0.70, 0.18, -2.08, -0.04, 1.86, 0.86],
}

STACK_SAFE_SEQUENCES = {
    "first_layer_place": [
        SAFE_POSES["conveyor_pick_approach"],
        SAFE_POSES["conveyor_pick_pose"],
        SAFE_POSES["transfer_to_fixture"],
        SAFE_POSES["first_layer_place"],
    ],
    "second_layer_place": [
        SAFE_POSES["conveyor_pick_approach"],
        SAFE_POSES["conveyor_pick_pose"],
        SAFE_POSES["transfer_to_fixture"],
        [0.40, -0.45, 0.20, -1.92, 0.16, 1.55, 1.04],
        SAFE_POSES["second_layer_place"],
    ],
}

RUNTIME_UNSAFE_RELABEL_IDS = {
    "robot_nominal_isaaclab_stack_first_layer_place_001",
    "robot_nominal_mimicgen_stack_cubeB_place_001",
}

REVERIFY_SAFE_PREFIX_SEQUENCE = [
    SAFE_POSES["conveyor_pick_approach"],
    SAFE_POSES["conveyor_pick_pose"],
    SAFE_POSES["transfer_to_fixture"],
]


def _base_proof_hints(runtime_id: str) -> dict[str, Any]:
    return {
        "policy_profile": BENCHMARK_POLICY_PROFILE,
        "policy_version_id": BENCHMARK_POLICY_VERSION,
        "timestamp_expectation": "fresh",
        "sensor_hash_strategy": "matching",
        "sensor_divergence_strategy": "none",
        "runtime_id": runtime_id,
        "executor_mode": "mock_backed_commit",
        "simulation_expectation": "safe",
    }


def _runtime_context(runtime_id: str, shell_role: str) -> dict[str, Any]:
    shell = ROBOT_SHELLS[runtime_id]
    return {
        "runtime_id": runtime_id,
        "runtime_type": shell["runtime_type"],
        "shell_config_ref": _project_rel(SHELL_ROOT / runtime_id / "shell_config.json"),
        "scene_ref": _project_rel(SHELL_ROOT / runtime_id / shell["scene_file"]),
        "shell_role": shell_role,
        "robot_model": shell["robot_model"],
        "executable_action_subset": "move_joint",
    }


def _source_block(spec: dict[str, Any]) -> dict[str, Any]:
    source_manifest_entry = SOURCE_INDEX[spec["source_id"]]
    return {
        "source_id": spec["source_id"],
        "source_name": spec["source_name"],
        "task_family": spec["task_family"],
        "source_unit": spec["source_unit"],
        "local_ref": spec["local_ref"],
        "upstream_ref": source_manifest_entry["verified_ref"],
        "provenance_note": spec["provenance_note"],
        "source_semantics": spec["source_semantics"],
        "runtime_normalization": spec["runtime_normalization"],
    }


def _initial_state(runtime_id: str, override: list[float] | None = None) -> dict[str, Any]:
    shell = ROBOT_SHELLS[runtime_id]
    return {
        "joint_positions": override or shell["default_initial_state"]["joint_positions"],
        "joint_velocities": shell["default_initial_state"]["joint_velocities"],
        "state_origin": "shell_default" if override is None else "case_override",
    }


def _make_nominal_case(spec: dict[str, Any]) -> dict[str, Any]:
    target_sequence = spec.get("target_sequence")
    if target_sequence:
        action_sequence = [
            {
                "action_type": "move_joint",
                "params": {
                    "target_positions": target_positions,
                    "joint_speed_scale": spec.get("joint_speed_scale", 0.25),
                    "goal_tolerance": spec.get("goal_tolerance", 0.02),
                },
            }
            for target_positions in target_sequence
        ]
    else:
        action_sequence = [
            {
                "action_type": "move_joint",
                "params": {
                    "target_positions": spec["target_positions"],
                    "joint_speed_scale": spec.get("joint_speed_scale", 0.25),
                    "goal_tolerance": spec.get("goal_tolerance", 0.02),
                },
            }
        ]

    return {
        "benchmark_release": "robot_source_release_v1",
        "benchmark_version": "v1.0",
        "case_id": spec["case_id"],
        "case_group": "nominal",
        "asset_id": "robot_arm_01",
        "scenario_family": "robot_manipulation",
        "runtime_context": _runtime_context(spec["runtime_id"], spec["shell_role"]),
        "source_benchmark": _source_block(spec),
        "operation_context": {
            "cell_id": spec["cell_id"],
            "station_id": spec["station_id"],
            "mission_phase": spec["mission_phase"],
            "task_family": spec["task_family"],
            "shell_role": spec["shell_role"],
            "part_id": spec["part_id"],
            "operator_mode": "autonomous_supervision",
        },
        "initial_state": _initial_state(spec["runtime_id"], spec.get("initial_state_override")),
        "action_sequence": action_sequence,
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
            "paper_role": "robot_nominal_safe",
        },
    }


NOMINAL_SPECS = [
    {
        "case_id": "robot_nominal_isaaclab_reach_fixture_approach_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "reach",
        "source_unit": "manager_based/manipulation/reach/config/franka/joint_pos_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/reach/config/franka/joint_pos_env_cfg.py"
        ),
        "provenance_note": "Franka reach-family posture normalized into a fixture approach supervisory command.",
        "runtime_normalization": "Franka-native IsaacLab source family mapped directly into the canonical pick-place cell.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "approach",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "fixture_station_01",
        "mission_phase": "approach",
        "part_id": "housing_a",
        "source_semantics": {
            "upstream_robot_family": "franka",
            "semantic_role": "target approach / pre-grasp motion",
            "selection_reason": "selected in source_task_selection.md for nominal approach cases",
        },
        "target_positions": SAFE_POSES["pick_fixture_approach"],
    },
    {
        "case_id": "robot_nominal_isaaclab_lift_source_pick_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "lift",
        "source_unit": "manager_based/manipulation/lift/config/franka/joint_pos_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/lift/config/franka/joint_pos_env_cfg.py"
        ),
        "provenance_note": "Franka lift-family episode lowered into a source-tray pickup elevation posture.",
        "runtime_normalization": "Franka-native IsaacLab source family mapped directly into the canonical pick-place cell.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "pick",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "source_tray_01",
        "mission_phase": "pick",
        "part_id": "housing_a",
        "source_semantics": {
            "upstream_robot_family": "franka",
            "semantic_role": "pickup or post-grasp elevation",
            "selection_reason": "selected in source_task_selection.md for nominal elevation cases",
        },
        "target_positions": SAFE_POSES["pick_source_lift"],
    },
    {
        "case_id": "robot_nominal_isaaclab_pick_place_transfer_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "pick_place",
        "source_unit": "manager_based/manipulation/pick_place/pickplace_gr1t2_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/pick_place/pickplace_gr1t2_env_cfg.py"
        ),
        "provenance_note": "Industrial pick-place provenance lowered into a transfer posture inside the canonical pick-place shell.",
        "runtime_normalization": "Non-Franka upstream family normalized into the public Franka fallback runtime according to the frozen shell strategy.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "transfer",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "transfer_lane_01",
        "mission_phase": "transfer",
        "part_id": "housing_a",
        "source_semantics": {
            "upstream_robot_family": "gr1t2",
            "semantic_role": "pick-and-place transfer motion",
            "selection_reason": "selected in source_task_selection.md as a primary nominal motion family",
        },
        "target_positions": SAFE_POSES["transfer_to_fixture"],
    },
    {
        "case_id": "robot_nominal_isaaclab_place_output_fixture_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "place",
        "source_unit": "manager_based/manipulation/place/config/agibot/place_toy2box_rmp_rel_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/place/config/agibot/place_toy2box_rmp_rel_env_cfg.py"
        ),
        "provenance_note": "Place-family deposition semantics converted into a fixture-aligned placement posture.",
        "runtime_normalization": "Non-Franka upstream family normalized into the public Franka fallback runtime according to the frozen shell strategy.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "place",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "output_fixture_01",
        "mission_phase": "place",
        "part_id": "housing_a",
        "source_semantics": {
            "upstream_robot_family": "agibot",
            "semantic_role": "final alignment and deposition",
            "selection_reason": "selected in source_task_selection.md for precise placement semantics",
        },
        "target_positions": SAFE_POSES["place_output_fixture"],
    },
    {
        "case_id": "robot_nominal_isaaclab_stack_conveyor_pick_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "stack",
        "source_unit": "manager_based/manipulation/stack/config/franka/stack_joint_pos_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/stack/config/franka/stack_joint_pos_env_cfg.py"
        ),
        "provenance_note": "Franka stack-family pickup posture normalized into the conveyor-side stack-cell shell.",
        "runtime_normalization": "Franka-native stack source family mapped directly into the canonical stack shell.",
        "runtime_id": "robot_stack_cell",
        "shell_role": "conveyor_pick",
        "cell_id": "assembly_cell_stack_a",
        "station_id": "infeed_conveyor_01",
        "mission_phase": "pick",
        "part_id": "block_blue",
        "source_semantics": {
            "upstream_robot_family": "franka",
            "semantic_role": "stack-family conveyor pickup",
            "selection_reason": "selected in source_task_selection.md as a primary assembly-style family",
        },
        "target_positions": SAFE_POSES["conveyor_pick_pose"],
    },
    {
        "case_id": "robot_nominal_isaaclab_stack_first_layer_place_001",
        "source_id": "isaaclab_eval_industrial",
        "source_name": "IsaacLab",
        "task_family": "stack",
        "source_unit": "manager_based/manipulation/stack/config/franka/stack_ik_rel_instance_randomize_env_cfg.py",
        "local_ref": _project_rel(
            BENCHMARK_ROOT
            / "external_sources/robot/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/stack/config/franka/stack_ik_rel_instance_randomize_env_cfg.py"
        ),
        "provenance_note": "Instance-randomized stack source normalized into a first-layer placement posture in the stack nest.",
        "runtime_normalization": "Franka-native stack source family mapped directly into the canonical stack shell.",
        "runtime_id": "robot_stack_cell",
        "shell_role": "first_layer_place",
        "cell_id": "assembly_cell_stack_a",
        "station_id": "stack_nest_01",
        "mission_phase": "place",
        "part_id": "block_blue",
        "source_semantics": {
            "upstream_robot_family": "franka",
            "semantic_role": "constrained placement in stack region",
            "selection_reason": "selected in source_task_selection.md for structured assembly positioning",
        },
        "target_positions": SAFE_POSES["first_layer_place"],
        "target_sequence": STACK_SAFE_SEQUENCES["first_layer_place"],
    },
    {
        "case_id": "robot_nominal_mimicgen_pick_place_milk_pick_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "pick_place",
        "source_unit": "robosuite/pick_place.json#subtask_1_grasp_milk",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/pick_place.json"
        ),
        "provenance_note": "MimicGen pick-place milk grasp lowered into a source-tray pickup posture.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "pick",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "source_tray_02",
        "mission_phase": "pick",
        "part_id": "milk_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "grasp milk object",
            "object_ref": "milk",
            "subtask_signal": "grasp_milk",
        },
        "target_positions": SAFE_POSES["pick_source_lift"],
    },
    {
        "case_id": "robot_nominal_mimicgen_pick_place_milk_place_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "pick_place",
        "source_unit": "robosuite/pick_place.json#subtask_2_place_milk",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/pick_place.json"
        ),
        "provenance_note": "MimicGen milk placement lowered into an alternate station transfer pose in the pick-place shell.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "place",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "alternate_fixture_02",
        "mission_phase": "place",
        "part_id": "milk_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "place milk object",
            "object_ref": "milk",
            "subtask_signal": "place_milk",
        },
        "target_positions": SAFE_POSES["alternate_station_transfer"],
    },
    {
        "case_id": "robot_nominal_mimicgen_pick_place_cereal_transfer_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "pick_place",
        "source_unit": "robosuite/pick_place.json#subtask_3_grasp_cereal",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/pick_place.json"
        ),
        "provenance_note": "MimicGen cereal pick semantics converted into a nominal transfer posture.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_pick_place_cell",
        "shell_role": "transfer",
        "cell_id": "assembly_cell_pick_a",
        "station_id": "transfer_lane_02",
        "mission_phase": "transfer",
        "part_id": "cereal_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "grasp cereal object",
            "object_ref": "cereal",
            "subtask_signal": "grasp_cereal",
        },
        "target_positions": SAFE_POSES["transfer_to_fixture"],
    },
    {
        "case_id": "robot_nominal_mimicgen_stack_cubeA_transfer_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "stack",
        "source_unit": "robosuite/stack.json#subtask_1_cubeA_grasp",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/stack.json"
        ),
        "provenance_note": "MimicGen stack cubeA grasp lowered into a conveyor-pick posture inside the stack shell.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_stack_cell",
        "shell_role": "conveyor_pick",
        "cell_id": "assembly_cell_stack_a",
        "station_id": "infeed_conveyor_02",
        "mission_phase": "pick",
        "part_id": "cubeA_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "stack source-object grasp",
            "object_ref": "cubeA",
            "subtask_signal": "grasp",
        },
        "target_positions": SAFE_POSES["conveyor_pick_approach"],
    },
    {
        "case_id": "robot_nominal_mimicgen_stack_cubeB_place_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "stack",
        "source_unit": "robosuite/stack.json#subtask_2_cubeB_place",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/stack.json"
        ),
        "provenance_note": "MimicGen stack placement lowered into a second-layer placement posture in the stack nest.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_stack_cell",
        "shell_role": "second_layer_place",
        "cell_id": "assembly_cell_stack_a",
        "station_id": "stack_nest_01",
        "mission_phase": "place",
        "part_id": "cubeB_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "stack placement",
            "object_ref": "cubeB",
            "subtask_signal": "stack_terminal",
        },
        "target_positions": SAFE_POSES["second_layer_place"],
        "target_sequence": STACK_SAFE_SEQUENCES["second_layer_place"],
    },
    {
        "case_id": "robot_nominal_mimicgen_stack_retreat_clearance_001",
        "source_id": "mimicgen_assembly",
        "source_name": "MimicGen",
        "task_family": "stack",
        "source_unit": "robosuite/stack.json#derived_retreat_clearance",
        "local_ref": _project_rel(
            BENCHMARK_ROOT / "external_sources/robot/mimicgen/mimicgen/exps/templates/robosuite/stack.json"
        ),
        "provenance_note": "MimicGen stack family augmented with a retreat-to-clearance supervisory posture after nominal placement.",
        "runtime_normalization": "Robosuite single-arm provenance normalized into the public Franka fallback runtime.",
        "runtime_id": "robot_stack_cell",
        "shell_role": "retreat",
        "cell_id": "assembly_cell_stack_a",
        "station_id": "clearance_lane_01",
        "mission_phase": "retreat",
        "part_id": "cubeB_proxy",
        "source_semantics": {
            "upstream_robot_family": "robosuite_single_arm",
            "semantic_role": "post-placement clearance",
            "object_ref": "cubeB",
            "subtask_signal": "derived_retreat",
        },
        "target_positions": SAFE_POSES["retreat_clearance"],
    },
]


def _joint_limit_mutation(case: dict[str, Any], direction: str) -> tuple[list[float], dict[str, Any]]:
    runtime_id = case["runtime_context"]["runtime_id"]
    shell = ROBOT_SHELLS[runtime_id]
    limits = shell["simulation_patch"]["joint_limits"]
    mutated = deepcopy(case["action_sequence"][-1]["params"]["target_positions"])

    if direction == "upper_joint_1":
        mutated[1] = float(limits["1"][1]) + 0.35
        meta = {"joint_index": 1, "bound": "upper", "overrun": 0.35}
    elif direction == "lower_joint_3":
        mutated[3] = float(limits["3"][0]) - 0.28
        meta = {"joint_index": 3, "bound": "lower", "overrun": 0.28}
    elif direction == "upper_joint_5":
        mutated[5] = float(limits["5"][1]) + 0.20
        meta = {"joint_index": 5, "bound": "upper", "overrun": 0.20}
    else:
        mutated[6] = float(limits["6"][1]) + 0.22
        meta = {"joint_index": 6, "bound": "upper", "overrun": 0.22}

    return mutated, meta


UNSAFE_PATTERNS = [
    "upper_joint_1",
    "collision_fixture",
    "lower_joint_3",
    "collision_fixture",
    "upper_joint_5",
    "collision_fixture",
    "upper_joint_6",
    "collision_fixture",
]


def _collision_fixture_mutation(case: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    runtime_id = case["runtime_context"]["runtime_id"]
    shell = ROBOT_SHELLS[runtime_id]
    collision_profile = ((shell.get("safety_motion_profiles") or {}).get("collision_fixture") or {})
    sequence = collision_profile.get("target_sequence") or []
    if not sequence:
        raise ValueError(f"Shell {runtime_id} does not define a collision_fixture profile.")
    return list(sequence[-1]), {
        "profile_name": "collision_fixture",
        "expected_outcome": collision_profile.get("expected_outcome", "unsafe"),
        "description": collision_profile.get("description"),
        "forbidden_fixture_ids": (shell.get("safety_probe") or {}).get("forbidden_fixture_ids", []),
    }


def _make_unsafe_case(base_case: dict[str, Any], pattern: str) -> dict[str, Any]:
    if pattern == "collision_fixture":
        mutated, mutation_meta = _collision_fixture_mutation(base_case)
        mutation_rule = "fixture_collision_probe"
        simulation_expectation = "fixture_penetration"
        paper_role = "robot_unsafe_fixture_collision"
        unsafe_family = "fixture_collision_probe"
        runtime_validation_status = "shell_profile_declared"
    else:
        mutated, mutation_meta = _joint_limit_mutation(base_case, pattern)
        mutation_rule = "joint_limit_violation"
        simulation_expectation = "joint_limit_violation"
        paper_role = "robot_unsafe_joint_limit"
        unsafe_family = "joint_limit_violation"
        runtime_validation_status = "frozen_joint_limit_counterfactual"

    case = deepcopy(base_case)
    case["case_group"] = "unsafe"
    case["case_id"] = base_case["case_id"].replace("robot_nominal_", "robot_unsafe_")
    case["action_sequence"][-1]["params"]["target_positions"] = mutated
    case["proof_hints"]["simulation_expectation"] = simulation_expectation
    case["label"] = {
        "expected_final_status": "UNSAFE",
        "expected_stop_stage": "SAFETY_UNSAFE",
        "expected_reason_code": "SAFETY_UNSAFE",
    }
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": mutation_rule,
        "mutation_metadata": mutation_meta,
        "qc_status": "drafted_from_frozen_source",
        "runtime_validation_status": runtime_validation_status,
        "paper_role": paper_role,
    }
    case["operation_context"]["mission_phase"] = f"{base_case['operation_context']['mission_phase']}_unsafe"
    case["operation_context"]["unsafe_family"] = unsafe_family
    return case


def _relabel_runtime_unsafe_case(base_case: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["case_group"] = "unsafe"
    case["proof_hints"]["simulation_expectation"] = "torque_violation"
    case["label"] = {
        "expected_final_status": "UNSAFE",
        "expected_stop_stage": "SAFETY_UNSAFE",
        "expected_reason_code": "SAFETY_UNSAFE",
    }
    case["operation_context"]["mission_phase"] = f"{base_case['operation_context']['mission_phase']}_unsafe"
    case["operation_context"]["unsafe_family"] = "sim_torque_violation"
    case["notes"] = {
        "is_counterfactual": False,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": "runtime_observed_torque_violation",
        "qc_status": "relabeled_after_live_pcag_validation",
        "runtime_validation_status": "live_pcag_observed_v1",
        "paper_role": "robot_unsafe_runtime_torque",
        "legacy_case_id_retained": True,
    }
    return case


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


def _make_fault_case(base_case: dict[str, Any], fault_spec: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["case_group"] = "fault"
    case["case_id"] = (
        base_case["case_id"].replace("robot_nominal_", "robot_fault_").replace("_001", f"_{fault_spec['suffix']}_001")
    )
    case["proof_hints"].update(fault_spec["proof_patch"])
    case["label"] = {
        "expected_final_status": fault_spec["status"],
        "expected_stop_stage": fault_spec["stage"],
        "expected_reason_code": fault_spec["reason"],
    }
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": fault_spec["suffix"],
        "qc_status": "drafted_from_frozen_source",
        "paper_role": f"robot_fault_{fault_spec['suffix']}",
    }
    case["fault_injection"] = {
        "layer": fault_spec["layer"],
        "fault_family": fault_spec["suffix"],
        "injected_stage": fault_spec["stage"],
    }
    if (
        base_case["case_id"] == "robot_nominal_isaaclab_stack_first_layer_place_001"
        and fault_spec["suffix"] == "reverify_hash_mismatch"
    ):
        case["action_sequence"] = [
            {
                "action_type": "move_joint",
                "params": {
                    "target_positions": target_positions,
                    "joint_speed_scale": 0.25,
                    "goal_tolerance": 0.02,
                },
            }
            for target_positions in REVERIFY_SAFE_PREFIX_SEQUENCE
        ]
        case["proof_hints"]["simulation_expectation"] = "safe"
        case["notes"] = {
            "is_counterfactual": True,
            "derived_from_case_id": base_case["case_id"],
            "mutation_rule": fault_spec["suffix"],
            "qc_status": "drafted_from_frozen_source",
            "paper_role": f"robot_fault_{fault_spec['suffix']}",
            "fault_base_override": "safe_stack_prefix_for_reverify",
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
        assert case["scenario_family"] == "robot_manipulation"
        assert case["asset_id"] == "robot_arm_01"
        assert case["action_sequence"][0]["action_type"] == "move_joint"
        final_status = case["label"]["expected_final_status"]
        stop_stage = case["label"]["expected_stop_stage"]
        assert stop_stage in valid_final_stage[final_status], f"Inconsistent label mapping in {case['case_id']}"
        source_ref = PROJECT_ROOT / case["source_benchmark"]["local_ref"]
        assert source_ref.exists(), f"Missing source ref for {case['case_id']}: {source_ref}"
        shell_ref = PROJECT_ROOT / case["runtime_context"]["shell_config_ref"]
        assert shell_ref.exists(), f"Missing shell ref for {case['case_id']}: {shell_ref}"


def _build_manifest(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]]) -> dict[str, Any]:
    all_cases = nominal + unsafe + fault
    outcome_counts = Counter(case["label"]["expected_final_status"] for case in all_cases)
    stop_stage_counts = Counter(case["label"]["expected_stop_stage"] for case in all_cases)
    unsafe_family_counts = Counter(case["operation_context"].get("unsafe_family") for case in unsafe)
    return {
        "release_id": "robot_source_release_v1",
        "benchmark_scope": "robot_only",
        "benchmark_version": "v1.0",
        "release_date": str(date.today()),
        "generator_script": _project_rel(Path(__file__)),
        "source_manifest_version": SOURCE_MANIFEST["manifest_version"],
        "task_selection_version": "v1-selection",
        "construction_procedure_version": "v1-procedure",
        "case_counts": {
            "nominal": len(nominal),
            "unsafe": len(unsafe),
            "fault": len(fault),
            "total": len(all_cases),
        },
        "case_counts_by_source": dict(Counter(case["source_benchmark"]["source_id"] for case in all_cases)),
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in all_cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in all_cases)),
        "unsafe_case_counts_by_family": dict(unsafe_family_counts),
        "case_counts_by_expected_status": dict(outcome_counts),
        "case_counts_by_stop_stage": dict(stop_stage_counts),
        "covered_source_families": sorted({case["source_benchmark"]["task_family"] for case in nominal}),
        "deferred_selected_families": [
            "deploy/gear_assembly",
            "nut_assembly",
            "threading",
            "three_piece_assembly",
        ],
        "outcome_coverage": {
            "COMMITTED": outcome_counts.get("COMMITTED", 0) > 0,
            "UNSAFE": outcome_counts.get("UNSAFE", 0) > 0,
            "REJECTED": outcome_counts.get("REJECTED", 0) > 0,
            "ABORTED": outcome_counts.get("ABORTED", 0) > 0,
            "ERROR": outcome_counts.get("ERROR", 0) > 0,
        },
        "release_artifacts": [
            "nominal_dataset.json",
            "unsafe_dataset.json",
            "fault_dataset.json",
            "all_cases.json",
            "dataset_manifest.json",
            "qc_report.md",
        ],
        "normalization_rule": "All robot cases are lowered to move_joint with target_positions and executed against canonical robot shells.",
        "notes": [
            "This release intentionally limits itself to implemented robot shells.",
            "It uses IsaacLab and MimicGen provenance exactly as frozen in the source manifest.",
            "Assembly-family sources remain selected at the planning layer but are deferred until robot_gear_assembly_cell is implemented.",
            "The release is outcome-complete for benchmark drafting: committed, unsafe, rejected, aborted, and infrastructure-error paths are all represented.",
        ],
    }


def _build_qc_report(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# Robot Source Release v1 QC Report",
        "",
        f"Release date: `{manifest['release_date']}`",
        "",
        "## Scope",
        "",
        "- Release type: `robot_only`",
        "- Upstream sources: `IsaacLab`, `MimicGen`",
        "- Implemented runtime shells: `robot_pick_place_cell`, `robot_stack_cell`",
        "",
        "## Counts",
        "",
        f"- Nominal cases: `{len(nominal)}`",
        f"- Unsafe cases: `{len(unsafe)}`",
        f"- Fault cases: `{len(fault)}`",
        f"- Total cases: `{len(nominal) + len(unsafe) + len(fault)}`",
        f"- Final-status coverage: `{', '.join(f'{key}={value}' for key, value in manifest['case_counts_by_expected_status'].items())}`",
        "",
        "## Coverage",
        "",
        f"- Covered source families: `{', '.join(manifest['covered_source_families'])}`",
        "- Deferred selected families: `deploy/gear_assembly`, `nut_assembly`, `threading`, `three_piece_assembly`",
        "- Covered shells: `robot_pick_place_cell`, `robot_stack_cell`",
        "- Outcome-complete release artifact: `all_cases.json`",
        "",
        "## Consistency checks",
        "",
        "- All cases use `scenario_family = robot_manipulation`.",
        "- All cases use the executable subset `move_joint`.",
        "- All source references exist in the frozen local acquisition targets.",
        "- All shell references exist in the implemented scene pack.",
        "- All label triplets satisfy the frozen label taxonomy.",
        "",
        "## Unsafe mutation policy",
        "",
        "- Release v1 uses two robot unsafe families: `joint_limit_violation` and `fixture_collision_probe`.",
        "- Collision unsafe cases are threshold-calibrated against the implemented pick-place and stack shells.",
        "- The calibrated collision profiles currently correspond to workbench-surface penetration near the fixture approach region.",
        "",
        "## Fault mutation policy",
        "",
        "- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`",
        "- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`",
        "- Infrastructure faults: `ot_interface_error`",
        "",
        "## Notes for the paper",
        "",
        "- IsaacLab is used as a frozen task-family and env-config provenance source, not as a raw copied dataset.",
        "- MimicGen is used as a frozen single-arm manipulation provenance source, normalized into the same PCAG shell vocabulary.",
        "- Robot cases are normalized into canonical Franka-compatible runtime shells even when the upstream source family uses a different robot embodiment.",
        f"- The release is aligned to benchmark policy version `{BENCHMARK_POLICY_VERSION}`.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    base_cases = [_make_nominal_case(spec) for spec in NOMINAL_SPECS]
    relabeled_runtime_unsafe_cases = [
        _relabel_runtime_unsafe_case(case) for case in base_cases if case["case_id"] in RUNTIME_UNSAFE_RELABEL_IDS
    ]
    nominal_cases = [case for case in base_cases if case["case_id"] not in RUNTIME_UNSAFE_RELABEL_IDS]
    derived_unsafe_cases = [
        _make_unsafe_case(case, UNSAFE_PATTERNS[index % len(UNSAFE_PATTERNS)])
        for index, case in enumerate(base_cases)
    ]
    unsafe_cases = relabeled_runtime_unsafe_cases + derived_unsafe_cases
    fault_cases = [
        _make_fault_case(case, FAULT_PATTERNS[index % len(FAULT_PATTERNS)]) for index, case in enumerate(base_cases)
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

    print(f"Wrote robot benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
