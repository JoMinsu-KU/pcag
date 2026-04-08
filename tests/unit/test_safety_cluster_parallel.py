"""Parallel orchestration tests for Safety Cluster."""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.apps.safety_cluster import service


PROFILE = {
    "asset_id": "reactor_01",
    "sil_level": 2,
    "consensus": {
        "mode": "WEIGHTED",
        "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
        "threshold": 0.5,
        "on_sim_indeterminate": "RENORMALIZE",
    },
    "ruleset": [],
    "simulation": {"engine": "none"},
}


def test_run_safety_validation_fans_out_validators_in_parallel():
    def _slow_rules(*args, **kwargs):
        time.sleep(0.2)
        return {"verdict": "SAFE", "details": {"validator": "rules"}}

    def _slow_cbf(*args, **kwargs):
        time.sleep(0.2)
        return {"verdict": "SAFE", "details": {"validator": "cbf"}}

    def _slow_sim(*args, **kwargs):
        time.sleep(0.2)
        return {"verdict": "INDETERMINATE", "details": {"validator": "simulation"}}

    started = time.perf_counter()
    with (
        patch.object(service, "_fetch_asset_profile", return_value=PROFILE),
        patch.object(service, "_get_cbf_state_mappings", return_value=[{"dummy": True}]),
        patch.object(service, "_run_rules_validator", side_effect=_slow_rules),
        patch.object(service, "_run_cbf_validator", side_effect=_slow_cbf),
        patch.object(service, "_run_simulation_validator", side_effect=_slow_sim),
    ):
        result = service.run_safety_validation(
            transaction_id="tx-parallel",
            asset_id="reactor_01",
            policy_version_id="v-test",
            action_sequence=[],
            current_sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        )
    elapsed = time.perf_counter() - started

    assert result["final_verdict"] == "SAFE"
    assert elapsed < 0.45
    assert result["validators"]["rules"]["verdict"] == "SAFE"
    assert result["validators"]["cbf"]["verdict"] == "SAFE"
    assert result["validators"]["simulation"]["verdict"] == "INDETERMINATE"


def test_run_safety_validation_propagates_validator_failures():
    with (
        patch.object(service, "_fetch_asset_profile", return_value=PROFILE),
        patch.object(service, "_get_cbf_state_mappings", return_value=[{"dummy": True}]),
        patch.object(service, "_run_rules_validator", side_effect=RuntimeError("rules boom")),
        patch.object(service, "_run_cbf_validator", return_value={"verdict": "SAFE", "details": {}}),
        patch.object(service, "_run_simulation_validator", return_value={"verdict": "INDETERMINATE", "details": {}}),
    ):
        with pytest.raises(RuntimeError, match="rules boom"):
            service.run_safety_validation(
                transaction_id="tx-fail",
                asset_id="reactor_01",
                policy_version_id="v-test",
                action_sequence=[],
                current_sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
            )


def test_run_simulation_validator_passes_collision_constraints():
    backend = MagicMock()
    backend.validate_trajectory.return_value = {"verdict": "SAFE", "details": {}}

    collision = {
        "enabled": True,
        "probe_radius_m": 0.05,
        "forbidden_objects": [
            {"object_id": "fixture_a", "center": [0.5, 0.0, 0.5], "scale": [0.1, 0.1, 0.1]}
        ],
    }

    with patch.object(service, "_resolve_simulation_backend", return_value=(backend, "isaac_sim")):
        result = service._run_simulation_validator(
            current_sensor_snapshot={"joint_positions": [0.0] * 9},
            action_sequence=[{"action_type": "move_joint", "params": {"target_positions": [0.1] * 9}}],
            ruleset=[],
            sim_config={"engine": "isaac_sim", "collision": collision},
        )

    assert result["verdict"] == "SAFE"
    sent_constraints = backend.validate_trajectory.call_args.kwargs["constraints"]
    assert sent_constraints["collision"]["enabled"] is True
    assert sent_constraints["collision"]["forbidden_objects"][0]["object_id"] == "fixture_a"
