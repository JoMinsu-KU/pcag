from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
SOURCE_RELEASE_ID = "robot_source_release_v1"
EXECUTION_RELEASE_ID = "robot_pcag_execution_release_v1"
EXECUTION_DATASET_NAME = "robot-pcag-execution-dataset-v1"
EXECUTION_VERSION = "1.0"
EXECUTION_DESCRIPTION = (
    "Gateway-facing robot execution dataset derived from the frozen IsaacLab/MimicGen "
    f"{SOURCE_RELEASE_ID} all_cases.json."
)
PROOF_ORIGIN = EXECUTION_RELEASE_ID
GENERATOR_SCRIPT = str(Path(__file__).relative_to(PROJECT_ROOT)).replace("\\", "/")

SOURCE_RELEASE_DIR = BENCHMARK_ROOT / "releases" / SOURCE_RELEASE_ID
SOURCE_ALL_CASES_PATH = SOURCE_RELEASE_DIR / "all_cases.json"

OUTPUT_DATASET_PATH = SOURCE_RELEASE_DIR / "pcag_execution_dataset.json"
OUTPUT_MANIFEST_PATH = SOURCE_RELEASE_DIR / "pcag_execution_manifest.json"
OUTPUT_QC_PATH = SOURCE_RELEASE_DIR / "pcag_execution_qc.md"

HASH_MISMATCH_VALUE = "f" * 64
BENCHMARK_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
BENCHMARK_POLICY_PROFILE = "pcag_benchmark_v1"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_sensor_snapshot(initial_state: dict[str, Any], *, divergent: bool = False) -> dict[str, Any]:
    joint_positions = list(initial_state.get("joint_positions", []))
    joint_velocities = list(initial_state.get("joint_velocities", []))
    joint_efforts = [0.0 for _ in joint_positions]

    if divergent and len(joint_positions) >= 4:
        joint_positions[1] = round(joint_positions[1] + 0.82, 5)
        joint_positions[3] = round(joint_positions[3] + 0.47, 5)

    snapshot: dict[str, Any] = {
        "joint_positions": joint_positions,
        "joint_velocities": joint_velocities,
        "joint_efforts": joint_efforts,
    }

    for index, value in enumerate(joint_positions):
        if index < 7:
            snapshot[f"joint_{index}"] = value
        elif index == 7:
            snapshot["finger_joint_0"] = value
        elif index == 8:
            snapshot["finger_joint_1"] = value

    for index, value in enumerate(joint_velocities):
        if index < 7:
            snapshot[f"joint_{index}_velocity"] = value
        elif index == 7:
            snapshot["finger_joint_0_velocity"] = value
        elif index == 8:
            snapshot["finger_joint_1_velocity"] = value

    for index, value in enumerate(joint_efforts):
        if index < 7:
            snapshot[f"joint_{index}_effort"] = value
        elif index == 7:
            snapshot["finger_joint_0_force"] = value
        elif index == 8:
            snapshot["finger_joint_1_force"] = value

    return snapshot


def _expected_evidence_stages(case: dict[str, Any]) -> list[str]:
    stage = case["label"]["expected_stop_stage"]
    base = ["RECEIVED", "SCHEMA_VALIDATED"]

    if stage == "COMMIT_ACK":
        return base + [
            "INTEGRITY_PASSED",
            "SAFETY_PASSED",
            "PREPARE_LOCK_GRANTED",
            "REVERIFY_PASSED",
            "COMMIT_ACK",
        ]
    if stage == "SAFETY_UNSAFE":
        return base + ["INTEGRITY_PASSED", "SAFETY_UNSAFE"]
    if stage == "INTEGRITY_REJECTED":
        return base + ["INTEGRITY_REJECTED"]
    if stage == "PREPARE_LOCK_DENIED":
        return base + ["INTEGRITY_PASSED", "SAFETY_PASSED", "PREPARE_LOCK_DENIED"]
    if stage == "REVERIFY_FAILED":
        return base + ["INTEGRITY_PASSED", "SAFETY_PASSED", "PREPARE_LOCK_GRANTED", "REVERIFY_FAILED"]
    if stage in {"COMMIT_TIMEOUT", "COMMIT_FAILED", "COMMIT_ERROR"}:
        return base + [
            "INTEGRITY_PASSED",
            "SAFETY_PASSED",
            "PREPARE_LOCK_GRANTED",
            "REVERIFY_PASSED",
            stage,
        ]
    raise ValueError(f"Unsupported stop stage: {stage}")


