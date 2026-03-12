"""
Evidence Ledger Contract (Gateway ↔ Evidence Ledger)
============================================
이 모듈은 Gateway Core와 Evidence Ledger 간의 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [140] Evidence Ledger

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.6
  - plans/PCAG_Modular_Architecture_Analysis.md §EvidenceLedger
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any

class EvidenceAppendRequest(BaseModel):
    """
    Gateway Core에서 발생하는 주요 이벤트를 Evidence Ledger에 기록하기 위한 요청.
    
    사용 경로: Gateway Core (100) → Evidence Ledger (140) (POST /v1/evidence/append)
    
    트랜잭션의 각 단계(수신, 검증, 합의, 커밋 등)마다 무결성이 보장된 해시 체인 형태로 이벤트를 기록합니다.
    """
    transaction_id: str  # 트랜잭션 식별자
    sequence_no: int = Field(ge=0)  # 트랜잭션 내 이벤트 순서 번호 (0부터 시작)
    stage: Literal[
        "RECEIVED", "SCHEMA_VALIDATED",
        "INTEGRITY_PASSED", "INTEGRITY_REJECTED",
        "SAFETY_PASSED", "SAFETY_UNSAFE",
        "PREPARE_LOCK_GRANTED", "PREPARE_LOCK_DENIED",
        "REVERIFY_PASSED", "REVERIFY_FAILED",
        "COMMIT_ACK", "COMMIT_TIMEOUT", "COMMIT_ERROR",
        "ABORTED", "ESTOP_TRIGGERED"
    ]  # 이벤트가 발생한 파이프라인 단계
    
    timestamp_ms: int  # 이벤트 발생 시각 (Unix Timestamp ms)
    payload: dict[str, Any]  # 이벤트 상세 데이터 (예: 검증 결과, 오류 메시지, 센서 값 등)
    input_hash: str  # 이 단계의 입력 데이터(이전 단계의 출력)에 대한 해시
    prev_hash: str  # 직전 이벤트의 해시 (해시 체인 연결용) — 첫 이벤트는 Genesis Hash 사용
    event_hash: str  # 현재 이벤트 전체(payload + metadata + prev_hash)에 대한 해시

class EvidenceAppendResponse(BaseModel):
    """
    증거 기록 요청에 대한 응답.
    
    Evidence Ledger가 기록 완료를 확인하고 저장된 해시를 반환합니다.
    """
    transaction_id: str
    sequence_no: int
    event_hash: str  # 원장에 저장된 최종 해시 (요청 시 보낸 해시와 일치해야 함)

class EvidenceEventResponse(BaseModel):
    """
    Evidence Ledger에서 조회한 단일 이벤트 정보.
    
    사용 경로: Evidence Ledger → Client (GET /v1/evidence/{tx_id})
    """
    transaction_id: str
    sequence_no: int
    stage: str
    timestamp_ms: int
    payload: dict[str, Any]
    input_hash: str
    prev_hash: str
    event_hash: str

class TransactionEvidenceResponse(BaseModel):
    """
    특정 트랜잭션의 전체 증거 체인(History).
    
    트랜잭션의 시작부터 끝까지 모든 이벤트를 순서대로 포함하며, 해시 체인의 유효성을 검증한 결과를 포함합니다.
    """
    transaction_id: str
    events: list[EvidenceEventResponse]  # 해당 트랜잭션의 모든 이벤트 목록 (순서대로 정렬됨)
    chain_valid: bool  # 해시 체인 무결성 검증 결과 (모든 prev_hash가 일치하는지 여부)
