from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
RELEASE_DIR = BENCHMARK_ROOT / "releases" / "process_source_release_v2"
SOURCE_MANIFEST_PATH = BENCHMARK_ROOT / "sources" / "source_provenance_manifest.json"
PROCESS_SHELL_ROOT = BENCHMARK_ROOT / "scene_pack" / "process"

BENCHMARK_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
BENCHMARK_POLICY_PROFILE = "pcag_benchmark_v1"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _project_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


SOURCE_MANIFEST = _load_json(SOURCE_MANIFEST_PATH)
SOURCE_INDEX = {item["source_id"]: item for item in SOURCE_MANIFEST["sources"]}

PROCESS_SHELLS = {
    "reactor_nominal_profile": _load_json(PROCESS_SHELL_ROOT / "reactor_nominal_profile" / "shell_config.json"),
    "reactor_high_heat_profile": _load_json(PROCESS_SHELL_ROOT / "reactor_high_heat_profile" / "shell_config.json"),
    "reactor_disturbance_profile": _load_json(PROCESS_SHELL_ROOT / "reactor_disturbance_profile" / "shell_config.json"),
}

V1_ALL_CASES_PATH = BENCHMARK_ROOT / "releases" / "process_source_release_v1" / "all_cases.json"

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


def _upgrade_case(case: dict[str, Any]) -> dict[str, Any]:
    upgraded = deepcopy(case)
    upgraded["benchmark_release"] = "process_source_release_v2"
    upgraded["benchmark_version"] = "v2.0"
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
        f"Existing process v1 template {template['case_id']} was remapped into the {task_family} expansion family."
    )
    cloned["source_benchmark"]["source_semantics"]["upstream_process_family"] = task_family
    cloned["source_benchmark"]["source_semantics"]["semantic_role"] = semantic_role
    cloned["operation_context"]["task_family"] = task_family
    cloned["operation_context"]["mission_phase"] = mission_phase
    cloned["notes"]["qc_status"] = "templated_from_process_source_release_v1"
    cloned["notes"]["paper_role"] = qc_role
    cloned["notes"]["derived_from_case_id"] = template["case_id"]
    cloned["notes"]["expansion_family"] = task_family
    return cloned


