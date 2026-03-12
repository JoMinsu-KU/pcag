"""
CBF Validator Service
============================================
이 모듈은 CBF(Control Barrier Function) 기반의 안전 필터링 서비스입니다.
수학적 모델을 사용하여 시스템 상태가 정의된 안전 집합 내에 유지되는지 검증합니다.

PCAG 파이프라인 위치:
  [122] CBF Validator (Safety Cluster 내부)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §CBFValidator
"""

import time
import copy
import logging
from pcag.core.ports.cbf_validator import ICBFValidator

logger = logging.getLogger(__name__)


class StaticCBFValidator(ICBFValidator):
    """
    정적 CBF 검증기 구현 (Phase 1).
    
    규칙 세트(Ruleset)를 안전 경계(Safety Boundary)로 변환하여,
    현재 상태와 액션 실행 후의 예측 상태가 경계 내에 머무르는지(안전 여유 > 0) 확인합니다.
    """
    
    def validate_safety(
        self,
        current_state: dict,
        action_sequence: list[dict],
        ruleset: list,
        cbf_state_mappings: list[dict]
    ) -> dict:
        """
        CBF 안전성 검증 수행.
        
        Args:
            current_state (dict): 현재 시스템 상태
            action_sequence (list[dict]): 실행할 액션 시퀀스
            ruleset (list): 안전 경계로 변환될 규칙 목록
            cbf_state_mappings (list[dict]): 액션 파라미터를 상태 변수에 매핑하는 정보
            
        Returns:
            dict: 검증 결과 (verdict, details)
        """
        start_time = time.time()
        
        # [Fix D10] No rules -> INDETERMINATE (Consensus will handle renormalization)
        if not ruleset:
            return {
                "verdict": "INDETERMINATE",
                "details": {
                    "reason": "No safety rules defined for CBF evaluation",
                    "computation_time_ms": 0
                }
            }
        
        all_barrier_values = {}  # 각 단계별 장벽 함수 값(h(x)) 저장용
        min_barrier = float('inf')  # 전체 시퀀스 중 최소 안전 여유 (가장 위험한 순간)
        first_violation_step = None  # 최초로 안전 위반이 발생한 단계 인덱스
        projected_states = []  # 예측된 미래 상태 궤적
        
        # 1단계: 현재 상태에 대한 장벽 값(안전 여유) 계산
        current_barriers = self._compute_barriers(current_state, ruleset)
        all_barrier_values["current_state"] = current_barriers
        
        current_min = min(current_barriers.values()) if current_barriers else float('inf')
        if current_min < min_barrier:
            min_barrier = current_min
        
        # 현재 상태가 이미 안전하지 않은 경우 (-1 단계)
        if current_min <= 0 and first_violation_step is None:
            first_violation_step = -1
        
        # 2단계: 각 액션에 대해 예측 상태를 생성하고 장벽 값 계산 (미래 상태 예측)
        for step_idx, action in enumerate(action_sequence):
            # 다음 상태 예측 (Simple Model: Next = Current + Action)
            projected = self._create_projected_state(
                current_state, action, cbf_state_mappings
            )
            projected_states.append({
                "step": step_idx,
                "action_type": action.get("action_type", "unknown"),
                "projected_state": projected
            })
            
            # 예측된 상태에서의 안전 여유 계산
            step_barriers = self._compute_barriers(projected, ruleset)
            all_barrier_values[f"step_{step_idx}"] = step_barriers
            
            step_min = min(step_barriers.values()) if step_barriers else float('inf')
            if step_min < min_barrier:
                min_barrier = step_min
            
            # 위반 발생 시점 기록 (최초 발생만)
            if step_min <= 0 and first_violation_step is None:
                first_violation_step = step_idx
            
            # 다음 스텝을 위해 상태 업데이트 (누적 적용)
            current_state = {**current_state, **projected}
        
        # 3단계: 최종 판결 결정
        if min_barrier == float('inf'):
            # 검증할 규칙이 없거나 데이터가 없어 계산되지 않음 -> UNSAFE (Fail-Closed)
            logger.warning("No CBF barriers computed (missing rules or data?) -> UNSAFE")
            min_barrier = -1.0
        
        # 최소 여유가 0보다 크면 안전(SAFE), 아니면 위험(UNSAFE)
        verdict = "SAFE" if min_barrier >= 0 else "UNSAFE"
        
        latency_ms = (time.time() - start_time) * 1000
        
        # 안전 여유 비율(Safe Margin Ratio) 계산 (모니터링 지표)
        barrier_vals = []
        for bv in all_barrier_values.values():
            barrier_vals.extend(bv.values())
        max_barrier = max(barrier_vals) if barrier_vals else 1.0
        safe_margin_ratio = min_barrier / max_barrier if max_barrier > 0 else 0.0
        
        return {
            "verdict": verdict,
            "details": {
                "min_barrier_value": round(min_barrier, 3),
                "barrier_values": {k: {rk: round(rv, 3) for rk, rv in v.items()} 
                                  for k, v in all_barrier_values.items()},
                "first_violation_step": first_violation_step,
                "safe_margin_ratio": round(safe_margin_ratio, 3),
                "projected_states": projected_states,
                "computation_time_ms": round(latency_ms, 3)
            }
        }
    
    def _compute_barriers(self, state: dict, ruleset: list) -> dict:
        """
        각 규칙에 대한 장벽 값(안전 경계까지의 거리, h(x))을 계산합니다.
        
        h(x) > 0: 안전
        h(x) = 0: 경계
        h(x) < 0: 위험
        """
        barriers = {}
        
        for rule in ruleset:
            rule_id = rule.get("rule_id", "unknown") if isinstance(rule, dict) else rule.rule_id
            rule_type = rule.get("type", "") if isinstance(rule, dict) else rule.type
            target_field = rule.get("target_field", "") if isinstance(rule, dict) else rule.target_field
            
            # 상태에서 값 가져오기 (중첩 필드 지원)
            value = self._get_nested_value(state, target_field)
            if value is None:
                # FAIL-CLOSED: Missing data for a safety rule -> UNSAFE (infinite penalty)
                barriers[rule_id] = -float('inf')
                continue
            
            # [Fix for Bug 2] Ensure value is numeric
            if not isinstance(value, (int, float)):
                # If value is not numeric (e.g. string), we cannot compute barrier.
                # Treat as unsafe.
                barriers[rule_id] = -float('inf')
                continue
            
            if rule_type in ("threshold",):
                operator = rule.get("operator", "lte") if isinstance(rule, dict) else (rule.operator or "lte")
                limit = rule.get("value") if isinstance(rule, dict) else rule.value
                if limit is None:
                    # Configuration Error: Rule must have a value. FAIL-HARD.
                    raise RuntimeError(f"Rule {rule_id} (threshold) missing 'value'")
                
                # h(x) 계산: 안전 영역 내부 방향으로 양수가 되도록 설정
                if operator in ("lte", "lt"):
                    # 값 <= 제한: 제한 - 값 (값이 커지면 여유 감소)
                    barriers[rule_id] = limit - value
                elif operator in ("gte", "gt"):
                    # 값 >= 제한: 값 - 제한 (값이 커지면 여유 증가)
                    barriers[rule_id] = value - limit
                    
            elif rule_type == "range":
                min_val = rule.get("min") if isinstance(rule, dict) else rule.min
                max_val = rule.get("max") if isinstance(rule, dict) else rule.max
                if min_val is None or max_val is None:
                    # Configuration Error. FAIL-HARD.
                    raise RuntimeError(f"Rule {rule_id} (range) missing 'min' or 'max'")
                
                # 범위 내에 있어야 함: 양쪽 경계 중 더 가까운 쪽까지의 거리
                barriers[rule_id] = min(value - min_val, max_val - value)
        
        return barriers
    
    def _create_projected_state(
        self, 
        current_state: dict, 
        action: dict, 
        cbf_state_mappings: list[dict]
    ) -> dict:
        """
        액션 파라미터를 적용하여 예측 상태를 생성합니다.
        매핑 정보를 사용하여 어떤 액션 파라미터가 어떤 상태 변수를 변경하는지 결정합니다.
        """
        projected = copy.deepcopy(current_state)
        
        action_type = action.get("action_type", "")
        params = action.get("params", {})
        
        for mapping in cbf_state_mappings:
            if mapping.get("action_type") == action_type:
                param_name = mapping.get("param", "")
                field_name = mapping.get("maps_to_field", "")
                
                if param_name in params and field_name:
                    # 단순 모델: 파라미터 값이 곧 상태 값이 됨 (또는 델타?)
                    # 여기서는 간단히 값 대체로 구현됨
                    self._set_nested_value(projected, field_name, params[param_name])
        
        return projected
        
    def _set_nested_value(self, state: dict, field: str, value):
        """Helper to set nested dictionary value by dot notation."""
        parts = field.split(".")
        current = state
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    def _get_nested_value(self, state: dict, field: str):
        """
        점(dot) 표기법을 사용하여 중첩된 딕셔너리에서 값을 안전하게 가져옵니다.
        """
        parts = field.split(".")
        current = state
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, (list, tuple)):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
