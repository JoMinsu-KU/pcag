"""
Reference seed data for the Policy Store.

This module provides a small built-in policy document that reflects the current
reference stack used by the public repository. It is intentionally lightweight
and is mainly useful for bootstrap paths, tests, and documentation-aligned
examples.
"""

REFERENCE_ACTIVE_VERSION = "v2025-03-06"
REFERENCE_POLICY_DATA = {
    "policy_version_id": REFERENCE_ACTIVE_VERSION,
    "issued_at_ms": 1740000000000,
    "global_policy": {
        "hash": {"algorithm": "sha256", "canonicalization_version": "1.0"},
        "defaults": {"timestamp_max_age_ms": 5000},
    },
    "assets": {
        "reactor_01": {
            "asset_id": "reactor_01",
            "sil_level": 2,
            "sensor_source": "modbus_sensor",
            "ot_executor": "modbus_executor",
            "consensus": {
                "mode": "WEIGHTED",
                "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
                "threshold": 0.8,
                "on_sim_indeterminate": "RENORMALIZE",
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": [
                    {
                        "sensor_type": "temperature",
                        "method": "absolute",
                        "max_divergence": 5.0,
                    },
                    {
                        "sensor_type": "pressure",
                        "method": "absolute",
                        "max_divergence": 1.0,
                    },
                ],
            },
            "ruleset": [
                {
                    "rule_id": "max_temperature",
                    "type": "threshold",
                    "target_field": "temperature",
                    "operator": "lte",
                    "value": 180.0,
                    "unit": "celsius",
                },
                {
                    "rule_id": "min_temperature",
                    "type": "threshold",
                    "target_field": "temperature",
                    "operator": "gte",
                    "value": 0.0,
                    "unit": "celsius",
                },
                {
                    "rule_id": "safe_pressure",
                    "type": "range",
                    "target_field": "pressure",
                    "min": 0.0,
                    "max": 3.0,
                    "unit": "atm",
                },
                {
                    "rule_id": "max_heater_output",
                    "type": "threshold",
                    "target_field": "heater_output",
                    "operator": "lte",
                    "value": 90.0,
                    "unit": "%",
                },
            ],
            "simulation": {
                "engine": "ode_solver",
                "timeout_ms": 5000,
                "horizon_ms": 5000,
                "dt_ms": 100,
            },
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [
                    {"action_type": "set_heater_output", "params": {"value": 0}},
                    {"action_type": "set_cooling_valve", "params": {"value": 100}},
                ],
            },
        },
        "robot_arm_01": {
            "asset_id": "robot_arm_01",
            "sil_level": 2,
            "sensor_source": "isaac_sim_sensor",
            "ot_executor": "mock_executor",
            "consensus": {
                "mode": "WEIGHTED",
                "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
                "threshold": 0.5,
                "on_sim_indeterminate": "RENORMALIZE",
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": [],
            },
            "ruleset": [
                {
                    "rule_id": "panda_joint1_pos",
                    "type": "range",
                    "target_field": "joint_0",
                    "min": -2.8973,
                    "max": 2.8973,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint2_pos",
                    "type": "range",
                    "target_field": "joint_1",
                    "min": -1.7628,
                    "max": 1.7628,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint3_pos",
                    "type": "range",
                    "target_field": "joint_2",
                    "min": -2.8973,
                    "max": 2.8973,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint4_pos",
                    "type": "range",
                    "target_field": "joint_3",
                    "min": -3.0718,
                    "max": -0.0698,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint5_pos",
                    "type": "range",
                    "target_field": "joint_4",
                    "min": -2.8973,
                    "max": 2.8973,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint6_pos",
                    "type": "range",
                    "target_field": "joint_5",
                    "min": -0.0175,
                    "max": 3.7525,
                    "unit": "rad",
                },
                {
                    "rule_id": "panda_joint7_pos",
                    "type": "range",
                    "target_field": "joint_6",
                    "min": -2.8973,
                    "max": 2.8973,
                    "unit": "rad",
                },
            ],
                "simulation": {
                    "engine": "isaac_sim",
                    "timeout_ms": 10000,
                    "headless": True,
                    "simulation_steps_per_action": 30,
                    "workspace_limits": [
                        [-0.855, 0.855],
                        [-0.855, 0.855],
                        [-0.36, 1.19],
                    ],
                    "collision": {
                        "enabled": False,
                        "mode": "end_effector_sphere",
                        "probe_radius_m": 0.045,
                        "forbidden_objects": [],
                    },
                },
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [
                    {
                        "action_type": "move_joint",
                        "params": {
                            "target_positions": [
                                0,
                                0,
                                0,
                                -1.5,
                                0,
                                1.0,
                                0,
                                0.04,
                                0.04,
                            ]
                        },
                    }
                ],
            },
        },
        "agv_01": {
            "asset_id": "agv_01",
            "sil_level": 1,
            "sensor_source": "modbus_sensor",
            "ot_executor": "modbus_executor",
            "consensus": {
                "mode": "WORST_CASE",
                "on_sim_indeterminate": "RENORMALIZE",
            },
            "integrity": {
                "timestamp_max_age_ms": 5000,
                "sensor_divergence_thresholds": [],
            },
            "ruleset": [
                {
                    "rule_id": "agv_x_bounds",
                    "type": "range",
                    "target_field": "position_x",
                    "min": 0.0,
                    "max": 10.0,
                    "unit": "cell",
                },
                {
                    "rule_id": "agv_y_bounds",
                    "type": "range",
                    "target_field": "position_y",
                    "min": 0.0,
                    "max": 10.0,
                    "unit": "cell",
                },
            ],
            "simulation": {
                "engine": "discrete_event",
                "timeout_ms": 1000,
                "grid": {
                    "width": 10,
                    "height": 10,
                    "obstacles": [[3, 3]],
                    "intersections": [],
                },
                "agvs": {
                    "agv_01": {"position": [0, 0], "speed": 1.0},
                    "agv_02": {"position": [9, 9], "speed": 1.0},
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
        },
    },
}

# Backward-compatible aliases for older imports and tests.
MOCK_ACTIVE_VERSION = REFERENCE_ACTIVE_VERSION
MOCK_POLICY_DATA = REFERENCE_POLICY_DATA
