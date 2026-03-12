"""
Policy Store DB 통합 테스트
============================
실제 SQLite DB를 사용하여 Policy Store의 CRUD 동작을 검증합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_policy_store_db.py -v
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pcag.core.database.engine import Base, get_db
from pcag.apps.policy_store.main import app as policy_app
from pcag.apps.policy_admin.main import app as admin_app


# 테스트용 in-memory SQLite DB
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSession = sessionmaker(bind=TEST_ENGINE)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

# 두 앱 모두 같은 테스트 DB 사용
policy_app.dependency_overrides[get_db] = override_get_db
admin_app.dependency_overrides[get_db] = override_get_db

policy_client = TestClient(policy_app)
admin_client = TestClient(admin_app)

ADMIN_HEADERS = {"X-Admin-Key": "pcag-admin-key-001"}

# Mock 정책 데이터
MOCK_POLICY = {
    "policy_version_id": "v2025-03-01",
    "global_policy": {
        "hash": {"algorithm": "sha256"},
        "defaults": {"timestamp_max_age_ms": 500}
    },
    "assets": {
        "reactor_01": {
            "asset_id": "reactor_01",
            "sil_level": 2,
            "sensor_source": "modbus_sensor",
            "ot_executor": "mock_executor",
            "consensus": {"mode": "WEIGHTED", "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25}, "threshold": 0.5},
            "integrity": {"timestamp_max_age_ms": 500, "sensor_divergence_thresholds": []},
            "ruleset": [
                {"rule_id": "max_temp", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0}
            ],
            "simulation": {"engine": "none"},
            "execution": {"lock_ttl_ms": 5000, "commit_ack_timeout_ms": 3000, "safe_state": []}
        }
    }
}


@pytest.fixture(autouse=True)
def setup_db():
    """각 테스트 전에 DB 테이블 초기화"""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def test_no_active_policy_initially():
    """초기 상태: 활성 정책 없음 → 404"""
    resp = policy_client.get("/v1/policies/active")
    assert resp.status_code == 404


def test_create_policy():
    """정책 생성"""
    resp = admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version_id"] == "v2025-03-01"


def test_create_duplicate_policy():
    """중복 정책 생성 → 409"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    resp = admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    assert resp.status_code == 409


def test_activate_policy():
    """정책 활성화"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    resp = admin_client.put("/v1/admin/policies/v2025-03-01/activate", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version_id"] == "v2025-03-01"


def test_get_active_policy():
    """활성 정책 조회"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    admin_client.put("/v1/admin/policies/v2025-03-01/activate", headers=ADMIN_HEADERS)
    
    resp = policy_client.get("/v1/policies/active")
    assert resp.status_code == 200
    assert resp.json()["policy_version_id"] == "v2025-03-01"


def test_get_policy_document():
    """전체 정책 문서 조회"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    
    resp = policy_client.get("/v1/policies/v2025-03-01")
    assert resp.status_code == 200
    data = resp.json()
    assert "reactor_01" in data["assets"]


def test_get_asset_policy():
    """자산별 정책 프로필 조회"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    
    resp = policy_client.get("/v1/policies/v2025-03-01/assets/reactor_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset_id"] == "reactor_01"
    assert data["profile"]["sil_level"] == 2


def test_get_nonexistent_asset():
    """존재하지 않는 자산 조회 → 404"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    
    resp = policy_client.get("/v1/policies/v2025-03-01/assets/nonexistent")
    assert resp.status_code == 404


def test_get_nonexistent_version():
    """존재하지 않는 버전 조회 → 404"""
    resp = policy_client.get("/v1/policies/v-unknown")
    assert resp.status_code == 404


def test_update_asset_policy():
    """자산 정책 수정"""
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    
    updated_profile = MOCK_POLICY["assets"]["reactor_01"].copy()
    updated_profile["sil_level"] = 3
    
    resp = admin_client.put("/v1/admin/policies/v2025-03-01/assets/reactor_01",
                           json={"profile": updated_profile}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    
    # 수정 확인
    resp = policy_client.get("/v1/policies/v2025-03-01/assets/reactor_01")
    assert resp.json()["profile"]["sil_level"] == 3


def test_switch_active_policy():
    """활성 정책 전환"""
    # v1 생성 + 활성화
    admin_client.post("/v1/admin/policies", json=MOCK_POLICY, headers=ADMIN_HEADERS)
    admin_client.put("/v1/admin/policies/v2025-03-01/activate", headers=ADMIN_HEADERS)
    
    # v2 생성
    v2 = MOCK_POLICY.copy()
    v2["policy_version_id"] = "v2025-03-02"
    admin_client.post("/v1/admin/policies", json=v2, headers=ADMIN_HEADERS)
    
    # v2 활성화
    resp = admin_client.put("/v1/admin/policies/v2025-03-02/activate", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["previous_active_version"] == "v2025-03-01"
    
    # 활성 버전 확인
    resp = policy_client.get("/v1/policies/active")
    assert resp.json()["policy_version_id"] == "v2025-03-02"


def test_health_check():
    """헬스 체크"""
    resp = admin_client.get("/v1/admin/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_plugins_list():
    """플러그인 목록"""
    resp = admin_client.get("/v1/admin/plugins", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["simulation"]) >= 1