FAMILY_EXPANSION_MAP: dict[str, dict[str, list[tuple[str, str, str]]]] = {
    "startup_ramp": {
        "nominal": [
            ("heater_stage_1", "process_nominal_tep_envelope_heat_trim_001", "heater ramp nudges the reactor into the operating envelope"),
            ("cooling_stage_1", "process_nominal_tep_envelope_cooling_trim_001", "cooling trim constrains startup overshoot during ramp-up"),
            ("hold_stable", "process_nominal_tep_envelope_hold_stable_001", "startup ramp settles at a stable intermediate plateau"),
            ("balance_hold", "process_nominal_tep_envelope_balance_hold_001", "balanced ramp hold preserves thermal margin"),
            ("hot_start_cooling_boost", "process_nominal_tep_high_heat_cooling_boost_001", "hot-start ramp uses aggressive cooling boost"),
            ("hot_start_recovery", "process_nominal_tep_high_heat_recovery_hold_001", "startup recovery holds the ramp near the safe ceiling"),
            ("disturbance_recovery", "process_nominal_tep_disturbance_recovery_001", "startup disturbance is recovered before steady production"),
            ("disturbance_hold", "process_nominal_tep_disturbance_hold_stable_001", "startup disturbance hold preserves pressure margin"),
        ],
        "unsafe": [
            ("heater_stage_1_overshoot", "process_unsafe_tep_envelope_heat_trim_001", "startup heater ramp overshoots the safe envelope"),
            ("cooling_stage_1_saturation", "process_unsafe_tep_envelope_cooling_trim_001", "startup cooling command saturates beyond the safe range"),
            ("hold_stable_range_violation", "process_unsafe_tep_envelope_hold_stable_001", "hold plateau violates manipulated-variable limits"),
            ("balance_hold_range_violation", "process_unsafe_tep_envelope_balance_hold_001", "balanced startup hold exits the safe envelope"),
            ("hot_start_pressure_a", "process_unsafe_tep_high_heat_cooling_boost_001", "hot-start cooling boost still leads to pressure overshoot"),
            ("hot_start_pressure_b", "process_unsafe_tep_high_heat_recovery_hold_001", "recovery hold fails to arrest startup pressure"),
            ("hot_start_pressure_c", "process_unsafe_tep_high_heat_trim_down_001", "trim-down sequence destabilizes startup pressure"),
            ("hot_start_pressure_d", "process_unsafe_tep_high_heat_balance_release_001", "balance release at startup exceeds safe pressure"),
            ("disturbance_pressure_a", "process_unsafe_tep_disturbance_recovery_001", "startup disturbance amplifies pressure"),
            ("disturbance_pressure_b", "process_unsafe_tep_disturbance_hold_stable_001", "startup hold cannot suppress pressure amplification"),
            ("disturbance_pressure_c", "process_unsafe_tep_disturbance_trim_down_001", "trim-down under disturbance destabilizes startup"),
            ("disturbance_pressure_d", "process_unsafe_tep_disturbance_balanced_relief_001", "balanced relief still exceeds startup safety margin"),
        ],
        "fault": [
            ("heater_stage_1_policy_mismatch", "process_fault_tep_envelope_heat_trim_policy_mismatch_001", "policy mismatch before startup heater ramp"),
            ("cooling_stage_1_timestamp_expired", "process_fault_tep_envelope_cooling_trim_timestamp_expired_001", "expired proof for startup cooling trim"),
            ("hold_stable_sensor_hash_mismatch", "process_fault_tep_envelope_hold_stable_sensor_hash_mismatch_001", "sensor hash mismatch during startup hold"),
            ("balance_hold_sensor_divergence", "process_fault_tep_envelope_balance_hold_sensor_divergence_001", "sensor divergence during balanced startup hold"),
            ("hot_start_lock_denied", "process_fault_tep_high_heat_cooling_boost_lock_denied_001", "lock denied while reserving startup ramp commit"),
            ("hot_start_reverify_hash_mismatch", "process_fault_tep_high_heat_recovery_hold_reverify_hash_mismatch_001", "reverify mismatch before startup recovery commit"),
            ("hot_start_commit_timeout", "process_fault_tep_high_heat_trim_down_commit_timeout_001", "commit timeout during startup trim-down"),
            ("startup_ot_interface_error", "process_fault_tep_disturbance_recovery_ot_interface_error_001", "OT interface failure during startup disturbance recovery"),
        ],
    },
    "cooling_failure_management": {
        "nominal": [
            ("boost_cooling", "process_nominal_tep_high_heat_cooling_boost_001", "cooling management increases valve opening under thermal stress"),
            ("recovery_hold", "process_nominal_tep_high_heat_recovery_hold_001", "cooling management holds the reactor near the safe ceiling"),
            ("trim_down", "process_nominal_tep_high_heat_trim_down_001", "cooling management trims heater output after stress"),
            ("balance_release", "process_nominal_tep_high_heat_balance_release_001", "cooling management coordinates balanced thermal release"),
            ("disturbance_recovery", "process_nominal_tep_disturbance_recovery_001", "cooling management recovers from upset heat load"),
            ("disturbance_hold", "process_nominal_tep_disturbance_hold_stable_001", "cooling management sustains stable operation under load"),
            ("cooling_trim", "process_nominal_tep_envelope_cooling_trim_001", "cooling trim preserves envelope during degraded cooling margin"),
            ("heat_trim_fallback", "process_nominal_tep_envelope_heat_trim_001", "heater fallback helps cooling management remain inside the envelope"),
        ],
        "unsafe": [
            ("boost_cooling_pressure_a", "process_unsafe_tep_high_heat_cooling_boost_001", "cooling failure causes pressure overshoot despite boost"),
            ("recovery_hold_pressure_b", "process_unsafe_tep_high_heat_recovery_hold_001", "cooling failure invalidates recovery hold"),
            ("trim_down_pressure_c", "process_unsafe_tep_high_heat_trim_down_001", "trim-down under cooling failure still violates pressure bound"),
            ("balance_release_pressure_d", "process_unsafe_tep_high_heat_balance_release_001", "balance release collapses under cooling failure"),
            ("disturbance_pressure_a", "process_unsafe_tep_disturbance_recovery_001", "disturbance plus cooling failure amplifies pressure"),
            ("disturbance_pressure_b", "process_unsafe_tep_disturbance_hold_stable_001", "hold strategy cannot contain pressure under cooling failure"),
            ("disturbance_pressure_c", "process_unsafe_tep_disturbance_trim_down_001", "trim-down remains unsafe during cooling failure"),
            ("disturbance_pressure_d", "process_unsafe_tep_disturbance_balanced_relief_001", "balanced relief is insufficient under cooling failure"),
            ("cooling_range_violation", "process_unsafe_tep_envelope_cooling_trim_001", "cooling command itself exits the valid range"),
            ("heater_range_violation", "process_unsafe_tep_envelope_heat_trim_001", "heater fallback exceeds envelope under cooling failure"),
            ("hold_range_violation", "process_unsafe_tep_envelope_hold_stable_001", "hold command drifts beyond safe actuator bounds"),
            ("balance_range_violation", "process_unsafe_tep_envelope_balance_hold_001", "balanced hold becomes unsafe under reduced cooling"),
        ],
        "fault": [
            ("boost_cooling_lock_denied", "process_fault_tep_high_heat_cooling_boost_lock_denied_001", "lock denied while reserving cooling management action"),
            ("recovery_hold_reverify_hash_mismatch", "process_fault_tep_high_heat_recovery_hold_reverify_hash_mismatch_001", "reverify mismatch during cooling recovery"),
            ("trim_down_commit_timeout", "process_fault_tep_high_heat_trim_down_commit_timeout_001", "commit timeout while trimming down after cooling failure"),
            ("balance_release_commit_failed", "process_fault_tep_high_heat_balance_release_commit_failed_recovered_001", "commit failure during cooling balance release"),
            ("cooling_trim_policy_mismatch", "process_fault_tep_envelope_heat_trim_policy_mismatch_001", "policy mismatch on cooling fallback action"),
            ("hold_sensor_hash_mismatch", "process_fault_tep_envelope_hold_stable_sensor_hash_mismatch_001", "sensor hash mismatch during cooling hold"),
            ("disturbance_timestamp_expired", "process_fault_tep_disturbance_trim_down_timestamp_expired_001", "expired proof for disturbance cooling trim"),
            ("cooling_ot_interface_error", "process_fault_tep_disturbance_recovery_ot_interface_error_001", "OT interface failure during cooling-failure recovery"),
        ],
    },
    "pressure_relief_margin": {
        "nominal": [
            ("disturbance_relief", "process_nominal_tep_disturbance_balanced_relief_001", "pressure relief brings the disturbed reactor back to margin"),
            ("disturbance_trim", "process_nominal_tep_disturbance_trim_down_001", "trim-down protects pressure relief margin"),
            ("disturbance_hold", "process_nominal_tep_disturbance_hold_stable_001", "hold strategy preserves pressure relief headroom"),
            ("disturbance_recovery", "process_nominal_tep_disturbance_recovery_001", "recovery sequence restores pressure relief margin"),
            ("high_heat_balance_release", "process_nominal_tep_high_heat_balance_release_001", "high-heat balance release preserves relief margin"),
            ("high_heat_trim_down", "process_nominal_tep_high_heat_trim_down_001", "trim-down after high heat protects relief margin"),
            ("envelope_balance_hold", "process_nominal_tep_envelope_balance_hold_001", "balanced hold keeps pressure relief available"),
            ("envelope_hold_stable", "process_nominal_tep_envelope_hold_stable_001", "stable hold maintains relief margin in the nominal envelope"),
        ],
        "unsafe": [
            ("disturbance_pressure_a", "process_unsafe_tep_disturbance_recovery_001", "pressure relief fails under disturbance recovery"),
            ("disturbance_pressure_b", "process_unsafe_tep_disturbance_hold_stable_001", "hold action cannot preserve relief margin"),
            ("disturbance_pressure_c", "process_unsafe_tep_disturbance_trim_down_001", "trim-down erodes pressure relief margin"),
            ("disturbance_pressure_d", "process_unsafe_tep_disturbance_balanced_relief_001", "balanced relief still exceeds pressure threshold"),
            ("high_heat_pressure_a", "process_unsafe_tep_high_heat_cooling_boost_001", "high-heat relief attempt overshoots pressure"),
            ("high_heat_pressure_b", "process_unsafe_tep_high_heat_recovery_hold_001", "recovery hold fails to protect pressure relief margin"),
            ("high_heat_pressure_c", "process_unsafe_tep_high_heat_trim_down_001", "trim-down under high heat still violates pressure margin"),
            ("high_heat_pressure_d", "process_unsafe_tep_high_heat_balance_release_001", "balance release consumes relief margin under stress"),
            ("envelope_range_a", "process_unsafe_tep_envelope_heat_trim_001", "nominal envelope action loses pressure headroom"),
            ("envelope_range_b", "process_unsafe_tep_envelope_cooling_trim_001", "cooling trim no longer maintains relief margin"),
            ("envelope_range_c", "process_unsafe_tep_envelope_hold_stable_001", "stable hold becomes unsafe with reduced pressure margin"),
            ("envelope_range_d", "process_unsafe_tep_envelope_balance_hold_001", "balanced hold fails to keep relief margin available"),
        ],
        "fault": [
            ("disturbance_policy_mismatch", "process_fault_tep_disturbance_hold_stable_policy_mismatch_001", "policy mismatch before pressure relief hold"),
            ("disturbance_timestamp_expired", "process_fault_tep_disturbance_trim_down_timestamp_expired_001", "expired proof for pressure relief trim"),
            ("disturbance_sensor_hash_mismatch", "process_fault_tep_disturbance_balanced_relief_sensor_hash_mismatch_001", "sensor hash mismatch during pressure relief"),
            ("recovery_ot_interface_error", "process_fault_tep_disturbance_recovery_ot_interface_error_001", "OT interface failure during pressure relief recovery"),
            ("high_heat_lock_denied", "process_fault_tep_high_heat_cooling_boost_lock_denied_001", "lock denied while reserving pressure relief action"),
            ("high_heat_reverify_hash_mismatch", "process_fault_tep_high_heat_recovery_hold_reverify_hash_mismatch_001", "reverify mismatch before relief recovery commit"),
            ("high_heat_commit_timeout", "process_fault_tep_high_heat_trim_down_commit_timeout_001", "commit timeout during pressure relief trim"),
            ("balance_release_commit_failed", "process_fault_tep_high_heat_balance_release_commit_failed_recovered_001", "commit failure while closing pressure relief action"),
        ],
    },
}


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


