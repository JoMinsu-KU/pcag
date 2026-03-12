"""
Rules Validator Service
============================================
이 모듈은 정적 규칙(Rule) 기반의 안전 검증 로직을 구현합니다.
사전에 정의된 임계값, 범위, 허용 목록 등을 현재 상태와 비교합니다.

PCAG 파이프라인 위치:
  [121] Rules Validator (Safety Cluster 내부)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §RulesValidator
"""

from typing import Any, Optional
from ..models.common import Rule, ValidatorVerdict, RuleType

def _get_nested_value(data: dict, path: str) -> Any:
    """
    점(dot) 표기법을 사용하여 중첩된 딕셔너리에서 값을 검색합니다.
    예: "sensor.temperature" -> data["sensor"]["temperature"]
    """
    keys = path.split('.')
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None # 필드가 없으면 None 반환
    return current

def _check_rule_logic(value: Any, rule: Rule) -> Optional[str]:
    """
    단일 값에 대해 규칙 위반 여부를 검사하고, 위반 시 사유를 반환합니다.
    """
    # 규칙 유형별 검증 로직
    if rule.type == RuleType.THRESHOLD:
        # 임계값 비교 (크기 비교)
        op = rule.operator
        threshold = rule.value
        
        # None safe comparison? Assuming validated before calling or handling TypeError
        try:
            if op == "lt" and not (value < threshold):
                return f"Value {value} not < {threshold}"
            elif op == "lte" and not (value <= threshold):
                return f"Value {value} not <= {threshold}"
            elif op == "gt" and not (value > threshold):
                return f"Value {value} not > {threshold}"
            elif op == "gte" and not (value >= threshold):
                return f"Value {value} not >= {threshold}"
            elif op == "eq" and not (value == threshold):
                return f"Value {value} != {threshold}"
            elif op == "ne" and not (value != threshold):
                return f"Value {value} == {threshold}"
        except TypeError:
            return f"Type mismatch for comparison: {value} vs {threshold}"
            
    elif rule.type == RuleType.RANGE:
        # 범위 확인 (Min/Max)
        min_val = rule.min
        max_val = rule.max
        try:
            if min_val is not None and value < min_val:
                return f"Value {value} < min {min_val}"
            if max_val is not None and value > max_val:
                return f"Value {value} > max {max_val}"
        except TypeError:
            return f"Type mismatch for range check: {value}"
            
    elif rule.type == RuleType.ENUM:
        # 허용된 값 목록 확인
        allowed = rule.allowed_values or []
        if value not in allowed:
            return f"Value {value} not in {allowed}"
            
    elif rule.type == RuleType.FORBIDDEN_COMBINATION:
        # 금지된 상태 조합 확인
        if rule.forbidden_pairs:
            for pair in rule.forbidden_pairs:
                if value == pair: # 정확한 일치 여부 확인
                    return f"Value {value} matches forbidden pair {pair}"
    
    return None

def validate_rules(
    sensor_snapshot: dict,
    action_sequence: list[dict],
    ruleset: list[Rule],
) -> ValidatorVerdict:
    """
    현재 센서 상태 및 액션 파라미터가 정적 규칙 세트(Ruleset)를 위반하는지 검증합니다.
    
    Args:
        sensor_snapshot (dict): 현재 센서 데이터 스냅샷
        action_sequence (list[dict]): 실행 예정인 액션 시퀀스
        ruleset (list[Rule]): 검증할 규칙 목록
        
    Returns:
        ValidatorVerdict: 검증 결과 (SAFE/UNSAFE 및 위반된 규칙 목록)
    """
    
    violated_rules = []
    
    for rule in ruleset:
        # 검증 대상 값 수집 (소스, 값) 튜플 리스트
        values_to_validate = []
        
        # 1. 센서 스냅샷에서 검색
        sensor_val = _get_nested_value(sensor_snapshot, rule.target_field)
        if sensor_val is not None:
            values_to_validate.append(("Sensor", sensor_val))
            
        # 2. 액션 시퀀스 파라미터에서 검색
        if action_sequence:
            for i, action in enumerate(action_sequence):
                # action['params'] 내부 검색 (예: target_field="velocity" -> params["velocity"])
                params = action.get("params")
                if isinstance(params, dict):
                    param_val = _get_nested_value(params, rule.target_field)
                    if param_val is not None:
                        values_to_validate.append((f"Action[{i}]", param_val))
                
                # action 최상위 검색 (예: target_field="action_type")
                action_val = _get_nested_value(action, rule.target_field)
                if action_val is not None:
                     # params 내부와 중복되지 않도록 확인 (params가 아닌 경우만)
                     if action_val is not params: 
                         values_to_validate.append((f"Action[{i}].Field", action_val))

        # 대상 필드가 어디에도 없는 경우
        if not values_to_validate and rule.type != RuleType.FORBIDDEN_COMBINATION:
            # 금지된 조합 외의 규칙에서 필드가 없으면 위반으로 간주 (데이터 불완전)
            violated_rules.append({
                "rule_id": rule.rule_id, 
                "reason": f"Field '{rule.target_field}' missing in sensor snapshot and action parameters"
            })
            continue

        # 수집된 모든 값에 대해 규칙 검증
        for source, val in values_to_validate:
            reason = _check_rule_logic(val, rule)
            if reason:
                violated_rules.append({
                    "rule_id": rule.rule_id,
                    "reason": f"[{source}] {reason}"
                })
                    
    # 하나라도 위반된 규칙이 있으면 UNSAFE
    if violated_rules:
        return ValidatorVerdict(verdict="UNSAFE", details={"violated_rules": violated_rules})
    
    # 위반 사항이 없으면 SAFE
    return ValidatorVerdict(verdict="SAFE")
