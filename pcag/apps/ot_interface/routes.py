"""
OT 인터페이스 노드 (OT Interface Node) — 실제 구현
====================================================
2PC(Two-Phase Commit) 상태머신을 사용하여 제어 명령을 실행합니다.

입력 억제 잠금(Input Suppression Lock):
  - PREPARE: 자산별 독점 잠금 획득 (다른 입력 차단)
  - COMMIT: 잠금 상태에서 명령 실행 + ACK
  - ABORT: 잠금 해제 + 안전 상태 전환
  - E-Stop: 모든 잠금 무시, 즉시 비상정지

Idempotency 보장:
  - 같은 tx_id로 COMMIT 재호출 → ALREADY_COMMITTED (재실행 안 함)
  - 같은 tx_id로 ABORT 재호출 → ALREADY_ABORTED

API:
  POST /v1/prepare  — 입력 억제 잠금 획득
  POST /v1/commit   — 장비에서 동작 실행
  POST /v1/abort    — 트랜잭션 중단 + 안전 상태
  POST /v1/estop    — 비상정지 (최우선)

conda pcag 환경에서 실행.
"""
import time
import logging
from fastapi import APIRouter
from pcag.core.contracts.ot_interface import (
    PrepareRequest, PrepareResponse,
    CommitRequest, CommitResponse,
    AbortRequest, AbortResponse,
    EstopRequest, EstopResponse
)
# from pcag.core.services.tx_state_machine import TxStateMachine
from pcag.apps.ot_interface.service import PersistentTxStateMachine
from pcag.apps.ot_interface.executor_manager import ExecutorManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["OTInterface"])

# 2PC 상태머신 인스턴스 (Persistent)
# DB 기반 Persistent Transaction State Machine 사용
_state_machine = PersistentTxStateMachine()


@router.post("/prepare")
def prepare(request: PrepareRequest):
    """
    입력 억제 잠금 획득 (PREPARE)
    
    PCAG 파이프라인 [130-1]:
    - 자산별 독점 잠금을 획득합니다
    - 다른 트랜잭션이 잠금 중이면 LOCK_DENIED
    - E-Stop은 잠금과 무관하게 항상 실행됩니다
    - 잠금에는 TTL이 있어 만료 시 자동 해제
    
    Idempotency: 같은 tx_id로 재호출 시 LOCK_GRANTED (재잠금 아님)
    """
    result = _state_machine.prepare(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        lock_ttl_ms=request.lock_ttl_ms
    )
    
    status = result.get("status", "LOCK_DENIED")
    logger.info(f"PREPARE tx={request.transaction_id} asset={request.asset_id} -> {status}")
    
    return PrepareResponse(
        transaction_id=request.transaction_id,
        status=status,
        lock_expires_at_ms=result.get("lock_expires_at_ms"),
        reason=result.get("reason")
    )


@router.post("/commit")
def commit(request: CommitRequest):
    """
    장비에서 동작 실행 (COMMIT)
    
    PCAG 파이프라인 [130-3]:
    - PREPARE로 잠금을 획득한 트랜잭션만 COMMIT 가능
    - 명령 실행 후 ACK 반환
    - 잠금이 자동 해제됩니다
    
    Idempotency: 같은 tx_id로 재호출 시 ALREADY_COMMITTED (재실행 안 함!)
    
    실제 장비 제어는 IOTExecutor 플러그인이 담당합니다.
    현재는 Mock Executor (로깅만) 사용.
    """
    result = _state_machine.commit(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id
    )
    
    # TxStateMachine returns "COMMITTED", but contract expects "ACK"
    raw_status = result.get("status", "TIMEOUT")
    if raw_status == "COMMITTED":
        # Execute actual command on device
        try:
            executor = ExecutorManager.get_executor(request.asset_id)
            exec_success = executor.execute(
                transaction_id=request.transaction_id,
                asset_id=request.asset_id,
                action_sequence=request.action_sequence
            )
            
            if exec_success:
                status = "ACK"
            else:
                logger.critical(f"[SYSTEM_ERROR] Execution failed for tx={request.transaction_id}")
                status = "ERROR" 
        except Exception as e:
            logger.critical(f"[SYSTEM_ERROR] Executor error for tx={request.transaction_id}: {e}", exc_info=True)
            status = "ERROR"
    else:
        status = raw_status
        
    logger.info(f"COMMIT tx={request.transaction_id} asset={request.asset_id} -> {status}")
    
    # 실행 시각 (ACK인 경우)
    executed_at_ms = int(time.time() * 1000) if status == "ACK" else None
    
    return CommitResponse(
        transaction_id=request.transaction_id,
        status=status,
        executed_at_ms=executed_at_ms
    )


@router.post("/abort")
def abort(request: AbortRequest):
    """
    트랜잭션 중단 (ABORT)
    
    PCAG 파이프라인 [130-ABORT]:
    - 잠금 해제 + 안전 상태(Safe State)로 전환
    - 물리 장비에서는 롤백이 불가능하므로 사전 정의된 안전 동작 실행
    - 예: 히터 OFF, 냉각 밸브 OPEN, 로봇 정지+홀드
    
    Idempotency: 같은 tx_id로 재호출 시 ALREADY_ABORTED
    """
    result = _state_machine.abort(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id
    )
    
    raw_status = result.get("status", "ABORTED")
    
    # Map ERROR (e.g. tx not found) to ALREADY_ABORTED for idempotency
    if raw_status == "ERROR":
        status = "ALREADY_ABORTED"
    else:
        status = raw_status
        
    logger.info(f"ABORT tx={request.transaction_id} asset={request.asset_id} -> {status}")
    
    # 안전 상태 실행 여부
    safe_state_executed = False
    
    if status == "ABORTED" or status == "ALREADY_ABORTED":
        try:
            executor = ExecutorManager.get_executor(request.asset_id)
            safe_state_executed = executor.safe_state(request.asset_id)
        except Exception as e:
            logger.error(f"Safe state execution failed for asset={request.asset_id}: {e}")
            safe_state_executed = False
    
    return AbortResponse(
        transaction_id=request.transaction_id,
        status=status,
        safe_state_executed=safe_state_executed
    )


@router.post("/estop")
def estop(request: EstopRequest):
    """
    비상정지 (E-Stop)
    
    최우선 명령 — 모든 잠금과 트랜잭션을 무시하고 즉시 실행됩니다.
    - 해당 자산의 모든 잠금을 강제 해제
    - 진행 중인 트랜잭션을 강제 중단
    - E-Stop은 절대 거부되지 않습니다
    """
    result = _state_machine.estop(asset_id=request.asset_id)
    
    # Always attempt to execute safe state for Estop
    try:
        executor = ExecutorManager.get_executor(request.asset_id)
        executor.safe_state(request.asset_id)
    except Exception as e:
        logger.error(f"E-Stop safe state execution failed for asset={request.asset_id}: {e}")
    
    status = result.get("status", "ESTOP_EXECUTED")
    logger.info(f"E-STOP asset={request.asset_id} reason={request.reason} -> {status}")
    
    return EstopResponse(
        asset_id=request.asset_id,
        status="ESTOP_EXECUTED",
        timestamp_ms=int(time.time() * 1000)
    )
