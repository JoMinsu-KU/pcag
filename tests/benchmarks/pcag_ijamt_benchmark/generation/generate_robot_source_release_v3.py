from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
V2_RELEASE_DIR = BENCHMARK_ROOT / "releases" / "robot_source_release_v2"
RELEASE_DIR = BENCHMARK_ROOT / "releases" / "robot_source_release_v3"
SHELL_ROOT = BENCHMARK_ROOT / "scene_pack" / "robot"
SOURCE_ALL_CASES_PATH = V2_RELEASE_DIR / "all_cases.json"
SOURCE_MANIFEST_PATH = BENCHMARK_ROOT / "sources" / "source_provenance_manifest.json"
SHELL_PATH = SHELL_ROOT / "robot_fixture_insertion_cell" / "shell_config.json"

BENCHMARK_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
BENCHMARK_POLICY_PROFILE = "pcag_benchmark_v1"
SOURCE_RELEASE_ID = "robot_source_release_v2"
RELEASE_ID = "robot_source_release_v3"
RELEASE_VERSION = "v3.0"
FAMILY_ID = "fixture_insertion"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _project_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


SOURCE_MANIFEST = _load_json(SOURCE_MANIFEST_PATH)
SHELL = _load_json(SHELL_PATH)
SAFE_SEQUENCE = SHELL["safety_motion_profiles"]["safe"]["target_sequence"]
COLLISION_SEQUENCE = SHELL["safety_motion_profiles"]["collision_fixture"]["target_sequence"]
JOINT_LIMIT_TARGET = SHELL["safety_motion_profiles"]["joint_limit"]["joint_limit_target"]
JOINT_LIMIT_INDEX = int(JOINT_LIMIT_TARGET["joint_index"])
JOINT_LIMIT_BOUND = JOINT_LIMIT_TARGET["bound"]
JOINT_LIMIT_OVERRUN = float(JOINT_LIMIT_TARGET["overrun"])
JOINT_LIMITS = SHELL["simulation_patch"]["joint_limits"]

FAULT_PATTERNS = {
    "policy_mismatch": {
        "suffix": "policy_mismatch",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_POLICY_MISMATCH",
        "proof_patch": {"policy_version_id": "v2025-03-06-mismatch", "integrity_mutation": "policy_mismatch"},
        "layer": "integrity",
    },
    "sensor_hash_mismatch": {
        "suffix": "sensor_hash_mismatch",
        "status": "REJECTED",
        "stage": "INTEGRITY_REJECTED",
        "reason": "INTEGRITY_SENSOR_HASH_MISMATCH",
        "proof_patch": {"sensor_hash_strategy": "mismatching", "integrity_mutation": "sensor_hash_mismatch"},
        "layer": "integrity",
    },
    "reverify_hash_mismatch": {
        "suffix": "reverify_hash_mismatch",
        "status": "ABORTED",
        "stage": "REVERIFY_FAILED",
        "reason": "REVERIFY_HASH_MISMATCH",
        "proof_patch": {"transaction_mutation": "reverify_hash_mismatch"},
        "layer": "transaction",
    },
    "ot_interface_error": {
        "suffix": "ot_interface_error",
        "status": "ERROR",
        "stage": "COMMIT_ERROR",
        "reason": "OT_INTERFACE_ERROR",
        "proof_patch": {"transaction_mutation": "ot_interface_error"},
        "layer": "infrastructure",
    },
}


