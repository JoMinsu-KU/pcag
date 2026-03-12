"""Tests for CBF Safety Filter (Phase 1 — Static Safety Margin)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pcag.core.services.cbf_validator import StaticCBFValidator
from pcag.core.ports.cbf_validator import ICBFValidator


# ============================================================
# Setup
# ============================================================

def make_validator():
    return StaticCBFValidator()


# Reactor ruleset
REACTOR_RULESET = [
    {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0},
    {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 120.0},
    {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.5, "max": 3.0},
]

REACTOR_CBF_MAPPINGS = [
    {"action_type": "set_heater_output", "param": "value", "maps_to_field": "heater_output"},
    {"action_type": "set_cooling_valve", "param": "value", "maps_to_field": "cooling_valve"},
]

# Robot ruleset
ROBOT_RULESET = [
    {"rule_id": "joint_0_limit", "type": "range", "target_field": "joint_0", "min": -2.897, "max": 2.897},
    {"rule_id": "joint_1_limit", "type": "range", "target_field": "joint_1", "min": -1.763, "max": 1.763},
    {"rule_id": "joint_3_limit", "type": "range", "target_field": "joint_3", "min": -3.072, "max": -0.070},
]

ROBOT_CBF_MAPPINGS = [
    {"action_type": "move_joint", "param": "target_joint_0", "maps_to_field": "joint_0"},
    {"action_type": "move_joint", "param": "target_joint_1", "maps_to_field": "joint_1"},
    {"action_type": "move_joint", "param": "target_joint_3", "maps_to_field": "joint_3"},
]

# AGV ruleset (distance-based would need custom logic; using position bounds)
AGV_RULESET = [
    {"rule_id": "agv_x_bounds", "type": "range", "target_field": "position_x", "min": 0.0, "max": 10.0},
    {"rule_id": "agv_y_bounds", "type": "range", "target_field": "position_y", "min": 0.0, "max": 10.0},
]

AGV_CBF_MAPPINGS = [
    {"action_type": "move_to", "param": "target_x", "maps_to_field": "position_x"},
    {"action_type": "move_to", "param": "target_y", "maps_to_field": "position_y"},
]


# ============================================================
# Basic Tests
# ============================================================

def test_cbf_is_icbf_validator():
    """StaticCBFValidator should implement ICBFValidator."""
    v = make_validator()
    assert isinstance(v, ICBFValidator)


def test_cbf_never_indeterminate():
    """CBF should never return INDETERMINATE."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=[]
    )
    assert result["verdict"] in ("SAFE", "UNSAFE")


# ============================================================
# Reactor Scenario Tests
# ============================================================

def test_reactor_safe_state():
    """Reactor at 150C, 1.5atm — well within limits."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5, "heater_output": 50},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=REACTOR_CBF_MAPPINGS
    )
    assert result["verdict"] == "SAFE"
    assert result["details"]["min_barrier_value"] > 0
    # Min barrier: min(180-150=30, 150-120=30, 1.5-0.5=1.0, 3.0-1.5=1.5) = 1.0
    assert abs(result["details"]["min_barrier_value"] - 1.0) < 0.01


def test_reactor_unsafe_current_state():
    """Reactor at 185C — exceeds max temperature."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 185, "pressure": 1.5},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=REACTOR_CBF_MAPPINGS
    )
    assert result["verdict"] == "UNSAFE"
    assert result["details"]["min_barrier_value"] <= 0
    # barrier for max_temp: 180 - 185 = -5
    assert result["details"]["min_barrier_value"] == -5.0


def test_reactor_boundary_state():
    """Reactor at exactly 180C — on the boundary (h=0 → SAFE in CBF theory)."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 180, "pressure": 1.5},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=REACTOR_CBF_MAPPINGS
    )
    assert result["verdict"] == "SAFE"  # barrier = 0 → SAFE (h(x) >= 0 is safe set)
    assert result["details"]["min_barrier_value"] == 0.0


def test_reactor_action_no_direct_effect():
    """Setting heater_output doesn't directly affect temperature barrier."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5, "heater_output": 50},
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 100}}
        ],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=REACTOR_CBF_MAPPINGS
    )
    # heater_output changes but temperature rules don't check heater_output
    # So barriers remain the same as current state
    assert result["verdict"] == "SAFE"


# ============================================================
# Robot Scenario Tests
# ============================================================

