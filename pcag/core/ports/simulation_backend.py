"""
Simulation Backend Port (Interface)
============================================
이 모듈은 다양한 시뮬레이션 엔진(Isaac Sim, ODE, Discrete Event 등)을
Safety Cluster에 연결하기 위한 추상 인터페이스를 정의합니다.

PCAG 파이프라인 위치:
  [122] Simulation Validator (Safety Cluster 내부)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §SimulationValidator
"""

from abc import ABC, abstractmethod
from typing import Any

class ISimulationBackend(ABC):
    """
    시뮬레이션 백엔드 인터페이스.
    
    모든 시뮬레이션 플러그인은 이 인터페이스를 구현해야 합니다.
    """
    
    @abstractmethod
    def initialize(self, config: dict) -> None:
        """
        플러그인 초기화 메서드.
        
        서버 시작 시 또는 플러그인 로드 시 한 번 호출됩니다.
        필요한 리소스(연결, 모델 로드 등)를 준비합니다.
        
        Args:
            config (dict): 초기화 설정 (URL, API 키, 모델 경로 등)
        """
        pass
    
    @abstractmethod
    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """
        궤적 안전성 검증 요청.
        
        현재 상태에서 액션 시퀀스를 가상으로 실행하여 안전성을 평가합니다.
        
        Args:
            current_state (dict): 현재 장비 및 환경 상태 (센서 데이터 기반)
            action_sequence (list[dict]): 실행하려는 액션 목록
            constraints (dict): 검증해야 할 제약 조건 (충돌 여부, 제한 속도 등)
            
        Returns:
            dict: SimulationResult 형식의 결과 (verdict, details 포함)
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """
        플러그인 종료 및 리소스 해제.
        
        서버 종료 시 또는 플러그인 언로드 시 호출됩니다.
        """
        pass
