"""
Consensus Engine Service
============================================
이 모듈은 다중 검증기(Rule, CBF, Simulation)의 결과를 종합하여
최종 안전 여부를 판단하는 SIL 기반 합의 엔진을 구현합니다.

PCAG 파이프라인 위치:
  [120] Safety Validation Cluster (Consensus Layer)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §SafetyCluster
"""

from ..models.common import ConsensusConfig, ValidatorVerdict, ConsensusResult, ConsensusMode

def evaluate_consensus(
    sil_level: int,
    config: ConsensusConfig,
    rules_verdict: ValidatorVerdict,
    cbf_verdict: ValidatorVerdict,
    sim_verdict: ValidatorVerdict,
) -> ConsensusResult:
    """
    다양한 검증기(Validator)의 판결 결과를 기반으로 최종 안전 합의를 도출합니다.
    
    Args:
        sil_level (int): 자산의 안전 무결성 수준 (SIL 1~4) — 합의 모드 결정에 영향을 줌
        config (ConsensusConfig): 자산별 합의 설정 (모드, 가중치 등)
        rules_verdict (ValidatorVerdict): 규칙 검증기 결과
        cbf_verdict (ValidatorVerdict): CBF 검증기 결과
        sim_verdict (ValidatorVerdict): 시뮬레이션 검증기 결과
        
    Returns:
        ConsensusResult: 최종 합의 결과 (SAFE/UNSAFE 및 상세 근거 포함)
    """
    
    # 1. 유효 합의 모드 결정 (Determine effective mode)
    # config.mode가 AUTO이면 SIL 레벨에 따라 자동으로 결정
    mode = config.mode
    if mode == ConsensusMode.AUTO:
        if sil_level >= 3:
            # SIL 3 이상: 모든 검증기가 SAFE여야 함 (보수적)
            mode = ConsensusMode.AND
        elif sil_level == 2:
            # SIL 2: 가중치 기반 점수 합산
            mode = ConsensusMode.WEIGHTED
        else:
            # SIL 1 이하 또는 기타: 하나라도 UNSAFE면 차단 (WORST_CASE)
            mode = ConsensusMode.WORST_CASE
            
    # 판결 상태 확인 헬퍼 함수들
    def is_safe(v: ValidatorVerdict) -> bool:
        return v.verdict == "SAFE"
    
    def is_unsafe(v: ValidatorVerdict) -> bool:
        return v.verdict == "UNSAFE"
        
    def is_indeterminate(v: ValidatorVerdict) -> bool:
        return v.verdict == "INDETERMINATE"

    # 2. 모드에 기반한 평가 수행 (Evaluate based on mode)
    if mode == ConsensusMode.AND:
        # AND 모드: 모든 검증기가 "SAFE"여야 함
        # INDETERMINATE(판단불가)도 UNSAFE로 간주 (Fail-Closed 원칙)
        all_safe = is_safe(rules_verdict) and is_safe(cbf_verdict) and is_safe(sim_verdict)
        final_verdict = "SAFE" if all_safe else "UNSAFE"
        score = 1.0 if all_safe else 0.0
        return ConsensusResult(
            final_verdict=final_verdict,
            mode_used=mode.value,
            score=score,
            explanation=f"AND mode: rules={rules_verdict.verdict}, cbf={cbf_verdict.verdict}, sim={sim_verdict.verdict}"
        )

    elif mode == ConsensusMode.WORST_CASE:
        # WORST_CASE 모드: 단 하나의 검증기라도 UNSAFE면 즉시 UNSAFE
        # INDETERMINATE도 위험 신호로 간주하여 UNSAFE 처리
        any_unsafe = is_unsafe(rules_verdict) or is_unsafe(cbf_verdict) or is_unsafe(sim_verdict)
        any_indeterminate = is_indeterminate(rules_verdict) or is_indeterminate(cbf_verdict) or is_indeterminate(sim_verdict)
        
        final_verdict = "UNSAFE" if (any_unsafe or any_indeterminate) else "SAFE"
        score = 0.0 if (any_unsafe or any_indeterminate) else 1.0
        return ConsensusResult(
            final_verdict=final_verdict,
            mode_used=mode.value,
            score=score,
            explanation=f"WORST_CASE mode: rules={rules_verdict.verdict}, cbf={cbf_verdict.verdict}, sim={sim_verdict.verdict}"
        )

    elif mode == ConsensusMode.WEIGHTED:
        # WEIGHTED 모드: 각 검증기의 결과에 가중치를 곱해 합산 점수 계산
        weights = config.weights or {"rules": 0.4, "cbf": 0.35, "sim": 0.25}
        threshold = config.threshold if config.threshold is not None else 0.5
        
        # 시뮬레이션 결과가 INDETERMINATE일 때의 처리 로직
        effective_weights = weights.copy()
        sim_val = 0.0
        
        if is_indeterminate(sim_verdict):
            if config.on_sim_indeterminate == "RENORMALIZE":
                # 시뮬레이션 가중치를 제거하고, 나머지 검증기의 가중치를 비율에 맞게 재조정(정규화)
                sim_weight = effective_weights.pop("sim", 0.0)
                total_remaining = sum(effective_weights.values())
                if total_remaining > 0:
                    for k in effective_weights:
                        effective_weights[k] = effective_weights[k] / total_remaining
            elif config.on_sim_indeterminate == "FAIL_CLOSED" or config.on_sim_indeterminate == "TREAT_AS_UNSAFE":
                # UNSAFE(0점)로 간주
                sim_val = 0.0
            elif config.on_sim_indeterminate == "IGNORE":
                # 점수에 반영하지 않음 (0점 처리하되, 가중치 재조정 없음 - 사실상 점수 깎임)
                sim_val = 0.0 
            else:
                sim_val = 0.0
        elif is_safe(sim_verdict):
            sim_val = 1.0
        else: # UNSAFE
            sim_val = 0.0
            
        # 다른 검증기 점수 변환 헬퍼
        def get_score(v: ValidatorVerdict) -> float:
            if is_safe(v): return 1.0
            if is_unsafe(v): return 0.0
            # Rule이나 CBF가 INDETERMINATE인 경우는 드물지만, 발생 시 0점(UNSAFE) 처리
            return 0.0

        rules_val = get_score(rules_verdict)
        cbf_val = get_score(cbf_verdict)
        
        # 최종 점수 계산
        score = 0.0
        if "rules" in effective_weights:
            score += effective_weights["rules"] * rules_val
        if "cbf" in effective_weights:
            score += effective_weights["cbf"] * cbf_val
        if "sim" in effective_weights:
            # RENORMALIZE된 경우 sim 키가 없을 수 있음
            score += effective_weights["sim"] * sim_val

        # 임계값 비교하여 최종 판정
        final_verdict = "SAFE" if score >= threshold else "UNSAFE"
        
        return ConsensusResult(
            final_verdict=final_verdict,
            mode_used=mode.value,
            weights_used=effective_weights,
            score=score,
            threshold=threshold,
            explanation=f"WEIGHTED mode: score={score:.2f} (thresh={threshold})"
        )
        
    else:
        # 알 수 없는 모드일 경우 안전하게 차단
        return ConsensusResult(
            final_verdict="UNSAFE",
            mode_used="UNKNOWN",
            explanation="Unknown consensus mode"
        )