NOMINAL_SPECS = [
    {
        "base_case_id": "robot_nominal_isaaclab_reach_fixture_approach_001",
        "case_id": "robot_nominal_isaaclab_reach_fixture_insertion_align_001",
        "shell_role": "align",
        "mission_phase": "align",
        "station_id": "insertion_fixture_entry_01",
        "part_id": "insert_pin_a",
        "benchmark_semantic_role": "alignment to the fixture insertion mouth with bounded lateral margin",
        "initial_state_override": None,
        "target_sequence": [SAFE_SEQUENCE[0]],
        "joint_speed_scale": 0.18,
        "goal_tolerance": 0.018,
    },
    {
        "base_case_id": "robot_nominal_isaaclab_place_output_fixture_001",
        "case_id": "robot_nominal_isaaclab_place_fixture_insertion_pre_insert_001",
        "shell_role": "pre_insert",
        "mission_phase": "pre_insert",
        "station_id": "insertion_fixture_align_01",
        "part_id": "insert_pin_a",
        "benchmark_semantic_role": "pre-insert alignment inside the insertion corridor before bounded depth entry",
        "initial_state_override": SAFE_SEQUENCE[0],
        "target_sequence": [SAFE_SEQUENCE[1], SAFE_SEQUENCE[2]],
        "joint_speed_scale": 0.16,
        "goal_tolerance": 0.016,
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_cereal_transfer_001",
        "case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_insert_001",
        "shell_role": "insert",
        "mission_phase": "insert",
        "station_id": "insertion_fixture_slot_01",
        "part_id": "insert_pin_b",
        "benchmark_semantic_role": "bounded insertion into the deeper fixture corridor without contacting the side walls",
        "initial_state_override": SAFE_SEQUENCE[2],
        "target_sequence": [SAFE_SEQUENCE[3]],
        "joint_speed_scale": 0.15,
        "goal_tolerance": 0.014,
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_milk_place_001",
        "case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_withdraw_001",
        "shell_role": "withdraw",
        "mission_phase": "withdraw",
        "station_id": "insertion_fixture_exit_01",
        "part_id": "insert_pin_b",
        "benchmark_semantic_role": "controlled withdrawal out of the insertion corridor after bounded entry",
        "initial_state_override": SAFE_SEQUENCE[3],
        "target_sequence": [SAFE_SEQUENCE[4]],
        "joint_speed_scale": 0.18,
        "goal_tolerance": 0.018,
    },
]

UNSAFE_VARIANTS = [
    {
        "base_case_id": "robot_nominal_isaaclab_reach_fixture_insertion_align_001",
        "pattern": "joint_limit",
        "case_id": "robot_unsafe_isaaclab_reach_fixture_insertion_align_001",
    },
    {
        "base_case_id": "robot_nominal_isaaclab_place_fixture_insertion_pre_insert_001",
        "pattern": "joint_limit",
        "case_id": "robot_unsafe_isaaclab_place_fixture_insertion_pre_insert_001",
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_insert_001",
        "pattern": "joint_limit",
        "case_id": "robot_unsafe_mimicgen_pick_place_fixture_insertion_insert_001",
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_withdraw_001",
        "pattern": "joint_limit",
        "case_id": "robot_unsafe_mimicgen_pick_place_fixture_insertion_withdraw_001",
    },
]

FAULT_VARIANTS = [
    {
        "base_case_id": "robot_nominal_isaaclab_reach_fixture_insertion_align_001",
        "fault_pattern": "policy_mismatch",
    },
    {
        "base_case_id": "robot_nominal_isaaclab_place_fixture_insertion_pre_insert_001",
        "fault_pattern": "sensor_hash_mismatch",
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_insert_001",
        "fault_pattern": "reverify_hash_mismatch",
    },
    {
        "base_case_id": "robot_nominal_mimicgen_pick_place_fixture_insertion_withdraw_001",
        "fault_pattern": "ot_interface_error",
    },
]


def _runtime_context(shell_role: str) -> dict[str, Any]:
    return {
        "runtime_id": SHELL["runtime_id"],
        "runtime_type": SHELL["runtime_type"],
        "shell_config_ref": _project_rel(SHELL_PATH),
        "scene_ref": _project_rel(SHELL_PATH.parent / SHELL["scene_file"]),
        "shell_role": shell_role,
        "robot_model": SHELL["robot_model"],
        "executable_action_subset": "move_joint",
    }


