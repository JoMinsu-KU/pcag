"""
Live E2E support for the single-entry Gateway evaluation flow.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATASET_PATH = Path(__file__).with_name("live_gateway_eval_dataset.json")
RESULTS_DIR = Path(__file__).with_name("results")

# Windows 환경에서는 localhost가 IPv6(::1)로 먼저 해석되며 재시도 지연이
# 붙을 수 있어, live E2E 기본값은 IPv4 loopback으로 고정한다.
GATEWAY_URL = os.environ.get("PCAG_GATEWAY_URL", "http://127.0.0.1:8000")
SAFETY_URL = os.environ.get("PCAG_SAFETY_URL", "http://127.0.0.1:8001")
POLICY_URL = os.environ.get("PCAG_POLICY_URL", "http://127.0.0.1:8002")
SENSOR_URL = os.environ.get("PCAG_SENSOR_URL", "http://127.0.0.1:8003")
OT_URL = os.environ.get("PCAG_OT_URL", "http://127.0.0.1:8004")
EVIDENCE_URL = os.environ.get("PCAG_EVIDENCE_URL", "http://127.0.0.1:8005")
POLICY_ADMIN_URL = os.environ.get("PCAG_POLICY_ADMIN_URL", "http://127.0.0.1:8006")
PLC_ADAPTER_URL = os.environ.get("PCAG_PLC_ADAPTER_URL", "http://127.0.0.1:8007")

DEFAULT_HEADERS = {"X-API-Key": "pcag-agent-key-001"}
FALLBACK_HASH = "a" * 64


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = deep_merge(merged.get(key), value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _resolve_library_entry(dataset: dict[str, Any], group: str, ref: str | None, default: Any = None) -> Any:
    if ref is None:
        return copy.deepcopy(default)
    libraries = dataset.get("libraries", {})
    return copy.deepcopy(libraries.get(group, {}).get(ref, default))


def _check_service(client: httpx.Client, name: str, url: str) -> dict[str, Any]:
    try:
        response = client.get(url, timeout=5.0)
        return {"name": name, "url": url, "ok": response.status_code == 200, "status_code": response.status_code}
    except Exception as exc:
        return {"name": name, "url": url, "ok": False, "error": str(exc)}


def check_required_services() -> dict[str, Any]:
    service_urls = {
        "gateway": f"{GATEWAY_URL}/openapi.json",
        "safety_cluster": f"{SAFETY_URL}/openapi.json",
        "policy_store": f"{POLICY_URL}/openapi.json",
        "sensor_gateway": f"{SENSOR_URL}/openapi.json",
        "ot_interface": f"{OT_URL}/openapi.json",
        "evidence_ledger": f"{EVIDENCE_URL}/openapi.json",
        "policy_admin": f"{POLICY_ADMIN_URL}/openapi.json",
        "plc_adapter": f"{PLC_ADAPTER_URL}/openapi.json",
    }
    with httpx.Client() as client:
        services = [_check_service(client, name, url) for name, url in service_urls.items()]
    ok = all(service["ok"] for service in services)
    return {"ok": ok, "services": services}


def _get_active_policy_version(client: httpx.Client, cache: dict[str, Any]) -> str:
    if "active_policy_version" in cache:
        return cache["active_policy_version"]
    response = client.get(f"{POLICY_URL}/v1/policies/active", timeout=10.0)
    response.raise_for_status()
    cache["active_policy_version"] = response.json()["policy_version_id"]
    return cache["active_policy_version"]


def _get_sensor_snapshot(client: httpx.Client, asset_id: str, cache: dict[str, Any]) -> dict[str, Any] | None:
    sensor_cache = cache.setdefault("sensor_snapshots", {})
    if asset_id in sensor_cache:
        return copy.deepcopy(sensor_cache[asset_id])

    try:
        response = client.get(f"{SENSOR_URL}/v1/assets/{asset_id}/snapshots/latest", timeout=15.0)
        response.raise_for_status()
        sensor_cache[asset_id] = response.json()
        return copy.deepcopy(sensor_cache[asset_id])
    except Exception:
        return None


def _prepare_case(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge(dataset.get("defaults", {}), case)
    merged["headers"] = merged.get("headers") or copy.deepcopy(DEFAULT_HEADERS)
    return merged


def _build_request_body(client: httpx.Client, case: dict[str, Any], dataset: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    asset_id = case["asset_id"]
    proof_cfg = copy.deepcopy(case.get("proof", {}))
    latest_sensor = _get_sensor_snapshot(client, asset_id, cache)

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
        sensor_snapshot = latest_sensor.get("sensor_snapshot") if latest_sensor else None
    elif sensor_snapshot_mode == "override":
        sensor_snapshot = _resolve_library_entry(dataset, "sensor_snapshots", proof_cfg.pop("sensor_snapshot_ref", None), {})
    elif sensor_snapshot_mode != "none":
        raise ValueError(f"Unsupported sensor_snapshot_mode: {sensor_snapshot_mode}")

    sensor_hash_mode = proof_cfg.pop("sensor_hash_mode", "latest")
    if sensor_hash_mode == "latest":
        sensor_snapshot_hash = latest_sensor["sensor_snapshot_hash"] if latest_sensor else FALLBACK_HASH
    elif sensor_hash_mode == "explicit":
        sensor_snapshot_hash = proof_cfg.pop("sensor_snapshot_hash", FALLBACK_HASH)
    else:
        raise ValueError(f"Unsupported sensor_hash_mode: {sensor_hash_mode}")

    sensor_reliability_index = proof_cfg.pop(
        "sensor_reliability_index",
        latest_sensor.get("sensor_reliability_index", 0.95) if latest_sensor else 0.95,
    )

    proof_package = {
        "schema_version": proof_cfg.pop("schema_version", "1.0"),
        "policy_version_id": policy_version_id,
        "timestamp_ms": timestamp_ms,
        "sensor_snapshot_hash": sensor_snapshot_hash,
        "sensor_reliability_index": sensor_reliability_index,
        "action_sequence": action_sequence,
        "safety_verification_summary": proof_cfg.pop(
            "safety_verification_summary",
            {"checks": [], "assumptions": [], "warnings": []},
        ),
    }

    if sensor_snapshot is not None:
        proof_package["sensor_snapshot"] = sensor_snapshot

    proof_package = deep_merge(proof_package, proof_cfg)

    for field_name in case.get("proof", {}).get("remove_fields", []):
        proof_package.pop(field_name, None)

    return {
        "transaction_id": case.get("transaction_id") or f"live-{case['case_id']}-{int(time.time() * 1000)}",
        "asset_id": asset_id,
        "proof_package": proof_package,
    }


def _fetch_evidence(client: httpx.Client, transaction_id: str, retries: int = 5, delay_s: float = 0.4) -> dict[str, Any] | None:
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

    if response.status_code != expected.get("http_status", response.status_code):
        errors.append(f"HTTP status mismatch: expected {expected.get('http_status')}, got {response.status_code}")

    if expected.get("status") is not None:
        actual_status = response_json.get("status") if isinstance(response_json, dict) else None
        if actual_status != expected["status"]:
            errors.append(f"Response status mismatch: expected {expected['status']}, got {actual_status}")

    if expected.get("reason_code") is not None:
        actual_reason_code = response_json.get("reason_code") if isinstance(response_json, dict) else None
        if actual_reason_code != expected["reason_code"]:
            errors.append(f"Reason code mismatch: expected {expected['reason_code']}, got {actual_reason_code}")

    if expected.get("reason_contains"):
        actual_reason = response_json.get("reason", "") if isinstance(response_json, dict) else ""
        if expected["reason_contains"] not in actual_reason:
            errors.append(f"Reason does not contain expected text: {expected['reason_contains']}")

    if "response_has_evidence_ref" in expected:
        actual_has_ref = bool(response_json.get("evidence_ref")) if isinstance(response_json, dict) else False
        if actual_has_ref != bool(expected["response_has_evidence_ref"]):
            errors.append(f"Evidence ref presence mismatch: expected {expected['response_has_evidence_ref']}, got {actual_has_ref}")

    if "alternative_actions_min_count" in expected:
        actual_count = len(response_json.get("alternative_actions") or []) if isinstance(response_json, dict) else 0
        if actual_count < int(expected["alternative_actions_min_count"]):
            errors.append(
                f"Alternative actions count mismatch: expected at least {expected['alternative_actions_min_count']}, got {actual_count}"
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

            for stage in expected.get("evidence_stages_include", []):
                if stage not in stages:
                    errors.append(f"Missing evidence stage: {stage}")

            if "evidence_min_events" in expected and len(evidence_json.get("events", [])) < int(expected["evidence_min_events"]):
                errors.append(
                    f"Evidence event count mismatch: expected at least {expected['evidence_min_events']}, got {len(evidence_json.get('events', []))}"
                )

    return errors


def run_case(case: dict[str, Any], dataset: dict[str, Any] | None = None, cache: dict[str, Any] | None = None) -> dict[str, Any]:
    dataset = dataset or load_dataset()
    cache = cache or {}
    prepared_case = _prepare_case(case, dataset)

    with httpx.Client() as client:
        request_body = _build_request_body(client, prepared_case, dataset, cache)
        headers = prepared_case.get("headers") or copy.deepcopy(DEFAULT_HEADERS)
        started_at = time.time()
        response = client.post(f"{GATEWAY_URL}/v1/control-requests", json=request_body, headers=headers, timeout=60.0)
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
        "passed": not errors,
        "errors": errors,
        "duration_ms": duration_ms,
        "request_body": request_body,
        "response_status_code": response.status_code,
        "response_json": response_json,
        "evidence": evidence_json,
    }


def run_all_cases(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    dataset = dataset or load_dataset()
    preflight = check_required_services()
    if not preflight["ok"]:
        raise RuntimeError(f"Required live services are not all available: {preflight}")

    cache: dict[str, Any] = {}
    results = [run_case(case, dataset=dataset, cache=cache) for case in dataset.get("cases", [])]
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    return {
        "generated_at_ms": int(time.time() * 1000),
        "dataset_name": dataset.get("meta", {}).get("name", DATASET_PATH.name),
        "dataset_path": str(DATASET_PATH),
        "preflight": preflight,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def write_report(report: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "live_gateway_eval_latest.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