def _build_expected(case: dict[str, Any]) -> dict[str, Any]:
    label = case["label"]
    status = label["expected_final_status"]
    expected: dict[str, Any] = {
        "http_status": 200,
        "status": status,
        "reason_code": label["expected_reason_code"],
        "response_has_evidence_ref": status == "COMMITTED",
        "evidence_required": True,
        "evidence_chain_valid": True,
        "evidence_stages_exact": _expected_evidence_stages(case),
    }
    return expected


def _build_module_expectations(case: dict[str, Any]) -> dict[str, Any]:
    status = case["label"]["expected_final_status"]
    simulation_hint = case.get("proof_hints", {}).get("simulation_expectation")
    consensus_verdict = None
    if status == "COMMITTED":
        consensus_verdict = "SAFE"
    elif status == "UNSAFE":
        consensus_verdict = "UNSAFE"

    return {
        "rules_verdict": None,
        "cbf_verdict": None,
        "simulation_verdict": simulation_hint,
        "consensus_verdict": consensus_verdict,
    }


def _build_additional_requirements(case: dict[str, Any]) -> list[str]:
    requirements = [
        "generic_runtime_context_transport",
        "generic_runtime_preload",
        "generic_sensor_alignment",
    ]
    fault_injection = case.get("fault_injection") or {}
    proof_hints = case.get("proof_hints") or {}

    if proof_hints.get("sensor_divergence_strategy") == "beyond_threshold":
        requirements.append("benchmark_policy_sensor_divergence_thresholds")
    if fault_injection.get("layer") in {"transaction", "infrastructure"}:
        requirements.append("generic_fault_injection_hook")

    return requirements


def _description(case: dict[str, Any]) -> str:
    source = case["source_benchmark"]
    label = case["label"]
    runtime_role = case["runtime_context"]["shell_role"]
    return (
        f"{source['source_name']} {source['task_family']} provenance normalized into "
        f"{case['runtime_context']['runtime_id']} ({runtime_role}); expected final PCAG outcome "
        f"{label['expected_final_status']} at {label['expected_stop_stage']}."
    )


def _build_case_entry(
    case: dict[str, Any],
    action_ref: str,
    runtime_ref: str,
    initial_state_ref: str,
    sensor_snapshot_ref: str | None,
) -> dict[str, Any]:
    proof_hints = case.get("proof_hints") or {}
    timestamp_expectation = proof_hints.get("timestamp_expectation", "fresh")
    timestamp_offset_ms = 0
    if timestamp_expectation == "expired":
        timestamp_offset_ms = -10000
    elif timestamp_expectation == "future":
        timestamp_offset_ms = 12000

    sensor_hash_strategy = proof_hints.get("sensor_hash_strategy", "matching")
    sensor_hash_mode = "latest" if sensor_hash_strategy == "matching" else "explicit"

    sensor_snapshot_strategy = proof_hints.get("sensor_divergence_strategy", "none")
    sensor_snapshot_mode = "override" if sensor_snapshot_strategy == "beyond_threshold" else "latest"

    proof_block: dict[str, Any] = {
        "schema_version": "1.0",
        "policy_version_mode": "explicit",
        "policy_version_id": proof_hints.get("policy_version_id", BENCHMARK_POLICY_VERSION),
        "timestamp_offset_ms": timestamp_offset_ms,
        "sensor_hash_mode": sensor_hash_mode,
        "sensor_snapshot_mode": sensor_snapshot_mode,
        "sensor_reliability_index": 0.95,
        "action_sequence_ref": action_ref,
        "safety_verification_summary": {
            "benchmark_release": case["benchmark_release"],
            "benchmark_version": case["benchmark_version"],
            "benchmark_case_id": case["case_id"],
            "case_group": case["case_group"],
            "expected_final_status": case["label"]["expected_final_status"],
        },
        "agent_id": "ijamt-benchmark-runner",
        "intent_id": case["case_id"],
        "proof_origin": PROOF_ORIGIN,
        "benchmark_case_id": case["case_id"],
        "runtime_context": case["runtime_context"],
        "proof_hints": proof_hints,
    }

    if sensor_hash_mode == "explicit":
        proof_block["sensor_snapshot_hash"] = HASH_MISMATCH_VALUE

    if sensor_snapshot_ref is not None:
        proof_block["sensor_snapshot_ref"] = sensor_snapshot_ref

    if case.get("fault_injection") is not None:
        proof_block["fault_injection"] = case["fault_injection"]

    return {
        "case_id": case["case_id"],
        "description": _description(case),
        "source_case_ref": f"all_cases.json#{case['case_id']}",
        "case_group": case["case_group"],
        "asset_id": case["asset_id"],
        "scenario_family": case["scenario_family"],
        "source_benchmark": case["source_benchmark"],
        "operation_context": case["operation_context"],
        "runtime": {
            "runtime_context_ref": runtime_ref,
            "initial_state_ref": initial_state_ref,
            "preload_required": True,
            "preload_mode": "shell_and_initial_state",
            "sensor_alignment_mode": "latest_after_preload",
        },
        "proof": proof_block,
        "fault_injection": case.get("fault_injection"),
        "label": case["label"],
        "expected": _build_expected(case),
        "module_expectations": _build_module_expectations(case),
        "readiness": {
            "generic_integration_requirements": _build_additional_requirements(case),
            "benchmark_policy_profile": proof_hints.get("policy_profile", BENCHMARK_POLICY_PROFILE),
            "notes": (
                "Derived from frozen all_cases.json; intended to be executed through the full PCAG "
                "pipeline without scenario-specific branching."
            ),
        },
        "notes": case.get("notes"),
    }


