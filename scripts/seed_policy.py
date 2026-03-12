"""
초기 정책 데이터 시딩
=====================
PCAG 시스템에 기본 정책을 등록하고 활성화합니다.
서비스가 실행 중이어야 합니다.

conda activate pcag && python scripts/seed_policy.py
"""
import httpx
import sys
import os

ADMIN_URL = "http://localhost:8006"
POLICY_URL = "http://localhost:8002"

API_KEY = os.environ.get("PCAG_ADMIN_KEY", "pcag-admin-key-001")
HEADERS = {"X-Admin-Key": API_KEY}

INITIAL_POLICY = {
    "policy_version_id": "v2025-03-06",
    "global_policy": {
        "hash": {"algorithm": "sha256", "canonicalization_version": "1.0"},
        "defaults": {"timestamp_max_age_ms": 5000}
    },
    "assets": {
        "reactor_01": {
            "asset_id": "reactor_01",
            "sil_level": 2,
            "sensor_source": "modbus_sensor",
            "allowed_action_types": ["set_heater_output", "set_cooling_valve"],
            "ot_executor": "mock_executor",
            "consensus": {
                "mode": "WEIGHTED",
                "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
                "threshold": 0.8,
                "on_sim_indeterminate": "RENORMALIZE"
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": [
                    {"sensor_type": "temperature", "method": "absolute", "max_divergence": 5.0},
                    {"sensor_type": "pressure", "method": "absolute", "max_divergence": 1.0}
                ]
            },
            "ruleset": [
                {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0, "unit": "celsius"},
                {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 0.0, "unit": "celsius"},
                {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.0, "max": 3.0, "unit": "atm"},
                {"rule_id": "max_heater_output", "type": "threshold", "target_field": "heater_output", "operator": "lte", "value": 90.0, "unit": "%"}
            ],
            "simulation": {
                "engine": "ode_solver",
                "timeout_ms": 5000,
                "horizon_ms": 5000,
                "dt_ms": 100
            },
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [
                    {"action_type": "set_heater_output", "params": {"value": 0}},
                    {"action_type": "set_cooling_valve", "params": {"value": 100}}
                ]
            }
        },
        "robot_arm_01": {
            "asset_id": "robot_arm_01",
            "sil_level": 2,
            "sensor_source": "mock_sensor",
            "allowed_action_types": ["move_joint"],
            "ot_executor": "mock_executor",
            "consensus": {
                "mode": "WEIGHTED",
                "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
                "threshold": 0.5,
                "on_sim_indeterminate": "RENORMALIZE"
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": []
            },
            "ruleset": [
                # 1. Joint Position Limits (range rules)
                {"rule_id": "panda_joint1_pos", "type": "range", "target_field": "joint_0", "min": -2.8973, "max": 2.8973, "unit": "rad"},
                {"rule_id": "panda_joint2_pos", "type": "range", "target_field": "joint_1", "min": -1.7628, "max": 1.7628, "unit": "rad"},
                {"rule_id": "panda_joint3_pos", "type": "range", "target_field": "joint_2", "min": -2.8973, "max": 2.8973, "unit": "rad"},
                {"rule_id": "panda_joint4_pos", "type": "range", "target_field": "joint_3", "min": -3.0718, "max": -0.0698, "unit": "rad"},
                {"rule_id": "panda_joint5_pos", "type": "range", "target_field": "joint_4", "min": -2.8973, "max": 2.8973, "unit": "rad"},
                {"rule_id": "panda_joint6_pos", "type": "range", "target_field": "joint_5", "min": -0.0175, "max": 3.7525, "unit": "rad"},
                {"rule_id": "panda_joint7_pos", "type": "range", "target_field": "joint_6", "min": -2.8973, "max": 2.8973, "unit": "rad"},
                {"rule_id": "panda_finger_joint1_pos", "type": "range", "target_field": "finger_joint_0", "min": 0.0, "max": 0.04, "unit": "m"},
                {"rule_id": "panda_finger_joint2_pos", "type": "range", "target_field": "finger_joint_1", "min": 0.0, "max": 0.04, "unit": "m"},
                # 2. Joint Velocity Limits (threshold rules)
                {"rule_id": "panda_joint1_vel", "type": "threshold", "target_field": "joint_0_velocity", "operator": "lte", "value": 2.175, "unit": "rad/s"},
                {"rule_id": "panda_joint2_vel", "type": "threshold", "target_field": "joint_1_velocity", "operator": "lte", "value": 2.175, "unit": "rad/s"},
                {"rule_id": "panda_joint3_vel", "type": "threshold", "target_field": "joint_2_velocity", "operator": "lte", "value": 2.175, "unit": "rad/s"},
                {"rule_id": "panda_joint4_vel", "type": "threshold", "target_field": "joint_3_velocity", "operator": "lte", "value": 2.175, "unit": "rad/s"},
                {"rule_id": "panda_joint5_vel", "type": "threshold", "target_field": "joint_4_velocity", "operator": "lte", "value": 2.610, "unit": "rad/s"},
                {"rule_id": "panda_joint6_vel", "type": "threshold", "target_field": "joint_5_velocity", "operator": "lte", "value": 2.610, "unit": "rad/s"},
                {"rule_id": "panda_joint7_vel", "type": "threshold", "target_field": "joint_6_velocity", "operator": "lte", "value": 2.610, "unit": "rad/s"},
                {"rule_id": "panda_finger_joint1_vel", "type": "threshold", "target_field": "finger_joint_0_velocity", "operator": "lte", "value": 0.2, "unit": "m/s"},
                {"rule_id": "panda_finger_joint2_vel", "type": "threshold", "target_field": "finger_joint_1_velocity", "operator": "lte", "value": 0.2, "unit": "m/s"},
                # 3. Joint Torque/Force Limits (threshold rules)
                {"rule_id": "panda_joint1_effort", "type": "threshold", "target_field": "joint_0_effort", "operator": "lte", "value": 87.0, "unit": "Nm"},
                {"rule_id": "panda_joint2_effort", "type": "threshold", "target_field": "joint_1_effort", "operator": "lte", "value": 87.0, "unit": "Nm"},
                {"rule_id": "panda_joint3_effort", "type": "threshold", "target_field": "joint_2_effort", "operator": "lte", "value": 87.0, "unit": "Nm"},
                {"rule_id": "panda_joint4_effort", "type": "threshold", "target_field": "joint_3_effort", "operator": "lte", "value": 150.0, "unit": "Nm"},
                {"rule_id": "panda_joint5_effort", "type": "threshold", "target_field": "joint_4_effort", "operator": "lte", "value": 12.0, "unit": "Nm"},
                {"rule_id": "panda_joint6_effort", "type": "threshold", "target_field": "joint_5_effort", "operator": "lte", "value": 50.0, "unit": "Nm"},
                {"rule_id": "panda_joint7_effort", "type": "threshold", "target_field": "joint_6_effort", "operator": "lte", "value": 12.0, "unit": "Nm"},
                {"rule_id": "panda_finger_joint1_force", "type": "threshold", "target_field": "finger_joint_0_force", "operator": "lte", "value": 20.0, "unit": "N"},
                {"rule_id": "panda_finger_joint2_force", "type": "threshold", "target_field": "finger_joint_1_force", "operator": "lte", "value": 20.0, "unit": "N"}
            ],
            "simulation": {
                "engine": "isaac_sim",
                "timeout_ms": 10000,
                "headless": True,
                "simulation_steps_per_action": 30,
                "world_ref": None,
                "workspace_limits": [[-0.855, 0.855], [-0.855, 0.855], [-0.36, 1.19]],
                "torque_limits": [87, 87, 87, 87, 12, 12, 12],
                "joint_limits": {
                    "0": [-2.8973, 2.8973],
                    "1": [-1.7628, 1.7628],
                    "2": [-2.8973, 2.8973],
                    "3": [-3.0718, -0.0698],
                    "4": [-2.8973, 2.8973],
                    "5": [-0.0175, 3.7525],
                    "6": [-2.8973, 2.8973],
                    "7": [0.0, 0.04],
                    "8": [0.0, 0.04]
                }
            },
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [{"action_type": "move_joint", "params": {"target_positions": [0,0,0,-1.5,0,1.0,0,0.04,0.04]}}]
            }
        },
        "agv_01": {
            "asset_id": "agv_01",
            "sil_level": 1,
            "sensor_source": "mock_sensor",
            "allowed_action_types": ["move_to"],
            "ot_executor": "mock_executor",
            "consensus": {
                "mode": "WORST_CASE",
                "on_sim_indeterminate": "RENORMALIZE"
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": []
            },
            "ruleset": [
                {"rule_id": "agv_x_bounds", "type": "range", "target_field": "position_x", "min": 0.0, "max": 10.0, "unit": "cell"},
                {"rule_id": "agv_y_bounds", "type": "range", "target_field": "position_y", "min": 0.0, "max": 10.0, "unit": "cell"}
            ],
            "simulation": {
                "engine": "discrete_event",
                "timeout_ms": 1000,
                "grid": {"width": 10, "height": 10, "obstacles": [[3,3]], "intersections": []},
                "agvs": {"agv_01": {"position": [0, 0], "speed": 1.0}, "agv_02": {"position": [9, 9], "speed": 1.0}},
                "min_distance": 1.0
            },
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [{"action_type": "move_to", "params": {"agv_id": "agv_01", "target_x": 0, "target_y": 0}}]
            }
        }
    }
}

