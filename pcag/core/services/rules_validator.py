"""
정책 ruleset 기반의 결정론적 안전 검증기.

Rules validator는 가장 설명 가능성이 높은 1차 필터다.
센서 상태와 action 파라미터를 정책 문서에 직접 대조해,
어떤 규칙이 왜 위반됐는지를 사람이 읽을 수 있는 형태로 반환한다.
"""

from typing import Any, Optional

from ..models.common import Rule, RuleCondition, RuleType, ValidatorVerdict


def _get_nested_value(data: dict, path: str) -> Any:
    """dot path 형태의 필드 경로에서 값을 꺼낸다."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _compare_values(actual: Any, operator: str, expected: Any) -> Optional[str]:
    """비교 실패 시 사람이 읽을 수 있는 위반 사유를 만든다."""
    try:
        if operator == "lt" and not (actual < expected):
            return f"Value {actual} not < {expected}"
        if operator == "lte" and not (actual <= expected):
            return f"Value {actual} not <= {expected}"
        if operator == "gt" and not (actual > expected):
            return f"Value {actual} not > {expected}"
        if operator == "gte" and not (actual >= expected):
            return f"Value {actual} not >= {expected}"
        if operator == "eq" and not (actual == expected):
            return f"Value {actual} != {expected}"
        if operator == "ne" and not (actual != expected):
            return f"Value {actual} == {expected}"
    except TypeError:
        return f"Type mismatch for comparison: {actual} vs {expected}"

    return None


def _check_rule_logic(value: Any, rule: Rule, source_data: Optional[dict] = None) -> Optional[str]:
    """단일 rule의 실제 판정 로직을 수행한다."""
    if rule.type == RuleType.THRESHOLD:
        return _compare_values(value, rule.operator or "eq", rule.value)

    if rule.type == RuleType.RANGE:
        try:
            if rule.min is not None and value < rule.min:
                return f"Value {value} < min {rule.min}"
            if rule.max is not None and value > rule.max:
                return f"Value {value} > max {rule.max}"
        except TypeError:
            return f"Type mismatch for range check: {value}"
        return None

    if rule.type == RuleType.ENUM:
        allowed = rule.allowed_values or []
        if value not in allowed:
            return f"Value {value} not in {allowed}"
        return None

    if rule.type == RuleType.FORBIDDEN_COMBINATION:
        # 다필드 조합 금지는 "각 필드가 동시에 조건을 만족했는가"를 본다.
        # 즉 단일 값 비교가 아니라 현재 상태 전체(source_data)를 함께 봐야 한다.
        if rule.conditions and source_data is not None:
            failing_conditions: list[str] = []
            for condition in rule.conditions:
                actual = _get_nested_value(source_data, condition.field)
                if actual is None:
                    failing_conditions.append(f"{condition.field}=<missing>")
                    break

                mismatch = _compare_values(actual, condition.operator, condition.value)
                if mismatch:
                    failing_conditions.append(mismatch)
                    break

            if not failing_conditions:
                condition_text = ", ".join(
                    f"{condition.field} {condition.operator} {condition.value}"
                    for condition in rule.conditions
                )
                return f"Forbidden combination matched: {condition_text}"
            return None

        if rule.forbidden_pairs:
            for pair in rule.forbidden_pairs:
                if value == pair:
                    return f"Value {value} matches forbidden pair {pair}"
                if isinstance(value, (list, tuple, set)) and all(item in value for item in pair):
                    return f"Value {value} contains forbidden pair {pair}"

    return None


def _evaluate_source(rule: Rule, source_name: str, source_data: dict) -> list[dict]:
    """하나의 source payload에 대해 rule을 평가하고 위반 목록을 반환한다."""
    violations: list[dict] = []

    if rule.type == RuleType.FORBIDDEN_COMBINATION and rule.conditions:
        reason = _check_rule_logic(None, rule, source_data)
        if reason:
            violations.append({"rule_id": rule.rule_id, "reason": f"[{source_name}] {reason}"})
        return violations

    value = _get_nested_value(source_data, rule.target_field)
    if value is None:
        return violations

    reason = _check_rule_logic(value, rule, source_data)
    if reason:
        violations.append({"rule_id": rule.rule_id, "reason": f"[{source_name}] {reason}"})

    return violations


def validate_rules(sensor_snapshot: dict, action_sequence: list[dict], ruleset: list[Rule]) -> ValidatorVerdict:
    """
    센서 상태와 action 파라미터를 정책 ruleset에 대조한다.

    같은 rule을 센서 / action.params / action 자체에 각각 적용하는 이유는,
    정책 필드가 어느 레이어에 실려 오더라도 동일한 rule 표현식을 재사용하기 위해서다.
    """
    violated_rules: list[dict] = []

    for rule in ruleset:
        found_any_source = False

        sensor_violations = _evaluate_source(rule, "Sensor", sensor_snapshot)
        if sensor_violations:
            found_any_source = True
            violated_rules.extend(sensor_violations)
        elif _get_nested_value(sensor_snapshot, rule.target_field) is not None or (rule.type == RuleType.FORBIDDEN_COMBINATION and rule.conditions):
            found_any_source = True

        for idx, action in enumerate(action_sequence or []):
            params = action.get("params") if isinstance(action, dict) else None
            if isinstance(params, dict):
                param_violations = _evaluate_source(rule, f"Action[{idx}]", params)
                if param_violations:
                    found_any_source = True
                    violated_rules.extend(param_violations)
                elif _get_nested_value(params, rule.target_field) is not None or (rule.type == RuleType.FORBIDDEN_COMBINATION and rule.conditions):
                    found_any_source = True

            if isinstance(action, dict):
                action_field_violations = _evaluate_source(rule, f"Action[{idx}].Field", action)
                if action_field_violations:
                    found_any_source = True
                    violated_rules.extend(action_field_violations)
                elif _get_nested_value(action, rule.target_field) is not None:
                    found_any_source = True

        if not found_any_source and rule.type != RuleType.FORBIDDEN_COMBINATION:
            violated_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "reason": f"Field '{rule.target_field}' missing in sensor snapshot and action parameters",
                }
            )

    if violated_rules:
        return ValidatorVerdict(verdict="UNSAFE", details={"violated_rules": violated_rules})

    return ValidatorVerdict(verdict="SAFE")
