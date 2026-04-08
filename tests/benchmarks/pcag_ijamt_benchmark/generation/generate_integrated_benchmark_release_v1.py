from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
POLICY_DIR = BENCHMARK_ROOT / "policies"
if str(POLICY_DIR) not in sys.path:
    sys.path.insert(0, str(POLICY_DIR))

from build_pcag_benchmark_policy_v1 import UNIFIED_POLICY_PROFILE, UNIFIED_POLICY_VERSION


RELEASE_DIR = BENCHMARK_ROOT / "releases" / "integrated_benchmark_release_v1"

SOURCE_RELEASES = {
    "robot": BENCHMARK_ROOT / "releases" / "robot_source_release_v1" / "all_cases.json",
    "agv": BENCHMARK_ROOT / "releases" / "agv_source_release_v2" / "all_cases.json",
    "process": BENCHMARK_ROOT / "releases" / "process_source_release_v1" / "all_cases.json",
}
EXECUTION_RELEASES = {
    "robot": BENCHMARK_ROOT / "releases" / "robot_source_release_v1" / "pcag_execution_dataset.json",
    "agv": BENCHMARK_ROOT / "releases" / "agv_source_release_v2" / "pcag_execution_dataset.json",
    "process": BENCHMARK_ROOT / "releases" / "process_source_release_v1" / "pcag_execution_dataset.json",
}

OUTPUT_ALL_CASES_PATH = RELEASE_DIR / "all_cases.json"
OUTPUT_SOURCE_MANIFEST_PATH = RELEASE_DIR / "dataset_manifest.json"
OUTPUT_EXECUTION_DATASET_PATH = RELEASE_DIR / "pcag_execution_dataset.json"
OUTPUT_EXECUTION_MANIFEST_PATH = RELEASE_DIR / "pcag_execution_manifest.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_execution_case(case: dict[str, Any], *, source_execution_release: str) -> dict[str, Any]:
    normalized = deepcopy(case)
    proof = normalized.setdefault("proof", {})
    fault_injection = normalized.get("fault_injection") or {}
    is_policy_mismatch_fault = (
        isinstance(fault_injection, dict) and fault_injection.get("fault_family") == "policy_mismatch"
    )

    # Keep explicit mismatched policy ids intact for integrity policy-mismatch
    # faults. All other cases are normalized to the unified benchmark policy.
    proof["policy_version_mode"] = "explicit"
    if not is_policy_mismatch_fault:
        proof["policy_version_id"] = UNIFIED_POLICY_VERSION
    proof["proof_origin"] = "pcag_integrated_execution_release_v1"

    proof_hints = proof.setdefault("proof_hints", {})
    proof_hints["policy_profile"] = UNIFIED_POLICY_PROFILE
    if not is_policy_mismatch_fault:
        proof_hints["policy_version_id"] = UNIFIED_POLICY_VERSION

    readiness = normalized.setdefault("readiness", {})
    readiness["benchmark_policy_profile"] = UNIFIED_POLICY_PROFILE

    notes = normalized.get("notes")
    if isinstance(notes, dict):
        notes["integrated_source_execution_release"] = source_execution_release
    else:
        normalized["notes"] = {"integrated_source_execution_release": source_execution_release}

    return normalized


def _merge_libraries(base: dict[str, dict[str, Any]], incoming: dict[str, dict[str, Any]]) -> None:
    for group, entries in incoming.items():
        target = base.setdefault(group, {})
        overlap = set(target).intersection(entries)
        if overlap:
            raise ValueError(f"Library key collision in group '{group}': {sorted(overlap)}")
        target.update(deepcopy(entries))


def _build_source_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for source_name, path in SOURCE_RELEASES.items():
        loaded_cases = _load_json(path)
        for case in loaded_cases:
            normalized = deepcopy(case)
            notes = normalized.get("notes")
            if isinstance(notes, dict):
                notes["integrated_source_release"] = source_name
            else:
                normalized["notes"] = {"integrated_source_release": source_name}
            cases.append(normalized)

    manifest = {
        "release_id": "integrated_benchmark_release_v1",
        "benchmark_version": "v1.0",
        "source_releases": {
            key: str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            for key, path in SOURCE_RELEASES.items()
        },
        "case_counts": {
            "total": len(cases),
            "nominal": sum(1 for case in cases if case.get("case_group") == "nominal"),
            "unsafe": sum(1 for case in cases if case.get("case_group") == "unsafe"),
            "fault": sum(1 for case in cases if case.get("case_group") == "fault"),
        },
        "case_counts_by_asset": dict(Counter(case.get("asset_id") for case in cases)),
        "case_counts_by_scenario_family": dict(Counter(case.get("scenario_family") for case in cases)),
        "case_counts_by_expected_status": dict(
            Counter((case.get("label") or {}).get("expected_final_status") for case in cases)
        ),
        "case_counts_by_source_release": dict(
            Counter(((case.get("notes") or {}).get("integrated_source_release")) for case in cases)
        ),
        "policy_profile": UNIFIED_POLICY_PROFILE,
        "policy_version_id": UNIFIED_POLICY_VERSION,
        "notes": [
            "This source-level integrated release is a non-destructive merge of the validated robot, AGV v2, and process source releases.",
            "Per-case provenance and source release identity are preserved inside each case.",
        ],
    }
    return cases, manifest


