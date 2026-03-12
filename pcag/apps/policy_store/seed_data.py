"""
Policy Store Seed Data
======================
Initial data for the Policy Store database.
"""

MOCK_ACTIVE_VERSION = "v2025-03-01"
MOCK_POLICY_DATA = {
    "policy_version_id": MOCK_ACTIVE_VERSION,
    "issued_at_ms": 1740000000000,
    "global_policy": {
        "hash": {"algorithm": "sha256", "canonicalization_version": "1.0"},
        "defaults": {"timestamp_max_age_ms": 500}
    },
    "assets": {
        "reactor_01": {
            "asset_id": "reactor_01",
            "sil_level": 2,
            "sensor_source": "modbus_sensor",
            "ot_executor": "mock_executor",
            "consensus": {
                "mode": "WEIGHTED",
                "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
                "threshold": 0.5,
                "on_sim_indeterminate": "RENORMALIZE"
            },
            "integrity": {
                "timestamp_max_age_ms": 500,
                "sensor_divergence_thresholds": [
                    {"sensor_type": "temperature", "method": "absolute", "max_divergence": 2.0},
                    {"sensor_type": "pressure", "method": "absolute", "max_divergence": 0.5}
                ]
            },
            "ruleset": [
                {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0, "unit": "celsius"},
                {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 120.0, "unit": "celsius"},
                {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.5, "max": 3.0, "unit": "atm"}
            ],
            "simulation": {"engine": "none", "timeout_ms": 200},
            "execution": {
                "lock_ttl_ms": 5000,
                "commit_ack_timeout_ms": 3000,
                "safe_state": [
                    {"action_type": "set_heater_output", "params": {"value": 0}},
                    {"action_type": "set_cooling_valve", "params": {"value": 100}}
                ]
            }
        }
    }
}
