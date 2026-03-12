"""
Transaction State Machine Service
============================================
이 모듈은 2단계 커밋(2PC) 프로토콜을 관리하는 상태 머신(State Machine)을 구현합니다.
트랜잭션의 상태 전이(준비 -> 커밋/중단)와 자원 잠금(Locking)을 제어합니다.

PCAG 파이프라인 위치:
  [130] OT Interface (2PC Coordinator)

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §TransactionManager
"""

import time
from enum import Enum
from typing import Optional, Dict, Callable

class TxStatus(str, Enum):
    """트랜잭션 상태 열거형"""
    IDLE = "IDLE"          # 대기 중 (존재하지 않음)
    LOCKED = "LOCKED"      # 1단계: 잠금 획득 (Prepare 완료)
    COMMITTED = "COMMITTED" # 2단계: 커밋 완료 (실행됨)
    ABORTED = "ABORTED"    # 중단됨 (롤백 또는 취소)

class LockStatus(str, Enum):
    """자산 잠금 상태 열거형"""
    FREE = "FREE"      # 잠금 없음
    LOCKED = "LOCKED"  # 잠김

class TxStateMachine:
    """
    2PC 트랜잭션 상태 관리 및 동시성 제어 클래스.
    (현재는 인메모리 구현, 추후 Redis 등으로 확장 가능)
    """
    
    def __init__(self, time_provider: Optional[Callable[[], float]] = None):
        # 자산별 잠금 상태: asset_id -> {"tx_id": str, "expiry": float}
        self._locks: Dict[str, dict] = {}
        # 트랜잭션 정보: tx_id -> {"status": TxStatus, "asset_id": str, ...}
        self._transactions: Dict[str, dict] = {}
        # 시간 제공자 (테스트 용이성을 위해 주입 가능)
        self._time_provider = time_provider or (lambda: time.time() * 1000)

    def _get_time(self) -> float:
        """현재 시각 반환 (ms)"""
        return self._time_provider()
    
    def _check_lock_expired(self, asset_id: str) -> None:
        """
        만료된 잠금을 확인하고 자동 해제합니다.
        (Lazy Expiration 방식: 접근 시 확인)
        """
        if asset_id in self._locks:
            lock = self._locks[asset_id]
            if self._get_time() > lock["expiry"]:
                # 잠금 만료 -> 해제
                del self._locks[asset_id]
                # 주의: 연관된 트랜잭션 상태는 변경하지 않음 (Commit 시도 시 실패 처리됨)
    
    def prepare(self, transaction_id: str, asset_id: str, lock_ttl_ms: int) -> dict:
        """
        [Phase 1] 준비 및 잠금 획득 요청.
        입력 억제(Input Suppression)를 위해 자산을 독점적으로 잠급니다.
        """
        self._check_lock_expired(asset_id)
        
        current_time = self._get_time()
        lock = self._locks.get(asset_id)
        
        # 이미 다른 트랜잭션이 잠금을 보유 중인 경우 -> 거부
        if lock and lock["tx_id"] != transaction_id:
            return {"status": "LOCK_DENIED", "reason": f"Asset {asset_id} locked by {lock['tx_id']}"}
        
        # 동일한 트랜잭션이 다시 요청한 경우 (재시도/멱등성) -> 승인 및 TTL 연장
        if lock and lock["tx_id"] == transaction_id:
            lock["expiry"] = current_time + lock_ttl_ms
            return {"status": "LOCK_GRANTED"}
        
        # 잠금 획득 성공 (신규)
        self._locks[asset_id] = {
            "tx_id": transaction_id,
            "expiry": current_time + lock_ttl_ms
        }
        self._transactions[transaction_id] = {
            "status": TxStatus.LOCKED,
            "asset_id": asset_id
        }
        return {"status": "LOCK_GRANTED"}
    
    def commit(self, transaction_id: str, asset_id: str) -> dict:
        """
        [Phase 2] 커밋 및 실행 확정 요청.
        잠금이 유효한 상태에서만 커밋이 가능합니다.
        """
        # 커밋 직전 잠금 유효성 재확인
        self._check_lock_expired(asset_id)
        
        tx = self._transactions.get(transaction_id)
        
        if not tx:
             return {"status": "ERROR", "reason": "Transaction not found"}
             
        if tx["status"] == TxStatus.COMMITTED:
            return {"status": "ALREADY_COMMITTED"}
            
        if tx["status"] == TxStatus.ABORTED:
             return {"status": "ERROR", "reason": "Transaction already aborted"}
             
        if tx["status"] != TxStatus.LOCKED:
            return {"status": "ERROR", "reason": "Transaction not in LOCKED state"}
            
        # 잠금 소유권 최종 확인
        lock = self._locks.get(asset_id)
        if not lock:
             return {"status": "ERROR", "reason": "Lock expired or lost"}
             
        if lock["tx_id"] != transaction_id:
             return {"status": "ERROR", "reason": "Lock stolen by another transaction"}
             
        # 상태 전이: LOCKED -> COMMITTED
        tx["status"] = TxStatus.COMMITTED
        
        # 커밋 완료 후 잠금 즉시 해제 (또는 후속 작업을 위해 유지할 수도 있으나, 여기선 즉시 해제)
        del self._locks[asset_id]
        
        return {"status": "COMMITTED"}
    
    def abort(self, transaction_id: str, asset_id: str) -> dict:
        """
        트랜잭션 중단 및 롤백 요청.
        보유 중인 잠금을 해제하고 상태를 ABORTED로 변경합니다.
        """
        tx = self._transactions.get(transaction_id)
        
        if not tx:
             return {"status": "ERROR", "reason": "Transaction not found"}
             
        if tx["status"] == TxStatus.ABORTED:
            return {"status": "ALREADY_ABORTED"}
            
        if tx["status"] == TxStatus.COMMITTED:
             return {"status": "ERROR", "reason": "Cannot abort committed transaction"}
             
        # 상태 전이: -> ABORTED
        tx["status"] = TxStatus.ABORTED
        
        # 보유 중인 잠금이 있다면 해제
        lock = self._locks.get(asset_id)
        if lock and lock["tx_id"] == transaction_id:
            del self._locks[asset_id]
            
        return {"status": "ABORTED"}
    
    def estop(self, asset_id: str) -> dict:
        """
        비상 정지(Emergency Stop) 처리.
        해당 자산에 대한 모든 잠금을 강제로 해제하고 즉시 정지시킵니다.
        """
        # 자산 잠금 강제 제거 (어떤 트랜잭션이든 무시)
        if asset_id in self._locks:
            del self._locks[asset_id]
            
        return {"status": "ESTOP_EXECUTED"}
