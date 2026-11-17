from sqlalchemy.orm import Session
from sqlalchemy import and_, case, or_, select, update
from pcag.core.database.models import (
    AssetExecutionLockRecord, OperationReceiptRecord, TransactionRecord,
)

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

    def update_status(self, transaction_id: str, status: str, *, clear_lock: bool = False):
        """트랜잭션 상태 변경 (COMMITTED, ABORTED)."""
        values = {"status": status}
        if clear_lock:
            values["lock_expires_at_ms"] = 0

        stmt = update(TransactionRecord).where(
            TransactionRecord.transaction_id == transaction_id
        ).values(**values)
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

    def get_operation(self, transaction_id: str, *, for_update: bool = False):
        stmt = select(OperationReceiptRecord).where(OperationReceiptRecord.transaction_id == transaction_id)
        if for_update:
            stmt = stmt.with_for_update()
        return self.session.execute(stmt.execution_options(populate_existing=True)).scalar_one_or_none()

    def get_asset_slot(self, asset_id: str):
        return self.session.execute(
            select(AssetExecutionLockRecord).where(AssetExecutionLockRecord.asset_id == asset_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def _insert(self, model):
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError(f"Atomic operation receipts require PostgreSQL or SQLite, got {dialect}")
        return insert(model)

    def ensure_operation(self, transaction_id: str, asset_id: str, now_ms: int,
                         payload_digest: str | None, action_sequence: list | None):
        stmt = self._insert(OperationReceiptRecord).values(
            transaction_id=transaction_id, asset_id=asset_id, schema_version=2,
            state="PREPARED", payload_digest=payload_digest, action_sequence=action_sequence,
            fencing_token=0, dispatch_count=0, created_at_ms=now_ms, updated_at_ms=now_ms,
        ).on_conflict_do_nothing(index_elements=["transaction_id"])
        self.session.execute(stmt)
        return self.get_operation(transaction_id, for_update=True)

    def reserve_asset(self, asset_id: str, transaction_id: str, now_ms: int, expires_ms: int):
        model = AssetExecutionLockRecord
        same_reservation = and_(model.transaction_id == transaction_id, model.phase == "RESERVED")
        eligible = or_(model.phase == "FREE", same_reservation,
                       and_(model.phase == "RESERVED", model.lease_expires_at_ms <= now_ms))
        stmt = self._insert(model).values(
            asset_id=asset_id, transaction_id=transaction_id, phase="RESERVED",
            fencing_token=1, lease_expires_at_ms=expires_ms, updated_at_ms=now_ms,
        ).on_conflict_do_update(
            index_elements=["asset_id"],
            set_={"transaction_id":transaction_id, "phase":"RESERVED",
                  "fencing_token":case((same_reservation, model.fencing_token), else_=model.fencing_token + 1),
                  "lease_expires_at_ms":expires_ms, "updated_at_ms":now_ms},
            where=eligible,
        ).returning(model.asset_id)
        if self.session.execute(stmt).first() is None:
            return None
        return self.get_asset_slot(asset_id)

    def transition_operation(self, transaction_id: str, states, values: dict,
                             *, claim_token: str | None = None):
        stmt = update(OperationReceiptRecord).where(
            OperationReceiptRecord.transaction_id == transaction_id,
            OperationReceiptRecord.state.in_(states),
        )
        if claim_token is not None:
            stmt = stmt.where(OperationReceiptRecord.claim_token == claim_token)
        return self.session.execute(stmt.values(**values).execution_options(synchronize_session=False)).rowcount

    def claim_asset_dispatch(self, asset_id: str, transaction_id: str, fence: int, now_ms: int):
        model = AssetExecutionLockRecord
        stmt = update(model).where(
            model.asset_id == asset_id, model.transaction_id == transaction_id,
            model.fencing_token == fence, model.phase == "RESERVED",
            model.lease_expires_at_ms > now_ms,
        ).values(phase="DISPATCHING", updated_at_ms=now_ms)
        return self.session.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1

    def release_asset(self, asset_id: str, transaction_id: str, fence: int, now_ms: int):
        stmt = update(AssetExecutionLockRecord).where(
            AssetExecutionLockRecord.asset_id == asset_id,
            AssetExecutionLockRecord.transaction_id == transaction_id,
            AssetExecutionLockRecord.fencing_token == fence,
        ).values(transaction_id=None, phase="FREE", lease_expires_at_ms=None, updated_at_ms=now_ms)
        self.session.execute(stmt.execution_options(synchronize_session=False))

    def quarantine_asset(self, asset_id: str, transaction_id: str, fence: int, now_ms: int):
        stmt = update(AssetExecutionLockRecord).where(
            AssetExecutionLockRecord.asset_id == asset_id,
            AssetExecutionLockRecord.transaction_id == transaction_id,
            AssetExecutionLockRecord.fencing_token == fence,
        ).values(phase="UNKNOWN", updated_at_ms=now_ms)
        self.session.execute(stmt.execution_options(synchronize_session=False))

    def list_operations(self, asset_id: str | None = None):
        stmt = select(OperationReceiptRecord)
        if asset_id is not None:
            stmt = stmt.where(OperationReceiptRecord.asset_id == asset_id)
        return list(self.session.execute(stmt.execution_options(populate_existing=True)).scalars())

    def list_asset_slots(self, asset_id: str | None = None):
        stmt = select(AssetExecutionLockRecord)
        if asset_id is not None:
            stmt = stmt.where(AssetExecutionLockRecord.asset_id == asset_id)
        return list(self.session.execute(stmt.execution_options(populate_existing=True)).scalars())
