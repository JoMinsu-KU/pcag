from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
POLICY_DIR = Path(__file__).resolve().parent
ROBOT_POLICY_PATH = POLICY_DIR / "robot_pcag_benchmark_policy_v1.json"
OUTPUT_PATH = POLICY_DIR / "agv_pcag_benchmark_policy_v1.json"

AGV_POLICY_VERSION = "v2026-03-19-agv-benchmark-v1"

AGV_ASSET_POLICY = {
    "asset_id": "agv_01",
    "sil_level": 1,
    "sensor_source": "modbus_sensor",
    "allowed_action_types": ["move_to"],
    "ot_executor": "modbus_executor",
    "consensus": {
        "mode": "WORST_CASE",
        "on_sim_indeterminate": "TREAT_AS_UNSAFE",
    },
    "integrity": {
        "timestamp_max_age_ms": 5000,
        "sensor_divergence_thresholds": [
            {"sensor_type": "position_x", "method": "absolute", "max_divergence": 0.5},
            {"sensor_type": "position_y", "method": "absolute", "max_divergence": 0.5},
            {"sensor_type": "heading", "method": "absolute", "max_divergence": 45.0},
            {"sensor_type": "speed", "method": "absolute", "max_divergence": 0.2},
        ],
    },
    "ruleset": [
        {"rule_id": "agv_x_bounds", "type": "range", "target_field": "position_x", "min": 0.0, "max": 13.0, "unit": "cell"},
        {"rule_id": "agv_y_bounds", "type": "range", "target_field": "position_y", "min": 0.0, "max": 9.0, "unit": "cell"},
        {"rule_id": "agv_heading_bounds", "type": "range", "target_field": "heading", "min": 0.0, "max": 360.0, "unit": "deg"},
        {"rule_id": "agv_speed_limit", "type": "threshold", "target_field": "speed", "operator": "lte", "value": 1.2, "unit": "cell/s"},
    ],
    "simulation": {
        "engine": "discrete_event",
        "timeout_ms": 1000,
        "grid": {
            "width": 14,
            "height": 10,
            "obstacles": [[4, 2]],
            "intersections": [[6, 3]],
        },
        "agvs": {
            "agv_01": {"position": [1, 1], "speed": 1.0},
            "agv_02": {"position": [13, 9], "speed": 1.0},
        },
        "min_distance": 1.0,
    },
    "execution": {
        "lock_ttl_ms": 5000,
        "commit_ack_timeout_ms": 3000,
        "safe_state": [
            {
                "action_type": "move_to",
                "params": {"agv_id": "agv_01", "target_x": 0, "target_y": 0},
            }
        ],
    },
}


def build_policy() -> dict:
    base_policy = json.loads(ROBOT_POLICY_PATH.read_text(encoding="utf-8"))
    policy = json.loads(json.dumps(base_policy))
    policy["policy_version_id"] = AGV_POLICY_VERSION
    policy["global_policy"]["metadata"] = {
        "benchmark_profile": "agv_benchmark_v1",
        "scope": "AGV-primary benchmark policy with robot/reactor reference carryover",
        "description": "Benchmark policy aligned to the frozen AGV warehouse-derived PCAG execution dataset.",
    }
    policy["assets"]["agv_01"] = AGV_ASSET_POLICY
    return policy


def main() -> None:
    policy = build_policy()
    OUTPUT_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote AGV benchmark policy to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