def _runtime_context(runtime_id: str, shell_role: str) -> dict[str, Any]:
    shell = PROCESS_SHELLS[runtime_id]
    return {
        "runtime_id": runtime_id,
        "runtime_type": shell["runtime_type"],
        "shell_config_ref": _project_rel(PROCESS_SHELL_ROOT / runtime_id / "shell_config.json"),
        "profile_ref": _project_rel(PROCESS_SHELL_ROOT / runtime_id / shell["profile_file"]),
        "shell_role": shell_role,
        "executable_action_subset": "set_heater_output,set_cooling_valve",
        "asset_family": shell["asset_family"],
    }


def _initial_state(runtime_id: str, override: dict[str, Any] | None = None) -> dict[str, Any]:
    shell = PROCESS_SHELLS[runtime_id]
    state = deepcopy(shell["default_initial_state"])
    if override:
        state.update(override)
    state["state_origin"] = "shell_default" if override is None else "case_override"
    return state


def _sequence(*actions: tuple[str, float, int]) -> list[dict[str, Any]]:
    return [
        {"action_type": action_type, "params": {"value": value}, "duration_ms": duration_ms}
        for action_type, value, duration_ms in actions
    ]


NOMINAL_ACTIONS = {
    "nominal_heat_trim": _sequence(("set_heater_output", 32.0, 1400), ("set_cooling_valve", 42.0, 1600)),
    "nominal_cooling_trim": _sequence(("set_cooling_valve", 48.0, 1700), ("set_heater_output", 34.0, 1200)),
    "nominal_hold_stable": _sequence(("set_heater_output", 36.0, 1400), ("set_cooling_valve", 38.0, 1400)),
    "nominal_balance_hold": _sequence(("set_cooling_valve", 45.0, 1000), ("set_heater_output", 33.0, 1400)),
    "high_heat_cooling_boost": _sequence(("set_cooling_valve", 58.0, 1800), ("set_heater_output", 32.0, 1200)),
    "high_heat_recovery_hold": _sequence(("set_heater_output", 35.0, 1500), ("set_cooling_valve", 44.0, 1400)),
    "high_heat_trim_down": _sequence(("set_heater_output", 22.0, 1200), ("set_cooling_valve", 58.0, 1600)),
    "high_heat_balance_release": _sequence(("set_cooling_valve", 52.0, 1500), ("set_heater_output", 18.0, 1200)),
    "disturbance_recovery": _sequence(("set_cooling_valve", 58.0, 1800), ("set_heater_output", 32.0, 1200)),
    "disturbance_hold_stable": _sequence(("set_heater_output", 35.0, 1500), ("set_cooling_valve", 44.0, 1400)),
    "disturbance_trim_down": _sequence(("set_heater_output", 22.0, 1200), ("set_cooling_valve", 58.0, 1600)),
    "disturbance_balanced_relief": _sequence(("set_cooling_valve", 52.0, 1500), ("set_heater_output", 18.0, 1200)),
}

