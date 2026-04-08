"""
Gateway-centric runner for the integrated robot + AGV + process PCAG benchmark dataset.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATASET_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "releases"
    / "integrated_benchmark_release_v2"
    / "pcag_execution_dataset.json"
)
RESULTS_DIR = ROOT_DIR / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results"

GATEWAY_URL = os.environ.get("PCAG_GATEWAY_URL", "http://127.0.0.1:8000")
SAFETY_URL = os.environ.get("PCAG_SAFETY_URL", "http://127.0.0.1:8001")
POLICY_URL = os.environ.get("PCAG_POLICY_URL", "http://127.0.0.1:8002")
SENSOR_URL = os.environ.get("PCAG_SENSOR_URL", "http://127.0.0.1:8003")
OT_URL = os.environ.get("PCAG_OT_URL", "http://127.0.0.1:8004")
EVIDENCE_URL = os.environ.get("PCAG_EVIDENCE_URL", "http://127.0.0.1:8005")
PLCADAPTER_URL = os.environ.get("PCAG_PLC_ADAPTER_URL", "http://127.0.0.1:8007")
DEFAULT_CASE_INTERVAL_SECONDS = float(os.environ.get("PCAG_BENCH_CASE_INTERVAL_SECONDS", "6.0"))


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = deep_merge(merged.get(key), value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def load_dataset(dataset_path: Path) -> dict[str, Any]:
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _resolve_library_entry(dataset: dict[str, Any], group: str, ref: str | None, default: Any = None) -> Any:
    if ref is None:
        return copy.deepcopy(default)
    return copy.deepcopy((dataset.get("libraries") or {}).get(group, {}).get(ref, default))


def _check_service(client: httpx.Client, name: str, url: str) -> dict[str, Any]:
    try:
        response = client.get(url, timeout=5.0)
        return {"name": name, "url": url, "ok": response.status_code == 200, "status_code": response.status_code}
    except Exception as exc:
        return {"name": name, "url": url, "ok": False, "error": str(exc)}


def check_required_services(*, needs_plc: bool) -> dict[str, Any]:
    service_urls = {
        "gateway": f"{GATEWAY_URL}/openapi.json",
        "safety_cluster": f"{SAFETY_URL}/openapi.json",
        "policy_store": f"{POLICY_URL}/openapi.json",
        "sensor_gateway": f"{SENSOR_URL}/openapi.json",
        "ot_interface": f"{OT_URL}/openapi.json",
        "evidence_ledger": f"{EVIDENCE_URL}/openapi.json",
    }
    if needs_plc:
        service_urls["plc_adapter"] = f"{PLCADAPTER_URL}/openapi.json"
    with httpx.Client() as client:
        services = [_check_service(client, name, url) for name, url in service_urls.items()]
    return {"ok": all(service["ok"] for service in services), "services": services}


def _prepare_case(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge(dataset.get("defaults", {}), case)
    merged["headers"] = merged.get("headers") or {"X-API-Key": "pcag-agent-key-001"}
    return merged


def _get_active_policy_version(client: httpx.Client, cache: dict[str, Any]) -> str:
    if "active_policy_version" in cache:
        return cache["active_policy_version"]
    response = client.get(f"{POLICY_URL}/v1/policies/active", timeout=10.0)
    response.raise_for_status()
    cache["active_policy_version"] = response.json()["policy_version_id"]
    return cache["active_policy_version"]


def _fetch_sensor_snapshot(client: httpx.Client, asset_id: str) -> dict[str, Any]:
    response = client.get(f"{SENSOR_URL}/v1/assets/{asset_id}/snapshots/latest", timeout=15.0)
    response.raise_for_status()
    return response.json()


def _resolve_runtime_context(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any] | None:
    runtime_context = (case.get("proof") or {}).get("runtime_context")
    if runtime_context:
        return copy.deepcopy(runtime_context)
    runtime_ref = ((case.get("runtime") or {}).get("runtime_context_ref"))
    return _resolve_library_entry(dataset, "runtime_contexts", runtime_ref, None)


def _resolve_initial_state(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any] | None:
    runtime_cfg = case.get("runtime") or {}
    return _resolve_library_entry(dataset, "initial_states", runtime_cfg.get("initial_state_ref"), None)


def _preload_runtime(client: httpx.Client, *, case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any] | None:
    runtime_cfg = case.get("runtime") or {}
    if not runtime_cfg.get("preload_required"):
        return None

    runtime_context = _resolve_runtime_context(case, dataset)
    if not runtime_context:
        raise RuntimeError(f"Case {case['case_id']} requires preload but has no runtime context")

    initial_state = _resolve_initial_state(case, dataset)
    preload_target = runtime_cfg.get("preload_target", "safety_cluster")
    if preload_target == "plc_adapter":
        preload_url = f"{PLCADAPTER_URL}/v1/runtime/preload"
    elif preload_target == "safety_cluster":
        preload_url = f"{SAFETY_URL}/v1/runtime/preload"
    else:
        raise RuntimeError(f"Unsupported preload_target '{preload_target}' in {case['case_id']}")

    response = client.post(
        preload_url,
        json={"asset_id": case["asset_id"], "runtime_context": runtime_context, "initial_state": initial_state},
        timeout=120.0,
    )
    response.raise_for_status()
    preload_result = response.json()
    if runtime_cfg.get("sensor_alignment_mode") == "latest_after_preload":
        time.sleep(0.25)
    return preload_result


def _build_request_body(
    client: httpx.Client,
    *,
    case: dict[str, Any],
    dataset: dict[str, Any],
    cache: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    proof_cfg = copy.deepcopy(case.get("proof", {}))
    asset_id = case["asset_id"]
    latest_sensor = _fetch_sensor_snapshot(client, asset_id)

    policy_version_mode = proof_cfg.pop("policy_version_mode", "active")
    if policy_version_mode == "active":
        policy_version_id = _get_active_policy_version(client, cache)
    elif policy_version_mode == "explicit":
        policy_version_id = proof_cfg.pop("policy_version_id")
    else:
        raise ValueError(f"Unsupported policy_version_mode: {policy_version_mode}")

    timestamp_ms = proof_cfg.pop("timestamp_ms", None)
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) + int(proof_cfg.pop("timestamp_offset_ms", 0))
    else:
        proof_cfg.pop("timestamp_offset_ms", None)

    action_sequence_ref = proof_cfg.pop("action_sequence_ref", None)
    if action_sequence_ref is not None:
        action_sequence = _resolve_library_entry(dataset, "action_sequences", action_sequence_ref, [])
    else:
        action_sequence = copy.deepcopy(proof_cfg.pop("action_sequence", []))

    sensor_snapshot_mode = proof_cfg.pop("sensor_snapshot_mode", "none")
    sensor_snapshot = None
    if sensor_snapshot_mode == "latest":
        sensor_snapshot = latest_sensor["sensor_snapshot"]
    elif sensor_snapshot_mode == "override":
        sensor_snapshot = _resolve_library_entry(dataset, "sensor_snapshots", proof_cfg.pop("sensor_snapshot_ref", None), {})
    elif sensor_snapshot_mode != "none":
        raise ValueError(f"Unsupported sensor_snapshot_mode: {sensor_snapshot_mode}")

    sensor_hash_mode = proof_cfg.pop("sensor_hash_mode", "latest")
    if sensor_hash_mode == "latest":
        sensor_snapshot_hash = latest_sensor["sensor_snapshot_hash"]
    elif sensor_hash_mode == "explicit":
        sensor_snapshot_hash = proof_cfg.pop("sensor_snapshot_hash")
    else:
        raise ValueError(f"Unsupported sensor_hash_mode: {sensor_hash_mode}")

    runtime_context = _resolve_runtime_context(case, dataset)
    if runtime_context is not None:
        proof_cfg["runtime_context"] = runtime_context

    fault_injection = case.get("fault_injection")
    if fault_injection is not None:
        proof_cfg["fault_injection"] = copy.deepcopy(fault_injection)

    proof_package = {
        "schema_version": proof_cfg.pop("schema_version", "1.0"),
        "policy_version_id": policy_version_id,
        "timestamp_ms": timestamp_ms,
        "sensor_snapshot_hash": sensor_snapshot_hash,
        "sensor_reliability_index": proof_cfg.pop("sensor_reliability_index", latest_sensor.get("sensor_reliability_index", 0.95)),
        "action_sequence": action_sequence,
        "safety_verification_summary": proof_cfg.pop("safety_verification_summary", {"checks": [], "assumptions": [], "warnings": []}),
    }
    if sensor_snapshot is not None:
        proof_package["sensor_snapshot"] = sensor_snapshot
    proof_package = deep_merge(proof_package, proof_cfg)

    request_body = {
        "transaction_id": case.get("transaction_id") or f"pcag-bench-{case['case_id']}-{int(time.time() * 1000)}",
        "asset_id": asset_id,
        "proof_package": proof_package,
    }
    return request_body, latest_sensor


def _fetch_evidence(client: httpx.Client, transaction_id: str, retries: int = 8, delay_s: float = 0.4) -> dict[str, Any] | None:
    for _ in range(retries):
        try:
            response = client.get(f"{EVIDENCE_URL}/v1/transactions/{transaction_id}", timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        time.sleep(delay_s)
    return None


def _validate_result(case: dict[str, Any], response: httpx.Response, response_json: Any, evidence_json: dict[str, Any] | None) -> list[str]:
    expected = case.get("expected", {})
    errors: list[str] = []

    expected_http_status = expected.get("http_status", response.status_code)
    if response.status_code != expected_http_status:
        errors.append(f"HTTP status mismatch: expected {expected_http_status}, got {response.status_code}")

    actual_status = response_json.get("status") if isinstance(response_json, dict) else None
    if expected.get("status") is not None and actual_status != expected["status"]:
        errors.append(f"Response status mismatch: expected {expected['status']}, got {actual_status}")

    actual_reason_code = response_json.get("reason_code") if isinstance(response_json, dict) else None
    if expected.get("reason_code") is not None and actual_reason_code != expected["reason_code"]:
        errors.append(f"Reason code mismatch: expected {expected['reason_code']}, got {actual_reason_code}")

    if "response_has_evidence_ref" in expected:
        actual_has_ref = bool(response_json.get("evidence_ref")) if isinstance(response_json, dict) else False
        if actual_has_ref != bool(expected["response_has_evidence_ref"]):
            errors.append(
                f"Evidence ref presence mismatch: expected {expected['response_has_evidence_ref']}, got {actual_has_ref}"
            )

    if expected.get("evidence_required"):
        if evidence_json is None:
            errors.append("Evidence document was expected but not found")
        else:
            if "evidence_chain_valid" in expected and evidence_json.get("chain_valid") != expected["evidence_chain_valid"]:
                errors.append(
                    f"Evidence chain_valid mismatch: expected {expected['evidence_chain_valid']}, got {evidence_json.get('chain_valid')}"
                )
            stages = [event["stage"] for event in evidence_json.get("events", [])]
            if "evidence_stages_exact" in expected and stages != expected["evidence_stages_exact"]:
                errors.append(f"Evidence stages mismatch: expected {expected['evidence_stages_exact']}, got {stages}")

    return errors


def run_case(client: httpx.Client, *, case: dict[str, Any], dataset: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    prepared_case = _prepare_case(case, dataset)
    preload_result = _preload_runtime(client, case=prepared_case, dataset=dataset)
    request_body, latest_sensor = _build_request_body(client, case=prepared_case, dataset=dataset, cache=cache)

    started_at = time.time()
    response = client.post(
        f"{GATEWAY_URL}/v1/control-requests",
        json=request_body,
        headers=prepared_case.get("headers") or {},
        timeout=90.0,
    )
    duration_ms = round((time.time() - started_at) * 1000, 2)

    try:
        response_json = response.json()
    except Exception:
        response_json = {"raw": response.text}

    evidence_json = None
    if prepared_case.get("expected", {}).get("evidence_required"):
        evidence_json = _fetch_evidence(client, request_body["transaction_id"])

    errors = _validate_result(prepared_case, response, response_json, evidence_json)
    return {
        "case_id": prepared_case["case_id"],
        "description": prepared_case.get("description"),
        "asset_id": prepared_case["asset_id"],
        "scenario_family": prepared_case.get("scenario_family"),
        "expected_final_status": (prepared_case.get("label") or {}).get("expected_final_status"),
        "passed": not errors,
        "errors": errors,
        "duration_ms": duration_ms,
        "preload_result": preload_result,
        "sensor_snapshot_after_preload": latest_sensor,
        "request_body": request_body,
        "response_status_code": response.status_code,
        "response_json": response_json,
        "evidence": evidence_json,
    }


def _select_cases(
    dataset: dict[str, Any],
    *,
    case_id: str | None,
    limit: int | None,
    asset_id: str | None,
    scenario_family: str | None,
    case_group: str | None,
) -> list[dict[str, Any]]:
    cases = dataset.get("cases", [])
    if case_id:
        selected = [case for case in cases if case.get("case_id") == case_id]
        if not selected:
            raise ValueError(f"Case not found: {case_id}")
        return selected

    selected = list(cases)
    if asset_id:
        selected = [case for case in selected if case.get("asset_id") == asset_id]
    if scenario_family:
        selected = [case for case in selected if case.get("scenario_family") == scenario_family]
    if case_group:
        selected = [case for case in selected if case.get("case_group") == case_group]
    if limit is not None:
        selected = selected[:limit]
    return selected


def run_cases(
    *,
    dataset: dict[str, Any],
    case_id: str | None,
    limit: int | None,
    asset_id: str | None,
    scenario_family: str | None,
    case_group: str | None,
    skip_preflight: bool,
    stop_on_fail: bool,
    case_interval_seconds: float,
) -> dict[str, Any]:
    selected_cases = _select_cases(
        dataset,
        case_id=case_id,
        limit=limit,
        asset_id=asset_id,
        scenario_family=scenario_family,
        case_group=case_group,
    )
    needs_plc = any(((case.get("runtime") or {}).get("preload_target") == "plc_adapter") for case in selected_cases)
    preflight = check_required_services(needs_plc=needs_plc)
    if not skip_preflight and not preflight["ok"]:
        raise RuntimeError(f"Required services are not all available: {preflight}")

    cache: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for index, case in enumerate(selected_cases):
            result = run_case(client, case=case, dataset=dataset, cache=cache)
            results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            final_status = result["response_json"].get("status") if isinstance(result["response_json"], dict) else "UNKNOWN"
            print(f"[{status}] {result['case_id']} -> {final_status}")
            if stop_on_fail and not result["passed"]:
                break
            if case_interval_seconds > 0 and index < len(selected_cases) - 1:
                print(f"[WAIT] cooling down for {case_interval_seconds:.1f}s before next case")
                time.sleep(case_interval_seconds)

    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    return {
        "generated_at_ms": int(time.time() * 1000),
        "dataset_name": dataset.get("meta", {}).get("name"),
        "dataset_path": str(DATASET_PATH),
        "gateway_url": GATEWAY_URL,
        "safety_url": SAFETY_URL,
        "case_interval_seconds": case_interval_seconds,
        "preflight": preflight,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def write_report(report: dict[str, Any], output_path: Path | None = None) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    latest_path = RESULTS_DIR / "integrated_pcag_benchmark_latest.json"
    archive_path = RESULTS_DIR / f"integrated_pcag_benchmark_{timestamp}.json"

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    latest_path.write_text(payload, encoding="utf-8")
    archive_path.write_text(payload, encoding="utf-8")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        return output_path
    return latest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the integrated robot + AGV + process PCAG benchmark.")
    parser.add_argument("--dataset-path", type=Path, default=DATASET_PATH)
    parser.add_argument("--case-id", type=str, default=None)
    parser.add_argument("--asset-id", type=str, default=None)
    parser.add_argument("--scenario-family", type=str, default=None)
    parser.add_argument("--case-group", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--case-interval-seconds", type=float, default=DEFAULT_CASE_INTERVAL_SECONDS)
    parser.add_argument("--output-path", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_dataset(args.dataset_path)
    report = run_cases(
        dataset=dataset,
        case_id=args.case_id,
        limit=args.limit,
        asset_id=args.asset_id,
        scenario_family=args.scenario_family,
        case_group=args.case_group,
        skip_preflight=args.skip_preflight,
        stop_on_fail=args.stop_on_fail,
        case_interval_seconds=args.case_interval_seconds,
    )
    report["dataset_path"] = str(args.dataset_path)
    written_path = write_report(report, args.output_path)
    print()
    print(
        json.dumps(
            {"total": report["total"], "passed": report["passed"], "failed": report["failed"], "report_path": str(written_path)},
            indent=2,
        )
    )
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
