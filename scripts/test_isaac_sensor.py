import httpx
import json
import sys

def test_sensor_reading():
    url = "http://localhost:8003/v1/assets/robot_arm_01/snapshots/latest"
    print(f"Querying {url}...")
    try:
        resp = httpx.get(url, timeout=5.0)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print("Response Data:")
            print(json.dumps(data, indent=2))
            
            snapshot = data.get("sensor_snapshot", {})
            
            # Check for joint positions (either joint_0 or joint_positions list)
            if snapshot and ("joint_0" in snapshot or "joint_positions" in snapshot):
                print("Success: Found joint data in snapshot")
                return True
            elif not snapshot:
                print("Warning: sensor_snapshot is empty. Isaac Sim might not be connected or running.")
                return False
            else:
                print(f"Warning: Snapshot found but no joint data: {snapshot}")
                return False
        else:
            print(f"Error: Request failed with {resp.status_code}")
            print(resp.text)
            return False
            
    except Exception as e:
        print(f"Exception: {e}")
        return False

def test_direct_simulation_state():
    url = "http://localhost:8001/v1/simulation/state"
    print(f"\nQuerying Safety Cluster Direct: {url}...")
    try:
        resp = httpx.get(url, timeout=5.0)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if "joint_positions" in data:
                print("Success: Safety Cluster returned simulation state")
                print(f"Joint Positions: {data['joint_positions'][:3]}...")
                return True
            else:
                print(f"Warning: Unexpected response from Safety Cluster: {data}")
                return False
        else:
            print(f"Error: Safety Cluster Request failed with {resp.status_code}")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False

if __name__ == "__main__":
    gateway_success = test_sensor_reading()
    safety_success = test_direct_simulation_state()
    
    if gateway_success and safety_success:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed.")
        sys.exit(1)