UNSAFE_ACTIONS = {
    "heater_above_limit": _sequence(("set_heater_output", 78.0, 1000)),
    "cooling_above_limit": _sequence(("set_cooling_valve", 112.0, 1000)),
    "heater_below_limit": _sequence(("set_heater_output", -4.0, 900)),
    "cooling_far_above_limit": _sequence(("set_cooling_valve", 118.0, 900)),
    "high_heat_pressure_a": _sequence(("set_cooling_valve", 8.0, 1600), ("set_heater_output", 68.0, 1400)),
    "high_heat_pressure_b": _sequence(("set_heater_output", 66.0, 1800), ("set_cooling_valve", 5.0, 1400)),
    "high_heat_pressure_c": _sequence(("set_heater_output", 70.0, 2200)),
    "high_heat_pressure_d": _sequence(("set_cooling_valve", 10.0, 1600), ("set_heater_output", 67.0, 1400)),
    "disturbance_pressure_a": _sequence(("set_heater_output", 68.0, 3000), ("set_cooling_valve", 5.0, 1200)),
    "disturbance_pressure_b": _sequence(("set_heater_output", 67.0, 3200), ("set_cooling_valve", 4.0, 1300)),
    "disturbance_pressure_c": _sequence(("set_heater_output", 68.0, 2800), ("set_cooling_valve", 2.0, 1600)),
    "disturbance_pressure_d": _sequence(
        ("set_cooling_valve", 6.0, 1200),
        ("set_heater_output", 70.0, 2800),
        ("set_cooling_valve", 0.0, 900),
    ),
}


