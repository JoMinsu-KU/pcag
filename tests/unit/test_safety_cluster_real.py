"""Safety Cluster integration-style unit tests without live Policy Store."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.apps.safety_cluster.service import run_safety_validation


REACTOR_PROFILE = {
    "asset_id": "reactor_01",
    "sil_level": 2,
    "consensus": {
        "mode": "WEIGHTED",
        "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
        "threshold": 0.5,
        "on_sim_indeterminate": "RENORMALIZE",
    },
    "ruleset": [
        {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0},
        {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 120.0},
        {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.5, "max": 3.0},
    ],
    "simulation": {"engine": "none"},
}


def _run_with_profile(sensor_snapshot, action_sequence, profile=None):
    from pcag.apps.safety_cluster import service

    selected_profile = profile or REACTOR_PROFILE
    with patch.object(service, "_fetch_asset_profile", return_value=selected_profile):
        return run_safety_validation(
            transaction_id="test-tx",
            asset_id="reactor_01",
            policy_version_id="v-test",
            action_sequence=action_sequence,
            current_sensor_snapshot=sensor_snapshot,
        )


def test_safe_reactor_state():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert result["final_verdict"] == "SAFE"
    assert result["validators"]["rules"]["verdict"] == "SAFE"
    assert result["validators"]["cbf"]["verdict"] == "SAFE"
    assert result["validators"]["simulation"]["verdict"] == "INDETERMINATE"


def test_unsafe_temperature_exceeds():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 185.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert result["final_verdict"] == "UNSAFE"
    assert result["validators"]["rules"]["verdict"] == "UNSAFE"
    assert result["validators"]["cbf"]["verdict"] == "UNSAFE"


def test_unsafe_pressure_out_of_range():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 3.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert result["final_verdict"] == "UNSAFE"


def test_consensus_mode_weighted():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert result["consensus_details"]["mode"] in ("WEIGHTED", "AUTO")


def test_simulation_always_indeterminate():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert result["validators"]["simulation"]["verdict"] == "INDETERMINATE"


def test_all_three_validators_run():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    assert "rules" in result["validators"]
    assert "cbf" in result["validators"]
    assert "simulation" in result["validators"]


def test_consensus_details_present():
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE,
    )
    consensus_details = result["consensus_details"]
    assert "mode" in consensus_details
    assert "explanation" in consensus_details


def test_empty_ruleset_safe_inputs_still_fail_worst_case():
    empty_profile = {
        "sil_level": 1,
        "consensus": {"mode": "WORST_CASE"},
        "ruleset": [],
        "simulation": {"engine": "none"},
    }
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0},
        action_sequence=[],
        profile=empty_profile,
    )
    assert result["validators"]["rules"]["verdict"] == "SAFE"
    assert result["validators"]["cbf"]["verdict"] == "INDETERMINATE"
    assert result["final_verdict"] == "UNSAFE"
