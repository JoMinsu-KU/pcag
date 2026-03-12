"""
증거 원장 (Evidence Ledger) — 실제 구현
========================================
PostgreSQL에 해시 체인 증거 이벤트를 저장합니다.

PCAG 파이프라인 위치:
  모든 단계(100~140)에서 Gateway Core가 여기에 이벤트를 기록합니다.

API:
  POST /v1/events/append                    — 증거 이벤트 추가
  GET  /v1/transactions/{transaction_id}    — 트랜잭션 증거 조회 + 체인 검증

conda pcag 환경에서 실행.
"""
import json
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pcag.core.contracts.evidence import (
    EvidenceAppendRequest, EvidenceAppendResponse,
    TransactionEvidenceResponse, EvidenceEventResponse
)
from pcag.core.database.engine import get_db
from pcag.apps.evidence_ledger.repository import EvidenceRepository

router = APIRouter(prefix="/v1", tags=["EvidenceLedger"])


@router.post("/events/append")
def append_event(request: EvidenceAppendRequest, db: Session = Depends(get_db)):
    """
    증거 이벤트 추가 (Append-Only)
    
    Gateway Core가 파이프라인의 각 단계마다 호출합니다.
    이벤트는 해시 체인으로 연결되어 변조 탐지가 가능합니다.
    
    해시 체인 규칙:
      - event_hash = sha256(prev_hash + canonical(payload))
      - 첫 이벤트의 prev_hash = sha256("") (Genesis Hash)
    """
    repo = EvidenceRepository(db)
    
    try:
        record = repo.append_event(
            transaction_id=request.transaction_id,
            sequence_no=request.sequence_no,
            stage=request.stage,
            timestamp_ms=request.timestamp_ms,
            payload=request.payload,
            input_hash=request.input_hash,
            prev_hash=request.prev_hash,
            event_hash=request.event_hash
        )
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"Duplicate event: {e}")
    
    return EvidenceAppendResponse(
        transaction_id=record.transaction_id,
        sequence_no=record.sequence_no,
        event_hash=record.event_hash
    )


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """
    트랜잭션의 모든 증거 이벤트 조회 + 해시 체인 무결성 검증
    
    반환값에 chain_valid 필드가 포함되어,
    해시 체인이 변조되지 않았는지 확인할 수 있습니다.
    """
    repo = EvidenceRepository(db)
    records = repo.get_transaction_events(transaction_id)
    
    # 해시 체인 무결성 검증
    chain_valid = repo.verify_chain(transaction_id)
    
    events = []
    for r in records:
        events.append(EvidenceEventResponse(
            transaction_id=r.transaction_id,
            sequence_no=r.sequence_no,
            stage=r.stage,
            timestamp_ms=r.timestamp_ms,
            payload=r.payload,
            input_hash=r.input_hash,
            prev_hash=r.prev_hash,
            event_hash=r.event_hash
        ))
    
    return TransactionEvidenceResponse(
        transaction_id=transaction_id,
        events=events,
        chain_valid=chain_valid
    )