NOMINAL_SPECS = [
    {
        "case_id": "process_nominal_tep_envelope_heat_trim_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "normal_operating_envelope",
        "source_unit": "normal_operating_envelope::heater_trim",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/README.md"),
        "provenance_note": "TE-style nominal operating envelope translated into a mild heater-trim supervisory command.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_nominal_profile",
        "shell_role": "nominal_heat_adjustment",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "nominal_heat_trim",
        "batch_id": "batch_alpha",
        "action_key": "nominal_heat_trim",
        "unsafe_variant": "heater_above_limit",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "nominal operating envelope preservation via heater trim",
            "selection_reason": "selected in source_task_selection.md as a process nominal envelope motif",
        },
    },
    {
        "case_id": "process_nominal_tep_envelope_cooling_trim_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "normal_operating_envelope",
        "source_unit": "normal_operating_envelope::cooling_trim",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/format.md"),
        "provenance_note": "TE-style nominal envelope translated into a cooling-trim supervisory command.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_nominal_profile",
        "shell_role": "nominal_cooling_adjustment",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "nominal_cooling_trim",
        "batch_id": "batch_alpha",
        "action_key": "nominal_cooling_trim",
        "unsafe_variant": "cooling_above_limit",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "nominal operating envelope preservation via cooling trim",
            "selection_reason": "selected in source_task_selection.md as a process nominal envelope motif",
        },
    },
    {
        "case_id": "process_nominal_tep_envelope_hold_stable_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "normal_operating_envelope",
        "source_unit": "normal_operating_envelope::steady_hold",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/tables/table2.txt"),
        "provenance_note": "TE-style steady operating logic lowered into a hold-stable supervisory sequence.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_nominal_profile",
        "shell_role": "steady_state_hold",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "steady_hold",
        "batch_id": "batch_beta",
        "action_key": "nominal_hold_stable",
        "unsafe_variant": "heater_below_limit",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "steady-state hold inside the safe operating envelope",
            "selection_reason": "selected in source_task_selection.md as a nominal envelope-preservation motif",
        },
    },
    {
        "case_id": "process_nominal_tep_envelope_balance_hold_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "normal_operating_envelope",
        "source_unit": "normal_operating_envelope::balanced_hold",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/TEMEX/README.md"),
        "provenance_note": "TE-style balanced supervisory adjustment lowered into a stable envelope-preservation sequence.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_nominal_profile",
        "shell_role": "steady_state_hold",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "balance_hold",
        "batch_id": "batch_gamma",
        "action_key": "nominal_balance_hold",
        "unsafe_variant": "cooling_far_above_limit",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "balanced supervisory hold under nominal envelope assumptions",
            "selection_reason": "selected in source_task_selection.md as a nominal envelope-preservation motif",
        },
    },
    {
        "case_id": "process_nominal_tep_high_heat_cooling_boost_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "interlock_compatible_recovery",
        "source_unit": "interlock_compatible_recovery::high_heat_cooling_boost",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/te4/README.md"),
        "provenance_note": "TE high-heat rationale lowered into a cooling-boost recovery command near the safe boundary.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_high_heat_profile",
        "shell_role": "nominal_cooling_boost",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "high_heat_cooling_boost",
        "batch_id": "batch_delta",
        "action_key": "high_heat_cooling_boost",
        "unsafe_variant": "high_heat_pressure_a",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "interlock-compatible cooling recovery under high heat stress",
            "selection_reason": "selected in source_task_selection.md as a recovery-style process motif",
        },
    },
    {
        "case_id": "process_nominal_tep_high_heat_recovery_hold_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "interlock_compatible_recovery",
        "source_unit": "interlock_compatible_recovery::high_heat_recovery_hold",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/teest3/README.md"),
        "provenance_note": "TE high-heat recovery logic translated into a hold-stable command under thermal stress.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_high_heat_profile",
        "shell_role": "recovery_hold",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "high_heat_recovery_hold",
        "batch_id": "batch_epsilon",
        "action_key": "high_heat_recovery_hold",
        "unsafe_variant": "high_heat_pressure_b",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "high-heat recovery hold inside interlock-compatible bounds",
            "selection_reason": "selected in source_task_selection.md as a recovery-style process motif",
        },
    },
    {
        "case_id": "process_nominal_tep_high_heat_trim_down_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "manipulated_variable_constraint_compliance",
        "source_unit": "manipulated_variable_constraint_compliance::high_heat_trim_down",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/teest6/README.md"),
        "provenance_note": "TE manipulated-variable stress rationale lowered into a trim-down supervisory command.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_high_heat_profile",
        "shell_role": "nominal_heat_trim_down",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "high_heat_trim_down",
        "batch_id": "batch_zeta",
        "action_key": "high_heat_trim_down",
        "unsafe_variant": "high_heat_pressure_c",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "manipulated-variable trim-down near the thermal boundary",
            "selection_reason": "selected in source_task_selection.md as a manipulated-variable constraint motif",
        },
    },
    {
        "case_id": "process_nominal_tep_high_heat_balance_release_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "manipulated_variable_constraint_compliance",
        "source_unit": "manipulated_variable_constraint_compliance::high_heat_balance_release",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/TEmex_tc/README.md"),
        "provenance_note": "TE manipulated-variable stress rationale translated into a balance-release command near the thermal boundary.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_high_heat_profile",
        "shell_role": "recovery_hold",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "high_heat_balance_release",
        "batch_id": "batch_eta",
        "action_key": "high_heat_balance_release",
        "unsafe_variant": "high_heat_pressure_d",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "balanced manipulated-variable release under high heat stress",
            "selection_reason": "selected in source_task_selection.md as a manipulated-variable constraint motif",
        },
    },
    {
        "case_id": "process_nominal_tep_disturbance_recovery_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "disturbance_inspired_supervision",
        "source_unit": "disturbance_inspired_supervision::disturbance_recovery",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/demos.md"),
        "provenance_note": "TE disturbance rationale translated into a recovery supervisory sequence after an upset-like condition.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_disturbance_profile",
        "shell_role": "disturbance_recovery",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "disturbance_recovery",
        "batch_id": "batch_theta",
        "action_key": "disturbance_recovery",
        "unsafe_variant": "disturbance_pressure_a",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "disturbance-inspired recovery under reduced pressure margin",
            "selection_reason": "selected in source_task_selection.md as a disturbance-inspired supervision motif",
        },
    },
    {
        "case_id": "process_nominal_tep_disturbance_hold_stable_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "disturbance_inspired_supervision",
        "source_unit": "disturbance_inspired_supervision::hold_stable",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/decentralized control strategy/idv1/u.dat"),
        "provenance_note": "TE disturbance-control material translated into a hold-stable supervisory sequence.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_disturbance_profile",
        "shell_role": "stabilization_hold",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "disturbance_hold_stable",
        "batch_id": "batch_iota",
        "action_key": "disturbance_hold_stable",
        "unsafe_variant": "disturbance_pressure_b",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "stabilization hold under disturbance-inspired supervision",
            "selection_reason": "selected in source_task_selection.md as a disturbance-inspired supervision motif",
        },
    },
    {
        "case_id": "process_nominal_tep_disturbance_trim_down_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "interlock_compatible_recovery",
        "source_unit": "interlock_compatible_recovery::disturbance_trim_down",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/decentralized control strategy/idv5/u.dat"),
        "provenance_note": "TE interlock-compatible disturbance recovery lowered into a trim-down supervisory sequence.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_disturbance_profile",
        "shell_role": "pressure_relief",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "disturbance_trim_down",
        "batch_id": "batch_kappa",
        "action_key": "disturbance_trim_down",
        "unsafe_variant": "disturbance_pressure_c",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "trim-down recovery compatible with process interlock logic",
            "selection_reason": "selected in source_task_selection.md as an interlock-compatible recovery motif",
        },
    },
    {
        "case_id": "process_nominal_tep_disturbance_balanced_relief_001",
        "source_id": "tep_process_curated",
        "source_name": "TennesseeEastman",
        "task_family": "interlock_compatible_recovery",
        "source_unit": "interlock_compatible_recovery::balanced_relief",
        "local_ref": _project_rel(BENCHMARK_ROOT / "external_sources/process/tennessee-eastman-reference/nl_mpc/README.md"),
        "provenance_note": "TE recovery/control material lowered into a balanced pressure-relief supervisory sequence.",
        "runtime_normalization": "TE process-control provenance normalized into the public process action subset set_heater_output/set_cooling_valve.",
        "runtime_id": "reactor_disturbance_profile",
        "shell_role": "pressure_relief",
        "cell_id": "reactor_cell_a",
        "station_id": "reactor_vessel_01",
        "mission_phase": "disturbance_balanced_relief",
        "batch_id": "batch_lambda",
        "action_key": "disturbance_balanced_relief",
        "unsafe_variant": "disturbance_pressure_d",
        "source_semantics": {
            "upstream_process_family": "tennessee_eastman",
            "semantic_role": "balanced relief under disturbance pressure stress",
            "selection_reason": "selected in source_task_selection.md as an interlock-compatible recovery motif",
        },
    },
]


