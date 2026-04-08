from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
POLICY_DIR = Path(__file__).resolve().parent
ROBOT_POLICY_PATH = POLICY_DIR / "robot_pcag_benchmark_policy_v1.json"
OUTPUT_PATH = POLICY_DIR / "process_pcag_benchmark_policy_v1.json"

PROCESS_POLICY_VERSION = "v2026-03-19-process-benchmark-v1"

PROCESS_ASSET_POLICY = {
    "asset_id": "reactor_01",
    "sil_level": 2,
    "sensor_source": "modbus_sensor",
    "allowed_action_types": ["set_heater_output", "set_cooling_valve"],
    "ot_executor": "modbus_executor",
    "consensus": {
        "mode": "WORST_CASE",
        "on_sim_indeterminate": "TREAT_AS_UNSAFE",
    },
    "integrity": {
        "timestamp_max_age_ms": 5000,
        "sensor_divergence_thresholds": [
            {"sensor_type": "temperature", "method": "absolute", "max_divergence": 4.0},
            {"sensor_type": "pressure", "method": "absolute", "max_divergence": 0.08},
            {"sensor_type": "heater_output", "method": "absolute", "max_divergence": 8.0},
            {"sensor_type": "cooling_valve", "method": "absolute", "max_divergence": 12.0},
        ],
    },
    "ruleset": [
        {"rule_id": "reactor_temperature_safe_range", "type": "range", "target_field": "temperature", "min": 35.0, "max": 118.0, "unit": "C"},
        {"rule_id": "reactor_pressure_safe_range", "type": "range", "target_field": "pressure", "min": 0.85, "max": 2.35, "unit": "atm"},
        {"rule_id": "heater_output_range", "type": "range", "target_field": "heater_output", "min": 0.0, "max": 70.0, "unit": "%"},
        {"rule_id": "cooling_valve_range", "type": "range", "target_field": "cooling_valve", "min": 0.0, "max": 100.0, "unit": "%"},
    ],
    "simulation": {
        "engine": "ode_solver",
        "timeout_ms": 5000,
        "horizon_ms": 6000,
        "dt_ms": 100,
        "visualization": {
            "enabled": False,
            "mode": "persistent",
            "step_delay_ms": 200,
            "hold_final_ms": 1500,
        },
    },
    "execution": {
        "lock_ttl_ms": 5000,
        "commit_ack_timeout_ms": 3000,
        "safe_state": [
            {"action_type": "set_heater_output", "params": {"value": 0}},
            {"action_type": "set_cooling_valve", "params": {"value": 100}},
        ],
    },
}


def build_policy() -> dict:
    base_policy = json.loads(ROBOT_POLICY_PATH.read_text(encoding="utf-8"))
    policy = json.loads(json.dumps(base_policy))
    policy["policy_version_id"] = PROCESS_POLICY_VERSION
    policy["global_policy"]["metadata"] = {
        "benchmark_profile": "process_benchmark_v1",
        "scope": "Process-primary benchmark policy with robot/agv reference carryover",
        "description": "Benchmark policy aligned to the frozen Tennessee-Eastman-anchored process PCAG execution dataset.",
    }
    policy["assets"]["reactor_01"] = PROCESS_ASSET_POLICY
    return policy


def main() -> None:
    policy = build_policy()
    OUTPUT_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote process benchmark policy to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
