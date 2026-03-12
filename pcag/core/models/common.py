"""
Common Domain Models
============================================
이 모듈은 PCAG 시스템 전반에서 사용되는 공통 도메인 모델을 정의합니다.
규칙(Rule), 검증 결과(Verdict), 합의 설정(Consensus Config) 등 핵심 데이터 구조를 포함합니다.

PCAG 파이프라인 위치:
  전체 시스템 공통 (Cross-cutting)

관련 문서:
  - plans/PCAG_Schema_Definitions.md §2.2
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
from enum import Enum

class RuleType(str, Enum):
    """
    검증 규칙(Rule)의 유형 정의.
    """
    THRESHOLD = "threshold"  # 단순 임계값 확인 (예: 온도 < 50)
    RANGE = "range"  # 최소/최대 범위 내 값 확인 (예: 10 <= 압력 <= 100)
    ENUM = "enum"  # 허용된 값 목록에 포함되는지 확인 (예: status in ["IDLE", "RUNNING"])
    FORBIDDEN_COMBINATION = "forbidden_combination"  # 금지된 상태 조합 확인 (예: [DOOR_OPEN, MOTOR_RUNNING])

class Rule(BaseModel):
    """
    개별 안전 규칙의 정의.
    
    Safety Cluster의 Rules Validator에서 사용되며,
    Policy Store에 저장된 정책의 일부로 관리됩니다.
    """
    rule_id: str  # 규칙 식별자 (예: "R001_TEMP_LIMIT")
    type: RuleType  # 규칙 유형
    target_field: str  # 검증 대상 필드의 JSON 경로 (예: "sensor_snapshot.temperature")
    
    # 조건부 필드 (규칙 유형에 따라 사용됨)
    operator: Optional[Literal["lt", "lte", "gt", "gte", "eq", "ne"]] = None  # 비교 연산자
    value: Optional[float] = None  # 비교 기준값
    min: Optional[float] = None  # 최소값 (RANGE 유형)
    max: Optional[float] = None  # 최대값 (RANGE 유형)
    allowed_values: Optional[list[Any]] = None  # 허용 값 목록 (ENUM 유형)
    forbidden_pairs: Optional[list[list[str]]] = None  # 금지된 조합 목록 (FORBIDDEN_COMBINATION 유형)
    
    unit: Optional[str] = None  # 물리 단위 (문서화 용도)
    aas_source: Optional[str] = None  # AAS(Asset Administration Shell)에서 유래한 경우 해당 필드 경로

class ValidatorVerdict(BaseModel):
    """
    단일 검증기(Validator)의 검증 결과 모델.
    
    Rules Validator, CBF Validator, Simulation Validator 등이
    각자의 검증 결과를 이 형식으로 반환합니다.
    """
    verdict: Literal["SAFE", "UNSAFE", "INDETERMINATE"]  # 검증 결과
    details: dict = Field(default_factory=dict)  # 상세 정보 (위반 사항, 시뮬레이션 결과 등)

class ConsensusMode(str, Enum):
    """
    검증기 결과 결합 전략(Consensus Strategy).
    """
    AUTO = "AUTO"  # 시스템이 상황에 따라 최적의 모드 자동 선택
    AND = "AND"  # 모든 검증기가 SAFE여야 최종 SAFE (보수적)
    WEIGHTED = "WEIGHTED"  # 각 검증기의 가중치 점수 합산 방식
    WORST_CASE = "WORST_CASE"  # 하나라도 UNSAFE면 즉시 UNSAFE (가장 보수적)

class ConsensusConfig(BaseModel):
    """
    합의 엔진(Consensus Engine) 설정.
    
    자산별 정책(AssetPolicyProfile)에 포함되어,
    해당 자산에 대한 안전 검증 결과 취합 방식을 결정합니다.
    """
    mode: ConsensusMode = ConsensusMode.AUTO  # 사용할 합의 모드
    weights: Optional[dict[str, float]] = None  # 가중치 설정 (예: {"rules": 0.4, "cbf": 0.35, "sim": 0.25})
    threshold: Optional[float] = None  # 점수 기반 합의 시 통과 임계값 (예: 0.8 이상이어야 SAFE)
    on_sim_indeterminate: Literal["FAIL_CLOSED", "RENORMALIZE", "TREAT_AS_UNSAFE", "IGNORE"] = "FAIL_CLOSED"
    # 시뮬레이션 결과가 '판단불가(INDETERMINATE)'일 때 처리 방식
    # FAIL_CLOSED: 전체 실패 처리
    # RENORMALIZE: 시뮬레이션을 제외하고 가중치 재계산
    # TREAT_AS_UNSAFE: UNSAFE로 간주

class ConsensusResult(BaseModel):
    """
    합의 엔진의 최종 수행 결과.
    """
    final_verdict: Literal["SAFE", "UNSAFE"]  # 최종 판정
    mode_used: str  # 실제 사용된 합의 모드
    weights_used: Optional[dict[str, float]] = None  # 적용된 가중치
    score: Optional[float] = None  # 계산된 점수
    threshold: Optional[float] = None  # 적용된 임계값
    explanation: str  # 결과에 대한 설명

class DivergenceThreshold(BaseModel):
    """
    센서 데이터 무결성 검증을 위한 허용 오차 설정.
    """
    sensor_type: str  # 대상 센서 유형
    method: Literal["absolute", "percentage"]  # 오차 계산 방식 (절대값 차이 / 백분율 차이)
    max_divergence: float  # 허용 최대 오차

class IntegrityConfig(BaseModel):
    """
    무결성 검사(Integrity Check) 설정.
    """
    timestamp_max_age_ms: int = 500  # 데이터 유효 시간 (이 시간보다 오래된 데이터는 무효)
    sensor_divergence_thresholds: list[DivergenceThreshold] = Field(default_factory=list)  # 센서별 오차 허용 설정
