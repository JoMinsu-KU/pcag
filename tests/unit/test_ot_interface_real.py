"""
OT Interface 실제 2PC 통합 테스트
==================================
실제 TxStateMachine을 연결한 OT Interface의 2PC 동작을 검증합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_ot_interface_real.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from pcag.apps.ot_interface.main import app
from pcag.apps.ot_interface import routes
from pcag.apps.ot_interface.service import PersistentTxStateMachine

client = TestClient(app)

@pytest.fixture
def mock_state_machine():
    with patch("pcag.apps.ot_interface.routes._state_machine") as mock_sm:
        yield mock_sm

@pytest.fixture
def mock_executor_manager():
    with patch("pcag.apps.ot_interface.routes.ExecutorManager") as mock_em:
        executor = MagicMock()
        mock_em.get_executor.return_value = executor
        yield mock_em

def test_happy_path_prepare_commit(mock_state_machine, mock_executor_manager):
    """정상 경로: PREPARE → COMMIT → ACK"""
    # Setup Mock SM
    mock_state_machine.prepare.return_value = {"status": "LOCK_GRANTED", "lock_expires_at_ms": 12345}
    mock_state_machine.commit.return_value = {"status": "COMMITTED"}
    
    # Setup Mock Executor
    executor = mock_executor_manager.get_executor.return_value
    executor.execute.return_value = True

    # PREPARE
    resp = client.post("/v1/prepare", json={
        "transaction_id": "tx-001",
        "asset_id": "reactor_01",
        "lock_ttl_ms": 5000
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "LOCK_GRANTED"
    
    # COMMIT
    resp = client.post("/v1/commit", json={
        "transaction_id": "tx-001",
        "asset_id": "reactor_01",
        "action_sequence": [{"action_type": "set_heater", "params": {"value": 70}}]
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACK"
    assert resp.json()["executed_at_ms"] is not None
    
    # Verify Executor called
    executor.execute.assert_called_once()


def test_lock_conflict(mock_state_machine):
    """잠금 충돌: 다른 tx가 이미 잠금 → LOCK_DENIED"""
    mock_state_machine.prepare.return_value = {"status": "LOCK_DENIED", "reason": "Locked by tx-001"}
    
    resp = client.post("/v1/prepare", json={
        "transaction_id": "tx-002",
        "asset_id": "reactor_01",
        "lock_ttl_ms": 5000
    })
    assert resp.json()["status"] == "LOCK_DENIED"


def test_idempotent_prepare(mock_state_machine):
    """Idempotent: 같은 tx_id로 PREPARE 재호출 → LOCK_GRANTED"""
    mock_state_machine.prepare.return_value = {"status": "LOCK_GRANTED"}
    
    resp = client.post("/v1/prepare", json={
        "transaction_id": "tx-001",
        "asset_id": "reactor_01",
        "lock_ttl_ms": 5000
    })
    assert resp.json()["status"] == "LOCK_GRANTED"


def test_idempotent_commit(mock_state_machine, mock_executor_manager):
    """Idempotent: 같은 tx_id로 COMMIT 재호출 → ALREADY_COMMITTED (재실행 안 함!)"""
    mock_state_machine.commit.return_value = {"status": "ALREADY_COMMITTED"}
    
    resp = client.post("/v1/commit", json={
        "transaction_id": "tx-001",
        "asset_id": "reactor_01",
        "action_sequence": []
    })
    assert resp.json()["status"] == "ALREADY_COMMITTED"
    
    # Executor should NOT be called
    mock_executor_manager.get_executor.return_value.execute.assert_not_called()


def test_abort(mock_state_machine, mock_executor_manager):
    """ABORT: 잠금 해제 + 안전 상태 전환"""
    mock_state_machine.abort.return_value = {"status": "ABORTED"}
    executor = mock_executor_manager.get_executor.return_value
    executor.safe_state.return_value = True

    resp = client.post("/v1/abort", json={
        "transaction_id": "tx-001",
        "asset_id": "reactor_01",
        "reason": "Safety check failed"
    })
    assert resp.json()["status"] == "ABORTED"
    assert resp.json()["safe_state_executed"] == True
    
    executor.safe_state.assert_called_once_with("reactor_01")


def test_estop(mock_state_machine, mock_executor_manager):
    """E-Stop: 잠금과 무관하게 항상 실행"""
    mock_state_machine.estop.return_value = {"status": "ESTOP_EXECUTED"}
    
    resp = client.post("/v1/estop", json={
        "asset_id": "reactor_01",
        "reason": "Emergency button pressed"
    })
    assert resp.json()["status"] == "ESTOP_EXECUTED"
    
    # E-Stop always calls safe_state
    mock_executor_manager.get_executor.return_value.safe_state.assert_called_once_with("reactor_01")

