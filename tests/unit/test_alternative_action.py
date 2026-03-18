import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.core.services.alternative_action import generate_alternative_actions


def test_generate_alternative_actions_from_safe_state():
    asset_profile = {
        "execution": {
            "safe_state": [
                {"action_type": "set_heater_output", "params": {"value": 0}},
                {"action_type": "set_cooling_valve", "params": {"value": 100}},
            ]
        }
    }

    proposals = generate_alternative_actions(asset_profile, "REVERIFY_HASH_MISMATCH")
    assert len(proposals) == 2
    assert proposals[0]["source"] == "policy.safe_state"


def test_generate_alternative_actions_empty_when_no_safe_state():
    assert generate_alternative_actions({}, "LOCK_DENIED") == []
