
import pytest
from pcag.core.services.rules_validator import validate_rules
from pcag.core.models.common import Rule, RuleType

def test_validate_rules_checks_action_params():
    """
    Test that rules_validator checks action parameters, not just sensor state.
    """
    # Rule: joint_1 must be <= 1.7
    rule = Rule(
        rule_id="limit_joint_1",
        target_field="joint_1",
        type=RuleType.THRESHOLD,
        operator="lte",
        value=1.7
    )
    
    # Sensor says joint_1 = 0.0 (SAFE)
    sensor_snapshot = {"joint_1": 0.0}
    
    # Action commands joint_1 = 2.5 (UNSAFE)
    action_sequence = [
        {
            "action_type": "move_joint",
            "params": {"joint_1": 2.5}
        }
    ]
    
    # Expect UNSAFE because action violates rule
    result = validate_rules(sensor_snapshot, action_sequence, [rule])
    
    assert result.verdict == "UNSAFE", f"Expected UNSAFE, got {result.verdict}. Details: {result.details}"
    assert len(result.details["violated_rules"]) >= 1
    
    violation = result.details["violated_rules"][0]
    assert violation["rule_id"] == "limit_joint_1"
    # Ensure reason mentions it came from Action/Parameter
    # (The implementation should ensure this)

def test_validate_rules_checks_sensor_and_action():
    """
    Test that it still checks sensor state AND action params.
    """
    # Rule: temperature < 100
    rule = Rule(
        rule_id="limit_temp",
        target_field="temperature",
        type=RuleType.THRESHOLD,
        operator="lt",
        value=100
    )
    
    # Case 1: Sensor UNSAFE, Action SAFE -> UNSAFE
    result1 = validate_rules(
        {"temperature": 150}, 
        [{"params": {"temperature": 50}}], 
        [rule]
    )
    assert result1.verdict == "UNSAFE"
    
    # Case 2: Sensor SAFE, Action UNSAFE -> UNSAFE
    result2 = validate_rules(
        {"temperature": 50}, 
        [{"params": {"temperature": 150}}], 
        [rule]
    )
    assert result2.verdict == "UNSAFE"
    
    # Case 3: Both SAFE -> SAFE
    result3 = validate_rules(
        {"temperature": 50}, 
        [{"params": {"temperature": 50}}], 
        [rule]
    )
    assert result3.verdict == "SAFE"

def test_validate_rules_nested_params():
    """
    Test checking nested parameters in action.
    """
    rule = Rule(
        rule_id="limit_nested",
        target_field="config.level",
        type=RuleType.THRESHOLD,
        operator="lt",
        value=5
    )
    
    sensor_snapshot = {}
    action_sequence = [
        {
            "params": {
                "config": {
                    "level": 10 # UNSAFE
                }
            }
        }
    ]
    
    result = validate_rules(sensor_snapshot, action_sequence, [rule])
    assert result.verdict == "UNSAFE"
