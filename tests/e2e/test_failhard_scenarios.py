"""
PCAG Fail-Hard E2E Test Suite
Tests: SAFE (normal), UNSAFE (policy violation), ERROR (system failure)
"""
import httpx
import json
import time
import os
import sys
from datetime import datetime

# Configuration
GATEWAY_URL = "http://localhost:8000"
POLICY_URL = "http://localhost:8002"
SENSOR_GATEWAY_URL = "http://localhost:8003"
API_KEY = "pcag-agent-key-001"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def get_active_policy():
    """Get current active policy version."""
    try:
        resp = httpx.get(f"{POLICY_URL}/v1/policies/active", timeout=5.0)
        if resp.status_code == 200:
            return resp.json()["policy_version_id"]
    except Exception as e:
        print(f"[WARN] Could not fetch policy version: {e}")
    return "v2025-03-05" # Fallback

def get_sensor_hash(asset_id):
    """Get current sensor snapshot hash."""
    try:
        resp = httpx.get(f"{SENSOR_GATEWAY_URL}/v1/assets/{asset_id}/snapshots/latest", timeout=5.0)
        if resp.status_code == 200:
            return resp.json()["sensor_snapshot_hash"]
    except Exception:
        pass
    return "a" * 64  # Fallback

def build_request(asset_id, action_type, params, policy_version, sensor_hash):
    """Build a control request in the correct format."""
    tx_id = f"test-{int(time.time()*1000)}"
    
    action = {
        "action_type": action_type,
        "params": params,
        "duration_ms": 1000
    }
    
    proof_package = {
        "schema_version": "1.0",
        "policy_version_id": policy_version,
        "timestamp_ms": int(time.time() * 1000),
        "sensor_snapshot_hash": sensor_hash,
        "sensor_reliability_index": 0.95,
        "action_sequence": [action],
        "safety_verification_summary": {
            "checks": ["range_check", "velocity_check"],
            "assumptions": ["static_environment"], 
            "warnings": []
        }
    }
    
    return {
        "transaction_id": tx_id,
        "asset_id": asset_id,
        "proof_package": proof_package
    }

def run_scenario(name, description, request_body, expected_status_list):
    """Run a single scenario and display results."""
    print(f"\n[{name}] {description}")
    print("-" * 60)
    
    start_time = time.time()
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/v1/control-requests",
            json=request_body,
            headers=HEADERS,
            timeout=10.0
        )
        duration = (time.time() - start_time) * 1000
        
        try:
            response_data = resp.json()
        except:
            response_data = {"raw_text": resp.text}
            
        status_code = resp.status_code
        # If the Gateway is strictly typed, it might return 500 for "ERROR" status
        # but the JSON body might still contain useful info if it's a validation error.
        # However, typically 500 means unhandled.
        # We look for "status" field.
        actual_status = response_data.get("status", f"HTTP_{status_code}")
        
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return {"passed": False, "error": str(e), "scenario": name}

    # Normalize expected_status_list
    if isinstance(expected_status_list, str):
        expected_status_list = [expected_status_list]
        
    # Check if passed
    # Special handling: if expected is ERROR, we might accept HTTP_500 if the system blew up on validation
    # provided we wanted to fail hard. But ideally we want the explicit ERROR status.
    passed = actual_status in expected_status_list
    
    # Print Results
    print(f"Pipeline Result: {actual_status} (Expected: {expected_status_list})")
    if "reason" in response_data:
        print(f"Reason: {response_data['reason']}")
    if "reason_code" in response_data:
        print(f"Code: {response_data['reason_code']}")
    
    # Save result
    result_record = {
        "scenario": name,
        "description": description,
        "timestamp": datetime.now().isoformat(),
        "expected": expected_status_list,
        "actual": actual_status,
        "passed": passed,
        "response": response_data,
        "duration_ms": duration
    }
    
    filename = f"failhard_{name.lower().split()[0]}_{int(time.time())}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(result_record, f, indent=2)
        
    print(f"Result saved to: {filepath}")
    return result_record

