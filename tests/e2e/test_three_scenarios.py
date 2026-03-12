"""
PCAG 3개 시나리오 E2E 테스트
==============================
시나리오 A (화학 반응기 + ODE Solver)
시나리오 B (로봇 팔 + Isaac Sim) - pcag-isaac 환경 필요
시나리오 C (AGV + Discrete Event)

각 시나리오마다 SAFE / UNSAFE 케이스를 테스트하고,
결과를 JSON 파일로 저장합니다.

실행 방법:
  1. 서비스 시작: python scripts/start_services.py (터미널 1)
  2. Safety Cluster: python scripts/start_safety_cluster.py (터미널 2, pcag-isaac)
  3. 정책 시딩: python scripts/seed_policy.py
  4. 테스트 실행: python tests/e2e/test_three_scenarios.py

conda pcag 환경에서 실행.
"""
import sys
import os
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx

GATEWAY_URL = "http://localhost:8000"
POLICY_URL = "http://localhost:8002"
SENSOR_GATEWAY_URL = "http://localhost:8003"
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

API_KEY = "pcag-agent-key-001"
HEADERS = {"X-API-Key": API_KEY}


def get_active_policy_version():
    """Policy Store에서 현재 활성 정책 버전을 동적으로 조회"""
    resp = httpx.get(f"{POLICY_URL}/v1/policies/active", timeout=5.0)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch active policy version: "
            f"HTTP {resp.status_code} - {resp.text}. "
            f"Did you run 'python scripts/seed_policy.py'?"
        )
    version = resp.json()["policy_version_id"]
    print(f"[INFO] Fetched active policy version: {version}")
    return version


def send_request(tx_id, asset_id, policy_version, action_sequence, extra_fields=None):
    """PCAG Gateway에 제어 요청 전송"""
    
    # 1. 최신 센서 해시 조회 (TOCTOU L1 대응)
    try:
        sensor_resp = httpx.get(f"{SENSOR_GATEWAY_URL}/v1/assets/{asset_id}/snapshots/latest", timeout=5.0)
        if sensor_resp.status_code == 200:
            current_hash = sensor_resp.json()["sensor_snapshot_hash"]
        else:
            print(f"[WARN] Failed to fetch sensor hash: {sensor_resp.status_code}")
            current_hash = "a" * 64  # Fallback (will likely fail integrity check)
    except Exception as e:
        print(f"[WARN] Failed to connect to Sensor Gateway: {e}")
        current_hash = "a" * 64

    proof_package = {
        "schema_version": "1.0",
        "policy_version_id": policy_version,
        "timestamp_ms": int(time.time() * 1000),
        "sensor_snapshot_hash": current_hash,
        "sensor_reliability_index": 0.95,
        "action_sequence": action_sequence,
        "safety_verification_summary": {"checks": [], "assumptions": [], "warnings": []}
    }
    if extra_fields:
        proof_package.update(extra_fields)
    
    request = {
        "transaction_id": tx_id,
        "asset_id": asset_id,
        "proof_package": proof_package
    }
    
    resp = httpx.post(f"{GATEWAY_URL}/v1/control-requests", json=request, timeout=30.0, headers=HEADERS)
    return resp.json(), request


def save_result(scenario, test_name, request, response, expected_status):
    """테스트 결과를 JSON 파일로 저장"""
    result = {
        "scenario": scenario,
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "expected_status": expected_status,
        "actual_status": response.get("status"),
        "passed": response.get("status") == expected_status,
        "request": request,
        "response": response
    }
    
    filename = f"{scenario}_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    return result, filepath


def check_services():
    """서비스 실행 여부 확인"""
    try:
        httpx.get(f"{GATEWAY_URL}/docs", timeout=3.0)
        return True
    except httpx.ConnectError:
        print("[ERROR] Gateway not running. Start services first.")
        return False


# ============================================================
# 시나리오 A: 화학 반응기 (ODE Solver)
# ============================================================

def test_scenario_a_safe(policy_version):
    """시나리오 A: 안전한 히터 조작 → COMMITTED"""
    print("\n[Scenario A - SAFE] Chemical Reactor: set_heater_output=60")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-a-safe-{int(time.time()*1000)}",
        asset_id="reactor_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 60}, "duration_ms": 2000}
        ]
    )
    
    result, filepath = save_result("scenario_a", "safe_heater_60", req, resp, "COMMITTED")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: COMMITTED")
    print(f"  Passed: {result['passed']}")
    print(f"  File: {filepath}")
    return result


def test_scenario_a_unsafe(policy_version):
    """시나리오 A: 위험한 히터 조작 (100% + 냉각 0%) → UNSAFE"""
    print("\n[Scenario A - UNSAFE] Chemical Reactor: heater=100%, cooling=0%")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-a-unsafe-{int(time.time()*1000)}",
        asset_id="reactor_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 100}, "duration_ms": 5000},
            {"action_type": "set_cooling_valve", "params": {"value": 0}, "duration_ms": 5000}
        ]
    )
    
    result, filepath = save_result("scenario_a", "unsafe_full_heater", req, resp, "UNSAFE")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: UNSAFE")
    print(f"  Passed: {result['passed']}")
    print(f"  Reason: {resp.get('reason', 'N/A')}")
    print(f"  File: {filepath}")
    return result