def _manifest(dataset: dict[str, Any]) -> dict[str, Any]:
    cases = dataset["cases"]
    requirement_counts = Counter()
    for case in cases:
        requirement_counts.update(case["readiness"]["generic_integration_requirements"])

    return {
        "release_id": EXECUTION_RELEASE_ID,
        "derived_from_release": SOURCE_RELEASE_ID,
        "source_entrypoint": "all_cases.json",
        "benchmark_scope": "robot_only",
        "benchmark_version": f"v{EXECUTION_VERSION}",
        "generator_script": GENERATOR_SCRIPT,
        "case_counts": {
            "nominal": sum(1 for case in cases if case["case_group"] == "nominal"),
            "unsafe": sum(1 for case in cases if case["case_group"] == "unsafe"),
            "fault": sum(1 for case in cases if case["case_group"] == "fault"),
            "total": len(cases),
        },
        "case_counts_by_expected_status": dict(Counter(case["expected"]["status"] for case in cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in cases)),
        "case_counts_by_runtime": dict(Counter(case["proof"]["runtime_context"]["runtime_id"] for case in cases)),
        "case_counts_by_source": dict(Counter(case["source_benchmark"]["source_id"] for case in cases)),
        "additional_requirement_counts": dict(requirement_counts),
        "libraries": {
            "action_sequences": len(dataset["libraries"]["action_sequences"]),
            "runtime_contexts": len(dataset["libraries"]["runtime_contexts"]),
            "initial_states": len(dataset["libraries"]["initial_states"]),
            "sensor_snapshots": len(dataset["libraries"]["sensor_snapshots"]),
        },
        "notes": [
            f"This execution dataset is derived directly from {SOURCE_RELEASE_ID}/all_cases.json.",
            "It preserves frozen provenance while reshaping each case into a Gateway-facing request template plus runtime preload instructions.",
            "The dataset is intentionally generic: all additional requirements are generic runtime or benchmark hooks, not scenario-specific PCAG branches.",
        ],
    }


