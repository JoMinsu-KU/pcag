from sqlalchemy.orm import Session
from sqlalchemy import select, update, and_
from pcag.core.database.models import TransactionRecord
import time

class TxRepository:
    """
    TransactionRecord에 대한 DB 접근 로직.
    """
    def __init__(self, session: Session):
        self.session = session

    def get_active_lock(self, asset_id: str, current_time_ms: int) -> TransactionRecord | None:
        """
        해당 자산에 대해 현재 유효한(LOCKED 상태이고 만료되지 않은) 잠금을 반환.
        """
        stmt = select(TransactionRecord).where(
            TransactionRecord.asset_id == asset_id,
            TransactionRecord.status == "LOCKED",
            TransactionRecord.lock_expires_at_ms > current_time_ms
        )
        return self.session.execute(stmt).scalars().first()

    def get_transaction(self, transaction_id: str) -> TransactionRecord | None:
        """트랜잭션 조회"""
        return self.session.get(TransactionRecord, transaction_id)

    def create_lock(self, transaction_id: str, asset_id: str, lock_expires_at_ms: int) -> TransactionRecord:
        """새로운 잠금(트랜잭션) 생성"""
        tx = TransactionRecord(
            transaction_id=transaction_id,
            asset_id=asset_id,
            status="LOCKED",
            lock_expires_at_ms=lock_expires_at_ms
        )
        self.session.add(tx)
        return tx

    def extend_lock(self, transaction_id: str, lock_expires_at_ms: int):
        """기존 잠금의 만료 시간 연장"""
        stmt = update(TransactionRecord).where(
            TransactionRecord.transaction_id == transaction_id
        ).values(lock_expires_at_ms=lock_expires_at_ms)
        self.session.execute(stmt)

    def update_status(self, transaction_id: str, status: str):
        """트랜잭션 상태 변경 (COMMITTED, ABORTED)"""
        # 상태 변경 시 만료 시간은 의미가 없어지므로 그대로 두거나 0으로 설정할 수 있음.
        # 여기서는 상태만 변경.
        stmt = update(TransactionRecord).where(
            TransactionRecord.transaction_id == transaction_id
        ).values(status=status)
        self.session.execute(stmt)

    def abort_active_locks_for_asset(self, asset_id: str):
        """
        특정 자산의 모든 활성 잠금(LOCKED)을 ABORTED로 변경 (E-Stop).
        """
        stmt = update(TransactionRecord).where(
            TransactionRecord.asset_id == asset_id,
            TransactionRecord.status == "LOCKED"
        ).values(status="ABORTED", lock_expires_at_ms=0)
        self.session.execute(stmt)