def test_robot_safe_movement():
    """Move joints within limits."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 1.0, "target_joint_1": -0.5, "target_joint_3": -2.0}}
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    assert result["verdict"] == "SAFE"
    assert result["details"]["min_barrier_value"] > 0


def test_robot_unsafe_joint_exceeds_limit():
    """Move joint_0 to 5.0 rad — exceeds limit [-2.897, 2.897]."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 5.0, "target_joint_1": 0.0, "target_joint_3": -1.5}}
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    assert result["verdict"] == "UNSAFE"
    assert result["details"]["first_violation_step"] == 0
    # barrier: 2.897 - 5.0 = -2.103
    assert result["details"]["min_barrier_value"] < 0


def test_robot_barrier_value_decreases():
    """Moving closer to boundary should reduce barrier value."""
    v = make_validator()
    
    # Far from boundary
    result_far = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 1.0, "target_joint_1": 0.0, "target_joint_3": -1.5}}
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    
    # Close to boundary
    result_close = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 2.5, "target_joint_1": 0.0, "target_joint_3": -1.5}}
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    
    assert result_far["details"]["min_barrier_value"] > result_close["details"]["min_barrier_value"]
    assert result_close["verdict"] == "SAFE"  # 2.5 is still within [-2.897, 2.897]


# ============================================================
# AGV Scenario Tests
# ============================================================

def test_agv_safe_movement():
    """Move AGV within grid bounds."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"position_x": 5.0, "position_y": 5.0},
        action_sequence=[
            {"action_type": "move_to", "params": {"target_x": 7.0, "target_y": 3.0}}
        ],
        ruleset=AGV_RULESET,
        cbf_state_mappings=AGV_CBF_MAPPINGS
    )
    assert result["verdict"] == "SAFE"


def test_agv_out_of_bounds():
    """Move AGV outside grid (x=12 > max=10)."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"position_x": 5.0, "position_y": 5.0},
        action_sequence=[
            {"action_type": "move_to", "params": {"target_x": 12.0, "target_y": 5.0}}
        ],
        ruleset=AGV_RULESET,
        cbf_state_mappings=AGV_CBF_MAPPINGS
    )
    assert result["verdict"] == "UNSAFE"
    # barrier: 10.0 - 12.0 = -2.0
    assert result["details"]["min_barrier_value"] < 0


# ============================================================
# Multi-Step Action Tests
# ============================================================

def test_multi_step_safe_then_unsafe():
    """First action safe, second action unsafe — should catch second."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 1.0, "target_joint_1": 0.0, "target_joint_3": -1.5}},
            {"action_type": "move_joint", "params": {"target_joint_0": 5.0, "target_joint_1": 0.0, "target_joint_3": -1.5}},
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    assert result["verdict"] == "UNSAFE"
    assert result["details"]["first_violation_step"] == 1  # Second action (index 1)


def test_empty_action_sequence():
    """No actions — just evaluate current state."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=[]
    )
    assert result["verdict"] == "SAFE"


def test_no_matching_mapping():
    """Action type doesn't match any mapping — projected state = current state."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5},
        action_sequence=[
            {"action_type": "unknown_action", "params": {"value": 999}}
        ],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=REACTOR_CBF_MAPPINGS
    )
    # No mapping for "unknown_action", so projected state = current state
    # Barriers unchanged
    assert result["verdict"] == "SAFE"


def test_details_contain_projected_states():
    """Result should include projected_states for transparency."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"joint_0": 0.0, "joint_1": 0.0, "joint_3": -1.5},
        action_sequence=[
            {"action_type": "move_joint", "params": {"target_joint_0": 1.0, "target_joint_1": -0.5, "target_joint_3": -2.0}}
        ],
        ruleset=ROBOT_RULESET,
        cbf_state_mappings=ROBOT_CBF_MAPPINGS
    )
    assert "projected_states" in result["details"]
    assert len(result["details"]["projected_states"]) == 1
    ps = result["details"]["projected_states"][0]
    assert ps["step"] == 0
    assert ps["action_type"] == "move_joint"
    assert ps["projected_state"]["joint_0"] == 1.0


def test_computation_time_recorded():
    """Result should include computation_time_ms."""
    v = make_validator()
    result = v.validate_safety(
        current_state={"temperature": 150, "pressure": 1.5},
        action_sequence=[],
        ruleset=REACTOR_RULESET,
        cbf_state_mappings=[]
    )
    assert "computation_time_ms" in result["details"]
    assert result["details"]["computation_time_ms"] >= 0
