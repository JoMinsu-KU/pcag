"""
Safety Cluster Contract (Gateway ↔ Safety Cluster)
============================================
이 모듈은 Gateway Core와 Safety Validation Cluster 간의 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [120] Safety Validation Cluster (Consensus Engine)

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.2
  - plans/PCAG_Modular_Architecture_Analysis.md §SafetyCluster
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any

class SafetyValidateRequest(BaseModel):
    """
    Gateway가 Safety Cluster에 안전 검증을 요청할 때 사용하는 데이터 구조.
    
    사용 경로: Gateway Core (100) → Safety Cluster (120)
    
    실행할 액션 시퀀스와 현재 센서 데이터를 포함하여, 다중 검증기(Rule, CBF, Simulation)의 판단을 요청합니다.
    """
    transaction_id: str  # 트랜잭션 고유 ID — 요청 추적 및 로그 기록용
    asset_id: str        # 대상 자산(장비) ID — 해당 장비의 안전 정책 적용을 위해 사용
    policy_version_id: str  # 적용할 정책 버전 ID — Policy Store에서 가져온 정책 버전과 일치해야 함
    action_sequence: list[dict]  # 검증 대상 액션 시퀀스 — 에이전트가 요청한 제어 명령 목록
    current_sensor_snapshot: dict  # 현재 장비의 센서 상태 — CBF 및 시뮬레이션의 초기 조건으로 사용

class ValidatorVerdictResponse(BaseModel):
    """
    개별 검증기(Validator)의 검증 결과.
    
    각 검증기(Rule, CBF, Simulation)는 독립적으로 이 구조의 결과를 반환합니다.
    """
    verdict: Literal["SAFE", "UNSAFE", "INDETERMINATE"]  # 검증 결과 판정 (안전, 위험, 판단불가)
    details: dict[str, Any] = Field(default_factory=dict)  # 상세 검증 내용 (예: 위반된 규칙 ID, 충돌 예상 시간 등)

class ConsensusDetailsResponse(BaseModel):
    """
    합의 엔진(Consensus Engine)의 최종 결정 과정 상세 정보.
    
    여러 검증기의 결과를 종합하여 최종 안전 여부를 판단한 근거를 포함합니다.
    """
    mode: str  # 합의 방식 (예: "weighted_score", "unanimous", "veto") — 정책에 정의된 방식
    weights_used: Optional[dict[str, float]] = None  # 각 검증기에 적용된 가중치 (Weighted Score 방식일 경우)
    score: Optional[float] = None  # 계산된 최종 안전 점수 (0.0 ~ 1.0)
    threshold: Optional[float] = None  # 안전 판정을 위한 최소 통과 점수
    explanation: str = ""  # 합의 결과에 대한 설명 (예: "Simulation vetoed the action")

class SafetyValidateResponse(BaseModel):
    """
    Safety Cluster가 Gateway에 반환하는 최종 검증 결과.
    
    사용 경로: Safety Cluster (120) → Gateway Core (100)
    
    최종 안전 여부와 각 검증기의 개별 결과 및 합의 상세 정보를 포함합니다.
    """
    transaction_id: str  # 요청에 대한 트랜잭션 ID 반환
    final_verdict: Literal["SAFE", "UNSAFE"]  # 최종 안전 여부 판정 (합의 결과)
    validators: dict[str, ValidatorVerdictResponse]  # 각 검증기별 결과 맵 (키: "rules", "cbf", "simulation" 등)
    consensus_details: ConsensusDetailsResponse  # 합의 로직 수행 결과 상세