def _make_nominal_case(spec: dict[str, Any]) -> dict[str, Any]:
    runtime_id = spec["runtime_id"]
    return {
        "benchmark_release": "process_source_release_v1",
        "benchmark_version": "v1.0",
        "case_id": spec["case_id"],
        "case_group": "nominal",
        "asset_id": "reactor_01",
        "scenario_family": "process_interlock",
        "runtime_context": _runtime_context(runtime_id, spec["shell_role"]),
        "source_benchmark": _source_block(spec),
        "operation_context": {
            "cell_id": spec["cell_id"],
            "station_id": spec["station_id"],
            "mission_phase": spec["mission_phase"],
            "task_family": spec["task_family"],
            "shell_role": spec["shell_role"],
            "batch_id": spec["batch_id"],
            "operator_mode": "autonomous_supervision",
        },
        "initial_state": _initial_state(runtime_id),
        "action_sequence": deepcopy(NOMINAL_ACTIONS[spec["action_key"]]),
        "proof_hints": _base_proof_hints(runtime_id),
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
            "paper_role": "process_nominal_safe",
            "unified_process_envelope": {"temperature": [35.0, 118.0], "pressure": [0.85, 2.35]},
        },
    }


def _make_unsafe_case(base_case: dict[str, Any], variant: str) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["case_group"] = "unsafe"
    case["case_id"] = base_case["case_id"].replace("process_nominal_", "process_unsafe_")
    case["action_sequence"] = deepcopy(UNSAFE_ACTIONS[variant])

    if base_case["runtime_context"]["runtime_id"] == "reactor_nominal_profile":
        simulation_expectation = "range_violation"
        unsafe_family = "manipulated_variable_constraint"
        paper_role = "process_unsafe_actuator_range"
    elif base_case["runtime_context"]["runtime_id"] == "reactor_high_heat_profile":
        simulation_expectation = "pressure_overshoot"
        unsafe_family = "thermal_overshoot"
        paper_role = "process_unsafe_high_heat"
    else:
        simulation_expectation = "pressure_amplification"
        unsafe_family = "disturbance_pressure_amplification"
        paper_role = "process_unsafe_disturbance"

    case["proof_hints"]["simulation_expectation"] = simulation_expectation
    case["label"] = {
        "expected_final_status": "UNSAFE",
        "expected_stop_stage": "SAFETY_UNSAFE",
        "expected_reason_code": "SAFETY_UNSAFE",
    }
    case["operation_context"]["mission_phase"] = f"{base_case['operation_context']['mission_phase']}_unsafe"
    case["operation_context"]["unsafe_family"] = unsafe_family
    case["notes"] = {
        "is_counterfactual": True,
        "derived_from_case_id": base_case["case_id"],
        "mutation_rule": variant,
        "qc_status": "drafted_from_frozen_source",
        "paper_role": paper_role,
    }
    return case