def _qc_report(dataset: dict[str, Any], manifest: dict[str, Any]) -> str:
    lines = [
        f"# Robot PCAG Execution Dataset v{EXECUTION_VERSION} QC",
        "",
        f"Derived source release: `{manifest['derived_from_release']}`",
        f"Source entrypoint: `{manifest['source_entrypoint']}`",
        "",
        "## Scope",
        "",
        "- Asset scope: `robot_only`",
        "- Purpose: `Gateway-facing execution dataset derived from frozen robot all_cases.json`",
        "- Provenance sources retained: `IsaacLab`, `MimicGen`",
        "",
        "## Counts",
        "",
        f"- Total cases: `{manifest['case_counts']['total']}`",
        f"- Nominal: `{manifest['case_counts']['nominal']}`",
        f"- Unsafe: `{manifest['case_counts']['unsafe']}`",
        f"- Fault: `{manifest['case_counts']['fault']}`",
        f"- Final status distribution: `{', '.join(f'{key}={value}' for key, value in manifest['case_counts_by_expected_status'].items())}`",
        "",
        "## Libraries",
        "",
        f"- Action sequences: `{manifest['libraries']['action_sequences']}`",
        f"- Runtime contexts: `{manifest['libraries']['runtime_contexts']}`",
        f"- Initial states: `{manifest['libraries']['initial_states']}`",
        f"- Sensor snapshots: `{manifest['libraries']['sensor_snapshots']}`",
        "",
        "## Execution-shaping rules",
        "",
        "- All cases keep the frozen final label from `all_cases.json`.",
        "- All cases are reshaped into a Gateway-facing case contract with:",
        "  - runtime preload instructions",
        "  - proof construction hints",
        "  - expected Gateway outcome",
        "- No scenario-specific PCAG branch is introduced by this dataset format.",
        "",
        "## Generic integration requirements observed in this release",
        "",
    ]

    for requirement, count in manifest["additional_requirement_counts"].items():
        lines.append(f"- `{requirement}`: `{count}` cases")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Sensor-divergence fault cases are preserved from the frozen robot source release.",
        f"- This execution dataset is aligned to benchmark policy version `{BENCHMARK_POLICY_VERSION}` and profile hint `{BENCHMARK_POLICY_PROFILE}`.",
        "- Transaction and infrastructure fault cases remain part of the dataset as generic benchmark cases and require generic fault-injection hooks, not scenario-specific logic.",
        "",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    source_cases = _load_json(SOURCE_ALL_CASES_PATH)

    action_sequences: dict[str, Any] = {}
    runtime_contexts: dict[str, Any] = {}
    initial_states: dict[str, Any] = {}
    sensor_snapshots: dict[str, Any] = {}
    cases: list[dict[str, Any]] = []

    for case in source_cases:
        action_ref = case["case_id"]
        runtime_ref = case["runtime_context"]["runtime_id"]
        initial_state_ref = f"{case['case_id']}__initial_state"

        action_sequences[action_ref] = case["action_sequence"]
        runtime_contexts[runtime_ref] = case["runtime_context"]
        initial_states[initial_state_ref] = case["initial_state"]

        sensor_snapshot_ref = None
        if (case.get("proof_hints") or {}).get("sensor_divergence_strategy") == "beyond_threshold":
            sensor_snapshot_ref = f"{case['case_id']}__proof_snapshot"
            sensor_snapshots[sensor_snapshot_ref] = _build_sensor_snapshot(case["initial_state"], divergent=True)

        cases.append(_build_case_entry(case, action_ref, runtime_ref, initial_state_ref, sensor_snapshot_ref))

    dataset = {
        "meta": {
            "name": EXECUTION_DATASET_NAME,
            "version": EXECUTION_VERSION,
            "description": EXECUTION_DESCRIPTION,
            "derived_from_release": SOURCE_RELEASE_ID,
            "derived_from_entrypoint": "all_cases.json",
        },
        "defaults": {
            "headers": {
                "X-API-Key": "pcag-agent-key-001",
            },
            "proof": {
                "schema_version": "1.0",
                "policy_version_mode": "explicit",
                "policy_version_id": BENCHMARK_POLICY_VERSION,
                "sensor_reliability_index": 0.95,
                "proof_origin": PROOF_ORIGIN,
            },
        },
        "libraries": {
            "action_sequences": action_sequences,
            "runtime_contexts": runtime_contexts,
            "initial_states": initial_states,
            "sensor_snapshots": sensor_snapshots,
        },
        "cases": cases,
    }

    manifest = _manifest(dataset)
    qc_report = _qc_report(dataset, manifest)

    _dump_json(OUTPUT_DATASET_PATH, dataset)
    _dump_json(OUTPUT_MANIFEST_PATH, manifest)
    OUTPUT_QC_PATH.write_text(qc_report, encoding="utf-8")

    print(f"Wrote PCAG execution dataset to: {OUTPUT_DATASET_PATH}")


if __name__ == "__main__":
    main()
