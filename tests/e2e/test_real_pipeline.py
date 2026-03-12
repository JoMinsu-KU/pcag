"""
PCAG 실제 E2E 파이프라인 테스트
================================
모든 서비스를 실제로 시작하고, HTTP를 통해 전체 파이프라인을 테스트합니다.

사전 조건:
  1. PostgreSQL 실행 중 (docker compose -f docker/docker-compose.db.yml up -d)
  2. 모든 서비스 실행 중 (python scripts/start_services.py)
  3. 정책 시딩 완료 (python scripts/seed_policy.py)

실행 방법 (conda pcag 환경):
  conda activate pcag
  python tests/e2e/test_real_pipeline.py

또는 서비스가 이미 실행 중이라면:
  python -m pytest tests/e2e/test_real_pipeline.py -v -s
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx

GATEWAY_URL = "http://localhost:8000"
ADMIN_URL = "http://localhost:8006"
POLICY_URL = "http://localhost:8002"
SENSOR_GATEWAY_URL = "http://localhost:8003"
EVIDENCE_URL = "http://localhost:8005"

API_KEY = "pcag-agent-key-001"
HEADERS = {"X-API-Key": API_KEY}


import pytest

@pytest.fixture(scope="session")
def policy_version():
    return get_active_policy_version()


def get_active_policy_version():
    """Policy Store에서 현재 활성 정책 버전을 동적으로 조회"""
    try:
        resp = httpx.get(f"{POLICY_URL}/v1/policies/active", timeout=5.0)
        if resp.status_code == 200:
            version = resp.json().get("policy_version_id")
            print(f"[INFO] Fetched active policy version: {version}")
            return version
    except Exception as e:
        print(f"[WARN] Failed to fetch active policy version: {e}")
    
    print("[WARN] Using fallback policy version: v2025-03-01")
    return "v2025-03-01"


def check_services():
    """서비스 실행 여부 확인"""
    services = [
        ("Gateway", f"{GATEWAY_URL}/docs"),
        ("Policy Store", f"{POLICY_URL}/v1/policies/active"),
    ]
    for name, url in services:
        try:
            httpx.get(url, timeout=2.0)
        except httpx.ConnectError:
            print(f"[ERROR] {name} not running at {url}")
            print("Start services first: python scripts/start_services.py")
            return False
    return True


def test_1_happy_path(policy_version=None):
    """Test 1: 정상 경로 — COMMITTED"""
    if policy_version is None:
        policy_version = get_active_policy_version()

    print("\n[TEST 1] Happy Path - COMMITTED")
    print("-" * 40)
    
    # Fetch real sensor hash
    try:
        s_resp = httpx.get(f"{SENSOR_GATEWAY_URL}/v1/assets/reactor_01/snapshots/latest", timeout=5.0)
        current_hash = s_resp.json()["sensor_snapshot_hash"]
    except Exception as e:
        print(f"[WARN] Failed to fetch sensor hash: {e}")
        current_hash = "a" * 64

    resp = httpx.post(f"{GATEWAY_URL}/v1/control-requests", json={
        "transaction_id": f"e2e-tx-{int(time.time()*1000)}",
        "asset_id": "reactor_01",
        "proof_package": {
            "schema_version": "1.0",
            "policy_version_id": policy_version,
            "timestamp_ms": int(time.time() * 1000),
            "sensor_snapshot_hash": current_hash,
            "sensor_reliability_index": 0.95,
            "action_sequence": [
                {"action_type": "set_heater_output", "params": {"value": 70}}
            ],
            "safety_verification_summary": {"checks": [], "assumptions": [], "warnings": []}
        }
    }, timeout=30.0, headers=HEADERS)
    
    data = resp.json()
    print(f"  Status: {data.get('status')}")
    print(f"  TX ID: {data.get('transaction_id')}")
    print(f"  Evidence: {data.get('evidence_ref')}")
    
    assert data["status"] == "COMMITTED", f"Expected COMMITTED, got {data['status']}: {data.get('reason')}"
    print("  Result: [PASS]")
    return data


def test_2_schema_invalid(policy_version=None):
    """Test 2: 스키마 오류 — REJECTED"""
    # policy_version not used here but kept for consistency if needed
    print("\n[TEST 2] Schema Invalid - REJECTED")
    print("-" * 40)
    
    resp = httpx.post(f"{GATEWAY_URL}/v1/control-requests", json={
        "transaction_id": f"e2e-tx-{int(time.time()*1000)}",
        "asset_id": "reactor_01",
        "proof_package": {
            "schema_version": "1.0"
            # Missing required fields!
        }
    }, timeout=10.0, headers=HEADERS)
    
    data = resp.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Reason: {data.get('reason')}")
    
    assert data["status"] == "REJECTED"
    assert data.get("reason_code") == "SCHEMA_INVALID"
    print("  Result: [PASS]")


def test_3_policy_mismatch(policy_version=None):
    """Test 3: 정책 불일치 — REJECTED"""
    print("\n[TEST 3] Policy Mismatch - REJECTED")
    print("-" * 40)
    
    resp = httpx.post(f"{GATEWAY_URL}/v1/control-requests", json={
        "transaction_id": f"e2e-tx-{int(time.time()*1000)}",
        "asset_id": "reactor_01",
        "proof_package": {
            "schema_version": "1.0",
            "policy_version_id": "v-WRONG-VERSION",
            "timestamp_ms": int(time.time() * 1000),
            "sensor_snapshot_hash": "a" * 64,
            "action_sequence": [],
            "safety_verification_summary": {}
        }
    }, timeout=10.0, headers=HEADERS)
    
    data = resp.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Reason Code: {data.get('reason_code')}")
    
    assert data["status"] == "REJECTED"
    assert data.get("reason_code") == "INTEGRITY_POLICY_MISMATCH"
    print("  Result: [PASS]")


def test_4_evidence_recorded(policy_version=None):
    """Test 4: 증거 체인 확인 — happy path의 증거가 DB에 기록되었는지"""
    if policy_version is None:
        policy_version = get_active_policy_version()

    print("\n[TEST 4] Evidence Chain Recorded")
    print("-" * 40)
    
    # Happy path 실행 (with explicit policy_version)
    happy_result = test_1_happy_path.__wrapped__(policy_version) if hasattr(test_1_happy_path, '__wrapped__') else test_1_happy_path(policy_version)
    
    # 최근 트랜잭션의 증거 확인 (별도 tx_id로)
    tx_id = f"e2e-evidence-{int(time.time()*1000)}"
    
    # Fetch hash again for new tx
    try:
        s_resp = httpx.get(f"{SENSOR_GATEWAY_URL}/v1/assets/reactor_01/snapshots/latest", timeout=5.0)
        current_hash = s_resp.json()["sensor_snapshot_hash"]
    except:
        current_hash = "a" * 64

    httpx.post(f"{GATEWAY_URL}/v1/control-requests", json={
        "transaction_id": tx_id,
        "asset_id": "reactor_01",
        "proof_package": {
            "schema_version": "1.0",
            "policy_version_id": policy_version,
            "timestamp_ms": int(time.time() * 1000),
            "sensor_snapshot_hash": current_hash,
            "sensor_reliability_index": 0.95,
            "action_sequence": [{"action_type": "set_heater_output", "params": {"value": 60}}],
            "safety_verification_summary": {}
        }
    }, timeout=30.0, headers=HEADERS)
    
    # 증거 조회
    resp = httpx.get(f"{EVIDENCE_URL}/v1/transactions/{tx_id}", timeout=5.0)
    data = resp.json()
    
    print(f"  Transaction: {tx_id}")
    print(f"  Events: {len(data.get('events', []))}")
    print(f"  Chain Valid: {data.get('chain_valid')}")
    
    if data.get("events"):
        for ev in data["events"]:
            print(f"    [{ev['sequence_no']}] {ev['stage']}")
    
    assert len(data.get("events", [])) >= 5, f"Expected at least 5 evidence events, got {len(data.get('events', []))}"
    assert data.get("chain_valid") == True
    print("  Result: [PASS]")


def main():
    print("=" * 60)
    print("PCAG Real E2E Pipeline Test")
    print("=" * 60)
    
    if not check_services():
        sys.exit(1)
    
    active_version = get_active_policy_version()
    print(f"Active policy version for tests: {active_version}")

    results = []
    
    try:
        test_1_happy_path(active_version)
        results.append(("Happy Path", True))
    except Exception as e:
        print(f"  Result: [FAIL] {e}")
        results.append(("Happy Path", False))
    
    try:
        test_2_schema_invalid(active_version)
        results.append(("Schema Invalid", True))
    except Exception as e:
        print(f"  Result: [FAIL] {e}")
        results.append(("Schema Invalid", False))
    
    try:
        test_3_policy_mismatch(active_version)
        results.append(("Policy Mismatch", True))
    except Exception as e:
        print(f"  Result: [FAIL] {e}")
        results.append(("Policy Mismatch", False))
    
    try:
        test_4_evidence_recorded(active_version)
        results.append(("Evidence Chain", True))
    except Exception as e:
        print(f"  Result: [FAIL] {e}")
        results.append(("Evidence Chain", False))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        print(f"  {'[PASS]' if r else '[FAIL]'} {name}")
    print(f"\nTotal: {passed}/{len(results)} passed")
    
    if passed == len(results):
        print("\nPCAG Full Pipeline E2E Test PASSED!")
        print("The complete system is operational.")

if __name__ == "__main__":
    main()
