"""Parallel orchestration tests for Safety Cluster."""

import os
import sys
import time
from unittest.mock import patch

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