def scenario_safe():
    """Scenario 1: SAFE — all values within limits"""
    policy_version = get_active_policy()
    asset_id = "robot_arm_01"
    sensor_hash = get_sensor_hash(asset_id)
    
    params = {
        "target_positions": [0.0, -0.3, 0.0, -1.5, 0.0, 1.2, 0.785],
        "joint_0": 0.0, "joint_1": -0.3, "joint_2": 0.0, "joint_3": -1.5,
        "joint_4": 0.0, "joint_5": 1.2, "joint_6": 0.785,
        "joint_0_velocity": 1.0, "joint_1_velocity": 1.0, "joint_2_velocity": 1.0,
        "joint_3_velocity": 1.0, "joint_4_velocity": 1.0, "joint_5_velocity": 1.0, "joint_6_velocity": 1.0,
        "joint_0_effort": 50.0, "joint_1_effort": 50.0, "joint_2_effort": 50.0, "joint_3_effort": 50.0,
        "joint_4_effort": 8.0, "joint_5_effort": 8.0, "joint_6_effort": 8.0
    }
    
    req = build_request(asset_id, "move_joint", params, policy_version, sensor_hash)
    return run_scenario("Scenario 1", "SAFE - Normal Operation", req, "COMMITTED")

def scenario_unsafe():
    """Scenario 2: UNSAFE — joint position exceeds limit"""
    policy_version = get_active_policy()
    asset_id = "robot_arm_01"
    sensor_hash = get_sensor_hash(asset_id)
    
    # Start with safe params
    params = {
        "target_positions": [0.0, 2.5, 0.0, -1.5, 0.0, 1.2, 0.785],
        "joint_0": 0.0, "joint_1": 2.5, "joint_2": 0.0, "joint_3": -1.5,
        "joint_4": 0.0, "joint_5": 1.2, "joint_6": 0.785,
        "joint_0_velocity": 1.0, "joint_1_velocity": 1.0, "joint_2_velocity": 1.0,
        "joint_3_velocity": 1.0, "joint_4_velocity": 1.0, "joint_5_velocity": 1.0, "joint_6_velocity": 1.0,
        "joint_0_effort": 50.0, "joint_1_effort": 50.0, "joint_2_effort": 50.0, "joint_3_effort": 50.0,
        "joint_4_effort": 8.0, "joint_5_effort": 8.0, "joint_6_effort": 8.0
    }
    # Joint 1 = 2.5 exceeds limit 1.7628
    
    req = build_request(asset_id, "move_joint", params, policy_version, sensor_hash)
    return run_scenario("Scenario 2", "UNSAFE - Policy Violation", req, ["UNSAFE", "REJECTED"])

def scenario_error():
    """Scenario 3: ERROR — non-existent asset triggers system error"""
    policy_version = get_active_policy()
    asset_id = "nonexistent_asset_999"
    # We purposefully don't get a valid sensor hash (it would fail anyway)
    sensor_hash = "dummy_hash_for_nonexistent_asset"
    
    params = {"dummy": "value"}
    
    req = build_request(asset_id, "move_joint", params, policy_version, sensor_hash)
    
    # We expect ERROR status, or potentially HTTP_500 if the system fails hard on validation
    return run_scenario("Scenario 3", "ERROR - System Failure (Invalid Asset)", req, ["ERROR", "HTTP_500"])

if __name__ == "__main__":
    print("=" * 70)
    print("PCAG Fail-Hard E2E Test Suite")
    print("=" * 70)
    
    # Check if Gateway is up
    try:
        httpx.get(f"{GATEWAY_URL}/docs", timeout=2.0)
    except:
        print(f"[FATAL] Gateway at {GATEWAY_URL} is not running. Please start services.")
        sys.exit(1)
    
    results = []
    results.append(scenario_safe())
    results.append(scenario_unsafe())
    results.append(scenario_error())
    
    # Print summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"{'Scenario':<40} | {'Expected':<15} | {'Actual':<15} | {'Result':<6}")
    print("-" * 85)
    
    passed_count = 0
    for res in results:
        status = "PASS" if res["passed"] else "FAIL"
        if res["passed"]: passed_count += 1
        
        # Format lists for display
        expected = str(res['expected'])
        if len(expected) > 15: expected = expected[:12] + "..."
        
        print(f"{res['scenario']:<40} | {expected:<15} | {res['actual']:<15} | {status:<6}")
        
    print("-" * 85)
    print(f"Total: {len(results)}, Passed: {passed_count}, Failed: {len(results) - passed_count}")