def seed():
    print("PCAG Initial Policy Seeding")
    print("=" * 50)
    
    version = INITIAL_POLICY["policy_version_id"]

    # 1. Create policy
    print(f"1. Creating policy {version}...")
    try:
        resp = httpx.post(f"{ADMIN_URL}/v1/admin/policies", json=INITIAL_POLICY, timeout=5.0, headers=HEADERS)
        if resp.status_code == 200:
            print(f"   Created: {resp.json()}")
        elif resp.status_code == 409:
            print("   Already exists - updating asset profiles...")
            _update_existing_assets()
        else:
            print(f"   Error: {resp.status_code} {resp.text}")
    except httpx.ConnectError:
        print("   ERROR: Admin service not running!")
        return
    
    # 2. Activate policy
    print(f"2. Activating policy {version}...")
    resp = httpx.put(f"{ADMIN_URL}/v1/admin/policies/{version}/activate", timeout=5.0, headers=HEADERS)
    print(f"   Result: {resp.json()}")
    
    # 3. Verify
    print("3. Verifying active policy...")
    resp = httpx.get(f"{POLICY_URL}/v1/policies/active", timeout=5.0)
    print(f"   Active: {resp.json()}")
    
    print("\nPolicy seeding complete!")


def _update_existing_assets():
    """기존 정책이 있을 때 자산 프로필을 최신 값으로 갱신"""
    version = INITIAL_POLICY["policy_version_id"]
    assets = INITIAL_POLICY["assets"]
    for asset_id, profile in assets.items():
        print(f"   Updating {asset_id}...")
        resp = httpx.put(
            f"{ADMIN_URL}/v1/admin/policies/{version}/assets/{asset_id}",
            json={"profile": profile},
            timeout=5.0,
            headers=HEADERS
        )
        if resp.status_code == 200:
            print(f"     Updated: {resp.json()}")
        else:
            print(f"     Error: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    seed()