# ============================================================
# 시나리오 C: AGV 교차로 (Discrete Event)
# ============================================================

def test_scenario_c_safe(policy_version):
    """시나리오 C: 충돌 없는 AGV 이동 → COMMITTED"""
    print("\n[Scenario C - SAFE] AGV: move agv_01 to (3,0) - no collision")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-c-safe-{int(time.time()*1000)}",
        asset_id="agv_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0],[3,0]]}}
        ]
    )
    
    result, filepath = save_result("scenario_c", "safe_no_collision", req, resp, "COMMITTED")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: COMMITTED")
    print(f"  Passed: {result['passed']}")
    print(f"  File: {filepath}")
    return result


def test_scenario_c_unsafe(policy_version):
    """시나리오 C: 그리드 경계 초과 AGV 이동 → UNSAFE"""
    print("\n[Scenario C - UNSAFE] AGV: move to (12,0) - out of grid bounds")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-c-unsafe-{int(time.time()*1000)}",
        asset_id="agv_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "target_x": 12, "target_y": 0}}
        ]
    )
    
    result, filepath = save_result("scenario_c", "unsafe_out_of_bounds", req, resp, "UNSAFE")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: UNSAFE")
    print(f"  Passed: {result['passed']}")
    print(f"  File: {filepath}")
    return result


# ============================================================
# 시나리오 B: 로봇 팔 (Isaac Sim - pcag-isaac 환경 필요)
# ============================================================

def test_scenario_b_safe(policy_version):
    """시나리오 B: 안전한 관절 이동 → COMMITTED (Isaac Sim 필요)"""
    print("\n[Scenario B - SAFE] Robot Arm: move joints within limits")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-b-safe-{int(time.time()*1000)}",
        asset_id="robot_arm_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_positions": [0.5, -0.3, 0.3, -1.0, 0.2, 1.5, -0.3, 0.04, 0.04]}}
        ]
    )
    
    result, filepath = save_result("scenario_b", "safe_within_limits", req, resp, "COMMITTED")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: COMMITTED")
    print(f"  Passed: {result['passed']}")
    print(f"  File: {filepath}")
    return result


def test_scenario_b_unsafe(policy_version):
    """시나리오 B: 관절 한계 초과 → UNSAFE"""
    print("\n[Scenario B - UNSAFE] Robot Arm: joint_0=5.0 rad (limit: 2.897)")
    print("-" * 50)
    
    resp, req = send_request(
        tx_id=f"scenario-b-unsafe-{int(time.time()*1000)}",
        asset_id="robot_arm_01",
        policy_version=policy_version,
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_positions": [5.0, -0.3, 0.3, -1.0, 0.2, 1.5, -0.3, 0.04, 0.04]}}
        ]
    )
    
    result, filepath = save_result("scenario_b", "unsafe_joint_exceed", req, resp, "UNSAFE")
    print(f"  Status: {resp.get('status')}")
    print(f"  Expected: UNSAFE")
    print(f"  Passed: {result['passed']}")
    print(f"  File: {filepath}")
    return result


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("PCAG 3-Scenario E2E Test")
    print(f"Results directory: {RESULTS_DIR}")
    print("=" * 60)
    
    if not check_services():
        sys.exit(1)
        
    active_version = get_active_policy_version()
    print(f"Active policy version for tests: {active_version}")
    
    all_results = []
    
    # Scenario A: Chemical Reactor
    print("\n" + "=" * 60)
    print("SCENARIO A: Chemical Reactor (ODE Solver)")
    print("=" * 60)
    all_results.append(test_scenario_a_safe(active_version))
    all_results.append(test_scenario_a_unsafe(active_version))
    
    # Scenario C: AGV
    print("\n" + "=" * 60)
    print("SCENARIO C: AGV Intersection (Discrete Event)")
    print("=" * 60)
    all_results.append(test_scenario_c_safe(active_version))
    all_results.append(test_scenario_c_unsafe(active_version))
    
    # Scenario B: Robot Arm (may fail if Isaac Sim Safety Cluster not running)
    print("\n" + "=" * 60)
    print("SCENARIO B: Robot Arm (Isaac Sim)")
    print("  NOTE: Requires Safety Cluster in pcag-isaac environment")
    print("=" * 60)
    all_results.append(test_scenario_b_safe(active_version))
    all_results.append(test_scenario_b_unsafe(active_version))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)
    
    for r in all_results:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"  {status} {r['scenario']} / {r['test_name']} - expected={r['expected_status']}, got={r['actual_status']}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": [
            {
                "scenario": r["scenario"],
                "test_name": r["test_name"],
                "passed": r["passed"],
                "expected": r["expected_status"],
                "actual": r["actual_status"]
            }
            for r in all_results
        ]
    }
    summary_path = os.path.join(RESULTS_DIR, f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSummary saved: {summary_path}")
    print(f"Detail files: {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