def _build_execution_dataset() -> tuple[dict[str, Any], dict[str, Any]]:
    merged_cases: list[dict[str, Any]] = []
    merged_libraries: dict[str, dict[str, Any]] = {}

    for source_name, path in EXECUTION_RELEASES.items():
        dataset = _load_json(path)
        _merge_libraries(merged_libraries, dataset.get("libraries", {}))
        for case in dataset.get("cases", []):
            merged_cases.append(_normalize_execution_case(case, source_execution_release=source_name))

    dataset = {
        "meta": {
            "name": "pcag-integrated-execution-dataset-v1",
            "benchmark_release": "integrated_benchmark_release_v1",
            "benchmark_version": "v1.0",
            "policy_profile": UNIFIED_POLICY_PROFILE,
            "policy_version_id": UNIFIED_POLICY_VERSION,
            "source_execution_releases": {
                key: str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                for key, path in EXECUTION_RELEASES.items()
            },
        },
        "defaults": {
            "headers": {"X-API-Key": "pcag-agent-key-001"},
            "proof": {
                "schema_version": "1.0",
                "policy_version_mode": "explicit",
                "policy_version_id": UNIFIED_POLICY_VERSION,
                "sensor_reliability_index": 0.95,
                "proof_origin": "pcag_integrated_execution_release_v1",
            },
        },
        "libraries": merged_libraries,
        "cases": merged_cases,
    }

    manifest = {
        "release_id": "pcag_integrated_execution_release_v1",
        "benchmark_version": "v1.0",
        "benchmark_scope": "robot_agv_process_integrated",
        "generator_script": str(Path(__file__).relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "policy_profile": UNIFIED_POLICY_PROFILE,
        "policy_version_id": UNIFIED_POLICY_VERSION,
        "derived_from_execution_releases": {
            key: str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            for key, path in EXECUTION_RELEASES.items()
        },
        "case_counts": {
            "total": len(merged_cases),
            "nominal": sum(1 for case in merged_cases if case.get("case_group") == "nominal"),
            "unsafe": sum(1 for case in merged_cases if case.get("case_group") == "unsafe"),
            "fault": sum(1 for case in merged_cases if case.get("case_group") == "fault"),
        },
        "case_counts_by_expected_status": dict(Counter(case["expected"]["status"] for case in merged_cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in merged_cases)),
        "case_counts_by_asset": dict(Counter(case["asset_id"] for case in merged_cases)),
        "case_counts_by_scenario_family": dict(Counter(case["scenario_family"] for case in merged_cases)),
        "libraries": {
            group: len(entries) for group, entries in merged_libraries.items()
        },
        "notes": [
            "This integrated execution dataset merges the validated robot v1, AGV v2, and process v1 execution datasets.",
            "Every case now references the unified benchmark policy version so asset switching no longer requires policy reseeding.",
            "Integrity policy-mismatch fault cases intentionally preserve their mismatched explicit policy version ids.",
            "Per-case runtime preload targets remain intact and are still driven entirely by dataset data rather than scenario-specific PCAG branching.",
        ],
    }
    return dataset, manifest


def main() -> None:
    source_cases, source_manifest = _build_source_cases()
    execution_dataset, execution_manifest = _build_execution_dataset()

    _dump_json(OUTPUT_ALL_CASES_PATH, source_cases)
    _dump_json(OUTPUT_SOURCE_MANIFEST_PATH, source_manifest)
    _dump_json(OUTPUT_EXECUTION_DATASET_PATH, execution_dataset)
    _dump_json(OUTPUT_EXECUTION_MANIFEST_PATH, execution_manifest)

    print(f"Wrote integrated source cases to: {OUTPUT_ALL_CASES_PATH}")
    print(f"Wrote integrated source manifest to: {OUTPUT_SOURCE_MANIFEST_PATH}")
    print(f"Wrote integrated execution dataset to: {OUTPUT_EXECUTION_DATASET_PATH}")
    print(f"Wrote integrated execution manifest to: {OUTPUT_EXECUTION_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
