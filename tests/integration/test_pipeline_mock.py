"""
Gateway pipeline integration tests with mocked downstream services.
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.apps.gateway.main import app as gateway_app
from pcag.core.utils.hash_utils import compute_sensor_hash


MOCK_POLICY_VERSION = "v2025-03-04"
HEADERS = {"X-API-Key": "pcag-agent-key-001"}
DEFAULT_SENSOR = {"temperature": 150.0, "pressure": 1.5}
DEFAULT_SENSOR_HASH = compute_sensor_hash(DEFAULT_SENSOR)
DEFAULT_ASSET_PROFILE = {
    "asset_id": "reactor_01",
    "sil_level": 2,
    "sensor_source": "modbus_sensor",
    "ot_executor": "mock_executor",
    "consensus": {"mode": "WEIGHTED", "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25}, "threshold": 0.5},
    "integrity": {"timestamp_max_age_ms": 5000, "sensor_divergence_thresholds": []},
    "ruleset": [],
    "simulation": {"engine": "none"},
    "execution": {
        "lock_ttl_ms": 7000,
        "commit_ack_timeout_ms": 3000,
        "safe_state": [
            {"action_type": "set_heater_output", "params": {"value": 0}},
            {"action_type": "set_cooling_valve", "params": {"value": 100}},
        ],
    },
}


def make_mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.text = str(json_data)
    return mock


def build_proof(sensor_hash: str, *, timestamp_ms: int | None = None, policy_version: str = MOCK_POLICY_VERSION):
    return {
        "schema_version": "1.0",
        "policy_version_id": policy_version,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        "sensor_snapshot_hash": sensor_hash,
        "sensor_reliability_index": 0.95,
        "action_sequence": [{"action_type": "set_heater_output", "params": {"value": 70}}],
        "safety_verification_summary": {"checks": [], "assumptions": [], "warnings": []},
    }


class ConfigurableMockClient:
    def __init__(
        self,
        safety_verdict="SAFE",
        prepare_status="LOCK_GRANTED",
        commit_status="ACK",
        commit_http_status=200,
        commit_reason=None,
        commit_safe_state_executed=True,
        evidence_status_code=200,
        evidence_bucket=None,
        active_policy_version=MOCK_POLICY_VERSION,
        asset_profile=None,
        sensor_sequence=None,
        abort_status="ABORTED",
        **kwargs,
    ):
        self.safety_verdict = safety_verdict
        self.prepare_status = prepare_status
        self.commit_status = commit_status
        self.commit_http_status = commit_http_status
        self.commit_reason = commit_reason
        self.commit_safe_state_executed = commit_safe_state_executed
        self.evidence_status_code = evidence_status_code
        self.evidence_bucket = evidence_bucket if evidence_bucket is not None else []
        self.active_policy_version = active_policy_version
        self.asset_profile = asset_profile or DEFAULT_ASSET_PROFILE
        self.sensor_sequence = sensor_sequence or [DEFAULT_SENSOR, DEFAULT_SENSOR]
        self.abort_status = abort_status
        self.calls = []
        self.sensor_call_index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def _next_sensor(self):
        idx = min(self.sensor_call_index, len(self.sensor_sequence) - 1)
        self.sensor_call_index += 1
        sensor = self.sensor_sequence[idx]
        return {
            "asset_id": "reactor_01",
            "snapshot_id": f"snap_{idx + 1:03d}",
            "timestamp_ms": int(time.time() * 1000),
            "sensor_snapshot": sensor,
            "sensor_snapshot_hash": compute_sensor_hash(sensor),
            "sensor_reliability_index": 0.95,
        }

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url))

        if "/policies/active" in url:
            return make_mock_response({"policy_version_id": self.active_policy_version})
        if f"/policies/{self.active_policy_version}/assets/" in url:
            asset_id = url.rsplit("/", 1)[-1]
            return make_mock_response({"policy_version_id": self.active_policy_version, "asset_id": asset_id, "profile": self.asset_profile})
        if "/snapshots/latest" in url:
            return make_mock_response(self._next_sensor())
        return make_mock_response({})

    async def post(self, url, **kwargs):
        payload = kwargs.get("json", {})
        self.calls.append(("POST", url, payload))

        if "/validate" in url:
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "final_verdict": self.safety_verdict,
                    "validators": {
                        "rules": {"verdict": self.safety_verdict, "details": {}},
                        "cbf": {"verdict": self.safety_verdict, "details": {}},
                        "simulation": {"verdict": "INDETERMINATE", "details": {"reason": "simulation_disabled"}},
                    },
                    "consensus_details": {
                        "mode": "WEIGHTED",
                        "weights_used": {},
                        "score": 1.0 if self.safety_verdict == "SAFE" else 0.0,
                        "threshold": 0.5,
                        "explanation": self.safety_verdict,
                    },
                }
            )
        if "/prepare" in url:
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "status": self.prepare_status,
                    "lock_expires_at_ms": int(time.time() * 1000) + payload.get("lock_ttl_ms", 0),
                    "reason": "Lock denied by OT" if self.prepare_status != "LOCK_GRANTED" else None,
                }
            )
        if "/commit" in url:
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "status": self.commit_status,
                    "executed_at_ms": int(time.time() * 1000),
                    "reason": self.commit_reason,
                    "safe_state_executed": self.commit_safe_state_executed,
                },
                status_code=self.commit_http_status,
            )
        if "/events/append" in url:
            self.evidence_bucket.append(payload)
            return make_mock_response(
                {
                    "transaction_id": payload["transaction_id"],
                    "sequence_no": payload["sequence_no"],
                    "event_hash": payload["event_hash"],
                },
                status_code=self.evidence_status_code,
            )
        if "/abort" in url:
            return make_mock_response({"status": self.abort_status, "safe_state_executed": True})

        return make_mock_response({})


def test_happy_path_committed():
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=ConfigurableMockClient):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-001", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "COMMITTED"


def test_schema_invalid_returns_422():
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=ConfigurableMockClient):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={
                "transaction_id": "tx-002",
                "asset_id": "reactor_01",
                "proof_package": {"schema_version": "1.0"},
            },
            headers=HEADERS,
        )
        assert response.status_code == 422


def test_policy_mismatch_rejected():
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=ConfigurableMockClient):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={
                "transaction_id": "tx-003",
                "asset_id": "reactor_01",
                "proof_package": build_proof(DEFAULT_SENSOR_HASH, policy_version="v-WRONG-VERSION"),
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert response.json()["reason_code"] == "INTEGRITY_POLICY_MISMATCH"


def test_timestamp_expired_rejected():
    old_timestamp = int(time.time() * 1000) - 10000
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=ConfigurableMockClient):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-004", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH, timestamp_ms=old_timestamp)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert response.json()["reason_code"] == "INTEGRITY_TIMESTAMP_EXPIRED"


def test_sensor_hash_mismatch_rejected_before_safety_and_2pc():
    mock_client = ConfigurableMockClient()
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", return_value=mock_client):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={
                "transaction_id": "tx-004b",
                "asset_id": "reactor_01",
                "proof_package": build_proof("a" * 64),
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["reason_code"] == "INTEGRITY_SENSOR_HASH_MISMATCH"

        called_paths = [call[1] for call in mock_client.calls]
        assert not any("/validate" in path for path in called_paths)
        assert not any("/prepare" in path for path in called_paths)
        assert not any("/commit" in path for path in called_paths)


def test_safety_unsafe_returns_alternative_actions():
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(safety_verdict="UNSAFE", **kwargs)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-005", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UNSAFE"
        assert data["reason_code"] == "SAFETY_UNSAFE"
        assert len(data["alternative_actions"]) == 2


def test_lock_denied_aborted():
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(prepare_status="LOCK_DENIED", **kwargs)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-006", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ABORTED"
        assert response.json()["reason_code"] == "LOCK_DENIED"


def test_commit_timeout_aborted():
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(commit_status="TIMEOUT", **kwargs)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-007", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ABORTED"
        assert response.json()["reason_code"] == "COMMIT_TIMEOUT"


def test_commit_execution_failed_returns_aborted_and_records_evidence():
    evidence_bucket = []
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(
        commit_status="EXECUTION_FAILED",
        commit_reason="modbus write failed",
        commit_safe_state_executed=True,
        evidence_bucket=evidence_bucket,
        **kwargs,
    )
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-007b", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ABORTED"
        assert response.json()["reason_code"] == "COMMIT_FAILED"
        stages = [event["stage"] for event in evidence_bucket]
        assert "COMMIT_FAILED" in stages
        assert "COMMIT_ACK" not in stages


def test_commit_transport_error_returns_error_and_records_commit_error_evidence():
    evidence_bucket = []
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(
        commit_http_status=503,
        commit_reason="ot unavailable",
        evidence_bucket=evidence_bucket,
        **kwargs,
    )
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-007c", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ERROR"
        assert response.json()["reason_code"] == "COMMIT_ERROR"
        stages = [event["stage"] for event in evidence_bucket]
        assert "COMMIT_ERROR" in stages
        assert "COMMIT_FAILED" not in stages
        assert "COMMIT_ACK" not in stages


def test_reverify_hash_mismatch_aborts_and_never_commits():
    evidence_bucket = []
    reverify_sensor = {"temperature": 151.0, "pressure": 1.5}
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(
        evidence_bucket=evidence_bucket,
        sensor_sequence=[DEFAULT_SENSOR, reverify_sensor],
        **kwargs,
    )

    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-008", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ABORTED"
        assert data["reason_code"] == "REVERIFY_HASH_MISMATCH"
        assert len(data["alternative_actions"]) == 2

        stages = [event["stage"] for event in evidence_bucket]
        assert "REVERIFY_FAILED" in stages
        assert "COMMIT_ACK" not in stages


def test_evidence_non_2xx_fails_hard():
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(evidence_status_code=503, **kwargs)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app, raise_server_exceptions=False)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-009", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 500


def test_prepare_uses_policy_lock_ttl():
    mock_client = ConfigurableMockClient()
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", return_value=mock_client):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-010", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        prepare_calls = [call for call in mock_client.calls if call[0] == "POST" and "/prepare" in call[1]]
        assert prepare_calls[0][2]["lock_ttl_ms"] == DEFAULT_ASSET_PROFILE["execution"]["lock_ttl_ms"]


def test_evidence_chain_recorded_for_happy_path():
    evidence_bucket = []
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(evidence_bucket=evidence_bucket, **kwargs)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-011", "asset_id": "reactor_01", "proof_package": build_proof(DEFAULT_SENSOR_HASH)},
            headers=HEADERS,
        )
        assert response.status_code == 200
        stages = [event["stage"] for event in evidence_bucket]
        assert stages == [
            "RECEIVED",
            "SCHEMA_VALIDATED",
            "INTEGRITY_PASSED",
            "SAFETY_PASSED",
            "PREPARE_LOCK_GRANTED",
            "REVERIFY_PASSED",
            "COMMIT_ACK",
        ]

        for idx in range(1, len(evidence_bucket)):
            assert evidence_bucket[idx]["prev_hash"] == evidence_bucket[idx - 1]["event_hash"]
