"""
OT Interface Contract (Gateway ↔ OT Interface)
============================================
이 모듈은 Gateway Core와 OT Interface 간의 2단계 커밋(2PC) 프로토콜을 위한 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [100] Gateway Core ↔ [130] OT Interface

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.5
  - plans/PCAG_Modular_Architecture_Analysis.md §OTInterface
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

class PrepareRequest(BaseModel):
    """
    [Phase 1] 2PC 준비(Prepare) 및 잠금 요청.
    
    Gateway Core가 OT Interface에게 트랜잭션 실행 준비와 자산 잠금을 요청합니다.
    이 단계에서 OT Interface는 자원을 확보하고 다른 요청이 개입하지 못하도록 잠급니다.
    """
    transaction_id: str  # 트랜잭션 식별자
    asset_id: str        # 제어 대상 자산 ID
    lock_ttl_ms: int = Field(gt=0)  # 요청하는 잠금 유지 시간 (Time-to-Live, ms) — 이 시간이 지나면 자동 잠금 해제

class PrepareResponse(BaseModel):
    """
    [Phase 1] 준비 요청에 대한 응답.
    
    OT Interface가 잠금 성공 여부를 반환합니다.
    """
    transaction_id: str
    status: Literal["LOCK_GRANTED", "LOCK_DENIED"]  # 잠금 획득 성공(LOCK_GRANTED) 또는 실패(LOCK_DENIED)
    lock_expires_at_ms: Optional[int] = None  # (성공 시) 잠금이 만료되는 절대 시각
    reason: Optional[str] = None  # (실패 시) 잠금 거부 사유 (예: "Already locked by another transaction")

class CommitRequest(BaseModel):
    """
    [Phase 2] 2PC 커밋(Commit) 및 실행 요청.
    
    Gateway Core가 안전 검증이 완료된 액션을 OT Interface에게 최종 실행하도록 지시합니다.
    Phase 1에서 획득한 잠금이 유효해야 실행됩니다.
    """
    transaction_id: str
    asset_id: str
    action_sequence: list[dict]  # 실제 OT 장비에 전달하여 실행할 액션 목록

class CommitResponse(BaseModel):
    """
    [Phase 2] 커밋 요청에 대한 실행 결과 응답.
    
    OT Interface가 액션 실행 결과를 반환합니다.
    """
    transaction_id: str
    status: Literal["ACK", "ALREADY_COMMITTED", "TIMEOUT", "EXECUTION_FAILED"]  # 실행 확인(ACK), 중복 커밋(ALREADY_COMMITTED), 시간 초과(TIMEOUT), 실행 실패
    executed_at_ms: Optional[int] = None  # 실제 실행 완료 시각
    reason: Optional[str] = None
    safe_state_executed: Optional[bool] = None

class AbortRequest(BaseModel):
    """
    트랜잭션 중단(Abort) 및 잠금 해제 요청.
    
    안전 검증 실패, 타임아웃, 또는 기타 오류 발생 시 트랜잭션을 취소하고 자원을 해제합니다.
    필요한 경우 안전 상태(Safe State)로 복귀하는 액션을 포함할 수 있습니다.
    """
    transaction_id: str
    asset_id: str
    reason: str  # 중단 사유 (로그 기록용)
    safe_state_actions: Optional[list[dict]] = None  # (선택) 시스템을 안전 상태로 복구하기 위한 액션 시퀀스

class AbortResponse(BaseModel):
    """
    중단 요청에 대한 응답.
    """
    transaction_id: str
    status: Literal["ABORTED", "ALREADY_ABORTED", "ABORT_REJECTED"]  # 중단 완료, 이미 중단됨, 혹은 중단 거부
    safe_state_executed: Optional[bool] = None  # 안전 상태 복귀 액션이 실행되었는지 여부
    reason: Optional[str] = None

class EstopRequest(BaseModel):
    """
    비상 정지(Emergency Stop) 요청.
    
    긴급 상황 발생 시 즉시 장비를 정지시키는 요청입니다.
    2PC 절차를 무시하고 최우선 순위로 처리됩니다.
    """
    asset_id: str
    reason: str  # 비상 정지 사유

class EstopResponse(BaseModel):
    """
    비상 정지 요청에 대한 응답.
    """
    asset_id: str
    status: Literal["ESTOP_EXECUTED"]  # 비상 정지 명령이 전달됨을 확인
    timestamp_ms: int  # 명령 전달 시각
