import time
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pcag.core.database.engine import SessionLocal
from pcag.core.services.tx_state_machine import TxStatus
from pcag.apps.ot_interface.repository import TxRepository

logger = logging.getLogger(__name__)

class PersistentTxStateMachine:
    """
    PostgreSQL 기반의 영구적 트랜잭션 상태 머신.
    메모리 대신 DB를 사용하여 상태와 잠금을 관리합니다.
    """
    
    def __init__(self):
        pass

    def _get_time(self) -> int:
        """현재 시각 (ms)"""
        return int(time.time() * 1000)

    def prepare(self, transaction_id: str, asset_id: str, lock_ttl_ms: int) -> dict:
        """
        [Phase 1] 준비 및 잠금 획득 요청.
        DB 트랜잭션을 사용하여 원자적으로 처리합니다.
        """
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            current_time = self._get_time()
            expires_at = current_time + lock_ttl_ms
            
            # 1. 활성 잠금 확인 (다른 트랜잭션이 선점했는지)
            active_lock = repo.get_active_lock(asset_id, current_time)
            
            if active_lock and active_lock.transaction_id != transaction_id:
                return {
                    "status": "LOCK_DENIED", 
                    "reason": f"Asset {asset_id} locked by {active_lock.transaction_id}",
                    "lock_expires_at_ms": active_lock.lock_expires_at_ms
                }
            
            # 2. 기존 트랜잭션 조회
            existing_tx = repo.get_transaction(transaction_id)
            
            if existing_tx:
                # 이미 존재하는 트랜잭션
                if existing_tx.asset_id != asset_id:
                    return {
                        "status": "ERROR", 
                        "reason": f"Transaction {transaction_id} is for asset {existing_tx.asset_id}, not {asset_id}"
                    }
                    
                if existing_tx.status == "LOCKED":
                    # 재시도 -> 잠금 연장
                    repo.extend_lock(transaction_id, expires_at)
                    session.commit()
                    return {
                        "status": "LOCK_GRANTED",
                        "lock_expires_at_ms": expires_at
                    }
                else:
                    # 이미 완료된 트랜잭션 (COMMITTED / ABORTED)
                    return {
                        "status": existing_tx.status,
                        "reason": "Transaction already finished"
                    }
            
            # 3. 신규 트랜잭션 생성 (잠금 획득)
            try:
                repo.create_lock(transaction_id, asset_id, expires_at)
                session.commit()
                return {
                    "status": "LOCK_GRANTED",
                    "lock_expires_at_ms": expires_at
                }
            except IntegrityError:
                session.rollback()
                # 동시성 문제로 생성 실패 시 (드문 경우)
                return {"status": "LOCK_DENIED", "reason": "Concurrent lock attempt failed"}
                
        except Exception as e:
            session.rollback()
            logger.error(f"PREPARE error: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e)}
        finally:
            session.close()

    def commit(self, transaction_id: str, asset_id: str) -> dict:
        """
        [Phase 2] 커밋 및 실행 확정 요청.
        """
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            current_time = self._get_time()
            
            tx = repo.get_transaction(transaction_id)
            
            if not tx:
                return {"status": "ERROR", "reason": "Transaction not found"}
            
            if tx.asset_id != asset_id:
                return {"status": "ERROR", "reason": "Asset mismatch"}

            if tx.status == "COMMITTED":
                return {"status": "ALREADY_COMMITTED"}
            
            if tx.status == "ABORTED":
                return {"status": "ERROR", "reason": "Transaction already aborted"}
            
            if tx.status != "LOCKED":
                return {"status": "ERROR", "reason": f"Invalid status: {tx.status}"}
            
            # 잠금 유효성 검사
            # 만약 시간이 지났다면?
            # 정책: 시간이 지났어도 '내' 트랜잭션이고, 그 사이 다른 놈이 채가지 않았다면?
            # DB에서는 'lock_expires_at_ms'가 지났으면 'active_lock' 조회 시 안 나옴.
            # 하지만 커밋 시점에는 내가 주인이면 됨.
            # 문제는 그 사이 다른 놈이 'LOCKED' 상태로 들어왔을 수 있음.
            # 즉, 내 lock_expires_at_ms < current_time 이면, 
            # 누군가 다른 트랜잭션이 들어왔는지 확인해야 함.
            
            active_lock = repo.get_active_lock(asset_id, current_time)
            
            if active_lock and active_lock.transaction_id != transaction_id:
                # 다른 놈이 잠금 획득함 (나는 만료됨)
                return {"status": "ERROR", "reason": "Lock stolen or expired"}
            
            # 만약 active_lock이 없으면? (즉, 내 것도 만료되고, 아무도 안 잡음)
            # 엄격한 2PC에서는 타임아웃 되면 ABORT 처리되어야 함.
            # 여기서는 만료되었으면 커밋 거부.
            if not active_lock and tx.lock_expires_at_ms < current_time:
                 return {"status": "ERROR", "reason": "Lock expired"}
                 
            # 상태 전이: LOCKED -> COMMITTED
            # 주의: 커밋하면 잠금은 해제된 것으로 간주됨 (더 이상 active_lock에 걸리지 않음 status != LOCKED)
            repo.update_status(transaction_id, "COMMITTED")
            session.commit()
            
            return {"status": "COMMITTED"}
            
        except Exception as e:
            session.rollback()
            logger.error(f"COMMIT error: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e)}
        finally:
            session.close()

    def abort(self, transaction_id: str, asset_id: str) -> dict:
        """
        트랜잭션 중단.
        """
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            tx = repo.get_transaction(transaction_id)
            
            if not tx:
                return {"status": "ERROR", "reason": "Transaction not found"}
                
            if tx.asset_id != asset_id:
                return {"status": "ERROR", "reason": "Asset mismatch"}
            
            if tx.status == "ABORTED":
                return {"status": "ALREADY_ABORTED"}
                
            if tx.status == "COMMITTED":
                return {"status": "ERROR", "reason": "Cannot abort committed transaction"}
                
            # 상태 전이: -> ABORTED
            repo.update_status(transaction_id, "ABORTED")
            session.commit()
            
            return {"status": "ABORTED"}
            
        except Exception as e:
            session.rollback()
            logger.error(f"ABORT error: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e)}
        finally:
            session.close()

    def estop(self, asset_id: str) -> dict:
        """
        비상 정지 (E-Stop). 해당 자산의 모든 잠금을 무효화.
        """
        session = SessionLocal()
        try:
            repo = TxRepository(session)
            # 해당 자산의 모든 LOCKED 상태 트랜잭션을 ABORTED로 변경
            repo.abort_active_locks_for_asset(asset_id)
            session.commit()
            
            return {"status": "ESTOP_EXECUTED"}
        except Exception as e:
            session.rollback()
            logger.error(f"ESTOP error: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e)}
        finally:
            session.close()
