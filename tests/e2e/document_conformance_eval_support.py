"""
Support utilities for the document-conformance E2E evaluation suite.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pcag.apps.gateway.main import app as gateway_app
from pcag.core.utils.hash_utils import GENESIS_HASH, compute_event_hash, compute_sensor_hash

DATASET_PATH = Path(__file__).with_name("document_conformance_eval_30.json")
RESULTS_DIR = Path(__file__).with_name("results")
DEFAULT_HEADERS = {"X-API-Key": "pcag-agent-key-001"}
DEFAULT_POLICY_VERSION = "v2025-03-04"


def make_mock_response(json_data: Any, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.text = json.dumps(json_data)
    return mock


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


def _prepare_case(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge(dataset.get("defaults", {}), case)
    mock_cfg = merged.setdefault("mock", {})
    merged["headers"] = merged.get("headers") or DEFAULT_HEADERS
    mock_cfg["active_policy_version"] = mock_cfg.get("active_policy_version", DEFAULT_POLICY_VERSION)
    mock_cfg["asset_profile"] = _resolve_library_entry(dataset, "asset_profiles", mock_cfg.get("asset_profile_ref"), {})
    mock_cfg["sensor_sequence"] = _resolve_library_entry(dataset, "sensor_sequences", mock_cfg.get("sensor_sequence_ref"), [{}])
    mock_cfg["sensor_status_sequence"] = mock_cfg.get("sensor_status_sequence", [200, 200])
    merged["request_body"] = _build_request_body(merged, dataset)
    return merged


def _build_request_body(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    tx_id = case.get("transaction_id") or f"eval-{case['case_id']}"
    proof = copy.deepcopy(case.get("proof", {}))
    sensor_sequence = case.get("mock", {}).get("sensor_sequence", [{}])
    first_sensor = copy.deepcopy(sensor_sequence[0] if sensor_sequence else {})
    proof["timestamp_ms"] = int(time.time() * 1000) + int(proof.pop("timestamp_offset_ms", 0))

    action_sequence_ref = proof.pop("action_sequence_ref", None)
    if action_sequence_ref is not None:
        proof["action_sequence"] = _resolve_library_entry(dataset, "action_sequences", action_sequence_ref, [])

    include_sensor_snapshot = proof.pop("include_sensor_snapshot", False)
    sensor_snapshot_ref = proof.pop("sensor_snapshot_ref", None)
    sensor_snapshot = None
    if sensor_snapshot_ref is not None:
        sensor_snapshot = _resolve_library_entry(dataset, "sensor_snapshots", sensor_snapshot_ref, {})
    elif include_sensor_snapshot:
        sensor_snapshot = first_sensor

    if sensor_snapshot is not None:
        proof["sensor_snapshot"] = sensor_snapshot

    sensor_hash_mode = proof.pop("sensor_hash_mode", "match_first_sensor")
    if sensor_hash_mode == "match_first_sensor":
        proof["sensor_snapshot_hash"] = compute_sensor_hash(first_sensor)
    elif sensor_hash_mode == "from_sensor_snapshot":
        proof["sensor_snapshot_hash"] = compute_sensor_hash(sensor_snapshot or first_sensor)
    elif sensor_hash_mode == "explicit":
        proof["sensor_snapshot_hash"] = proof.get("sensor_snapshot_hash", "")
    else:
        raise ValueError(f"Unsupported sensor_hash_mode: {sensor_hash_mode}")

    remove_fields = proof.pop("remove_fields", [])

    request_body = {
        "transaction_id": tx_id,
        "asset_id": case["asset_id"],
        "proof_package": proof,
    }

    request_override = case.get("request_override")
    if request_override:
        request_body = deep_merge(request_body, request_override)

    for field_name in remove_fields:
        request_body.get("proof_package", {}).pop(field_name, None)

    return request_body


class DatasetDrivenMockClient:
    def __init__(self, case: dict[str, Any], evidence_bucket: list[dict[str, Any]]):
        self.case = case
        self.mock_cfg = case.get("mock", {})
        self.evidence_bucket = evidence_bucket
        self.calls: list[tuple] = []
        self.sensor_call_index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def _sequence_value(self, values: list[Any] | None, index: int, default: Any) -> Any:
        if not values:
            return default
        return values[min(index, len(values) - 1)]

    def _next_sensor_payload(self) -> dict[str, Any]:
        sensor_sequence = self.mock_cfg.get("sensor_sequence", [{}])
        idx = min(self.sensor_call_index, len(sensor_sequence) - 1)
        sensor_snapshot = copy.deepcopy(sensor_sequence[idx])
        payload = {
            "asset_id": self.case["asset_id"],
            "snapshot_id": f"snap_{idx + 1:03d}",
            "timestamp_ms": int(time.time() * 1000),
            "sensor_snapshot": sensor_snapshot,
            "sensor_snapshot_hash": compute_sensor_hash(sensor_snapshot),
            "sensor_reliability_index": 0.95,
        }
        self.sensor_call_index += 1
        return payload

    def _build_safety_result(self, transaction_id: str) -> dict[str, Any]:
        verdict = self.mock_cfg.get("safety_verdict", "SAFE")
        validators = {
            "rules": {"verdict": "SAFE", "details": {}},
            "cbf": {"verdict": "SAFE", "details": {}},
            "simulation": {"verdict": "INDETERMINATE", "details": {"reason": "simulation_disabled"}},
        }
        validators = deep_merge(validators, self.mock_cfg.get("validator_verdicts", {}))
        consensus_details = {
            "mode": "WEIGHTED",
            "weights_used": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
            "score": 1.0 if verdict == "SAFE" else 0.0,
            "threshold": 0.5,
            "explanation": verdict,
        }
        consensus_details = deep_merge(consensus_details, self.mock_cfg.get("consensus_details", {}))
        return {
            "transaction_id": transaction_id,
            "final_verdict": verdict,
            "validators": validators,
            "consensus_details": consensus_details,
        }

    async def get(self, url: str, **kwargs):
        self.calls.append(("GET", url))

        if "/policies/active" in url:
            if self.mock_cfg.get("policy_active_error"):
                raise RuntimeError(self.mock_cfg["policy_active_error"])
            status_code = int(self.mock_cfg.get("policy_active_status_code", 200))
            payload = {"policy_version_id": self.mock_cfg.get("active_policy_version", DEFAULT_POLICY_VERSION)}
            if status_code != 200:
                payload = {"detail": self.mock_cfg.get("policy_active_error_detail", "active policy lookup failed")}
            return make_mock_response(payload, status_code=status_code)

        if "/policies/" in url and "/assets/" in url:
            if self.mock_cfg.get("policy_asset_error"):
                raise RuntimeError(self.mock_cfg["policy_asset_error"])
            status_code = int(self.mock_cfg.get("policy_asset_status_code", 200))
            asset_id = url.rsplit("/", 1)[-1]
            payload = {
                "policy_version_id": self.mock_cfg.get("active_policy_version", DEFAULT_POLICY_VERSION),
                "asset_id": asset_id,
                "profile": self.mock_cfg.get("asset_profile", {}),
            }
            if status_code != 200:
                payload = {"detail": self.mock_cfg.get("policy_asset_error_detail", "asset profile lookup failed")}
            return make_mock_response(payload, status_code=status_code)

        if "/snapshots/latest" in url:
            idx = self.sensor_call_index
            error_value = self._sequence_value(self.mock_cfg.get("sensor_error_sequence"), idx, None)
            status_code = int(self._sequence_value(self.mock_cfg.get("sensor_status_sequence"), idx, 200))
            if error_value:
                self.sensor_call_index += 1
                raise RuntimeError(str(error_value))
            if status_code != 200:
                self.sensor_call_index += 1
                return make_mock_response(
                    {"detail": self._sequence_value(self.mock_cfg.get("sensor_error_details"), idx, "sensor gateway error")},
                    status_code=status_code,
                )
            return make_mock_response(self._next_sensor_payload())

        return make_mock_response({}, status_code=404)

    async def post(self, url: str, **kwargs):
        payload = kwargs.get("json", {})
        self.calls.append(("POST", url, copy.deepcopy(payload)))

        if "/validate" in url:
            if self.mock_cfg.get("safety_error"):
                raise RuntimeError(self.mock_cfg["safety_error"])
            status_code = int(self.mock_cfg.get("safety_status_code", 200))
            if status_code != 200:
                return make_mock_response({"detail": self.mock_cfg.get("safety_error_detail", "safety validation failed")}, status_code=status_code)
            return make_mock_response(self._build_safety_result(payload["transaction_id"]))

        if "/prepare" in url:
            if self.mock_cfg.get("prepare_error"):
                raise RuntimeError(self.mock_cfg["prepare_error"])
            status_code = int(self.mock_cfg.get("prepare_http_status", 200))
            if status_code != 200:
                return make_mock_response({"detail": self.mock_cfg.get("prepare_error_detail", "prepare failed")}, status_code=status_code)
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "status": self.mock_cfg.get("prepare_status", "LOCK_GRANTED"),
                    "lock_expires_at_ms": int(time.time() * 1000) + int(payload.get("lock_ttl_ms", 0)),
                    "reason": self.mock_cfg.get("prepare_reason", "Lock denied by OT"),
                }
            )

        if "/commit" in url:
            if self.mock_cfg.get("commit_error"):
                raise RuntimeError(self.mock_cfg["commit_error"])
            status_code = int(self.mock_cfg.get("commit_http_status", 200))
            if status_code != 200:
                return make_mock_response({"detail": self.mock_cfg.get("commit_error_detail", "commit failed")}, status_code=status_code)
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "status": self.mock_cfg.get("commit_status", "ACK"),
                    "executed_at_ms": int(time.time() * 1000),
                }
            )

        if "/events/append" in url:
            if self.mock_cfg.get("evidence_error"):
                raise RuntimeError(self.mock_cfg["evidence_error"])
            self.evidence_bucket.append(copy.deepcopy(payload))
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "sequence_no": payload["sequence_no"],
                    "event_hash": payload["event_hash"],
                },
                status_code=int(self.mock_cfg.get("evidence_status_code", 200)),
            )

        if "/abort" in url:
            if self.mock_cfg.get("abort_error"):
                raise RuntimeError(self.mock_cfg["abort_error"])
            status_code = int(self.mock_cfg.get("abort_http_status", 200))
            if status_code != 200:
                return make_mock_response({"detail": self.mock_cfg.get("abort_error_detail", "abort failed")}, status_code=status_code)
            return make_mock_response({"status": self.mock_cfg.get("abort_status", "ABORTED"), "safe_state_executed": True})

        return make_mock_response({}, status_code=404)


def _response_json_or_none(response) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def _contains_all_path_fragments(calls: list[tuple], fragments: list[str]) -> list[str]:
    missing = []
    urls = [call[1] for call in calls]
    for fragment in fragments:
        if not any(fragment in url for url in urls):
            missing.append(fragment)
    return missing


def _contains_any_path_fragment(calls: list[tuple], fragments: list[str]) -> list[str]:
    present = []
    urls = [call[1] for call in calls]
    for fragment in fragments:
        if any(fragment in url for url in urls):
            present.append(fragment)
    return present


def _extract_prepare_lock_ttl(calls: list[tuple]) -> int | None:
    for call in calls:
        if len(call) < 3:
            continue
        method, url, payload = call
        if method == "POST" and "/prepare" in url:
            return payload.get("lock_ttl_ms")
    return None


def _evidence_chain_valid(events: list[dict[str, Any]]) -> bool:
    if not events:
        return True
    if events[0].get("prev_hash") != GENESIS_HASH:
        return False
    for index, event in enumerate(events):
        if compute_event_hash(event["prev_hash"], event["payload"]) != event["event_hash"]:
            return False
        if index > 0 and event["prev_hash"] != events[index - 1]["event_hash"]:
            return False
    return True


def _validate_result(case: dict[str, Any], response, response_json: Any, evidence_bucket: list[dict[str, Any]], calls: list[tuple]) -> list[str]:
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

    if "alternative_actions_min_count" in expected:
        actual_count = len(response_json.get("alternative_actions") or []) if isinstance(response_json, dict) else 0
        if actual_count < int(expected["alternative_actions_min_count"]):
            errors.append(
                f"Alternative actions count mismatch: expected at least {expected['alternative_actions_min_count']}, got {actual_count}"
            )

    if "alternative_actions_exact_count" in expected:
        actual_count = len(response_json.get("alternative_actions") or []) if isinstance(response_json, dict) else 0
        if actual_count != int(expected["alternative_actions_exact_count"]):
            errors.append(
                f"Alternative actions count mismatch: expected exactly {expected['alternative_actions_exact_count']}, got {actual_count}"
            )

    if "response_has_evidence_ref" in expected:
        actual_ref = response_json.get("evidence_ref") if isinstance(response_json, dict) else None
        actual_has_ref = actual_ref is not None
        if actual_has_ref != bool(expected["response_has_evidence_ref"]):
            errors.append(
                f"Evidence ref presence mismatch: expected {expected['response_has_evidence_ref']}, got {actual_has_ref}"
            )

    stages = [event["stage"] for event in evidence_bucket]
    for stage in expected.get("must_include_stages", []):
        if stage not in stages:
            errors.append(f"Missing expected evidence stage: {stage}")

    for stage in expected.get("must_exclude_stages", []):
        if stage in stages:
            errors.append(f"Unexpected evidence stage present: {stage}")

    if "evidence_count_exact" in expected and len(evidence_bucket) != int(expected["evidence_count_exact"]):
        errors.append(f"Evidence count mismatch: expected {expected['evidence_count_exact']}, got {len(evidence_bucket)}")

    missing_paths = _contains_all_path_fragments(calls, expected.get("must_call_paths", []))
    if missing_paths:
        errors.append(f"Expected downstream calls were not made: {missing_paths}")

    unexpected_paths = _contains_any_path_fragment(calls, expected.get("must_not_call_paths", []))
    if unexpected_paths:
        errors.append(f"Unexpected downstream calls were made: {unexpected_paths}")

    if "prepare_lock_ttl_ms" in expected:
        actual_ttl = _extract_prepare_lock_ttl(calls)
        if actual_ttl != int(expected["prepare_lock_ttl_ms"]):
            errors.append(f"Prepare lock TTL mismatch: expected {expected['prepare_lock_ttl_ms']}, got {actual_ttl}")

    if expected.get("verify_evidence_chain") and not _evidence_chain_valid(evidence_bucket):
        errors.append("Evidence hash chain validation failed")

    return errors


def run_case(case: dict[str, Any], dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    dataset = dataset or load_dataset()
    prepared_case = _prepare_case(case, dataset)
    evidence_bucket: list[dict[str, Any]] = []
    client_holder: dict[str, DatasetDrivenMockClient] = {}

    def client_factory(*args, **kwargs):
        mock_client = DatasetDrivenMockClient(prepared_case, evidence_bucket)
        client_holder["client"] = mock_client
        return mock_client

    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app, raise_server_exceptions=False)
        response = client.post(
            "/v1/control-requests",
            json=prepared_case["request_body"],
            headers=prepared_case["headers"],
        )

    response_json = _response_json_or_none(response)
    downstream_calls = client_holder.get("client").calls if client_holder.get("client") else []
    errors = _validate_result(prepared_case, response, response_json, evidence_bucket, downstream_calls)
    return {
        "case_id": prepared_case["case_id"],
        "category": prepared_case.get("category"),
        "description": prepared_case.get("description"),
        "passed": not errors,
        "errors": errors,
        "request_body": prepared_case["request_body"],
        "response_status_code": response.status_code,
        "response_json": response_json,
        "evidence_stages": [event["stage"] for event in evidence_bucket],
        "evidence_count": len(evidence_bucket),
        "downstream_calls": downstream_calls,
    }


def run_all_cases(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    dataset = dataset or load_dataset()
    results = [run_case(case, dataset=dataset) for case in dataset.get("cases", [])]
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    category_summary: dict[str, dict[str, int]] = {}
    for result in results:
        category = result.get("category") or "uncategorized"
        category_summary.setdefault(category, {"passed": 0, "failed": 0, "total": 0})
        category_summary[category]["total"] += 1
        category_summary[category]["passed" if result["passed"] else "failed"] += 1
    return {
        "generated_at_ms": int(time.time() * 1000),
        "dataset_name": dataset.get("meta", {}).get("name", DATASET_PATH.name),
        "dataset_path": str(DATASET_PATH),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "category_summary": category_summary,
        "results": results,
    }


def write_report(report: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "document_conformance_eval_30_latest.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path