def _make_fault_case(base_case: dict[str, Any], fault_spec: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base_case)
    case["case_group"] = "fault"
    case["case_id"] = (
        base_case["case_id"].replace("process_nominal_", "process_fault_").replace("_001", f"_{fault_spec['suffix']}_001")
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
        "paper_role": f"process_fault_{fault_spec['suffix']}",
    }
    return case


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    valid_final_stage = {
        "COMMITTED": {"COMMIT_ACK"},
        "UNSAFE": {"SAFETY_UNSAFE"},
        "REJECTED": {"INTEGRITY_REJECTED"},
        "ABORTED": {"PREPARE_LOCK_DENIED", "REVERIFY_FAILED", "COMMIT_TIMEOUT", "COMMIT_FAILED"},
        "ERROR": {"COMMIT_ERROR"},
    }
    for case in cases:
        assert case["scenario_family"] == "process_interlock"
        assert case["asset_id"] == "reactor_01"
        assert case["action_sequence"]
        assert all(action["action_type"] in {"set_heater_output", "set_cooling_valve"} for action in case["action_sequence"])
        assert case["label"]["expected_stop_stage"] in valid_final_stage[case["label"]["expected_final_status"]]
        source_ref = PROJECT_ROOT / case["source_benchmark"]["local_ref"]
        assert source_ref.exists(), f"Missing source ref for {case['case_id']}: {source_ref}"
        shell_ref = PROJECT_ROOT / case["runtime_context"]["shell_config_ref"]
        assert shell_ref.exists(), f"Missing shell ref for {case['case_id']}: {shell_ref}"
        profile_ref = PROJECT_ROOT / case["runtime_context"]["profile_ref"]
        assert profile_ref.exists(), f"Missing profile ref for {case['case_id']}: {profile_ref}"


def _build_manifest(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]]) -> dict[str, Any]:
    all_cases = nominal + unsafe + fault
    outcome_counts = Counter(case["label"]["expected_final_status"] for case in all_cases)
    stop_stage_counts = Counter(case["label"]["expected_stop_stage"] for case in all_cases)
    unsafe_family_counts = Counter(case["operation_context"].get("unsafe_family") for case in unsafe)
    return {
        "release_id": "process_source_release_v2",
        "benchmark_scope": "process_only",
        "benchmark_version": "v2.0",
        "release_date": str(date.today()),
        "generator_script": _project_rel(Path(__file__)),
        "derived_from_release": "process_source_release_v1",
        "case_counts": {
            "nominal": len(nominal),
            "unsafe": len(unsafe),
            "fault": len(fault),
            "total": len(all_cases),
        },
        "case_counts_by_source": dict(Counter(case["source_benchmark"]["source_id"] for case in all_cases)),
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in all_cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in all_cases)),
        "case_counts_by_expected_status": dict(outcome_counts),
        "case_counts_by_stop_stage": dict(stop_stage_counts),
        "unsafe_case_counts_by_family": dict(unsafe_family_counts),
        "covered_source_families": sorted({case["source_benchmark"]["task_family"] for case in all_cases}),
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
        "normalization_rule": "All process cases are lowered to set_heater_output/set_cooling_valve and executed against canonical process profiles.",
        "notes": [
            "This release preserves the validated v1 process benchmark and adds startup_ramp, cooling_failure_management, and pressure_relief_margin families.",
            "The Tennessee Eastman reference tree remains a frozen provenance anchor rather than a raw copied classification dataset.",
            "The release is outcome-complete for process benchmark drafting: committed, unsafe, rejected, aborted, and infrastructure-error paths are all represented.",
        ],
    }


