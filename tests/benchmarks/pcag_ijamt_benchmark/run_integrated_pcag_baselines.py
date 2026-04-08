"""
Baseline runner for the integrated PCAG benchmark dataset.

This runner intentionally does not modify the Gateway / Safety Cluster / OT
main code. Instead, it reuses the same dataset, preload path, policy fetch,
sensor fetch, and validator implementations from outside the production path.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pcag.apps.ot_interface.executor_manager import ExecutorManager
from pcag.core.models.common import DivergenceThreshold, Rule
from pcag.core.services.cbf_validator import StaticCBFValidator
from pcag.core.services.integrity_service import check_integrity
from pcag.core.services.rules_validator import validate_rules
from pcag.core.utils.config_loader import get_cbf_mappings
from tests.benchmarks.pcag_ijamt_benchmark.run_integrated_pcag_benchmark import (
    DATASET_PATH as DEFAULT_DATASET_PATH,
    GATEWAY_URL,
    OT_URL,
    POLICY_URL,
    RESULTS_DIR,
    SAFETY_URL,
    SENSOR_URL,
    _build_request_body,
    _prepare_case,
    _preload_runtime,
    check_required_services,
    load_dataset,
)

BASELINE_PROFILES_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "baselines"
    / "baseline_profiles.json"
)
BASELINE_RESULTS_DIR = RESULTS_DIR / "baselines"
DEFAULT_CASE_INTERVAL_SECONDS = 0.25


def _preload_with_retry(client: httpx.Client, *, case: dict[str, Any], dataset: dict[str, Any], retries: int = 3, delay_s: float = 2.0) -> dict[str, Any] | None:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return _preload_runtime(client, case=case, dataset=dataset)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay_s)
    if last_exc is not None:
        raise last_exc
    return None


def _load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["baseline_id"]: item for item in payload.get("profiles", [])}


def _fetch_active_policy_version(client: httpx.Client, cache: dict[str, Any]) -> str:
    if "active_policy_version" in cache:
        return cache["active_policy_version"]
    response = client.get(f"{POLICY_URL}/v1/policies/active", timeout=10.0)
    response.raise_for_status()
    cache["active_policy_version"] = response.json()["policy_version_id"]
    return cache["active_policy_version"]


def _fetch_asset_profile(client: httpx.Client, policy_version_id: str, asset_id: str) -> dict[str, Any]:
    response = client.get(f"{POLICY_URL}/v1/policies/{policy_version_id}/assets/{asset_id}", timeout=10.0)
    response.raise_for_status()
    return response.json().get("profile", {})


def _fetch_latest_sensor_snapshot(client: httpx.Client, asset_id: str) -> dict[str, Any]:
    response = client.get(f"{SENSOR_URL}/v1/assets/{asset_id}/snapshots/latest", timeout=20.0)
    response.raise_for_status()
    return response.json()


def _resolve_case_selection(
    dataset: dict[str, Any],
    *,
    case_id: str | None,
    limit: int | None,
    asset_id: str | None,
    scenario_family: str | None,
    case_group: str | None,
) -> list[dict[str, Any]]:
    cases = list(dataset.get("cases", []))
    if case_id:
        selected = [case for case in cases if case.get("case_id") == case_id]
        if not selected:
            raise ValueError(f"Case not found: {case_id}")
        return selected
    if asset_id:
        cases = [case for case in cases if case.get("asset_id") == asset_id]
    if scenario_family:
        cases = [case for case in cases if case.get("scenario_family") == scenario_family]
    if case_group:
        cases = [case for case in cases if case.get("case_group") == case_group]
    if limit is not None:
        cases = cases[:limit]
    return cases


def _build_divergence_thresholds(raw_thresholds: list[dict[str, Any]] | None) -> list[DivergenceThreshold]:
    thresholds: list[DivergenceThreshold] = []
    for item in raw_thresholds or []:
        thresholds.append(DivergenceThreshold(**item))
    return thresholds


def _build_ruleset(ruleset_raw: list[Any]) -> list[Rule | dict[str, Any]]:
    ruleset: list[Rule | dict[str, Any]] = []
    for item in ruleset_raw or []:
        if isinstance(item, dict):
            try:
                ruleset.append(Rule(**item))
            except Exception:
                ruleset.append(copy.deepcopy(item))
        else:
            ruleset.append(item)
    return ruleset


def _fault_enabled(case: dict[str, Any], fault_family: str) -> bool:
    fault_injection = case.get("fault_injection")
    if not isinstance(fault_injection, dict):
        return False
    return fault_injection.get("fault_family") == fault_family


def _force_hash_mismatch(sensor_hash: str) -> str:
    if len(sensor_hash) != 64:
        return "f" * 64
    last = sensor_hash[-1].lower()
    replacement = "0" if last != "0" else "1"
    return sensor_hash[:-1] + replacement


def _semantic_group(expected: dict[str, Any]) -> str:
    status = expected.get("status")
    if status == "COMMITTED":
        return "nominal"
    if status == "UNSAFE":
        return "unsafe"
    if status == "REJECTED":
        return "integrity_fault"
    if status == "ABORTED":
        return "transaction_fault"
    if status == "ERROR":
        return "execution_fault"
    return "unknown"


def _run_integrity(
    *,
    proof_package: dict[str, Any],
    active_policy_version: str,
    latest_sensor: dict[str, Any],
    asset_profile: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    integrity_config = asset_profile.get("integrity", {}) or {}
    proof_snapshot = proof_package.get("sensor_snapshot") or {}
    thresholds = _build_divergence_thresholds(integrity_config.get("sensor_divergence_thresholds"))
    ok, reason = check_integrity(
        proof_policy_version=proof_package["policy_version_id"],
        active_policy_version=active_policy_version,
        proof_timestamp_ms=proof_package["timestamp_ms"],
        current_timestamp_ms=int(time.time() * 1000),
        timestamp_max_age_ms=integrity_config.get("timestamp_max_age_ms", 5000),
        proof_sensor_snapshot=proof_snapshot,
        current_sensor_snapshot=latest_sensor["sensor_snapshot"],
        divergence_thresholds=thresholds if proof_snapshot else [],
        proof_sensor_snapshot_hash=proof_package.get("sensor_snapshot_hash"),
        current_sensor_snapshot_hash=latest_sensor.get("sensor_snapshot_hash"),
    )
    return ok, reason, {
        "policy_version": active_policy_version,
        "sensor_hash": latest_sensor.get("sensor_snapshot_hash"),
        "proof_sensor_hash": proof_package.get("sensor_snapshot_hash"),
        "sensor_hash_match": proof_package.get("sensor_snapshot_hash") == latest_sensor.get("sensor_snapshot_hash"),
    }


def _run_rules(snapshot: dict[str, Any], action_sequence: list[dict[str, Any]], ruleset: list[Rule | dict[str, Any]]) -> dict[str, Any]:
    result = validate_rules(snapshot, action_sequence, ruleset)
    return {"verdict": result.verdict, "details": result.details}


def _run_cbf(
    snapshot: dict[str, Any],
    action_sequence: list[dict[str, Any]],
    ruleset: list[Rule | dict[str, Any]],
) -> dict[str, Any]:
    validator = StaticCBFValidator()
    result = validator.validate_safety(snapshot, action_sequence, ruleset, get_cbf_mappings())
    return {"verdict": result["verdict"], "details": result.get("details", {})}


def _run_safety_http(
    client: httpx.Client,
    *,
    transaction_id: str,
    asset_id: str,
    policy_version_id: str,
    action_sequence: list[dict[str, Any]],
    current_sensor_snapshot: dict[str, Any],
    runtime_context: dict[str, Any] | None,
) -> dict[str, Any]:
    response = client.post(
        f"{SAFETY_URL}/v1/validate",
        json={
            "transaction_id": transaction_id,
            "asset_id": asset_id,
            "policy_version_id": policy_version_id,
            "action_sequence": action_sequence,
            "current_sensor_snapshot": current_sensor_snapshot,
            "runtime_context": runtime_context,
        },
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


def _enabled_validators_safe(results: dict[str, dict[str, Any]], enabled: list[str]) -> tuple[bool, str | None]:
    for key in enabled:
        verdict = results.get(key, {}).get("verdict")
        if verdict != "SAFE":
            return False, key
    return True, None


def _direct_execute(case: dict[str, Any], transaction_id: str, asset_id: str, action_sequence: list[dict[str, Any]]) -> dict[str, Any]:
    if _fault_enabled(case, "ot_interface_error"):
        return {
            "final_status": "ERROR",
            "stop_stage": "COMMIT_ERROR",
            "reason_code": "OT_INTERFACE_ERROR",
            "reason": "Injected benchmark OT interface error",
        }

    executor = ExecutorManager.get_executor(asset_id)

    if _fault_enabled(case, "commit_timeout"):
        safe_state = executor.safe_state(asset_id)
        return {
            "final_status": "ABORTED" if safe_state else "ERROR",
            "stop_stage": "COMMIT_TIMEOUT",
            "reason_code": "COMMIT_TIMEOUT",
            "reason": "Injected benchmark commit timeout",
            "safe_state_executed": safe_state,
        }

    if _fault_enabled(case, "commit_failed_recovered"):
        safe_state = executor.safe_state(asset_id)
        return {
            "final_status": "ABORTED" if safe_state else "ERROR",
            "stop_stage": "COMMIT_FAILED",
            "reason_code": "COMMIT_FAILED",
            "reason": "Injected benchmark recovered commit failure",
            "safe_state_executed": safe_state,
        }

    try:
        success = executor.execute(transaction_id, asset_id, action_sequence)
    except Exception as exc:
        safe_state = executor.safe_state(asset_id)
        return {
            "final_status": "ABORTED" if safe_state else "ERROR",
            "stop_stage": "COMMIT_ERROR",
            "reason_code": "COMMIT_ERROR",
            "reason": str(exc),
            "safe_state_executed": safe_state,
        }

    if success:
        return {
            "final_status": "COMMITTED",
            "stop_stage": "COMMIT_ACK",
            "reason_code": None,
            "reason": None,
        }

    safe_state = executor.safe_state(asset_id)
    return {
        "final_status": "ABORTED" if safe_state else "ERROR",
        "stop_stage": "COMMIT_FAILED",
        "reason_code": "COMMIT_FAILED",
        "reason": getattr(executor, "last_error", None) or "Executor returned unsuccessful result",
        "safe_state_executed": safe_state,
    }


def _prepare_ot(client: httpx.Client, *, case: dict[str, Any], transaction_id: str, asset_id: str, lock_ttl_ms: int) -> dict[str, Any]:
    if _fault_enabled(case, "lock_denied"):
        return {"status": "LOCK_DENIED", "reason": "Injected benchmark lock denial"}
    response = client.post(
        f"{OT_URL}/v1/prepare",
        json={"transaction_id": transaction_id, "asset_id": asset_id, "lock_ttl_ms": lock_ttl_ms},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _abort_ot(client: httpx.Client, *, transaction_id: str, asset_id: str, reason: str) -> dict[str, Any]:
    response = client.post(
        f"{OT_URL}/v1/abort",
        json={"transaction_id": transaction_id, "asset_id": asset_id, "reason": reason},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _commit_ot(
    client: httpx.Client,
    *,
    case: dict[str, Any],
    transaction_id: str,
    asset_id: str,
    action_sequence: list[dict[str, Any]],
) -> dict[str, Any]:
    if _fault_enabled(case, "commit_timeout"):
        return {"status": "TIMEOUT", "reason": "Injected benchmark commit timeout"}
    if _fault_enabled(case, "commit_failed_recovered"):
        return {
            "status": "EXECUTION_FAILED",
            "reason": "Injected benchmark recovered commit failure",
            "safe_state_executed": True,
        }
    if _fault_enabled(case, "ot_interface_error"):
        raise RuntimeError("Injected benchmark OT interface error")
    response = client.post(
        f"{OT_URL}/v1/commit",
        json={"transaction_id": transaction_id, "asset_id": asset_id, "action_sequence": action_sequence},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def _normalize_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["semantic_group"], []).append(result)

    def _rate(items: list[dict[str, Any]], predicate) -> float | None:
        if not items:
            return None
        return round(sum(1 for item in items if predicate(item)) / len(items), 4)

    nominal = grouped.get("nominal", [])
    unsafe = grouped.get("unsafe", [])
    integrity_fault = grouped.get("integrity_fault", [])
    transaction_fault = grouped.get("transaction_fault", [])
    execution_fault = grouped.get("execution_fault", [])

    reverify_fault_cases = [
        item
        for item in results
        if item.get("expected_reason_code") == "REVERIFY_HASH_MISMATCH"
    ]
    latencies = [item["duration_ms"] for item in results if item.get("duration_ms") is not None]
    exact_match_rate = _rate(results, lambda item: item["normalized_final_status"] == item["expected_status"])

    status_counts: dict[str, int] = {}
    for item in results:
        status_counts[item["normalized_final_status"]] = status_counts.get(item["normalized_final_status"], 0) + 1

    return {
        "total_cases": len(results),
        "status_counts": status_counts,
        "exact_match_rate": exact_match_rate,
        "safe_pass_rate": _rate(nominal, lambda item: item["normalized_final_status"] == "COMMITTED"),
        "unsafe_interception_rate": _rate(unsafe, lambda item: item["normalized_final_status"] != "COMMITTED"),
        "unsafe_commit_count": sum(
            1
            for item in results
            if item["semantic_group"] in {"unsafe", "integrity_fault", "transaction_fault", "execution_fault"}
            and item["normalized_final_status"] == "COMMITTED"
        ),
        "integrity_reject_rate": _rate(integrity_fault, lambda item: item["normalized_final_status"] == "REJECTED"),
        "transaction_fault_noncommit_rate": _rate(transaction_fault, lambda item: item["normalized_final_status"] != "COMMITTED"),
        "execution_fault_noncommit_rate": _rate(execution_fault, lambda item: item["normalized_final_status"] != "COMMITTED"),
        "toctou_catch_rate": _rate(reverify_fault_cases, lambda item: item["normalized_final_status"] != "COMMITTED"),
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else None,
        "trace_completeness_rate": _rate(results, lambda item: bool(item.get("stop_stage"))),
    }


def _write_report(payload: dict[str, Any], *, baseline_id: str, output_path: Path | None = None) -> Path:
    BASELINE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    latest_path = BASELINE_RESULTS_DIR / f"{baseline_id.lower()}_latest.json"
    archive_path = BASELINE_RESULTS_DIR / f"{baseline_id.lower()}_{timestamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest_path.write_text(text, encoding="utf-8")
    archive_path.write_text(text, encoding="utf-8")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return output_path
    return latest_path


def _infer_stop_stage_from_evidence(evidence: dict[str, Any] | None) -> str | None:
    if not evidence:
        return None
    events = evidence.get("events", [])
    if not events:
        return None
    return events[-1].get("stage")


def _baseline_b5_from_existing(dataset_path: Path) -> dict[str, Any]:
    latest_path = RESULTS_DIR / "integrated_pcag_benchmark_latest.json"
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    dataset = load_dataset(dataset_path)
    case_index = {case["case_id"]: case for case in dataset.get("cases", [])}
    results: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        case_meta = case_index.get(item["case_id"], {})
        expected = case_meta.get("expected", {})
        expected_status = expected.get("status", item.get("expected_final_status"))
        reason_code = None
        if isinstance(item.get("response_json"), dict):
            reason_code = item["response_json"].get("reason_code")
        results.append(
            {
                "case_id": item["case_id"],
                "asset_id": item["asset_id"],
                "scenario_family": case_meta.get("scenario_family", item.get("scenario_family")),
                "case_group": case_meta.get("case_group"),
                "semantic_group": _semantic_group(expected or {"status": expected_status}),
                "expected_status": expected_status,
                "expected_reason_code": expected.get("reason_code"),
                "normalized_final_status": item.get("response_json", {}).get("status"),
                "stop_stage": _infer_stop_stage_from_evidence(item.get("evidence")),
                "reason_code": reason_code,
                "duration_ms": item.get("duration_ms"),
            }
        )
    metrics = _normalize_metrics(results)
    return {
        "baseline_id": "B5",
        "display_name": "Full PCAG",
        "dataset_path": str(dataset_path),
        "source": str(latest_path),
        "generated_at_ms": int(time.time() * 1000),
        "total_cases": metrics["total_cases"],
        "status_counts": metrics["status_counts"],
        "metrics": metrics,
        "results": results,
    }


def run_case(
    client: httpx.Client,
    *,
    profile: dict[str, Any],
    case: dict[str, Any],
    dataset: dict[str, Any],
    cache: dict[str, Any],
) -> dict[str, Any]:
    prepared_case = _prepare_case(case, dataset)
    preload_result = _preload_with_retry(client, case=prepared_case, dataset=dataset)
    request_body, latest_sensor = _build_request_body(client, case=prepared_case, dataset=dataset, cache=cache)
    proof_package = request_body["proof_package"]
    transaction_id = request_body["transaction_id"]
    asset_id = prepared_case["asset_id"]
    runtime_context = proof_package.get("runtime_context")
    action_sequence = proof_package.get("action_sequence", [])
    expected = prepared_case.get("expected", {})

    started_at = int(time.time() * 1000)
    t0 = time.time()

    active_policy_version = _fetch_active_policy_version(client, cache)
    asset_profile = _fetch_asset_profile(client, active_policy_version, asset_id)
    execution_config = asset_profile.get("execution", {}) or {}
    ruleset = _build_ruleset(asset_profile.get("ruleset", []))

    validators: dict[str, dict[str, Any]] = {}
    consensus_result: dict[str, Any] | None = None
    integrity_details: dict[str, Any] | None = None
    prepare_result: dict[str, Any] | None = None
    commit_result: dict[str, Any] | None = None

    if profile["integrity"]:
        integrity_ok, integrity_reason, integrity_details = _run_integrity(
            proof_package=proof_package,
            active_policy_version=active_policy_version,
            latest_sensor=latest_sensor,
            asset_profile=asset_profile,
        )
        if not integrity_ok:
            return {
                "case_id": prepared_case["case_id"],
                "asset_id": asset_id,
                "scenario_family": prepared_case.get("scenario_family"),
                "case_group": prepared_case.get("case_group"),
                "semantic_group": _semantic_group(expected),
                "expected_status": expected.get("status"),
                "expected_reason_code": expected.get("reason_code"),
                "baseline_id": profile["baseline_id"],
                "display_name": profile["display_name"],
                "started_at_ms": started_at,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "normalized_final_status": "REJECTED",
                "raw_status": "REJECTED",
                "stop_stage": "INTEGRITY_REJECTED",
                "reason_code": integrity_reason,
                "reason": integrity_reason,
                "preload_result": preload_result,
                "integrity_result": integrity_details,
                "validators": validators,
                "consensus_result": consensus_result,
                "prepare_result": prepare_result,
                "commit_result": commit_result,
            }

    if profile["rules"]:
        validators["rules"] = _run_rules(latest_sensor["sensor_snapshot"], action_sequence, ruleset)

    if profile["barrier"]:
        validators["cbf"] = _run_cbf(latest_sensor["sensor_snapshot"], action_sequence, ruleset)

    if profile["simulation"] or profile["consensus"]:
        safety_result = _run_safety_http(
            client,
            transaction_id=transaction_id,
            asset_id=asset_id,
            policy_version_id=active_policy_version,
            action_sequence=action_sequence,
            current_sensor_snapshot=latest_sensor["sensor_snapshot"],
            runtime_context=runtime_context,
        )
        if not validators.get("rules"):
            validators["rules"] = copy.deepcopy(safety_result.get("validators", {}).get("rules", {}))
        if profile["barrier"] and not validators.get("cbf"):
            validators["cbf"] = copy.deepcopy(safety_result.get("validators", {}).get("cbf", {}))
        if profile["simulation"]:
            validators["simulation"] = copy.deepcopy(safety_result.get("validators", {}).get("simulation", {}))
        if profile["consensus"]:
            consensus_result = copy.deepcopy(safety_result.get("consensus_details", {}))
            consensus_verdict = safety_result.get("final_verdict")
        else:
            consensus_verdict = None
    else:
        consensus_verdict = None

    if profile["consensus"]:
        if consensus_verdict != "SAFE":
            return {
                "case_id": prepared_case["case_id"],
                "asset_id": asset_id,
                "scenario_family": prepared_case.get("scenario_family"),
                "case_group": prepared_case.get("case_group"),
                "semantic_group": _semantic_group(expected),
                "expected_status": expected.get("status"),
                "expected_reason_code": expected.get("reason_code"),
                "baseline_id": profile["baseline_id"],
                "display_name": profile["display_name"],
                "started_at_ms": started_at,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "normalized_final_status": "UNSAFE",
                "raw_status": "UNSAFE",
                "stop_stage": "SAFETY_UNSAFE",
                "reason_code": "SAFETY_UNSAFE",
                "reason": "Safety consensus returned UNSAFE",
                "preload_result": preload_result,
                "integrity_result": integrity_details,
                "validators": validators,
                "consensus_result": consensus_result,
                "prepare_result": prepare_result,
                "commit_result": commit_result,
            }
    elif validators:
        enabled = []
        if profile["rules"]:
            enabled.append("rules")
        if profile["barrier"]:
            enabled.append("cbf")
        if profile["simulation"]:
            enabled.append("simulation")
        safe, failing_validator = _enabled_validators_safe(validators, enabled)
        if not safe:
            return {
                "case_id": prepared_case["case_id"],
                "asset_id": asset_id,
                "scenario_family": prepared_case.get("scenario_family"),
                "case_group": prepared_case.get("case_group"),
                "semantic_group": _semantic_group(expected),
                "expected_status": expected.get("status"),
                "expected_reason_code": expected.get("reason_code"),
                "baseline_id": profile["baseline_id"],
                "display_name": profile["display_name"],
                "started_at_ms": started_at,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "normalized_final_status": "UNSAFE",
                "raw_status": "UNSAFE",
                "stop_stage": "SAFETY_UNSAFE",
                "reason_code": "SAFETY_UNSAFE",
                "reason": f"Enabled validator '{failing_validator}' returned {validators.get(failing_validator, {}).get('verdict')}",
                "preload_result": preload_result,
                "integrity_result": integrity_details,
                "validators": validators,
                "consensus_result": consensus_result,
                "prepare_result": prepare_result,
                "commit_result": commit_result,
            }

    if profile["prepare"]:
        prepare_result = _prepare_ot(
            client,
            case=prepared_case,
            transaction_id=transaction_id,
            asset_id=asset_id,
            lock_ttl_ms=execution_config.get("lock_ttl_ms", 5000),
        )
        if prepare_result.get("status") != "LOCK_GRANTED":
            return {
                "case_id": prepared_case["case_id"],
                "asset_id": asset_id,
                "scenario_family": prepared_case.get("scenario_family"),
                "case_group": prepared_case.get("case_group"),
                "semantic_group": _semantic_group(expected),
                "expected_status": expected.get("status"),
                "expected_reason_code": expected.get("reason_code"),
                "baseline_id": profile["baseline_id"],
                "display_name": profile["display_name"],
                "started_at_ms": started_at,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "normalized_final_status": "ABORTED",
                "raw_status": "LOCK_DENIED",
                "stop_stage": "PREPARE_LOCK_DENIED",
                "reason_code": "LOCK_DENIED",
                "reason": prepare_result.get("reason"),
                "preload_result": preload_result,
                "integrity_result": integrity_details,
                "validators": validators,
                "consensus_result": consensus_result,
                "prepare_result": prepare_result,
                "commit_result": commit_result,
            }

        if profile["reverify"]:
            reverify_sensor = _fetch_latest_sensor_snapshot(client, asset_id)
            reverify_hash = reverify_sensor.get("sensor_snapshot_hash")
            current_hash = latest_sensor.get("sensor_snapshot_hash")
            if _fault_enabled(prepared_case, "reverify_hash_mismatch"):
                reverify_hash = _force_hash_mismatch(current_hash or "")
            if reverify_hash != current_hash:
                _abort_ot(
                    client,
                    transaction_id=transaction_id,
                    asset_id=asset_id,
                    reason=f"TOCTOU reverify hash mismatch: original={current_hash}, reverify={reverify_hash}",
                )
                return {
                    "case_id": prepared_case["case_id"],
                    "asset_id": asset_id,
                    "scenario_family": prepared_case.get("scenario_family"),
                    "case_group": prepared_case.get("case_group"),
                    "semantic_group": _semantic_group(expected),
                    "expected_status": expected.get("status"),
                    "expected_reason_code": expected.get("reason_code"),
                    "baseline_id": profile["baseline_id"],
                    "display_name": profile["display_name"],
                    "started_at_ms": started_at,
                    "duration_ms": round((time.time() - t0) * 1000, 2),
                    "normalized_final_status": "ABORTED",
                    "raw_status": "REVERIFY_FAILED",
                    "stop_stage": "REVERIFY_FAILED",
                    "reason_code": "REVERIFY_HASH_MISMATCH",
                    "reason": "Sensor state changed after PREPARE",
                    "preload_result": preload_result,
                    "integrity_result": integrity_details,
                    "validators": validators,
                    "consensus_result": consensus_result,
                    "prepare_result": prepare_result,
                    "commit_result": commit_result,
                }

    if profile["execution_mode"] == "ot_commit":
        try:
            commit_result = _commit_ot(
                client,
                case=prepared_case,
                transaction_id=transaction_id,
                asset_id=asset_id,
                action_sequence=action_sequence,
            )
        except Exception as exc:
            _abort_ot(client, transaction_id=transaction_id, asset_id=asset_id, reason=str(exc))
            return {
                "case_id": prepared_case["case_id"],
                "asset_id": asset_id,
                "scenario_family": prepared_case.get("scenario_family"),
                "case_group": prepared_case.get("case_group"),
                "semantic_group": _semantic_group(expected),
                "expected_status": expected.get("status"),
                "expected_reason_code": expected.get("reason_code"),
                "baseline_id": profile["baseline_id"],
                "display_name": profile["display_name"],
                "started_at_ms": started_at,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "normalized_final_status": "ERROR",
                "raw_status": "COMMIT_ERROR",
                "stop_stage": "COMMIT_ERROR",
                "reason_code": "OT_INTERFACE_ERROR" if _fault_enabled(prepared_case, "ot_interface_error") else "COMMIT_ERROR",
                "reason": str(exc),
                "preload_result": preload_result,
                "integrity_result": integrity_details,
                "validators": validators,
                "consensus_result": consensus_result,
                "prepare_result": prepare_result,
                "commit_result": commit_result,
            }

        commit_status = commit_result.get("status")
        if commit_status == "ACK":
            final_status = "COMMITTED"
            stop_stage = "COMMIT_ACK"
            reason_code = None
        elif commit_status == "TIMEOUT":
            final_status = "ABORTED"
            stop_stage = "COMMIT_TIMEOUT"
            reason_code = "COMMIT_TIMEOUT"
        elif commit_status == "EXECUTION_FAILED":
            final_status = "ABORTED" if commit_result.get("safe_state_executed") else "ERROR"
            stop_stage = "COMMIT_FAILED"
            reason_code = "COMMIT_FAILED"
        else:
            final_status = "ERROR"
            stop_stage = "COMMIT_ERROR"
            reason_code = "COMMIT_ERROR"
    else:
        commit_result = _direct_execute(prepared_case, transaction_id, asset_id, action_sequence)
        final_status = commit_result["final_status"]
        stop_stage = commit_result["stop_stage"]
        reason_code = commit_result["reason_code"]

    return {
        "case_id": prepared_case["case_id"],
        "asset_id": asset_id,
        "scenario_family": prepared_case.get("scenario_family"),
        "case_group": prepared_case.get("case_group"),
        "semantic_group": _semantic_group(expected),
        "expected_status": expected.get("status"),
        "expected_reason_code": expected.get("reason_code"),
        "baseline_id": profile["baseline_id"],
        "display_name": profile["display_name"],
        "started_at_ms": started_at,
        "duration_ms": round((time.time() - t0) * 1000, 2),
        "normalized_final_status": final_status,
        "raw_status": final_status,
        "stop_stage": stop_stage,
        "reason_code": reason_code,
        "reason": commit_result.get("reason") if commit_result else None,
        "preload_result": preload_result,
        "integrity_result": integrity_details,
        "validators": validators,
        "consensus_result": consensus_result,
        "prepare_result": prepare_result,
        "commit_result": commit_result,
    }


def run_baseline(
    *,
    dataset: dict[str, Any],
    profile: dict[str, Any],
    case_id: str | None,
    limit: int | None,
    asset_id: str | None,
    scenario_family: str | None,
    case_group: str | None,
    case_interval_seconds: float,
    stop_on_fail: bool,
) -> dict[str, Any]:
    selected_cases = _resolve_case_selection(
        dataset,
        case_id=case_id,
        limit=limit,
        asset_id=asset_id,
        scenario_family=scenario_family,
        case_group=case_group,
    )
    needs_plc = any(((case.get("runtime") or {}).get("preload_target") == "plc_adapter") for case in selected_cases)
    preflight = check_required_services(needs_plc=needs_plc)
    if not preflight["ok"]:
        raise RuntimeError(f"Required services are not all available: {preflight}")

    cache: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for index, case in enumerate(selected_cases):
            try:
                result = run_case(client, profile=profile, case=case, dataset=dataset, cache=cache)
            except Exception as exc:
                result = {
                    "case_id": case.get("case_id"),
                    "asset_id": case.get("asset_id"),
                    "scenario_family": case.get("scenario_family"),
                    "case_group": case.get("case_group"),
                    "semantic_group": _semantic_group(case.get("expected", {})),
                    "expected_status": (case.get("expected") or {}).get("status"),
                    "expected_reason_code": (case.get("expected") or {}).get("reason_code"),
                    "baseline_id": profile["baseline_id"],
                    "display_name": profile["display_name"],
                    "started_at_ms": int(time.time() * 1000),
                    "duration_ms": None,
                    "normalized_final_status": "ERROR",
                    "raw_status": "ERROR",
                    "stop_stage": "RUNNER_EXCEPTION",
                    "reason_code": "RUNNER_EXCEPTION",
                    "reason": str(exc),
                    "validators": {},
                    "consensus_result": None,
                    "prepare_result": None,
                    "commit_result": None,
                }
            results.append(result)
            print(f"[{profile['baseline_id']}] {result['case_id']} -> {result['normalized_final_status']}")
            if stop_on_fail and result["normalized_final_status"] == "ERROR":
                break
            if case_interval_seconds > 0 and index < len(selected_cases) - 1:
                time.sleep(case_interval_seconds)

    return {
        "baseline_id": profile["baseline_id"],
        "display_name": profile["display_name"],
        "generated_at_ms": int(time.time() * 1000),
        "dataset_path": str(DEFAULT_DATASET_PATH),
        "gateway_url": GATEWAY_URL,
        "safety_url": SAFETY_URL,
        "case_interval_seconds": case_interval_seconds,
        "preflight": preflight,
        "metrics": _normalize_metrics(results),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run integrated PCAG baseline experiments without modifying PCAG main code.")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--baseline-id", type=str, required=True, help="B0, B1, B2, B3, B4, B5, or E1")
    parser.add_argument("--case-id", type=str, default=None)
    parser.add_argument("--asset-id", type=str, default=None)
    parser.add_argument("--scenario-family", type=str, default=None)
    parser.add_argument("--case-group", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--case-interval-seconds", type=float, default=DEFAULT_CASE_INTERVAL_SECONDS)
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--output-path", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles = _load_profiles(BASELINE_PROFILES_PATH)
    if args.baseline_id not in profiles:
        raise SystemExit(f"Unknown baseline_id: {args.baseline_id}")
    dataset = load_dataset(args.dataset_path)

    if args.baseline_id == "B5":
        report = _baseline_b5_from_existing(args.dataset_path)
    else:
        report = run_baseline(
            dataset=dataset,
            profile=profiles[args.baseline_id],
            case_id=args.case_id,
            limit=args.limit,
            asset_id=args.asset_id,
            scenario_family=args.scenario_family,
            case_group=args.case_group,
            case_interval_seconds=args.case_interval_seconds,
            stop_on_fail=args.stop_on_fail,
        )
        report["dataset_path"] = str(args.dataset_path)

    written_path = _write_report(report, baseline_id=args.baseline_id, output_path=args.output_path)
    print()
    print(
        json.dumps(
            {
                "baseline_id": args.baseline_id,
                "total": report["metrics"]["total_cases"],
                "status_counts": report["metrics"]["status_counts"],
                "report_path": str(written_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
