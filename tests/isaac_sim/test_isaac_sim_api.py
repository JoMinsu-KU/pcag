"""
PCAG Isaac Sim API Client Test
================================
Tests the Isaac Sim simulation server REST API.

Prerequisites:
  1. Start the server first:
     conda activate pcag-isaac
     python tests/isaac_sim/isaac_sim_server.py
     
  2. Then run this test in another terminal:
     python tests/isaac_sim/test_isaac_sim_api.py

Works with any Python (3.10 or 3.13) — only needs 'requests' package.
"""

import json
import time
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE_URL = "http://localhost:8011"

def test_health():
    """Test 1: Health check"""
    print("\n[TEST 1] Health Check")
    print("-" * 40)
    try:
        resp = requests.get(f"{BASE_URL}/pcag/health", timeout=30)
        data = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Response: {data}")
        assert data["status"] == "healthy"
        print("  Result: [PASS]")
        return True
    except requests.ConnectionError:
        print("  [FAIL] Cannot connect to server. Is isaac_sim_server.py running?")
        return False
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

def test_simulate_safe():
    """Test 2: Simulate a cube falling — should be SAFE (within bounds)"""
    print("\n[TEST 2] Simulate Cube Drop (SAFE scenario)")
    print("-" * 40)
    
    request = {
        "initial_position": [0.0, 0.0, 2.0],
        "cube_size": 0.1,
        "cube_mass": 1.0,
        "steps": 60,
        "workspace_bounds": {
            "x": [-5.0, 5.0],
            "y": [-5.0, 5.0],
            "z": [0.0, 10.0]  # z >= 0, so falling to ground is OK
        }
    }
    
    resp = requests.post(f"{BASE_URL}/pcag/simulate", json=request, timeout=120)
    data = resp.json()
    
    print(f"  Verdict: {data['verdict']}")
    print(f"  Engine: {data['engine']}")
    print(f"  Steps: {data['total_steps']}")
    print(f"  Final Position: {data['final_position']}")
    print(f"  Collision with ground: {data['collision_with_ground']}")
    print(f"  Violations: {len(data['violations'])}")
    print(f"  Latency: {data['latency_ms']:.1f} ms")
    
    # Should be SAFE — cube falls within workspace bounds
    passed = data["verdict"] == "SAFE" and data["collision_with_ground"] == True
    print(f"  Result: {'[PASS]' if passed else '[FAIL]'}")
    return passed

def test_simulate_unsafe():
    """Test 3: Simulate a cube falling from very high — should be UNSAFE (exits workspace)"""
    print("\n[TEST 3] Simulate Cube Drop (UNSAFE scenario)")
    print("-" * 40)
    
    request = {
        "initial_position": [0.0, 0.0, 2.0],
        "cube_size": 0.1,
        "cube_mass": 1.0,
        "steps": 60,
        "workspace_bounds": {
            "x": [-5.0, 5.0],
            "y": [-5.0, 5.0],
            "z": [1.0, 10.0]  # z >= 1.0, so falling below 1m is UNSAFE
        }
    }
    
    resp = requests.post(f"{BASE_URL}/pcag/simulate", json=request, timeout=120)
    data = resp.json()
    
    print(f"  Verdict: {data['verdict']}")
    print(f"  Violations: {len(data['violations'])}")
    if data['violations']:
        print(f"  First violation: step={data['violations'][0]['step']}, "
              f"constraint={data['violations'][0]['constraint']}")
    print(f"  Latency: {data['latency_ms']:.1f} ms")
    
    # Should be UNSAFE — cube falls below z=1.0
    passed = data["verdict"] == "UNSAFE" and len(data["violations"]) > 0
    print(f"  Result: {'[PASS]' if passed else '[FAIL]'}")
    return passed

def test_trajectory_recording():
    """Test 4: Verify trajectory data quality"""
    print("\n[TEST 4] Trajectory Data Quality")
    print("-" * 40)
    
    request = {
        "initial_position": [0.0, 0.0, 3.0],
        "cube_size": 0.1,
        "cube_mass": 1.0,
        "steps": 30,
    }
    
    resp = requests.post(f"{BASE_URL}/pcag/simulate", json=request, timeout=120)
    data = resp.json()
    
    trajectory = data["trajectory"]
    print(f"  Trajectory points: {len(trajectory)}")
    print(f"  First: step={trajectory[0]['step']}, z={trajectory[0]['position']['z']:.3f}")
    print(f"  Last:  step={trajectory[-1]['step']}, z={trajectory[-1]['position']['z']:.3f}")
    
    # Verify trajectory is monotonically decreasing in z (gravity)
    z_values = [p["position"]["z"] for p in trajectory]
    is_falling = z_values[0] > z_values[-1]
    has_all_steps = len(trajectory) == 30
    
    passed = is_falling and has_all_steps
    print(f"  Z decreased: {is_falling}")
    print(f"  All steps recorded: {has_all_steps}")
    print(f"  Result: {'[PASS]' if passed else '[FAIL]'}")
    return passed

def main():
    print("=" * 60)
    print("PCAG Isaac Sim API Client Test")
    print(f"Server: {BASE_URL}")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health
    if not test_health():
        print("\n[ERROR] Server not reachable. Start it first:")
        print("  conda activate pcag-isaac")
        print("  python tests/isaac_sim/isaac_sim_server.py")
        return
    results.append(("Health Check", True))
    
    # Test 2: Safe simulation
    results.append(("Simulate SAFE", test_simulate_safe()))
    
    # Test 3: Unsafe simulation
    results.append(("Simulate UNSAFE", test_simulate_unsafe()))
    
    # Test 4: Trajectory quality
    results.append(("Trajectory Quality", test_trajectory_recording()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        print(f"  {'[PASS]' if r else '[FAIL]'} {name}")
    print(f"\nTotal: {passed}/{len(results)} tests passed")

if __name__ == "__main__":
    main()