def _build_qc_report(nominal: list[dict[str, Any]], unsafe: list[dict[str, Any]], fault: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# Process Source Release v2 QC Report",
        "",
        f"Release date: `{manifest['release_date']}`",
        "",
        "## Scope",
        "",
        "- Release type: `process_only`",
        "- Base release: `process_source_release_v1`",
        "- Added families: `startup_ramp`, `cooling_failure_management`, `pressure_relief_margin`",
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
        "- Covered runtime profiles: `reactor_nominal_profile`, `reactor_high_heat_profile`, `reactor_disturbance_profile`",
        "- Outcome-complete release artifact: `all_cases.json`",
        "",
        "## Consistency checks",
        "",
        "- All cases use `scenario_family = process_interlock`.",
        "- All cases lower to the public process action subset `set_heater_output` / `set_cooling_valve`.",
        "- All source references exist in the frozen local Tennessee Eastman reference acquisition target.",
        "- All process profile references exist in the implemented scene pack.",
        "- All label triplets satisfy the frozen label taxonomy.",
        "",
        "## Expansion families",
        "",
        "- `startup_ramp`: staged startup stabilization and ramp overshoot counterfactuals.",
        "- `cooling_failure_management`: high-heat cooling recovery and degraded-cooling supervision motifs.",
        "- `pressure_relief_margin`: disturbance and relief-margin preservation motifs.",
        "",
        "## Fault mutation policy",
        "",
        "- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`",
        "- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`",
        "- Infrastructure faults: `ot_interface_error`",
        "",
        "## Notes for the paper",
        "",
        "- The Tennessee Eastman tree is used as a public process-control provenance anchor, not as a raw time-series classification benchmark.",
        f"- This release is aligned to benchmark policy version `{BENCHMARK_POLICY_VERSION}`.",
        "- The process benchmark is intended to evaluate envelope preservation, startup/cooling/relief supervision, and fault-aware execution assurance through the full PCAG stack.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _build_expanded_cases(source_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    role_by_group = {
        "nominal": "process_nominal_safe",
        "unsafe": "process_unsafe_counterfactual",
        "fault": "process_fault_expanded",
    }
    for family, groups in FAMILY_EXPANSION_MAP.items():
        for group, entries in groups.items():
            prefix = {"nominal": "process_nominal_tep_", "unsafe": "process_unsafe_tep_", "fault": "process_fault_tep_"}[group]
            for slug, source_case_id, semantic_role in entries:
                expanded.append(
                    _clone_case(
                        source_index[source_case_id],
                        case_id=f"{prefix}{family}_{slug}_001",
                        task_family=family,
                        mission_phase=slug,
                        semantic_role=semantic_role,
                        qc_role=role_by_group[group],
                    )
                )
    return expanded


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    base_cases = [_upgrade_case(case) for case in _load_json(V1_ALL_CASES_PATH)]
    source_index = {case["case_id"]: case for case in base_cases}
    expanded_cases = _build_expanded_cases(source_index)
    all_cases = base_cases + expanded_cases

    _validate_cases(all_cases)

    nominal_cases = [case for case in all_cases if case["case_group"] == "nominal"]
    unsafe_cases = [case for case in all_cases if case["case_group"] == "unsafe"]
    fault_cases = [case for case in all_cases if case["case_group"] == "fault"]

    manifest = _build_manifest(nominal_cases, unsafe_cases, fault_cases)
    qc_report = _build_qc_report(nominal_cases, unsafe_cases, fault_cases, manifest)

    _dump_json(RELEASE_DIR / "nominal_dataset.json", nominal_cases)
    _dump_json(RELEASE_DIR / "unsafe_dataset.json", unsafe_cases)
    _dump_json(RELEASE_DIR / "fault_dataset.json", fault_cases)
    _dump_json(RELEASE_DIR / "all_cases.json", all_cases)
    _dump_json(RELEASE_DIR / "dataset_manifest.json", manifest)
    (RELEASE_DIR / "qc_report.md").write_text(qc_report, encoding="utf-8")

    print(f"Wrote process benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
