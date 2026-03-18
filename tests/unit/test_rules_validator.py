from pcag.core.models.common import Rule, RuleCondition, RuleType
from pcag.core.services.rules_validator import validate_rules


def test_threshold_rule():
    rule = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="temp", operator="lt", value=100.0)
    assert validate_rules({"temp": 99.0}, [], [rule]).verdict == "SAFE"
    assert validate_rules({"temp": 100.0}, [], [rule]).verdict == "UNSAFE"


def test_range_rule():
    rule = Rule(rule_id="r2", type=RuleType.RANGE, target_field="pressure", min=10.0, max=20.0)
    assert validate_rules({"pressure": 15.0}, [], [rule]).verdict == "SAFE"
    assert validate_rules({"pressure": 9.9}, [], [rule]).verdict == "UNSAFE"


def test_enum_rule():
    rule = Rule(rule_id="r3", type=RuleType.ENUM, target_field="status", allowed_values=["IDLE", "RUNNING"])
    assert validate_rules({"status": "IDLE"}, [], [rule]).verdict == "SAFE"
    assert validate_rules({"status": "ERROR"}, [], [rule]).verdict == "UNSAFE"


def test_forbidden_combination_rule_with_conditions():
    rule = Rule(
        rule_id="r4",
        type=RuleType.FORBIDDEN_COMBINATION,
        target_field="door_open",
        conditions=[
            RuleCondition(field="door_open", operator="eq", value=True),
            RuleCondition(field="motor_on", operator="eq", value=True),
        ],
    )

    assert validate_rules({"door_open": True, "motor_on": False}, [], [rule]).verdict == "SAFE"
    result = validate_rules({"door_open": True, "motor_on": True}, [], [rule])
    assert result.verdict == "UNSAFE"
    assert "Forbidden combination matched" in result.details["violated_rules"][0]["reason"]


def test_forbidden_combination_legacy_pairs_still_work():
    rule = Rule(
        rule_id="r5",
        type=RuleType.FORBIDDEN_COMBINATION,
        target_field="pos",
        forbidden_pairs=[["A", "B"], ["C", "D"]],
    )

    assert validate_rules({"pos": ["A", "C"]}, [], [rule]).verdict == "SAFE"
    assert validate_rules({"pos": ["A", "B"]}, [], [rule]).verdict == "UNSAFE"


def test_nested_field_access():
    rule = Rule(rule_id="r6", type=RuleType.THRESHOLD, target_field="system.cpu.temp", operator="gt", value=80.0)
    assert validate_rules({"system": {"cpu": {"temp": 81.0}}}, [], [rule]).verdict == "SAFE"
    assert validate_rules({"system": {"cpu": {"temp": 79.0}}}, [], [rule]).verdict == "UNSAFE"


def test_multiple_rules():
    r1 = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="a", operator="eq", value=1)
    r2 = Rule(rule_id="r2", type=RuleType.THRESHOLD, target_field="b", operator="eq", value=2)
    assert validate_rules({"a": 1, "b": 2}, [], [r1, r2]).verdict == "SAFE"
    result = validate_rules({"a": 1, "b": 3}, [], [r1, r2])
    assert result.verdict == "UNSAFE"
    assert result.details["violated_rules"][0]["rule_id"] == "r2"


def test_validate_action_params():
    rule = Rule(rule_id="r1", type=RuleType.THRESHOLD, target_field="speed", operator="lte", value=10.0)
    assert validate_rules({}, [{"params": {"speed": 5.0}}], [rule]).verdict == "SAFE"
    result = validate_rules({}, [{"params": {"speed": 15.0}}], [rule])
    assert result.verdict == "UNSAFE"
    assert "Action[0]" in result.details["violated_rules"][0]["reason"]


def test_validate_both_sources():
    rule = Rule(rule_id="r2", type=RuleType.THRESHOLD, target_field="temp", operator="lte", value=50.0)
    assert validate_rules({"temp": 40.0}, [{"params": {"temp": 45.0}}], [rule]).verdict == "SAFE"
    assert validate_rules({"temp": 60.0}, [{"params": {"temp": 45.0}}], [rule]).verdict == "UNSAFE"
    assert validate_rules({"temp": 40.0}, [{"params": {"temp": 55.0}}], [rule]).verdict == "UNSAFE"


def test_missing_field_logic():
    rule = Rule(rule_id="r3", type=RuleType.THRESHOLD, target_field="pressure", operator="lt", value=100.0)
    result = validate_rules({"temp": 10}, [{"params": {"speed": 5}}], [rule])
    assert result.verdict == "UNSAFE"
    assert "missing" in result.details["violated_rules"][0]["reason"]
