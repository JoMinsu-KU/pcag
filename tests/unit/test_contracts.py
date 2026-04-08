"""Contract tests for Pydantic models."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.core.contracts.admin import (
    CreatePolicyRequest,
    CreatePolicyResponse,
    HealthResponse,
    PluginsListResponse,
    UpdateAssetPolicyRequest,
    UpdateAssetPolicyResponse,
)
from pcag.core.contracts.common import ErrorResponse
from pcag.core.contracts.evidence import EvidenceAppendRequest, TransactionEvidenceResponse
from pcag.core.contracts.gateway import ControlRequest, ControlResponse
from pcag.core.contracts.ot_interface import (
    AbortRequest,
    AbortResponse,
    CommitRequest,
    CommitResponse,
    EstopRequest,
    EstopResponse,
    PrepareRequest,
    PrepareResponse,
)
from pcag.core.contracts.policy import ActivePolicyResponse, AssetPolicyProfileResponse, PolicyDocumentResponse
from pcag.core.contracts.proof_package import ProofPackage
from pcag.core.contracts.safety import (
    ConsensusDetailsResponse,
    SafetyValidateRequest,
    SafetyValidateResponse,
    ValidatorVerdictResponse,
)
from pcag.core.models.policy import AssetPolicyProfile
from pcag.core.contracts.sensor import SensorSnapshotResponse


def sample_proof_package() -> dict:
    return {
        "schema_version": "1.0",
        "policy_version_id": "v2025-03-01",
        "timestamp_ms": 1740000000000,
        "sensor_snapshot_hash": "a" * 64,
        "sensor_reliability_index": 0.95,
        "action_sequence": [{"action_type": "set_heater", "params": {"value": 90}}],
        "safety_verification_summary": {"checks": [], "assumptions": [], "warnings": []},
    }


def test_proof_package_contract():
    proof = ProofPackage(**sample_proof_package())
    assert proof.sensor_reliability_index == 0.95


def test_control_request():
    req = ControlRequest(transaction_id="tx-001", asset_id="reactor_01", proof_package=sample_proof_package())
    assert req.transaction_id == "tx-001"
    assert req.proof_package.policy_version_id == "v2025-03-01"


def test_control_response_committed():
    resp = ControlResponse(transaction_id="tx-001", status="COMMITTED", evidence_ref="ev-001")
    assert resp.status == "COMMITTED"


def test_control_response_with_alternatives():
    resp = ControlResponse(
        transaction_id="tx-001",
        status="ABORTED",
        reason_code="REVERIFY_HASH_MISMATCH",
        alternative_action={"action_type": "stop", "params": {}},
        alternative_actions=[
            {
                "proposal_id": "safe-state-0",
                "action_type": "set_heater_output",
                "params": {"value": 0},
                "rationale": "Derived from policy execution.safe_state for REVERIFY_HASH_MISMATCH",
                "source": "policy.safe_state",
            }
        ],
    )
    assert resp.alternative_actions[0].action_type == "set_heater_output"


def test_safety_validate_request():
    req = SafetyValidateRequest(
        transaction_id="tx-001",
        asset_id="reactor_01",
        policy_version_id="v2025-01",
        action_sequence=[{"action_type": "set_heater", "params": {"value": 90}}],
        current_sensor_snapshot={"temperature": 150},
    )
    assert req.asset_id == "reactor_01"


def test_safety_validate_response():
    resp = SafetyValidateResponse(
        transaction_id="tx-001",
        final_verdict="SAFE",
        validators={
            "rules": ValidatorVerdictResponse(verdict="SAFE", details={}),
            "cbf": ValidatorVerdictResponse(verdict="SAFE", details={"min_barrier_value": 30.0}),
            "simulation": ValidatorVerdictResponse(verdict="INDETERMINATE", details={"reason": "simulation_disabled"}),
        },
        consensus_details=ConsensusDetailsResponse(
            mode="WEIGHTED",
            weights_used={"rules": 0.533, "cbf": 0.467, "simulation": 0.0},
            score=0.75,
            threshold=0.5,
            explanation="Renormalized (sim INDETERMINATE)",
        ),
    )
    assert resp.final_verdict == "SAFE"


def test_policy_contracts():
    active = ActivePolicyResponse(policy_version_id="v2025-03-01")
    document = PolicyDocumentResponse(
        policy_version_id="v2025-03-01",
        issued_at_ms=1740000000000,
        global_policy={"hash": {"algorithm": "sha256"}},
        assets={"reactor_01": {"sil_level": 2}},
    )
    asset = AssetPolicyProfileResponse(
        policy_version_id="v2025-03-01",
        asset_id="reactor_01",
        profile={"sil_level": 2},
    )
    assert active.policy_version_id == document.policy_version_id == asset.policy_version_id


def test_policy_model_accepts_collision_config():
    profile = AssetPolicyProfile(
        asset_id="robot_arm_01",
        sil_level=2,
        sensor_source="isaac_sim_sensor",
        ot_executor="mock_executor",
        consensus={"mode": "WEIGHTED"},
        integrity={"timestamp_max_age_ms": 5000},
        ruleset=[],
        simulation={
            "engine": "isaac_sim",
            "collision": {
                "enabled": True,
                "probe_radius_m": 0.05,
                "forbidden_objects": [
                    {"object_id": "fixture_a", "center": [0.5, 0.0, 0.5], "scale": [0.1, 0.1, 0.1]}
                ],
            },
        },
        execution={},
    )
    assert profile.simulation.collision.enabled is True
    assert profile.simulation.collision.forbidden_objects[0].object_id == "fixture_a"


def test_sensor_snapshot_response():
    resp = SensorSnapshotResponse(
        asset_id="reactor_01",
        snapshot_id="snap_001",
        timestamp_ms=1740000000000,
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        sensor_snapshot_hash="a" * 64,
        sensor_reliability_index=0.95,
    )
    assert resp.sensor_reliability_index == 0.95


def test_prepare_commit_abort_estop_contracts():
    assert PrepareRequest(transaction_id="tx-001", asset_id="reactor_01", lock_ttl_ms=5000).lock_ttl_ms == 5000
    assert PrepareResponse(transaction_id="tx-001", status="LOCK_GRANTED", lock_expires_at_ms=1740000005000).status == "LOCK_GRANTED"
    assert CommitRequest(transaction_id="tx-001", asset_id="reactor_01", action_sequence=[]).asset_id == "reactor_01"
    assert CommitResponse(transaction_id="tx-001", status="ACK", executed_at_ms=1740000001000).status == "ACK"
    assert CommitResponse(transaction_id="tx-001", status="EXECUTION_FAILED", reason="modbus write error").reason == "modbus write error"
    assert AbortRequest(transaction_id="tx-001", asset_id="reactor_01", reason="REVERIFY_FAILED").reason == "REVERIFY_FAILED"
    assert AbortResponse(transaction_id="tx-001", status="ABORTED", safe_state_executed=True).safe_state_executed is True
    assert AbortResponse(transaction_id="tx-001", status="ABORT_REJECTED", reason="Cannot abort committed transaction").reason is not None
    assert EstopRequest(asset_id="reactor_01", reason="Emergency button pressed").asset_id == "reactor_01"
    assert EstopResponse(asset_id="reactor_01", status="ESTOP_EXECUTED", timestamp_ms=1740000000000).status == "ESTOP_EXECUTED"


def test_evidence_contracts():
    req = EvidenceAppendRequest(
        transaction_id="tx-001",
        sequence_no=0,
        stage="RECEIVED",
        timestamp_ms=1740000000000,
        payload={"proof_package": {}},
        input_hash="b" * 64,
        prev_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        event_hash="c" * 64,
    )
    resp = TransactionEvidenceResponse(transaction_id="tx-001", events=[], chain_valid=True)
    assert req.stage == "RECEIVED"
    assert resp.chain_valid is True


def test_admin_contracts():
    create_req = CreatePolicyRequest(
        policy_version_id="v2025-03-01",
        global_policy={"hash": {"algorithm": "sha256"}},
        assets={"reactor_01": {"sil_level": 3}},
    )
    create_resp = CreatePolicyResponse(policy_version_id="v2025-03-01", created_at_ms=1740000000000)
    update_req = UpdateAssetPolicyRequest(profile={"sil_level": 4}, new_policy_version_id="v2025-03-02", change_reason="safety tightening")
    update_resp = UpdateAssetPolicyResponse(
        policy_version_id="v2025-03-02",
        asset_id="reactor_01",
        updated_at_ms=1740000001000,
        previous_policy_version_id="v2025-03-01",
    )
    assert create_req.policy_version_id == create_resp.policy_version_id
    assert update_req.new_policy_version_id == update_resp.policy_version_id


def test_health_plugins_and_error_contracts():
    health = HealthResponse(
        status="healthy",
        services=[
            {"name": "gateway", "status": "healthy", "url": "http://localhost:8000"},
            {"name": "safety_cluster", "status": "healthy", "url": "http://localhost:8001"},
        ],
        uptime_s=3600.0,
    )
    plugins = PluginsListResponse(
        simulation=[{"name": "none", "module": "pcag.plugins.simulation.none_backend", "plugin_class": "NoneBackend", "status": "active"}],
        sensor=[],
        executor=[],
    )
    error = ErrorResponse(error={"code": "SCHEMA_INVALID", "message": "Missing field", "details": {"field": "action_sequence"}})
    assert len(health.services) == 2
    assert len(plugins.simulation) == 1
    assert error.error.code == "SCHEMA_INVALID"


def test_invalid_sensor_hash_rejected():
    with pytest.raises(Exception):
        SensorSnapshotResponse(
            asset_id="x",
            snapshot_id="s",
            timestamp_ms=0,
            sensor_snapshot={},
            sensor_snapshot_hash="short",
            sensor_reliability_index=0.5,
        )


def test_invalid_proof_package_rejected():
    with pytest.raises(Exception):
        ProofPackage(
            schema_version="1.0",
            policy_version_id="v1",
            timestamp_ms=0,
            sensor_snapshot_hash="bad",
            sensor_reliability_index=1.5,
            action_sequence=[],
            safety_verification_summary={},
        )