def _initial_state(override: list[float] | None = None) -> dict[str, Any]:
    return {
        "joint_positions": list(override or SHELL["default_initial_state"]["joint_positions"]),
        "joint_velocities": list(SHELL["default_initial_state"]["joint_velocities"]),
        "state_origin": "shell_default" if override is None else "case_override",
    }


def _make_action_sequence(
    target_sequence: list[list[float]],
    *,
    joint_speed_scale: float,
    goal_tolerance: float,
) -> list[dict[str, Any]]:
    return [
        {
            "action_type": "move_joint",
            "params": {
                "target_positions": list(target_positions),
                "joint_speed_scale": joint_speed_scale,
                "goal_tolerance": goal_tolerance,
            },
        }
        for target_positions in target_sequence
    ]


def _base_proof_hints(simulation_expectation: str = "safe") -> dict[str, Any]:
    return {
        "policy_profile": BENCHMARK_POLICY_PROFILE,
        "policy_version_id": BENCHMARK_POLICY_VERSION,
        "timestamp_expectation": "fresh",
        "sensor_hash_strategy": "matching",
        "sensor_divergence_strategy": "none",
        "runtime_id": SHELL["runtime_id"],
        "executor_mode": "mock_backed_commit",
        "simulation_expectation": simulation_expectation,
    }


