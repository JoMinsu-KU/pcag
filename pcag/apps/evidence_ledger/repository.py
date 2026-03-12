"""
증거 원장 저장소 (Evidence Repository)
======================================
증거 이벤트의 DB CRUD 연산을 캡슐화합니다.
Append-Only: 삽입과 조회만 허용합니다.

conda pcag 환경에서 실행.
"""
import json
from sqlalchemy.orm import Session
from pcag.core.database.models import EvidenceEventRecord


class EvidenceRepository:
    """증거 원장 저장소 — Append-Only DB CRUD"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def append_event(self, transaction_id: str, sequence_no: int, stage: str,
                     timestamp_ms: int, payload: dict, input_hash: str,
                     prev_hash: str, event_hash: str) -> EvidenceEventRecord:
        """
        증거 이벤트 추가 (Append-Only)
        
        해시 체인: event_hash = sha256(prev_hash + canonical(payload))
        첫 이벤트의 prev_hash = sha256("") (Genesis Hash)
        """
        record = EvidenceEventRecord(
            transaction_id=transaction_id,
            sequence_no=sequence_no,
            stage=stage,
            timestamp_ms=timestamp_ms,
            payload=payload,  # JSONB accepts dict directly, no json.dumps needed
            input_hash=input_hash,
            prev_hash=prev_hash,
            event_hash=event_hash
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_transaction_events(self, transaction_id: str) -> list[EvidenceEventRecord]:
        """트랜잭션의 모든 증거 이벤트를 순서대로 조회"""
        return (
            self.db.query(EvidenceEventRecord)
            .filter(EvidenceEventRecord.transaction_id == transaction_id)
            .order_by(EvidenceEventRecord.sequence_no)
            .all()
        )
    
    def verify_chain(self, transaction_id: str) -> bool:
        """
        해시 체인 무결성 검증
        
        각 이벤트의 prev_hash가 이전 이벤트의 event_hash와 일치하는지 확인합니다.
        """
        events = self.get_transaction_events(transaction_id)
        if not events:
            return True  # 이벤트 없으면 유효
        
        from pcag.core.utils.hash_utils import GENESIS_HASH, compute_event_hash
        
        # 첫 이벤트의 prev_hash는 Genesis Hash여야 함
        if events[0].prev_hash != GENESIS_HASH:
            return False
        
        # 각 이벤트의 해시 체인 검증
        for i in range(1, len(events)):
            if events[i].prev_hash != events[i-1].event_hash:
                return False
        
        # 각 이벤트의 event_hash 재계산 검증
        for event in events:
            # Handle potential string/dict differences in different DB backends
            payload = event.payload
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    pass
            
            expected_hash = compute_event_hash(event.prev_hash, payload)
            if event.event_hash != expected_hash:
                return False
        
        return True
