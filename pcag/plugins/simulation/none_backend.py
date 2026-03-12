"""
None Simulation Backend (Fallback Plugin)
============================================
시뮬레이션 모델이 존재하지 않거나 비활성화된 경우 사용되는 대체 플러그인입니다.
항상 "INDETERMINATE"(판단불가) 결과를 반환하여, 
Consensus Engine이 설정(on_sim_indeterminate)에 따라 적절히 처리하도록 합니다.

PCAG 파이프라인 위치:
  [122] Simulation Validator (Plugin)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §SimulationValidator
"""

from pcag.core.ports.simulation_backend import ISimulationBackend

class NoneBackend(ISimulationBackend):
    """
    비활성화된 시뮬레이션 백엔드.
    
    어떤 검증 요청에도 항상 판단 불가(INDETERMINATE)를 반환합니다.
    """
    
    def initialize(self, config: dict) -> None:
        """
        초기화 불필요. (아무 작업도 수행하지 않음)
        """
        pass
    
    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """
        항상 INDETERMINATE 반환.
        
        시뮬레이션이 없으므로 안전 여부를 판단할 수 없음을 명시합니다.
        합의 엔진은 이를 받아 가중치 재분배(Renormalize) 또는 보수적 차단(Fail-Closed) 등을 수행합니다.
        """
        return {
            "verdict": "INDETERMINATE",
            "engine": "none",
            "common": {
                "first_violation_step": None,
                "violated_constraint": None,
                "latency_ms": 0.0,
                "steps_completed": 0
            },
            "details": {
                "reason": "simulation_disabled"
            }
        }
    
    def shutdown(self) -> None:
        """
        종료 처리 불필요.
        """
        pass
