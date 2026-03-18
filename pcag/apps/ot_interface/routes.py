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
from fastapi import APIRouter, HTTPException
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


def _execute_safe_state(asset_id: str) -> bool:
    # 장비 실행 실패 후에도 현장을 안전 상태로 되돌릴 수 있도록
    # executor별 safe_state 경로를 공통 함수로 묶는다.
    try:
        executor = ExecutorManager.get_executor(asset_id)
        logger.warning(
            "SAFE_STATE dispatch | asset=%s executor_id=%s executor_type=%s",
            asset_id,
            id(executor),
            executor.__class__.__name__,
        )
        result = executor.safe_state(asset_id)
        logger.warning(
            "SAFE_STATE result | asset=%s executor_id=%s success=%s",
            asset_id,
            id(executor),
            result,
        )
        return result
    except Exception as exc:
        logger.error("Safe state execution failed for asset=%s: %s", asset_id, exc, exc_info=True)
        return False


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
    # PREPARE는 "실행 전에 자산 점유권을 확보"하는 단계다.
    result = _state_machine.prepare(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        lock_ttl_ms=request.lock_ttl_ms
    )
    
    raw_status = result.get("status", "LOCK_DENIED")
    status = "LOCK_GRANTED" if raw_status == "LOCK_GRANTED" else "LOCK_DENIED"
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
    # COMMIT은 세 단계로 읽으면 이해가 쉽다.
    # 1) 아직 커밋 가능한 상태인지 확인
    # 2) executor로 실제 장비 실행
    # 3) 성공 시에만 COMMITTED finalize
    readiness = _state_machine.check_commit_ready(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id
    )
    readiness_status = readiness.get("status", "REJECTED")

    if readiness_status == "ALREADY_COMMITTED":
        logger.info("COMMIT tx=%s asset=%s -> ALREADY_COMMITTED", request.transaction_id, request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="ALREADY_COMMITTED",
            reason=readiness.get("reason"),
        )

    if readiness_status == "TIMEOUT":
        logger.warning("COMMIT tx=%s asset=%s -> TIMEOUT", request.transaction_id, request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="TIMEOUT",
            reason=readiness.get("reason"),
        )

    if readiness_status != "READY":
        detail = readiness.get("reason", "Commit rejected")
        logger.error("COMMIT tx=%s asset=%s rejected: %s", request.transaction_id, request.asset_id, detail)
        raise HTTPException(status_code=409, detail=detail)

    try:
        # 자산별 executor 선택 결과를 남겨 두면 장애 분석 시 어느 경로를 탔는지 바로 알 수 있다.
        executor = ExecutorManager.get_executor(request.asset_id)
        logger.info(
            "COMMIT executor selected | tx=%s asset=%s executor_id=%s executor_type=%s action_count=%s",
            request.transaction_id,
            request.asset_id,
            id(executor),
            executor.__class__.__name__,
            len(request.action_sequence),
        )
        exec_success = executor.execute(
            transaction_id=request.transaction_id,
            asset_id=request.asset_id,
            action_sequence=request.action_sequence
        )
    except Exception as exc:
        logger.critical("[SYSTEM_ERROR] Executor error for tx=%s: %s", request.transaction_id, exc, exc_info=True)
        abort_result = _state_machine.abort(request.transaction_id, request.asset_id)
        if abort_result.get("status") not in {"ABORTED", "ALREADY_ABORTED"}:
            raise HTTPException(
                status_code=500,
                detail=f"Execution failed and transaction could not be aborted: {abort_result.get('reason', 'unknown')}",
            )

        safe_state_executed = _execute_safe_state(request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="EXECUTION_FAILED",
            reason=str(exc),
            safe_state_executed=safe_state_executed,
        )

    if not exec_success:
        # 예외가 아니더라도 executor가 False를 반환하면 장비 적용 실패로 취급한다.
        # 이 경우에도 abort + safe_state 복구 절차를 동일하게 적용한다.
        failure_reason = getattr(executor, "last_error", None) or "Executor returned unsuccessful result"
        logger.error("COMMIT execution failed for tx=%s asset=%s: %s", request.transaction_id, request.asset_id, failure_reason)
        abort_result = _state_machine.abort(request.transaction_id, request.asset_id)
        if abort_result.get("status") not in {"ABORTED", "ALREADY_ABORTED"}:
            raise HTTPException(
                status_code=500,
                detail=f"Execution failed and transaction could not be aborted: {abort_result.get('reason', 'unknown')}",
            )

        safe_state_executed = _execute_safe_state(request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="EXECUTION_FAILED",
            reason=failure_reason,
            safe_state_executed=safe_state_executed,
        )

    # finalize 단계는 executor 성공 이후에만 호출된다.
    # 따라서 여기서 COMMITTED가 되면 "실제로 장비 적용이 끝났다"는 의미를 갖는다.
    finalize_result = _state_machine.finalize_commit(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
    )
    finalize_status = finalize_result.get("status", "REJECTED")

    if finalize_status == "COMMITTED":
        logger.info("COMMIT tx=%s asset=%s -> ACK", request.transaction_id, request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="ACK",
            executed_at_ms=int(time.time() * 1000),
        )

    if finalize_status == "ALREADY_COMMITTED":
        logger.info("COMMIT tx=%s asset=%s -> ALREADY_COMMITTED", request.transaction_id, request.asset_id)
        return CommitResponse(
            transaction_id=request.transaction_id,
            status="ALREADY_COMMITTED",
            reason=finalize_result.get("reason"),
        )

    detail = finalize_result.get("reason", "Finalize commit rejected")
    logger.error("Finalize COMMIT failed for tx=%s asset=%s: %s", request.transaction_id, request.asset_id, detail)
    raise HTTPException(status_code=409, detail=detail)


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
    # ABORT는 논리 상태(잠금/트랜잭션)와 물리 상태(safe_state)를 함께 정리하는 경로다.
    result = _state_machine.abort(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id
    )

    status = result.get("status", "ABORT_REJECTED")
    logger.info(f"ABORT tx={request.transaction_id} asset={request.asset_id} -> {status}")

    safe_state_executed = False
    if status in {"ABORTED", "ALREADY_ABORTED"}:
        safe_state_executed = _execute_safe_state(request.asset_id)

    return AbortResponse(
        transaction_id=request.transaction_id,
        status=status,
        safe_state_executed=safe_state_executed,
        reason=result.get("reason"),
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
    
    # E-Stop은 일반 실패 여부와 무관하게 safe_state를 즉시 시도한다.
    _execute_safe_state(request.asset_id)
    
    status = result.get("status", "ESTOP_EXECUTED")
    logger.info(f"E-STOP asset={request.asset_id} reason={request.reason} -> {status}")
    
    return EstopResponse(
        asset_id=request.asset_id,
        status="ESTOP_EXECUTED",
        timestamp_ms=int(time.time() * 1000)
    )
