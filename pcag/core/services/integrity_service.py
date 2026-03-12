"""
Integrity Service
============================================
이 모듈은 데이터 무결성 검증을 담당합니다.
증명 패키지(Proof Package)의 내용이 현재 시스템 상태와 일치하는지,
정책 위반이나 데이터 위변조가 없는지 확인합니다.

PCAG 파이프라인 위치:
  [110] Integrity Check Service

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §IntegrityService
"""

from typing import Tuple, Optional
from ..models.common import DivergenceThreshold, IntegrityConfig

def check_integrity(
    proof_policy_version: str,
    active_policy_version: str,
    proof_timestamp_ms: int,
    current_timestamp_ms: int,
    timestamp_max_age_ms: int,
    proof_sensor_snapshot: dict,
    current_sensor_snapshot: dict,
    divergence_thresholds: list[DivergenceThreshold],
) -> Tuple[bool, Optional[str]]:
    """
    증명 패키지(Proof Package)에 대한 포괄적인 무결성 검사를 수행합니다.
    
    Args:
        proof_policy_version (str): 증명 생성 시 사용된 정책 버전
        active_policy_version (str): 현재 시스템의 활성 정책 버전
        proof_timestamp_ms (int): 증명 생성 시각
        current_timestamp_ms (int): 현재 시각
        timestamp_max_age_ms (int): 허용되는 최대 데이터 지연 시간
        proof_sensor_snapshot (dict): 증명에 포함된 센서 데이터
        current_sensor_snapshot (dict): 현재 실제 센서 데이터
        divergence_thresholds (list): 센서 데이터 허용 오차 설정
        
    Returns:
        Tuple[bool, Optional[str]]: (통과 여부, 실패 사유 코드)
    """
    
    # 1. 정책 버전 일치 확인 (Policy Version Match)
    # 에이전트가 구버전 정책으로 증명을 생성했다면 거부
    if proof_policy_version != active_policy_version:
        return False, "INTEGRITY_POLICY_MISMATCH"
        
    # 2. 타임스탬프 최신성 확인 (Timestamp Freshness)
    # 너무 오래된 증명(Replay Attack 등) 방지
    age = current_timestamp_ms - proof_timestamp_ms
    if age > timestamp_max_age_ms:
        return False, "INTEGRITY_TIMESTAMP_EXPIRED"
    if age < -5000:  # [Fix D11] 5초 이상 미래인 경우 (클럭 오차 허용 범위 확대)
        return False, "INTEGRITY_TIMESTAMP_FUTURE" 
    
    # 3. 센서 데이터 발산(Divergence) 확인
    # 증명 생성 시점의 데이터와 현재 실제 데이터 간의 차이가 허용 범위를 넘는지 확인
    for thresh in divergence_thresholds:
        sensor_key = thresh.sensor_type
        
        # 중첩 키 값 추출 헬퍼
        def get_val(snap, key):
            keys = key.split('.')
            curr = snap
            for k in keys:
                if isinstance(curr, dict) and k in curr:
                    curr = curr[k]
                else:
                    return None
            return curr

        proof_val = get_val(proof_sensor_snapshot, sensor_key)
        curr_val = get_val(current_sensor_snapshot, sensor_key)
        
        if proof_val is None or curr_val is None:
            # 데이터가 없으면 검증 불가 -> 안전을 위해 실패 처리
            return False, "INTEGRITY_SENSOR_DIVERGENCE"

        if isinstance(proof_val, (int, float)) and isinstance(curr_val, (int, float)):
            diff = abs(curr_val - proof_val)
            
            if thresh.method == "absolute":
                # 절대값 차이 검사
                if diff > thresh.max_divergence:
                    return False, "INTEGRITY_SENSOR_DIVERGENCE"
            elif thresh.method == "percentage":
                # 백분율 차이 검사
                if proof_val == 0:
                    if diff > 0: # 0이어야 하는데 아니면 무한대 오차
                         return False, "INTEGRITY_SENSOR_DIVERGENCE"
                else:
                    pct = (diff / abs(proof_val)) * 100.0
                    if pct > thresh.max_divergence:
                        return False, "INTEGRITY_SENSOR_DIVERGENCE"
        else:
            # 숫자가 아닌 경우 정확한 일치 여부 확인
            if proof_val != curr_val:
                return False, "INTEGRITY_SENSOR_DIVERGENCE"

    # 모든 검사를 통과함
    return True, None
