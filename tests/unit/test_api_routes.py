"""Tests for FastAPI route signatures."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("PCAG_DATABASE_URL", "sqlite:///./test_api_routes_bootstrap.db")

from pcag.core.database.engine import Base, get_db


TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=TEST_ENGINE)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)


def test_gateway_route_exists():
    from pcag.apps.gateway.main import app

    client = TestClient(app)
    with patch("pcag.apps.gateway.routes.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = MagicMock()
        resp = client.post(
            "/v1/control-requests",
            json={"transaction_id": "tx-001", "asset_id": "reactor_01", "proof_package": {"test": True}},
            headers={"X-API-Key": "pcag-agent-key-001"},
        )
        assert resp.status_code == 422


def test_safety_route_exists():
    from pcag.apps.safety_cluster.main import app

    client = TestClient(app)
    with patch("pcag.apps.safety_cluster.routes.run_safety_validation") as mock_run:
        mock_run.return_value = {
            "transaction_id": "tx-001",
            "final_verdict": "SAFE",
            "validators": {
                "rules": {"verdict": "SAFE", "details": {}},
                "cbf": {"verdict": "SAFE", "details": {}},
                "simulation": {"verdict": "SAFE", "details": {}},
            },
            "consensus_details": {"mode": "WEIGHTED", "weights_used": {}, "score": 1.0, "threshold": 0.5, "explanation": "ok"},
        }
        resp = client.post(
            "/v1/validate",
            json={
                "transaction_id": "tx-001",
                "asset_id": "reactor_01",
                "policy_version_id": "v1",
                "action_sequence": [],
                "current_sensor_snapshot": {"temperature": 100},
            },
        )
    assert resp.status_code == 200


def test_policy_routes_exist():
    from pcag.apps.policy_store.main import app

    app.dependency_overrides[get_db] = override_get_db
    setup_db()

    client = TestClient(app)
    assert client.get("/v1/policies/active").status_code == 404
    assert client.get("/v1/policies/v2025-03-01").status_code == 404


def test_sensor_route_exists():
    from pcag.apps.sensor_gateway.main import app
    from pcag.apps.sensor_gateway import routes

    mock_source = MagicMock()
    mock_source.read_snapshot.return_value = {"temperature": 100.0}
    mock_source.get_source_name.return_value = "modbus"
    routes._sensor_source = mock_source
    client = TestClient(app)
    assert client.get("/v1/assets/reactor_01/snapshots/latest").status_code == 200


def test_ot_interface_routes_exist():
    from pcag.apps.ot_interface.main import app

    client = TestClient(app)
    with patch("pcag.apps.ot_interface.routes._state_machine") as mock_sm, patch("pcag.apps.ot_interface.routes.ExecutorManager") as mock_em:
        executor = MagicMock()
        executor.execute.return_value = True
        executor.safe_state.return_value = True
        mock_em.get_executor.return_value = executor
        mock_sm.prepare.return_value = {"status": "LOCK_GRANTED", "lock_expires_at_ms": 1}
        mock_sm.check_commit_ready.return_value = {"status": "READY"}
        mock_sm.finalize_commit.return_value = {"status": "COMMITTED"}
        mock_sm.abort.return_value = {"status": "ABORTED"}
        mock_sm.estop.return_value = {"status": "ESTOP_EXECUTED"}

        assert client.post("/v1/prepare", json={"transaction_id": "t", "asset_id": "a", "lock_ttl_ms": 5000}).status_code == 200
        assert client.post("/v1/commit", json={"transaction_id": "t", "asset_id": "a", "action_sequence": []}).status_code == 200
        assert client.post("/v1/abort", json={"transaction_id": "t", "asset_id": "a", "reason": "test"}).status_code == 200
        assert client.post("/v1/estop", json={"asset_id": "a", "reason": "test"}).status_code == 200


def test_plc_adapter_routes_exist():
    from pcag.apps.plc_adapter.main import app

    client = TestClient(app)
    with patch("pcag.apps.plc_adapter.routes._service") as mock_service:
        mock_service.get_health.return_value = {"status": "OK", "connections": []}
        mock_service.read_snapshot.return_value = ({"temperature": 100.0}, "127.0.0.1:503")
        mock_service.execute_actions.return_value = (True, None, "127.0.0.1:503")
        mock_service.safe_state.return_value = (True, None, "127.0.0.1:503")

        assert client.get("/v1/health").status_code == 200
        assert client.get("/v1/assets/reactor_01/snapshots/latest").status_code == 200
        assert client.post(
            "/v1/execute",
            json={"transaction_id": "t", "asset_id": "reactor_01", "action_sequence": []},
        ).status_code == 200
        assert client.post("/v1/safe-state", json={"asset_id": "reactor_01"}).status_code == 200


def test_dashboard_routes_exist():
    from pcag.apps.dashboard.main import app
    from pcag.apps.dashboard.routes import stream

    client = TestClient(app)
    with patch("pcag.apps.dashboard.routes._monitor.build_snapshot", new=AsyncMock(return_value={"generated_at": "2026-03-13T18:00:00", "overview": {}, "services": []})):
        assert client.get("/").status_code == 200
        assert client.get("/v1/health").status_code == 200
        resp = client.get("/v1/snapshot")
        assert resp.status_code == 200
        assert resp.json()["generated_at"] == "2026-03-13T18:00:00"
        stream_resp = asyncio.run(stream())
        assert stream_resp.media_type == "text/event-stream"


def test_evidence_routes_exist():
    from pcag.apps.evidence_ledger.main import app

    app.dependency_overrides[get_db] = override_get_db
    setup_db()

    client = TestClient(app)
    assert (
        client.post(
            "/v1/events/append",
            json={
                "transaction_id": "t",
                "sequence_no": 0,
                "stage": "RECEIVED",
                "timestamp_ms": 0,
                "payload": {},
                "input_hash": "a" * 64,
                "prev_hash": "b" * 64,
                "event_hash": "c" * 64,
            },
        ).status_code
        == 200
    )
    assert client.get("/v1/transactions/tx-001").status_code == 200


def test_admin_routes_exist():
    from pcag.apps.policy_admin.main import app

    app.dependency_overrides[get_db] = override_get_db
    setup_db()

    client = TestClient(app)
    assert client.get("/v1/admin/health").status_code == 200
    assert client.get("/v1/admin/plugins", headers={"X-Admin-Key": "pcag-admin-key-001"}).status_code == 200
    assert client.post("/v1/admin/policies", json={}, headers={"X-Admin-Key": "pcag-admin-key-001"}).status_code == 422


def test_gateway_validation_error():
    from pcag.apps.gateway.main import app

    client = TestClient(app)
    resp = client.post("/v1/control-requests", json={"transaction_id": "tx-001"}, headers={"X-API-Key": "pcag-agent-key-001"})
    assert resp.status_code == 422