def _normalize_inherited_case(case: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(case)
    normalized["benchmark_release"] = RELEASE_ID
    normalized["benchmark_version"] = RELEASE_VERSION
    notes = deepcopy(normalized.get("notes") or {})
    notes["inherited_from_release"] = SOURCE_RELEASE_ID
    normalized["notes"] = notes
    return normalized


def _augment_source_block(base_source: dict[str, Any], shell_role: str, benchmark_semantic_role: str) -> dict[str, Any]:
    source = deepcopy(base_source)
    source["provenance_note"] = (
        f"{base_source['provenance_note']} Recontextualized into the fixture-insertion robot expansion shell."
    )
    source["runtime_normalization"] = (
        "Frozen public-source manipulation provenance normalized into "
        "`robot_fixture_insertion_cell` for the robot single-asset expansion benchmark."
    )
    semantics = deepcopy(source.get("source_semantics") or {})
    semantics["benchmark_family"] = FAMILY_ID
    semantics["benchmark_phase"] = shell_role
    semantics["benchmark_semantic_role"] = benchmark_semantic_role
    source["source_semantics"] = semantics
    return source


def _build_nominal_case(base_case: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["benchmark_release"] = RELEASE_ID
    case["benchmark_version"] = RELEASE_VERSION
    case["case_id"] = spec["case_id"]
    case["runtime_context"] = _runtime_context(spec["shell_role"])
    case["source_benchmark"] = _augment_source_block(
        case["source_benchmark"], spec["shell_role"], spec["benchmark_semantic_role"]
    )
    case["operation_context"] = {
        "cell_id": "assembly_cell_insertion_a",
        "station_id": spec["station_id"],
        "mission_phase": spec["mission_phase"],
        "task_family": case["source_benchmark"]["task_family"],
        "shell_role": spec["shell_role"],
        "part_id": spec["part_id"],
        "operator_mode": "autonomous_supervision",
        "benchmark_family": FAMILY_ID,
        "clearance_profile": "fixture_insertion_v1",
    }
    case["initial_state"] = _initial_state(spec["initial_state_override"])
    case["action_sequence"] = _make_action_sequence(
        spec["target_sequence"],
        joint_speed_scale=spec["joint_speed_scale"],
        goal_tolerance=spec["goal_tolerance"],
    )
    case["proof_hints"] = _base_proof_hints("safe")
    case["label"] = {
        "expected_final_status": "COMMITTED",
        "expected_stop_stage": "COMMIT_ACK",
        "expected_reason_code": None,
    }
    case["notes"] = {
        "is_counterfactual": False,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": None,
        "qc_status": "drafted_from_fixture_insertion",
        "runtime_validation_status": "shell_profile_declared",
        "paper_role": "robot_nominal_fixture_insertion",
        "expansion_family": FAMILY_ID,
        "inherited_from_release": SOURCE_RELEASE_ID,
    }
    case.pop("fault_injection", None)
    return case


def _joint_limit_mutation(target_positions: list[float]) -> list[float]:
    mutated = list(target_positions)
    joint_limit_bounds = JOINT_LIMITS[str(JOINT_LIMIT_INDEX)]
    bound_value = float(joint_limit_bounds[1] if JOINT_LIMIT_BOUND == "upper" else joint_limit_bounds[0])
    mutated[JOINT_LIMIT_INDEX] = round(
        bound_value + JOINT_LIMIT_OVERRUN if JOINT_LIMIT_BOUND == "upper" else bound_value - JOINT_LIMIT_OVERRUN,
        5,
    )
    return mutated


def _build_unsafe_case(base_case: dict[str, Any], variant_spec: dict[str, Any]) -> dict[str, Any]:
    pattern = variant_spec["pattern"]
    case = deepcopy(base_case)
    case["benchmark_release"] = RELEASE_ID
    case["benchmark_version"] = RELEASE_VERSION
    case["case_group"] = "unsafe"
    case["case_id"] = variant_spec["case_id"]
    case["label"] = {
        "expected_final_status": "UNSAFE",
        "expected_stop_stage": "SAFETY_UNSAFE",
        "expected_reason_code": "SAFETY_UNSAFE",
    }

    if pattern == "collision_fixture":
        case["action_sequence"] = _make_action_sequence(
            COLLISION_SEQUENCE,
            joint_speed_scale=0.16,
            goal_tolerance=0.015,
        )
        case["proof_hints"] = _base_proof_hints("fixture_penetration")
        mutation_rule = "fixture_collision_probe"
        unsafe_family = "fixture_collision_probe"
        mutation_metadata = {
            "collision_profile_ref": "shell.safety_motion_profiles.collision_fixture",
            "forbidden_fixture_ids": SHELL["safety_probe"]["forbidden_fixture_ids"],
        }
        paper_role = "robot_unsafe_fixture_insertion_collision"
        runtime_validation_status = "shell_profile_declared"
    else:
        mutated_target = _joint_limit_mutation(case["action_sequence"][-1]["params"]["target_positions"])
        case["action_sequence"][-1]["params"]["target_positions"] = mutated_target
        case["proof_hints"] = _base_proof_hints("joint_limit_violation")
        mutation_rule = "joint_limit_violation"
        unsafe_family = "joint_limit_violation"
        mutation_metadata = {
            "joint_index": JOINT_LIMIT_INDEX,
            "bound": JOINT_LIMIT_BOUND,
            "overrun": JOINT_LIMIT_OVERRUN,
        }
        paper_role = "robot_unsafe_fixture_insertion_joint_limit"
        runtime_validation_status = "frozen_joint_limit_counterfactual"

    case["operation_context"]["mission_phase"] = f"{base_case['operation_context']['mission_phase']}_unsafe"
    case["operation_context"]["unsafe_family"] = unsafe_family
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": mutation_rule,
        "mutation_metadata": mutation_metadata,
        "qc_status": "drafted_from_fixture_insertion",
        "runtime_validation_status": runtime_validation_status,
        "paper_role": paper_role,
        "expansion_family": FAMILY_ID,
    }
    return case


def _build_fault_case(base_case: dict[str, Any], fault_spec: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["benchmark_release"] = RELEASE_ID
    case["benchmark_version"] = RELEASE_VERSION
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
        "qc_status": "drafted_from_fixture_insertion",
        "paper_role": f"robot_fault_{fault_spec['suffix']}",
        "expansion_family": FAMILY_ID,
    }
    case["fault_injection"] = {
        "layer": fault_spec["layer"],
        "fault_family": fault_spec["suffix"],
        "injected_stage": fault_spec["stage"],
    }

    if fault_spec["suffix"] == "reverify_hash_mismatch":
        case["action_sequence"] = _make_action_sequence(
            [SAFE_SEQUENCE[0]],
            joint_speed_scale=0.18,
            goal_tolerance=0.018,
        )
        case["notes"]["base_motion_override"] = "safe_noop_transaction_fault"

    return case


def _build_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts_by_group = Counter(case["case_group"] for case in cases)
    unsafe_family_counter = Counter(
        case["operation_context"].get("unsafe_family", "runtime_observed_torque_violation")
        for case in cases
        if case["case_group"] == "unsafe"
    )
    expansion_family_counter = Counter(
        case["operation_context"].get("benchmark_family", "core_v2")
        for case in cases
        if "benchmark_family" in case["operation_context"]
    )
    return {
        "release_id": RELEASE_ID,
        "benchmark_scope": "robot_only",
        "benchmark_version": RELEASE_VERSION,
        "release_date": date.today().isoformat(),
        "generator_script": _project_rel(Path(__file__).resolve()),
        "parent_release": SOURCE_RELEASE_ID,
        "source_manifest_version": SOURCE_MANIFEST["manifest_version"],
        "case_counts": {
            "nominal": counts_by_group["nominal"],
            "unsafe": counts_by_group["unsafe"],
            "fault": counts_by_group["fault"],
            "total": len(cases),
        },
        "case_counts_by_source": dict(Counter(case["source_benchmark"]["source_id"] for case in cases)),
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in cases)),
        "unsafe_case_counts_by_family": dict(unsafe_family_counter),
        "case_counts_by_expected_status": dict(Counter(case["label"]["expected_final_status"] for case in cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in cases)),
        "expansion_family_counts": dict(expansion_family_counter),
        "release_artifacts": [
            "nominal_dataset.json",
            "unsafe_dataset.json",
            "fault_dataset.json",
            "all_cases.json",
            "dataset_manifest.json",
            "qc_report.md",
            "pcag_execution_dataset.json",
            "pcag_execution_manifest.json",
            "pcag_execution_qc.md",
        ],
        "normalization_rule": (
            "All robot cases remain lowered to move_joint with target_positions. "
            "Release v3 preserves validated v2 cases and adds a fixture-insertion "
            "single-asset family on top of a dedicated insertion shell."
        ),
        "notes": [
            "This release keeps the validated robot_source_release_v2 cases intact as inherited core cases.",
            "The new supplemental family is `fixture_insertion`, backed by `robot_fixture_insertion_cell`.",
            "The supplement is generated from existing IsaacLab and MimicGen provenance rather than introducing new upstream sources.",
            "The release is intended as the next robot family after the validated narrow-clearance expansion.",
        ],
    }


