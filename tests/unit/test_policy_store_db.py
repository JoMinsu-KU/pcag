"""Policy Store / Policy Admin DB integration tests."""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("PCAG_DATABASE_URL", "sqlite:///./test_policy_store_bootstrap.db")

from pcag.apps.policy_admin.main import app as admin_app
from pcag.apps.policy_store.main import app as policy_app
from pcag.core.database.engine import Base, get_db


TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=TEST_ENGINE)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


policy_app.dependency_overrides[get_db] = override_get_db
admin_app.dependency_overrides[get_db] = override_get_db

policy_client = TestClient(policy_app)
admin_client = TestClient(admin_app)

ADMIN_HEADERS = {"X-Admin-Key": "pcag-admin-key-001"}

MOCK_POLICY = {
    "policy_version_id": "v2025-03-01",
    "global_policy": {"hash": {"algorithm": "sha256"}, "defaults": {"timestamp_max_age_ms": 500}},
    "assets": {
        "reactor_01": {
            "asset_id": "reactor_01",
            "sil_level": 2,
            "sensor_source": "modbus_sensor",
            "ot_executor": "mock_executor",
            "consensus": {"mode": "WEIGHTED", "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25}, "threshold": 0.5},
            "integrity": {"timestamp_max_age_ms": 500, "sensor_divergence_thresholds": []},
            "ruleset": [{"rule_id": "max_temp", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0}],
            "simulation": {"engine": "none"},
            "execution": {"lock_ttl_ms": 5000, "commit_ack_timeout_ms": 3000, "safe_state": []},
        }
    },
}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def test_no_active_policy_initially():
    resp = policy_client.get("/v1/policies/active")
    assert resp.status_code == 404


def test_create_and_activate_policy():
    resp = admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["policy_version_id"] == "v2025-03-01"

    resp = admin_client.put("/v1/admin/policies/v2025-03-01/activate", headers=ADMIN_HEADERS)
    assert resp.status_code == 200

    resp = policy_client.get("/v1/policies/active")
    assert resp.status_code == 200
    assert resp.json()["policy_version_id"] == "v2025-03-01"


def test_create_duplicate_policy():
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    resp = admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    assert resp.status_code == 409


def test_get_policy_document_and_asset():
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)

    resp = policy_client.get("/v1/policies/v2025-03-01")
    assert resp.status_code == 200
    assert "reactor_01" in resp.json()["assets"]

    resp = policy_client.get("/v1/policies/v2025-03-01/assets/reactor_01")
    assert resp.status_code == 200
    assert resp.json()["profile"]["sil_level"] == 2


def test_update_asset_policy_creates_new_version_and_preserves_old():
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)

    updated_profile = dict(MOCK_POLICY["assets"]["reactor_01"])
    updated_profile["sil_level"] = 3

    resp = admin_client.put(
        "/v1/admin/policies/v2025-03-01/assets/reactor_01",
        json={"profile": updated_profile, "change_reason": "Raise SIL level"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version_id"] != "v2025-03-01"
    assert data["previous_policy_version_id"] == "v2025-03-01"

    old_resp = policy_client.get("/v1/policies/v2025-03-01/assets/reactor_01")
    new_resp = policy_client.get(f"/v1/policies/{data['policy_version_id']}/assets/reactor_01")
    assert old_resp.status_code == 200
    assert new_resp.status_code == 200
    assert old_resp.json()["profile"]["sil_level"] == 2
    assert new_resp.json()["profile"]["sil_level"] == 3


def test_switch_active_policy():
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    admin_client.put("/v1/admin/policies/v2025-03-01/activate", headers=ADMIN_HEADERS)

    v2 = dict(MOCK_POLICY)
    v2["policy_version_id"] = "v2025-03-02"
    admin_client.post("/v1/admin/policies", json=v2, headers=ADMIN_HEADERS)

    resp = admin_client.put("/v1/admin/policies/v2025-03-02/activate", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["previous_active_version"] == "v2025-03-01"

    resp = policy_client.get("/v1/policies/active")
    assert resp.json()["policy_version_id"] == "v2025-03-02"


def test_get_nonexistent_resources():
    assert policy_client.get("/v1/policies/v-unknown").status_code == 404
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    assert policy_client.get("/v1/policies/v2025-03-01/assets/nonexistent").status_code == 404


def test_health_check_and_plugins():
    assert admin_client.get("/v1/admin/health").status_code == 200
    plugins = admin_client.get("/v1/admin/plugins", headers=ADMIN_HEADERS)
    assert plugins.status_code == 200
    assert len(plugins.json()["simulation"]) >= 1
