"""
PCAG 파이프라인 통합 테스트 (Mock 서비스)
==========================================
전체 파이프라인을 Mock 서비스로 연결하여 E2E 흐름을 검증합니다.
실제 HTTP 통신 없이 FastAPI TestClient로 각 서비스를 직접 호출합니다.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from pcag.apps.gateway.main import app as gateway_app


MOCK_POLICY_VERSION = "v2025-03-04"
HEADERS = {"X-API-Key": "pcag-agent-key-001"}


# 서비스 응답을 Mock하기 위한 helper
def make_mock_response(json_data, status_code=200):
    """httpx.Response를 흉내내는 Mock 객체"""
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    return mock


class ConfigurableMockClient:
    """테스트별로 다른 응답을 반환하도록 설정 가능한 Mock 클라이언트"""
    
    def __init__(self, safety_verdict="SAFE", prepare_status="LOCK_GRANTED", 
                 commit_status="ACK", evidence_bucket=None, **kwargs):
        self.safety_verdict = safety_verdict
        self.prepare_status = prepare_status
        self.commit_status = commit_status
        # evidence_bucket이 제공되면 증거 기록 호출을 수집 (테스트 검증용)
        self.evidence_bucket = evidence_bucket if evidence_bucket is not None else []
        self.calls = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        
        if "/policies/active" in url:
            return make_mock_response({"policy_version_id": MOCK_POLICY_VERSION})
        elif "/snapshots/latest" in url:
            from pcag.core.utils.hash_utils import compute_sensor_hash
            sensor = {"temperature": 150.0, "pressure": 1.5}
            return make_mock_response({
                "asset_id": "reactor_01",
                "snapshot_id": "snap_001",
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot": sensor,
                "sensor_snapshot_hash": compute_sensor_hash(sensor),
                "sensor_reliability_index": 0.95
            })
        return make_mock_response({})
    
    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs.get("json", {})))
        
        if "/validate" in url:
            return make_mock_response({
                "transaction_id": kwargs["json"]["transaction_id"],
                "final_verdict": self.safety_verdict,
                "validators": {
                    "rules": {"verdict": self.safety_verdict, "details": {}},
                    "cbf": {"verdict": self.safety_verdict, "details": {}},
                    "simulation": {"verdict": "INDETERMINATE", "details": {"reason": "simulation_disabled"}}
                },
                "consensus_details": {
                    "mode": "WEIGHTED", "weights_used": {}, "score": 1.0 if self.safety_verdict == "SAFE" else 0.0,
                    "threshold": 0.5, "explanation": self.safety_verdict
                }
            })
        elif "/prepare" in url:
            status = self.prepare_status
            return make_mock_response({
                "transaction_id": kwargs["json"]["transaction_id"],
                "status": status,
                "lock_expires_at_ms": int(time.time() * 1000) + 5000,
                "reason": "Lock denied by OT" if status != "LOCK_GRANTED" else None
            })
        elif "/commit" in url:
            status = self.commit_status
            return make_mock_response({
                "transaction_id": kwargs["json"]["transaction_id"],
                "status": status,
                "executed_at_ms": int(time.time() * 1000)
            })
        elif "/events/append" in url:
            call_data = kwargs.get("json", {})
            self.evidence_bucket.append(call_data)
            return make_mock_response({
                "transaction_id": call_data["transaction_id"],
                "sequence_no": call_data["sequence_no"],
                "event_hash": call_data["event_hash"]
            })
        elif "/abort" in url:
             return make_mock_response({"status": "ABORTED"})

        return make_mock_response({})


# 기존 MockAsyncClient 하위 호환성 (기본값 사용)
MockAsyncClient = ConfigurableMockClient


def test_happy_path_committed():
    """정상 경로: SAFE 판정 → COMMITTED"""
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=MockAsyncClient):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-001",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "sensor_reliability_index": 0.95,
                "action_sequence": [
                    {"action_type": "set_heater_output", "params": {"value": 70}}
                ],
                "safety_verification_summary": {"checks": [], "assumptions": [], "warnings": []}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMMITTED"
        assert data["transaction_id"] == "tx-001"


def test_schema_invalid_rejected():
    """스키마 오류: 필수 필드 누락 → REJECTED"""
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=MockAsyncClient):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-002",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0"
                # 나머지 필수 필드 누락!
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["reason_code"] == "SCHEMA_INVALID"


def test_policy_mismatch_rejected():
    """정책 불일치: 잘못된 버전 → REJECTED"""
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=MockAsyncClient):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-003",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": "v-WRONG-VERSION",  # 잘못된 정책 버전
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["reason_code"] == "INTEGRITY_POLICY_MISMATCH"


def test_timestamp_expired_rejected():
    """타임스탬프 만료: 오래된 ProofPackage → REJECTED"""
    # 현재 시간보다 10초(10000ms) 이전의 타임스탬프 사용 (허용치 500ms 초과)
    old_timestamp = int(time.time() * 1000) - 10000
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=MockAsyncClient):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-004",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": old_timestamp,
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["reason_code"] == "INTEGRITY_TIMESTAMP_EXPIRED"


def test_safety_unsafe():
    """안전 검증 실패: Safety Cluster가 UNSAFE 반환 → UNSAFE"""
    # Safety Cluster가 UNSAFE를 반환하도록 설정
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(safety_verdict="UNSAFE", **kwargs)
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-005",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UNSAFE"
        assert data["reason_code"] == "SAFETY_UNSAFE"


def test_lock_denied_aborted():
    """잠금 실패: OT Interface가 LOCK_DENIED 반환 → ABORTED"""
    # OT Interface가 LOCK_DENIED를 반환하도록 설정
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(prepare_status="LOCK_DENIED", **kwargs)
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-006",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ABORTED"
        assert data["reason_code"] == "LOCK_DENIED"


def test_commit_timeout_aborted():
    """커밋 타임아웃: OT Interface가 TIMEOUT 반환 → ABORTED"""
    # OT Interface가 TIMEOUT을 반환하도록 설정
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(commit_status="TIMEOUT", **kwargs)
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-007",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ABORTED"
        assert data["reason_code"] == "COMMIT_TIMEOUT"


def test_sensor_hash_mismatch():
    """센서 해시 불일치 — 증거 패키지의 해시와 현재 센서 해시가 다름"""
    # 현재 Gateway 구현상 해시 불일치는 파이프라인을 중단시키지 않지만(timestamp, policy만 체크),
    # Evidence Ledger에 기록된 센서 해시가 실제 센서값(Mock)과 일치하는지 확인합니다.
    
    evidence_bucket = []
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(evidence_bucket=evidence_bucket, **kwargs)
    
    # ProofPackage에는 임의의 해시 "hash_mismatch_000..." 전송
    fake_hash = "f" * 64
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-008",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": fake_hash,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        # 불일치해도 현재는 통과(COMMITTED) - 미래에 정책 강화 가능
        assert response.status_code == 200
        
        # 증거 로그 확인
        # INTEGRITY_PASSED 단계에서 실제 센서 해시가 기록되었는지 확인
        integrity_events = [e for e in evidence_bucket if e["stage"] == "INTEGRITY_PASSED"]
        assert len(integrity_events) == 1
        
        # MockAsyncClient.get에서 계산된 실제 해시 가져오기
        from pcag.core.utils.hash_utils import compute_sensor_hash
        expected_sensor_data = {"temperature": 150.0, "pressure": 1.5}
        expected_hash = compute_sensor_hash(expected_sensor_data)
        
        logged_hash = integrity_events[0]["payload"]["sensor_hash"]
        assert logged_hash == expected_hash
        assert logged_hash != fake_hash  # 입력된 해시와 다름이 확인됨


def test_evidence_chain_recorded():
    """증거 체인: 정상 경로에서 모든 증거 이벤트가 기록되는지 확인"""
    evidence_bucket = []
    client_factory = lambda *args, **kwargs: ConfigurableMockClient(evidence_bucket=evidence_bucket, **kwargs)
    
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=client_factory):
        client = TestClient(gateway_app)
        response = client.post("/v1/control-requests", json={
            "transaction_id": "tx-009",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert response.status_code == 200
        
        # 필수 단계별 증거가 모두 기록되었는지 확인
        stages = [e["stage"] for e in evidence_bucket]
        expected_stages = [
            "RECEIVED", 
            "SCHEMA_VALIDATED", 
            "INTEGRITY_PASSED", 
            "SAFETY_PASSED", 
            "PREPARE_LOCK_GRANTED", 
            "REVERIFY_PASSED", 
            "COMMIT_ACK"
        ]
        
        for stage in expected_stages:
            assert stage in stages, f"Missing evidence stage: {stage}"
            
        # 체인 무결성 확인 (prev_hash 연결)
        for i in range(1, len(evidence_bucket)):
            current = evidence_bucket[i]
            prev = evidence_bucket[i-1]
            assert current["prev_hash"] == prev["event_hash"], \
                f"Chain broken at index {i}: {current['stage']}"


def test_multiple_requests_independent():
    """여러 요청: 각 요청이 독립적으로 처리되는지 확인"""
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient", side_effect=MockAsyncClient):
        client = TestClient(gateway_app)
        
        # 요청 1
        resp1 = client.post("/v1/control-requests", json={
            "transaction_id": "tx-010-A",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert resp1.status_code == 200
        assert resp1.json()["transaction_id"] == "tx-010-A"
        
        # 요청 2
        resp2 = client.post("/v1/control-requests", json={
            "transaction_id": "tx-010-B",
            "asset_id": "reactor_01",
            "proof_package": {
                "schema_version": "1.0",
                "policy_version_id": MOCK_POLICY_VERSION,
                "timestamp_ms": int(time.time() * 1000),
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [],
                "safety_verification_summary": {}
            }
        }, headers=HEADERS)
        assert resp2.status_code == 200
        assert resp2.json()["transaction_id"] == "tx-010-B"