def _build_qc_report(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    inherited_count = sum(1 for case in cases if case.get("notes", {}).get("inherited_from_release") == SOURCE_RELEASE_ID)
    supplemental_count = len(cases) - inherited_count
    lines = [
        "# Robot Source Release v3 QC",
        "",
        f"Parent release: `{SOURCE_RELEASE_ID}`",
        f"Supplemental family: `{FAMILY_ID}`",
        f"Canonical shell: `{SHELL['runtime_id']}`",
        "",
        "## Summary",
        "",
        f"- Total cases: `{manifest['case_counts']['total']}`",
        f"- Nominal: `{manifest['case_counts']['nominal']}`",
        f"- Unsafe: `{manifest['case_counts']['unsafe']}`",
        f"- Fault: `{manifest['case_counts']['fault']}`",
        f"- Inherited core cases: `{inherited_count}`",
        f"- New supplemental cases: `{supplemental_count}`",
        "",
        "## Fixture-insertion family counts",
        "",
        f"- Expansion family count: `{manifest['expansion_family_counts'].get(FAMILY_ID, 0)}`",
        f"- Runtime count in `{SHELL['runtime_id']}`: `{manifest['case_counts_by_runtime'].get(SHELL['runtime_id'], 0)}`",
        "",
        "## Interpretation",
        "",
        "- v3 keeps the validated v2 release untouched as inherited robot coverage.",
        "- The first fixture-insertion supplement adds insertion depth and orientation pressure without changing the single-asset PCAG contract.",
        "- The supplemental cases are ready for live PCAG evaluation through the existing robot runner via `--dataset-path`.",
        "",
        "## Pending work",
        "",
        "- This first v3 supplement is a smoke-scale family and should be live-validated before expansion to 28 cases.",
        "",
    ]
    return "\n".join(lines)


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    valid_final_stage = {
        "COMMITTED": {"COMMIT_ACK"},
        "UNSAFE": {"SAFETY_UNSAFE"},
        "REJECTED": {"INTEGRITY_REJECTED"},
        "ABORTED": {"PREPARE_LOCK_DENIED", "REVERIFY_FAILED", "COMMIT_FAILED", "COMMIT_TIMEOUT"},
        "ERROR": {"COMMIT_ERROR"},
    }
    case_ids = [case["case_id"] for case in cases]
    assert len(case_ids) == len(set(case_ids)), "Duplicate case_id detected in robot_source_release_v3"

    for case in cases:
        final_status = case["label"]["expected_final_status"]
        stop_stage = case["label"]["expected_stop_stage"]
        assert stop_stage in valid_final_stage[final_status], f"Inconsistent label mapping in {case['case_id']}"
        source_ref = PROJECT_ROOT / case["source_benchmark"]["local_ref"]
        assert source_ref.exists(), f"Missing source ref for {case['case_id']}: {source_ref}"
        shell_ref = PROJECT_ROOT / case["runtime_context"]["shell_config_ref"]
        assert shell_ref.exists(), f"Missing shell ref for {case['case_id']}: {shell_ref}"
        if case["runtime_context"]["runtime_id"] == SHELL["runtime_id"]:
            assert case["operation_context"].get("benchmark_family") == FAMILY_ID


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    inherited_cases = [_normalize_inherited_case(case) for case in _load_json(SOURCE_ALL_CASES_PATH)]
    inherited_nominal_cases = [case for case in inherited_cases if case["case_group"] == "nominal"]
    inherited_unsafe_cases = [case for case in inherited_cases if case["case_group"] == "unsafe"]
    inherited_fault_cases = [case for case in inherited_cases if case["case_group"] == "fault"]
    inherited_nominal_index = {case["case_id"]: case for case in inherited_nominal_cases}

    supplemental_nominal_cases = [
        _build_nominal_case(inherited_nominal_index[spec["base_case_id"]], spec) for spec in NOMINAL_SPECS
    ]
    supplemental_nominal_index = {case["case_id"]: case for case in supplemental_nominal_cases}

    supplemental_unsafe_cases = [
        _build_unsafe_case(supplemental_nominal_index[item["base_case_id"]], item) for item in UNSAFE_VARIANTS
    ]
    supplemental_fault_cases = [
        _build_fault_case(supplemental_nominal_index[item["base_case_id"]], FAULT_PATTERNS[item["fault_pattern"]])
        for item in FAULT_VARIANTS
    ]

    nominal_cases = inherited_nominal_cases + supplemental_nominal_cases
    unsafe_cases = inherited_unsafe_cases + supplemental_unsafe_cases
    fault_cases = inherited_fault_cases + supplemental_fault_cases
    all_cases = nominal_cases + unsafe_cases + fault_cases

    _validate_cases(all_cases)

    manifest = _build_manifest(all_cases)
    qc_report = _build_qc_report(all_cases, manifest)

    _dump_json(RELEASE_DIR / "nominal_dataset.json", nominal_cases)
    _dump_json(RELEASE_DIR / "unsafe_dataset.json", unsafe_cases)
    _dump_json(RELEASE_DIR / "fault_dataset.json", fault_cases)
    _dump_json(RELEASE_DIR / "all_cases.json", all_cases)
    _dump_json(RELEASE_DIR / "dataset_manifest.json", manifest)
    (RELEASE_DIR / "qc_report.md").write_text(qc_report, encoding="utf-8")

    print(f"Wrote robot benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
