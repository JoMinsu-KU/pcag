"""
PCAG 데이터베이스 ORM 모델
===========================
PostgreSQL 테이블 정의.

스키마 문서 참조: plans/PCAG_Schema_Definitions.md §5 Database Schemas
conda pcag 환경에서 실행.
"""
from sqlalchemy import (
    Column, String, BigInteger, Boolean, Integer, DateTime,
    UniqueConstraint, Index, JSON
)
from sqlalchemy.sql import func
from pcag.core.database.engine import Base
import json


class PolicyRecord(Base):
    """
    정책 문서 테이블 (policies)
    ============================
    각 버전의 PolicyDocument를 JSONB로 저장합니다.
    한 번 저장된 정책은 수정 불가 (immutable per version).
    
    DDL 참조: plans/PCAG_Schema_Definitions.md §5.1
    """
    __tablename__ = "policies"
    
    policy_version_id = Column(String, primary_key=True, comment="정책 버전 ID (예: v2025-03-01)")
    issued_at_ms = Column(BigInteger, nullable=False, comment="정책 발행 시각 (epoch ms)")
    document = Column(JSON, nullable=False, comment="전체 PolicyDocument (JSONB)")
    is_active = Column(Boolean, default=False, comment="현재 활성 정책 여부")
    created_by = Column(String, nullable=True, comment="생성자")
    created_at = Column(DateTime, server_default=func.now(), comment="DB 기록 시각")
    
    # 인덱스
    __table_args__ = (
        Index('idx_policies_is_active', 'is_active'),
    )
    
    def get_document(self) -> dict:
        """JSONB 데이터를 dict로 반환 (PostgreSQL JSONB는 이미 dict)"""
        if isinstance(self.document, str):
            return json.loads(self.document)
        return self.document  # JSONB는 이미 dict
    
    def get_assets(self) -> dict:
        """assets 부분만 추출"""
        doc = self.get_document()
        return doc.get("assets", {})
    
    def get_asset_profile(self, asset_id: str) -> dict | None:
        """특정 자산의 정책 프로필 반환"""
        return self.get_assets().get(asset_id)


class EvidenceEventRecord(Base):
    """
    증거 이벤트 테이블 (evidence_events)
    ======================================
    해시 체인 방식의 증거 이벤트를 저장합니다.
    각 트랜잭션의 모든 파이프라인 단계가 이벤트로 기록되며,
    이전 이벤트의 해시를 참조하여 변조 탐지가 가능합니다.
    
    Append-Only: 삽입만 허용, 수정/삭제 불가 (감사 추적용).
    
    DDL 참조: plans/PCAG_Schema_Definitions.md §5.2
    """
    __tablename__ = "evidence_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동 증가 ID")
    transaction_id = Column(String, nullable=False, comment="트랜잭션 ID (UUIDv4)")
    sequence_no = Column(Integer, nullable=False, comment="트랜잭션 내 이벤트 순서 (0부터)")
    stage = Column(String, nullable=False, comment="파이프라인 단계 (RECEIVED, SCHEMA_VALIDATED, ...)")
    timestamp_ms = Column(BigInteger, nullable=False, comment="이벤트 발생 시각 (epoch ms)")
    payload = Column(JSON, nullable=False, comment="이벤트 페이로드 (JSONB)")
    input_hash = Column(String(64), nullable=False, comment="페이로드 해시 (SHA-256)")
    prev_hash = Column(String(64), nullable=False, comment="이전 이벤트 해시 (체인 연결)")
    event_hash = Column(String(64), nullable=False, comment="이 이벤트의 해시 (SHA-256)")
    created_at = Column(DateTime, server_default=func.now(), comment="DB 기록 시각")
    
    # 제약 조건 + 인덱스
    __table_args__ = (
        UniqueConstraint('transaction_id', 'sequence_no', name='uq_tx_seq'),
        Index('idx_evidence_transaction_id', 'transaction_id'),
        Index('idx_evidence_event_hash', 'event_hash'),
    )


class TransactionRecord(Base):
    """
    트랜잭션 상태 테이블 (transactions)
    ======================================
    2PC 트랜잭션의 상태와 잠금 정보를 저장합니다.
    
    Persistent State Machine을 위한 저장소.
    """
    __tablename__ = "transactions"
    
    transaction_id = Column(String, primary_key=True, comment="트랜잭션 ID (UUID)")
    asset_id = Column(String, nullable=False, comment="대상 자산 ID")
    status = Column(String, nullable=False, default="LOCKED", comment="상태 (LOCKED, COMMITTED, ABORTED)")
    lock_expires_at_ms = Column(BigInteger, nullable=True, comment="잠금 만료 시각 (epoch ms)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 시각")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="수정 시각")
    
    __table_args__ = (
        Index('idx_transactions_asset_status', 'asset_id', 'status'),
    )
