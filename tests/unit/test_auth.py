"""
API Key 인증 테스트
===================
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
from pcag.apps.gateway.main import app as gateway_app


def test_request_without_key_rejected():
    """API Key 없이 요청 → 401"""
    # Auth가 enabled일 때만 테스트
    from pcag.core.utils.config_loader import load_config
    config = load_config("services.yaml")
    if not config.get("auth", {}).get("enabled", False):
        pytest.skip("Auth not enabled")
    
    client = TestClient(gateway_app)
    resp = client.post("/v1/control-requests", json={
        "transaction_id": "test",
        "asset_id": "reactor_01",
        "proof_package": {"schema_version": "1.0"}
    })
    assert resp.status_code == 401


def test_request_with_valid_key_accepted():
    """유효한 API Key → 통과 (422 validation error는 OK — 인증은 통과)"""
    from pcag.core.utils.config_loader import load_config
    config = load_config("services.yaml")
    if not config.get("auth", {}).get("enabled", False):
        pytest.skip("Auth not enabled")
    
    client = TestClient(gateway_app)
    resp = client.post("/v1/control-requests", 
        json={"transaction_id": "test", "asset_id": "r", "proof_package": {}},
        headers={"X-API-Key": "pcag-agent-key-001"}
    )
    # 인증은 통과, 스키마 검증에서 실패할 수 있음 (200 REJECTED or 422)
    assert resp.status_code != 401


def test_request_with_invalid_key_rejected():
    """잘못된 API Key → 401"""
    from pcag.core.utils.config_loader import load_config
    config = load_config("services.yaml")
    if not config.get("auth", {}).get("enabled", False):
        pytest.skip("Auth not enabled")
    
    client = TestClient(gateway_app)
    resp = client.post("/v1/control-requests",
        json={"transaction_id": "test", "asset_id": "r", "proof_package": {}},
        headers={"X-API-Key": "wrong-key-12345"}
    )
    assert resp.status_code == 401
