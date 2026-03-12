from pcag.core.services.rules_validator import validate_rules
from pcag.core.models.common import Rule, RuleType, ValidatorVerdict

def test_threshold_rule():
    r = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="temp", operator="lt", value=100.0)
    
    # Safe
    res = validate_rules({"temp": 99.0}, [], [r])
    assert res.verdict == "SAFE"
    
    # Unsafe
    res = validate_rules({"temp": 100.0}, [], [r])
    assert res.verdict == "UNSAFE"
    assert len(res.details["violated_rules"]) == 1
    assert res.details["violated_rules"][0]["rule_id"] == "r1"

def test_range_rule():
    r = Rule(rule_id="r2", type=RuleType.RANGE, target_field="pressure", min=10.0, max=20.0)
    
    # Safe
    assert validate_rules({"pressure": 15.0}, [], [r]).verdict == "SAFE"
    assert validate_rules({"pressure": 10.0}, [], [r]).verdict == "SAFE"
    assert validate_rules({"pressure": 20.0}, [], [r]).verdict == "SAFE"
    
    # Unsafe
    assert validate_rules({"pressure": 9.9}, [], [r]).verdict == "UNSAFE"
    assert validate_rules({"pressure": 20.1}, [], [r]).verdict == "UNSAFE"

def test_enum_rule():
    r = Rule(rule_id="r3", type=RuleType.ENUM, target_field="status", allowed_values=["IDLE", "RUNNING"])
    
    assert validate_rules({"status": "IDLE"}, [], [r]).verdict == "SAFE"
    assert validate_rules({"status": "ERROR"}, [], [r]).verdict == "UNSAFE"

def test_forbidden_combination_rule():
    # Interpreted as: if target_field matches any forbidden pair (or value)
    # Assuming target_field is a list or we check against a list
    # Let's test checking if a list value matches forbidden
    r = Rule(
        rule_id="r4", 
        type=RuleType.FORBIDDEN_COMBINATION, 
        target_field="pos", 
        forbidden_pairs=[["A", "B"], ["C", "D"]]
    )
    
    assert validate_rules({"pos": ["A", "C"]}, [], [r]).verdict == "SAFE"
    assert validate_rules({"pos": ["A", "B"]}, [], [r]).verdict == "UNSAFE"

def test_nested_field_access():
    r = Rule(rule_id="r5", type=RuleType.THRESHOLD, target_field="system.cpu.temp", operator="gt", value=80.0)
    
    # Safe
    assert validate_rules({"system": {"cpu": {"temp": 81.0}}}, [], [r]).verdict == "SAFE" # Wait, op is gt 80?
    # If op is gt, then value must be > 80.
    # Actually, usually threshold rule implies "Safe if condition met" or "Unsafe if condition met"?
    # Validator logic:
    # "threshold: Get sensor_snapshot[target_field], compare with operator (lt, lte, gt, gte, eq, ne) against value"
    # "Return SAFE if all rules pass"
    # So if rule is "lt 100", then value < 100 is PASS (SAFE).
    # My previous test: operator="lt", value=100. 99 < 100 -> SAFE.
    # Here: operator="gt", value=80. 
    # If 81 > 80 -> SAFE.
    # If 79 > 80 -> False -> UNSAFE.
    
    assert validate_rules({"system": {"cpu": {"temp": 81.0}}}, [], [r]).verdict == "SAFE"
    assert validate_rules({"system": {"cpu": {"temp": 79.0}}}, [], [r]).verdict == "UNSAFE"

def test_multiple_rules():
    r1 = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="a", operator="eq", value=1)
    r2 = Rule(rule_id="r2", type=RuleType.THRESHOLD, target_field="b", operator="eq", value=2)
    
    # All pass
    assert validate_rules({"a": 1, "b": 2}, [], [r1, r2]).verdict == "SAFE"
    
    # One fail
    res = validate_rules({"a": 1, "b": 3}, [], [r1, r2])
    assert res.verdict == "UNSAFE"
    assert len(res.details["violated_rules"]) == 1
    assert res.details["violated_rules"][0]["rule_id"] == "r2"

def test_validate_action_params():
    # Rule: speed <= 10
    r = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="speed", operator="lte", value=10.0)
    
    # 1. Action parameter is SAFE
    action_seq = [{"params": {"speed": 5.0}}]
    res = validate_rules({}, action_seq, [r])
    assert res.verdict == "SAFE"
    
    # 2. Action parameter is UNSAFE
    action_seq_unsafe = [{"params": {"speed": 15.0}}]
    res = validate_rules({}, action_seq_unsafe, [r])
    assert res.verdict == "UNSAFE"
    assert "Action[0]" in res.details["violated_rules"][0]["reason"]
    
def test_validate_both_sources():
    # Rule: temp <= 50
    r = Rule(rule_id="r2", type=RuleType.THRESHOLD, target_field="temp", operator="lte", value=50.0)
    
    # Sensor: 40 (Safe), Action: 45 (Safe)
    res = validate_rules({"temp": 40.0}, [{"params": {"temp": 45.0}}], [r])
    assert res.verdict == "SAFE"
    
    # Sensor: 60 (Unsafe), Action: 45 (Safe) -> UNSAFE
    res = validate_rules({"temp": 60.0}, [{"params": {"temp": 45.0}}], [r])
    assert res.verdict == "UNSAFE"
    assert "Sensor" in res.details["violated_rules"][0]["reason"]
    
    # Sensor: 40 (Safe), Action: 55 (Unsafe) -> UNSAFE
    res = validate_rules({"temp": 40.0}, [{"params": {"temp": 55.0}}], [r])
    assert res.verdict == "UNSAFE"
    assert "Action[0]" in res.details["violated_rules"][0]["reason"]
    
def test_missing_field_logic():
    r = Rule(rule_id="r3", type=RuleType.THRESHOLD, target_field="pressure", operator="lt", value=100.0)
    
    # Missing in both -> Violation (Missing field)
    res = validate_rules({"temp": 10}, [{"params": {"speed": 5}}], [r])
    assert res.verdict == "UNSAFE"
    assert "missing" in res.details["violated_rules"][0]["reason"]
    
    # Present in sensor only -> Checked (Safe)
    res = validate_rules({"pressure": 50}, [{"params": {"speed": 5}}], [r])
    assert res.verdict == "SAFE"
    
    # Present in action only -> Checked (Safe)
    res = validate_rules({"temp": 10}, [{"params": {"pressure": 50}}], [r])
    assert res.verdict == "SAFE"

def test_nested_action_params():
    r = Rule(rule_id="r4", type=RuleType.THRESHOLD, target_field="config.level", operator="eq", value=1)
    
    # Action params nested
    action = {"params": {"config": {"level": 1}}}
    res = validate_rules({}, [action], [r])
    assert res.verdict == "SAFE"
    
    action_unsafe = {"params": {"config": {"level": 2}}}
    res = validate_rules({}, [action_unsafe], [r])
    assert res.verdict == "UNSAFE"

def test_top_level_action_field():
    # Check action_type
    r = Rule(rule_id="r5", type=RuleType.ENUM, target_field="action_type", allowed_values=["move", "stop"])
    
    action = {"action_type": "move", "params": {}}
    res = validate_rules({}, [action], [r])
    assert res.verdict == "SAFE"
    
    action_unsafe = {"action_type": "explode", "params": {}}
    res = validate_rules({}, [action_unsafe], [r])
    assert res.verdict == "UNSAFE"
