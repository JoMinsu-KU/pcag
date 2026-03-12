"""
Evidence Ledger DB 통합 테스트
===============================
PostgreSQL(테스트 시 in-memory SQLite)을 사용하여 
증거 이벤트의 CRUD + 해시 체인 검증을 테스트합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_evidence_ledger_db.py -v
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pcag.core.database.engine import Base, get_db
from pcag.core.utils.hash_utils import GENESIS_HASH, compute_event_hash, compute_sensor_hash
from pcag.apps.evidence_ledger.main import app


# 테스트용 in-memory SQLite DB
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """각 테스트 전에 DB 테이블 초기화"""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _make_event(tx_id, seq, stage, payload, prev_hash):
    """테스트용 증거 이벤트 생성 헬퍼"""
    input_hash = compute_sensor_hash(payload)
    event_hash = compute_event_hash(prev_hash, payload)
    return {
        "transaction_id": tx_id,
        "sequence_no": seq,
        "stage": stage,
        "timestamp_ms": int(time.time() * 1000),
        "payload": payload,
        "input_hash": input_hash,
        "prev_hash": prev_hash,
        "event_hash": event_hash
    }


def test_append_single_event():
    """단일 증거 이벤트 추가"""
    event = _make_event("tx-001", 0, "RECEIVED", {"test": True}, GENESIS_HASH)
    resp = client.post("/v1/events/append", json=event)
    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_id"] == "tx-001"
    assert data["sequence_no"] == 0


def test_append_chain():
    """해시 체인으로 연결된 3개 이벤트 추가"""
    prev = GENESIS_HASH
    
    for i, stage in enumerate(["RECEIVED", "SCHEMA_VALIDATED", "INTEGRITY_PASSED"]):
        payload = {"stage": stage, "step": i}
        event = _make_event("tx-002", i, stage, payload, prev)
        resp = client.post("/v1/events/append", json=event)
        assert resp.status_code == 200
        prev = event["event_hash"]  # 다음 이벤트의 prev_hash


def test_get_transaction_events():
    """트랜잭션 증거 조회"""
    prev = GENESIS_HASH
    for i, stage in enumerate(["RECEIVED", "SCHEMA_VALIDATED"]):
        event = _make_event("tx-003", i, stage, {"step": i}, prev)
        client.post("/v1/events/append", json=event)
        prev = event["event_hash"]
    
    resp = client.get("/v1/transactions/tx-003")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 2
    assert data["events"][0]["stage"] == "RECEIVED"
    assert data["events"][1]["stage"] == "SCHEMA_VALIDATED"


def test_chain_valid():
    """해시 체인 무결성 검증 — 정상"""
    prev = GENESIS_HASH
    for i, stage in enumerate(["RECEIVED", "SCHEMA_VALIDATED", "INTEGRITY_PASSED"]):
        event = _make_event("tx-004", i, stage, {"step": i}, prev)
        client.post("/v1/events/append", json=event)
        prev = event["event_hash"]
    
    resp = client.get("/v1/transactions/tx-004")
    assert resp.json()["chain_valid"] == True


def test_empty_transaction():
    """존재하지 않는 트랜잭션 조회 — 빈 결과"""
    resp = client.get("/v1/transactions/tx-nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 0
    assert data["chain_valid"] == True  # 이벤트 없으면 유효


def test_duplicate_event_rejected():
    """중복 이벤트 (같은 tx_id + seq) → 거부"""
    event = _make_event("tx-005", 0, "RECEIVED", {"test": True}, GENESIS_HASH)
    resp1 = client.post("/v1/events/append", json=event)
    assert resp1.status_code == 200
    
    resp2 = client.post("/v1/events/append", json=event)
    assert resp2.status_code == 409  # Conflict


def test_full_pipeline_evidence():
    """전체 파이프라인 증거 체인 (7개 이벤트)"""
    stages = [
        "RECEIVED", "SCHEMA_VALIDATED", "INTEGRITY_PASSED",
        "SAFETY_PASSED", "PREPARE_LOCK_GRANTED", "REVERIFY_PASSED", "COMMIT_ACK"
    ]
    
    prev = GENESIS_HASH
    for i, stage in enumerate(stages):
        event = _make_event("tx-006", i, stage, {"stage": stage, "step": i}, prev)
        resp = client.post("/v1/events/append", json=event)
        assert resp.status_code == 200
        prev = event["event_hash"]
    
    # 전체 조회 + 체인 검증
    resp = client.get("/v1/transactions/tx-006")
    data = resp.json()
    assert len(data["events"]) == 7
    assert data["chain_valid"] == True
    
    # 각 단계 순서 확인
    for i, stage in enumerate(stages):
        assert data["events"][i]["stage"] == stage
        assert data["events"][i]["sequence_no"] == i


def test_multiple_transactions_independent():
    """여러 트랜잭션이 독립적으로 관리됨"""
    # tx-A
    event_a = _make_event("tx-A", 0, "RECEIVED", {"tx": "A"}, GENESIS_HASH)
    client.post("/v1/events/append", json=event_a)
    
    # tx-B
    event_b = _make_event("tx-B", 0, "RECEIVED", {"tx": "B"}, GENESIS_HASH)
    client.post("/v1/events/append", json=event_b)
    
    # 각각 독립 조회
    resp_a = client.get("/v1/transactions/tx-A")
    resp_b = client.get("/v1/transactions/tx-B")
    
    assert len(resp_a.json()["events"]) == 1
    assert len(resp_b.json()["events"]) == 1
    assert resp_a.json()["events"][0]["payload"]["tx"] == "A"
    assert resp_b.json()["events"][0]["payload"]["tx"] == "B"
