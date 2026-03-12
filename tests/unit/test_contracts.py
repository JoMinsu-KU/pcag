"""Tests for service contracts — verify all Pydantic models are valid."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.core.contracts.gateway import ControlRequest, ControlResponse
from pcag.core.contracts.safety import SafetyValidateRequest, SafetyValidateResponse, ValidatorVerdictResponse, ConsensusDetailsResponse
from pcag.core.contracts.policy import ActivePolicyResponse, PolicyDocumentResponse, AssetPolicyProfileResponse
from pcag.core.contracts.sensor import SensorSnapshotResponse
from pcag.core.contracts.ot_interface import PrepareRequest, PrepareResponse, CommitRequest, CommitResponse, AbortRequest, AbortResponse, EstopRequest, EstopResponse
from pcag.core.contracts.evidence import EvidenceAppendRequest, EvidenceAppendResponse, TransactionEvidenceResponse
from pcag.core.contracts.admin import CreatePolicyRequest, CreatePolicyResponse, HealthResponse, PluginsListResponse
from pcag.core.contracts.common import ErrorResponse
import pytest

def test_control_request():
    req = ControlRequest(
        transaction_id="tx-001",
        asset_id="reactor_01",
        proof_package={"schema_version": "1.0", "action_sequence": []}
    )
    assert req.transaction_id == "tx-001"

def test_control_response_committed():
    resp = ControlResponse(transaction_id="tx-001", status="COMMITTED", evidence_ref="ev-001")
    assert resp.status == "COMMITTED"

def test_control_response_rejected():
    resp = ControlResponse(transaction_id="tx-001", status="REJECTED", reason="Schema invalid", reason_code="SCHEMA_INVALID")
    assert resp.reason_code == "SCHEMA_INVALID"

def test_safety_validate_request():
    req = SafetyValidateRequest(
        transaction_id="tx-001",
        asset_id="reactor_01",
        policy_version_id="v2025-01",
        action_sequence=[{"action_type": "set_heater", "params": {"value": 90}}],
        current_sensor_snapshot={"temperature": 150}
    )
    assert req.asset_id == "reactor_01"

def test_safety_validate_response():
    resp = SafetyValidateResponse(
        transaction_id="tx-001",
        final_verdict="SAFE",
        validators={
            "rules": ValidatorVerdictResponse(verdict="SAFE", details={}),
            "cbf": ValidatorVerdictResponse(verdict="SAFE", details={"min_barrier_value": 30.0}),
            "simulation": ValidatorVerdictResponse(verdict="INDETERMINATE", details={"reason": "simulation_disabled"})
        },
        consensus_details=ConsensusDetailsResponse(
            mode="WEIGHTED",
            weights_used={"rules": 0.533, "cbf": 0.467, "simulation": 0.0},
            score=0.75,
            threshold=0.5,
            explanation="Renormalized (sim INDETERMINATE)"
        )
    )
    assert resp.final_verdict == "SAFE"
    assert resp.validators["simulation"].verdict == "INDETERMINATE"

def test_sensor_snapshot_response():
    resp = SensorSnapshotResponse(
        asset_id="reactor_01",
        snapshot_id="snap_001",
        timestamp_ms=1740000000000,
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        sensor_snapshot_hash="a" * 64,
        sensor_reliability_index=0.95
    )
    assert resp.sensor_reliability_index == 0.95

def test_prepare_request_response():
    req = PrepareRequest(transaction_id="tx-001", asset_id="reactor_01", lock_ttl_ms=5000)
    resp = PrepareResponse(transaction_id="tx-001", status="LOCK_GRANTED", lock_expires_at_ms=1740000005000)
    assert resp.status == "LOCK_GRANTED"

def test_commit_request_response():
    req = CommitRequest(transaction_id="tx-001", asset_id="reactor_01", action_sequence=[{"action_type": "set_heater", "params": {"value": 90}}])
    resp = CommitResponse(transaction_id="tx-001", status="ACK", executed_at_ms=1740000001000)
    assert resp.status == "ACK"

def test_abort_request_response():
    req = AbortRequest(transaction_id="tx-001", asset_id="reactor_01", reason="REVERIFY_FAILED")
    resp = AbortResponse(transaction_id="tx-001", status="ABORTED", safe_state_executed=True)
    assert resp.safe_state_executed == True

def test_estop_request_response():
    req = EstopRequest(asset_id="reactor_01", reason="Emergency button pressed")
    resp = EstopResponse(asset_id="reactor_01", status="ESTOP_EXECUTED", timestamp_ms=1740000000000)
    assert resp.status == "ESTOP_EXECUTED"

def test_evidence_append():
    req = EvidenceAppendRequest(
        transaction_id="tx-001",
        sequence_no=0,
        stage="RECEIVED",
        timestamp_ms=1740000000000,
        payload={"proof_package": {}},
        input_hash="b" * 64,
        prev_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        event_hash="c" * 64
    )
    assert req.stage == "RECEIVED"

def test_evidence_transaction():
    resp = TransactionEvidenceResponse(
        transaction_id="tx-001",
        events=[],
        chain_valid=True
    )
    assert resp.chain_valid == True

def test_error_response():
    resp = ErrorResponse(error={"code": "SCHEMA_INVALID", "message": "Missing field", "details": {"field": "action_sequence"}})
    assert resp.error.code == "SCHEMA_INVALID"

def test_health_response():
    resp = HealthResponse(
        status="healthy",
        services=[
            {"name": "gateway", "status": "healthy", "url": "http://localhost:8000"},
            {"name": "safety_cluster", "status": "healthy", "url": "http://localhost:8001"}
        ],
        uptime_s=3600.0
    )
    assert len(resp.services) == 2

def test_create_policy():
    req = CreatePolicyRequest(
        policy_version_id="v2025-03-01",
        global_policy={"hash": {"algorithm": "sha256"}},
        assets={"reactor_01": {"sil_level": 3}}
    )
    resp = CreatePolicyResponse(policy_version_id="v2025-03-01", created_at_ms=1740000000000)
    assert resp.policy_version_id == "v2025-03-01"

def test_plugins_list():
    resp = PluginsListResponse(
        simulation=[{"name": "none", "module": "pcag.plugins.simulation.none_backend", "plugin_class": "NoneBackend", "status": "active"}],
        sensor=[],
        executor=[]
    )
    assert len(resp.simulation) == 1

def test_all_status_literals():
    """Verify all status literal values are accepted."""
    ControlResponse(transaction_id="t", status="COMMITTED")
    ControlResponse(transaction_id="t", status="REJECTED")
    ControlResponse(transaction_id="t", status="UNSAFE")
    ControlResponse(transaction_id="t", status="ABORTED")
    
    PrepareResponse(transaction_id="t", status="LOCK_GRANTED")
    PrepareResponse(transaction_id="t", status="LOCK_DENIED")
    
    CommitResponse(transaction_id="t", status="ACK")
    CommitResponse(transaction_id="t", status="ALREADY_COMMITTED")
    CommitResponse(transaction_id="t", status="TIMEOUT")

def test_invalid_sensor_hash_rejected():
    """Sensor hash must be exactly 64 hex characters."""
    with pytest.raises(Exception):
        SensorSnapshotResponse(
            asset_id="x", snapshot_id="s", timestamp_ms=0,
            sensor_snapshot={}, sensor_snapshot_hash="short",
            sensor_reliability_index=0.5
        )
