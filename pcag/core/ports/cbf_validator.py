"""
CBF Validator Port (Interface)
============================================
이 모듈은 제어 장벽 함수(Control Barrier Function, CBF) 기반 안전 필터를
Safety Cluster에 연결하기 위한 추상 인터페이스를 정의합니다.

PCAG 파이프라인 위치:
  [122] CBF Validator (Safety Cluster 내부)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §CBFValidator
"""

from abc import ABC, abstractmethod
from typing import Any

class ICBFValidator(ABC):
    """
    CBF(Control Barrier Function) 검증기 인터페이스.
    
    수학적 모델 기반의 실시간 안전 필터링 로직을 구현합니다.
    """
    
    @abstractmethod
    def validate_safety(
        self,
        current_state: dict,
        action_sequence: list[dict],
        ruleset: list,
        cbf_state_mappings: list[dict]
    ) -> dict:
        """
        CBF 안전 검증 수행.
        
        시스템 상태가 안전 집합(Safe Set) 내에 유지되는지 수학적으로 증명합니다.
        
        Args:
            current_state (dict): 현재 시스템 상태 벡터 (x, v, a 등)
            action_sequence (list[dict]): 제어 입력 시퀀스 (u)
            ruleset (list): 적용할 안전 규칙 (h(x) >= 0 형태의 제약 조건으로 변환됨)
            cbf_state_mappings (list[dict]): 상태 변수 매핑 정보
            
        Returns:
            dict: ValidatorVerdict 형식의 결과 (SAFE/UNSAFE). 
                  CBF는 결정론적이므로 INDETERMINATE를 반환하지 않아야 합니다.
        """
        pass
