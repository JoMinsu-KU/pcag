"""
Policy Models
============================================
이 모듈은 자산의 동작 및 안전 규칙을 정의하는 정책 관련 모델을 정의합니다.
시뮬레이션, 실행, 센서, 합의 등 자산 제어의 모든 측면을 설정합니다.

PCAG 파이프라인 위치:
  [Policy Store] 및 전체 시스템

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.3
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from .common import ConsensusConfig, IntegrityConfig, Rule


class CollisionObjectConfig(BaseModel):
    """
    Forbidden collision fixture expressed as an axis-aligned box.
    """

    object_id: str = Field(min_length=1)
    center: list[float] = Field(min_length=3, max_length=3)
    scale: list[float] = Field(min_length=3, max_length=3)


class CollisionConfig(BaseModel):
    """
    Policy-driven collision probe settings for the Isaac validator.
    """

    enabled: bool = False
    mode: Literal["end_effector_sphere"] = "end_effector_sphere"
    probe_radius_m: float = Field(default=0.045, gt=0.0)
    forbidden_objects: list[CollisionObjectConfig] = Field(default_factory=list)

class SimulationConfig(BaseModel):
    """
    시뮬레이션 검증을 위한 설정.
    """
    engine: Literal["isaac_sim", "ode_solver", "discrete_event", "none"] = "none"  # 사용할 시뮬레이션 엔진
    horizon_ms: Optional[int] = None  # 시뮬레이션 예측 시간 (Lookahead horizon)
    dt_ms: Optional[int] = None  # 시뮬레이션 시간 단계 (Time step)
    timeout_ms: Optional[int] = 200  # 시뮬레이션 최대 허용 시간 (이 시간 내에 결과가 안 나오면 타임아웃)
    world_ref: Optional[str] = None  # 로드할 시뮬레이션 월드/장면 ID (USD 파일 경로 등)

    collision: CollisionConfig = Field(default_factory=CollisionConfig)

class UnitAction(BaseModel):
    """
    단일 원자적 액션(Atomic Action) 정의.
    
    안전 상태(Safe State) 복귀 절차 등을 정의할 때 사용됩니다.
    """
    action_id: Optional[str] = None  # 액션 식별자
    action_type: str = Field(min_length=1)  # 액션 유형 (예: "MOVE_JOINT", "STOP")
    params: dict  # 액션 실행 파라미터
    duration_ms: Optional[int] = None  # 예상 소요 시간

class ExecutionConfig(BaseModel):
    """
    액션 실행 관련 설정.
    
    2PC(2단계 커밋) 프로토콜의 타임아웃 및 안전 장치를 정의합니다.
    """
    lock_ttl_ms: int = 5000  # 2PC Phase 1 잠금 유지 시간 (Time-to-Live)
    commit_ack_timeout_ms: int = 3000  # 커밋 요청 후 응답(ACK) 대기 시간 제한
    safe_state: list[UnitAction] = Field(default_factory=list)  # 오류 발생 시 시스템을 안전 상태로 복구하기 위한 액션 시퀀스

class AssetPolicyProfile(BaseModel):
    """
    특정 자산(Asset)에 대한 전체 정책 프로필.
    
    이 객체는 해당 자산의 안전, 무결성, 실행, 시뮬레이션 등 모든 제어 정책을 포괄합니다.
    """
    asset_id: str  # 자산 ID
    sil_level: int = Field(ge=1, le=4)  # 안전 무결성 수준 (SIL 1~4) — 높을수록 더 엄격한 검증 요구
    
    sensor_source: Literal["mock_sensor", "isaac_sim_sensor", "modbus_sensor", "opcua_sensor"]
    # 센서 데이터 소스 플러그인 선택
    
    ot_executor: Literal["mock_executor", "isaac_sim_executor", "modbus_executor", "opcua_executor"]
    # 명령 실행기 플러그인 선택
    
    consensus: ConsensusConfig  # 합의 엔진 설정
    integrity: IntegrityConfig  # 무결성 검사 설정
    ruleset: list[Rule] = Field(default_factory=list)  # 적용할 정적 안전 규칙 목록
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)  # 시뮬레이션 설정
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)  # 실행 및 2PC 설정
