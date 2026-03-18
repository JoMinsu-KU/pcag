import logging
import time

from pcag.apps.ot_interface.repository import TxRepository
from pcag.core.database.engine import SessionLocal

logger = logging.getLogger(__name__)


class PersistentTxStateMachine:
    """PostgreSQL-backed transaction state machine for the OT interface."""

    def _get_time(self) -> int:
        return int(time.time() * 1000)

    def prepare(self, transaction_id: str, asset_id: str, lock_ttl_ms: int) -> dict:
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            current_time = self._get_time()
            expires_at = current_time + lock_ttl_ms

            active_lock = repo.get_active_lock(asset_id, current_time)
            if active_lock and active_lock.transaction_id != transaction_id:
                return {
                    "status": "LOCK_DENIED",
                    "reason": f"Asset {asset_id} locked by {active_lock.transaction_id}",
                    "lock_expires_at_ms": active_lock.lock_expires_at_ms,
                }

            existing_tx = repo.get_transaction(transaction_id)
            if existing_tx:
                if existing_tx.asset_id != asset_id:
                    return {
                        "status": "PREPARE_REJECTED",
                        "reason": f"Transaction {transaction_id} is for asset {existing_tx.asset_id}, not {asset_id}",
                    }

                if existing_tx.status == "LOCKED":
                    repo.extend_lock(transaction_id, expires_at)
                    session.commit()
                    return {"status": "LOCK_GRANTED", "lock_expires_at_ms": expires_at}

                return {
                    "status": "PREPARE_REJECTED",
                    "reason": f"Transaction already finished with status {existing_tx.status}",
                }

            repo.create_lock(transaction_id, asset_id, expires_at)
            session.commit()
            return {"status": "LOCK_GRANTED", "lock_expires_at_ms": expires_at}
        except Exception as exc:
            session.rollback()
            logger.error("PREPARE error: %s", exc, exc_info=True)
            return {"status": "PREPARE_REJECTED", "reason": str(exc)}
        finally:
            session.close()

    def check_commit_ready(self, transaction_id: str, asset_id: str) -> dict:
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            current_time = self._get_time()
            tx = repo.get_transaction(transaction_id)

            if not tx:
                return {"status": "REJECTED", "reason": "Transaction not found"}
            if tx.asset_id != asset_id:
                return {"status": "REJECTED", "reason": "Asset mismatch"}
            if tx.status == "COMMITTED":
                return {"status": "ALREADY_COMMITTED", "reason": "Transaction already committed"}
            if tx.status == "ABORTED":
                return {"status": "REJECTED", "reason": "Transaction already aborted"}
            if tx.status != "LOCKED":
                return {"status": "REJECTED", "reason": f"Invalid status: {tx.status}"}

            active_lock = repo.get_active_lock(asset_id, current_time)
            if active_lock and active_lock.transaction_id != transaction_id:
                return {"status": "TIMEOUT", "reason": "Lock stolen or expired"}
            if not active_lock and tx.lock_expires_at_ms is not None and tx.lock_expires_at_ms < current_time:
                return {"status": "TIMEOUT", "reason": "Lock expired"}

            return {"status": "READY"}
        except Exception as exc:
            logger.error("COMMIT readiness check error: %s", exc, exc_info=True)
            return {"status": "REJECTED", "reason": str(exc)}
        finally:
            session.close()

    def finalize_commit(self, transaction_id: str, asset_id: str) -> dict:
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            tx = repo.get_transaction(transaction_id)

            if not tx:
                return {"status": "REJECTED", "reason": "Transaction not found"}
            if tx.asset_id != asset_id:
                return {"status": "REJECTED", "reason": "Asset mismatch"}
            if tx.status == "COMMITTED":
                return {"status": "ALREADY_COMMITTED", "reason": "Transaction already committed"}
            if tx.status != "LOCKED":
                return {"status": "REJECTED", "reason": f"Invalid status: {tx.status}"}

            repo.update_status(transaction_id, "COMMITTED", clear_lock=True)
            session.commit()
            return {"status": "COMMITTED"}
        except Exception as exc:
            session.rollback()
            logger.error("Finalize COMMIT error: %s", exc, exc_info=True)
            return {"status": "REJECTED", "reason": str(exc)}
        finally:
            session.close()

    def abort(self, transaction_id: str, asset_id: str) -> dict:
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            tx = repo.get_transaction(transaction_id)

            if not tx:
                return {"status": "ABORT_REJECTED", "reason": "Transaction not found"}
            if tx.asset_id != asset_id:
                return {"status": "ABORT_REJECTED", "reason": "Asset mismatch"}
            if tx.status == "ABORTED":
                return {"status": "ALREADY_ABORTED", "reason": "Transaction already aborted"}
            if tx.status == "COMMITTED":
                return {"status": "ABORT_REJECTED", "reason": "Cannot abort committed transaction"}

            repo.update_status(transaction_id, "ABORTED", clear_lock=True)
            session.commit()
            return {"status": "ABORTED"}
        except Exception as exc:
            session.rollback()
            logger.error("ABORT error: %s", exc, exc_info=True)
            return {"status": "ABORT_REJECTED", "reason": str(exc)}
        finally:
            session.close()

    def estop(self, asset_id: str) -> dict:
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            repo.abort_active_locks_for_asset(asset_id)
            session.commit()
            return {"status": "ESTOP_EXECUTED"}
        except Exception as exc:
            session.rollback()
            logger.error("ESTOP error: %s", exc, exc_info=True)
            return {"status": "ERROR", "reason": str(exc)}
        finally:
            session.close()
