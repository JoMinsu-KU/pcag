"""OT request boundary: durable dispatch claims, receipts and reconciliation.

ACK means the explicitly reported executor boundary, not universal physical
completion. A missing ACK becomes UNKNOWN, never a fabricated non-execution.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from pcag.core.contracts.ot_interface import (
    PrepareRequest, PrepareResponse, CommitRequest, CommitResponse,
    AbortRequest, AbortResponse, EstopRequest, EstopResponse,
    ReconcileRequest, RevisionResetRequest,
)
from pcag.core.middleware.auth import verify_api_key
from pcag.apps.ot_interface.service import PersistentTxStateMachine, compute_operation_digest
from pcag.apps.ot_interface.executor_manager import ExecutorManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["OTInterface"])
_state_machine = PersistentTxStateMachine()


def _execute_safe_state(asset_id: str) -> bool:
    try:
        result = bool(ExecutorManager.get_executor(asset_id).safe_state(asset_id))
        logger.warning("SAFE_STATE asset=%s success=%s", asset_id, result)
        return result
    except Exception as exc:
        logger.error("Safe-state attempt failed for %s: %s", asset_id, exc)
        return False


def _commit_response(transaction_id: str, result: dict[str, Any], **extra) -> CommitResponse:
    result = {**result, **extra, "transaction_id":transaction_id}
    if result.get("status") == "COMMITTED":
        result["status"] = "ACK"
    return CommitResponse(**result)


def _executor_receipt(executor, result: Any, request: CommitRequest) -> dict:
    """Prefer an explicit receipt; a legacy bool must retain its limited boundary."""
    receipt = result if isinstance(result, dict) else getattr(executor, "last_execution_receipt", None)
    if not isinstance(receipt, dict):
        receipt = getattr(executor, "last_receipt", None)
    now = int(time.time() * 1000)
    if not isinstance(receipt, dict):
        if bool(result):
            mock = executor.__class__.__name__ == "MockExecutor"
            receipt = {"status":"COMPLETED" if mock else "ACCEPTED", "accepted":True,
                       "completed":mock, "execution_confirmed":False,
                       "ack_boundary":"mock_ack" if mock else "legacy_executor_ack",
                       "accepted_at_ms":now}
            if mock:
                receipt["completed_at_ms"] = now
        else:
            receipt = {"status":"FAILED", "completed":False,
                       "reason":getattr(executor, "last_error", None) or "Executor reported failure",
                       "ack_boundary":"executor_failure_report", "effects_may_have_occurred":True}
    receipt = dict(receipt)
    receipt["status"] = str(receipt.get("status", "UNKNOWN")).upper()
    receipt.setdefault("transaction_id", request.transaction_id)
    receipt.setdefault("asset_id", request.asset_id)
    receipt.setdefault("payload_digest", compute_operation_digest(request.asset_id, request.action_sequence))
    if receipt["status"] in {"ACCEPTED", "COMPLETED"}:
        receipt.setdefault("accepted", True)
        receipt.setdefault("completed", receipt["status"] == "COMPLETED")
    return receipt


@router.post("/prepare")
def prepare(request: PrepareRequest):
    kwargs = {"transaction_id":request.transaction_id, "asset_id":request.asset_id, "lock_ttl_ms":request.lock_ttl_ms}
    if request.action_sequence is not None:
        kwargs["action_sequence"] = request.action_sequence
    if request.payload_digest is not None:
        kwargs["payload_digest"] = request.payload_digest
    result = _state_machine.prepare(**kwargs)
    return PrepareResponse(transaction_id=request.transaction_id,
        status="LOCK_GRANTED" if result.get("status") == "LOCK_GRANTED" else "LOCK_DENIED",
        lock_expires_at_ms=result.get("lock_expires_at_ms"), reason=result.get("reason"),
        lock_token=result.get("lock_token"), payload_digest=result.get("payload_digest"),
        operation_state=result.get("operation_state"))


def _dispatch_claimed(request: CommitRequest, readiness: dict) -> CommitResponse:
    status = readiness.get("status", "REJECTED")
    if status in {"ALREADY_COMMITTED", "TIMEOUT", "IN_PROGRESS", "UNKNOWN", "EXECUTION_FAILED"}:
        return _commit_response(request.transaction_id, readiness)
    if status != "READY":
        raise HTTPException(status_code=409, detail=readiness.get("reason", "Commit rejected"))
    claim_token = readiness.get("claim_token")
    try:
        executor = ExecutorManager.get_executor(request.asset_id)
        result = executor.execute(transaction_id=request.transaction_id, asset_id=request.asset_id,
                                  action_sequence=request.action_sequence)
        receipt = _executor_receipt(executor, result, request)
    except Exception as exc:
        # Failure after a dispatch claim can mean a lost ACK after acceptance.
        unknown = _state_machine.mark_unknown(request.transaction_id, request.asset_id,
                                              f"EXECUTION_OUTCOME_UNKNOWN: {exc}", claim_token=claim_token)
        safe = _execute_safe_state(request.asset_id)
        _state_machine.record_safe_state(request.transaction_id, safe)
        return _commit_response(request.transaction_id, {**unknown, "status":"UNKNOWN"},
                                safe_state_executed=safe)
    if receipt["status"] not in {"ACCEPTED", "COMPLETED", "FAILED", "REJECTED"}:
        unknown = _state_machine.mark_unknown(request.transaction_id, request.asset_id,
                                              receipt.get("reason") or "Executor outcome is unknown", claim_token=claim_token)
        return _commit_response(request.transaction_id, {**unknown, "status":"UNKNOWN"})
    if receipt["status"] in {"FAILED", "REJECTED"}:
        failure = _state_machine.finalize_failure(request.transaction_id, request.asset_id,
                                                  claim_token=claim_token, executor_receipt=receipt)
        if failure.get("status") == "UNKNOWN":
            return _commit_response(request.transaction_id, failure)
        # This is an explicit failure report. Partial effects remain possible;
        # ABORTED bookkeeping is not evidence that no dispatch ever occurred.
        _state_machine.abort(request.transaction_id, request.asset_id)
        safe = _execute_safe_state(request.asset_id)
        _state_machine.record_safe_state(request.transaction_id, safe)
        return _commit_response(request.transaction_id, {"status":"EXECUTION_FAILED",
            "reason":receipt.get("reason"), "safe_state_executed":safe,
            "operation_state":"FAILED", "effects_may_have_occurred":True,
            "ack_boundary":receipt.get("ack_boundary"), "receipt":receipt,
            "dispatch_count":readiness.get("dispatch_count")})
    finalize_kwargs = {"transaction_id":request.transaction_id, "asset_id":request.asset_id}
    if claim_token is not None:
        finalize_kwargs.update(claim_token=claim_token, executor_receipt=receipt)
    finalized = _state_machine.finalize_commit(**finalize_kwargs)
    if finalized.get("status") not in {"COMMITTED", "ALREADY_COMMITTED"}:
        unknown = _state_machine.mark_unknown(request.transaction_id, request.asset_id,
                                              finalized.get("reason") or "Receipt persistence is unresolved", claim_token=claim_token)
        return _commit_response(request.transaction_id, {**unknown, "status":"UNKNOWN"})
    # executed_at_ms is a retained legacy ACK timestamp. Completion is explicit.
    return _commit_response(request.transaction_id, {**receipt, **finalized},
                            executed_at_ms=receipt.get("completed_at_ms") or receipt.get("accepted_at_ms") or int(time.time()*1000))


@router.post("/commit")
def commit(request: CommitRequest):
    readiness = _state_machine.check_commit_ready(
        transaction_id=request.transaction_id, asset_id=request.asset_id,
        action_sequence=request.action_sequence, lock_token=request.lock_token)
    return _dispatch_claimed(request, readiness)


@router.get("/operations/{transaction_id}")
def operation_status(transaction_id: str):
    result = _state_machine.get_operation_status(transaction_id)
    if result.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result.get("reason"))
    return result


@router.post("/reconcile")
def reconcile(request: ReconcileRequest):
    stored = _state_machine.get_operation_status(request.transaction_id)
    if stored.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=stored.get("reason"))
    if stored.get("asset_id") != request.asset_id:
        raise HTTPException(status_code=409, detail="ASSET_MISMATCH")
    if stored.get("operation_state") in {"COMPLETED", "FAILED", "ABORTED", "PREPARED"}:
        return stored
    try:
        executor = ExecutorManager.get_executor(request.asset_id)
        query = getattr(executor, "query_operation", None)
        receipt = query(transaction_id=request.transaction_id, asset_id=request.asset_id) if callable(query) else None
    except Exception as exc:
        return _state_machine.mark_unknown(request.transaction_id, request.asset_id, f"Executor query failed: {exc}")
    return _state_machine.reconcile(request.transaction_id, request.asset_id, receipt)


@router.post("/abort")
def abort(request: AbortRequest):
    result = _state_machine.abort(transaction_id=request.transaction_id, asset_id=request.asset_id)
    status = result.get("status", "ABORT_REJECTED")
    safe = _execute_safe_state(request.asset_id) if status in {"ABORTED", "ALREADY_ABORTED"} else False
    return AbortResponse(transaction_id=request.transaction_id, status=status,
                         safe_state_executed=safe, reason=result.get("reason"))


@router.post("/estop")
def estop(request: EstopRequest):
    try:
        _state_machine.estop(asset_id=request.asset_id)
    except Exception as exc:
        logger.error("E-Stop bookkeeping failed: %s", exc)
    _execute_safe_state(request.asset_id)
    return EstopResponse(asset_id=request.asset_id, status="ESTOP_EXECUTED", timestamp_ms=int(time.time()*1000))


def _require_revision_mode():
    if os.environ.get("PCAG_REVISION_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Revision controls are disabled")


@router.get("/revision/state", dependencies=[Depends(_require_revision_mode), Depends(verify_api_key)])
def revision_state(asset_id: str | None = None):
    return _state_machine.revision_state(asset_id)


@router.post("/revision/reset", dependencies=[Depends(_require_revision_mode), Depends(verify_api_key)])
def revision_reset(request: RevisionResetRequest):
    result = _state_machine.reset_prepared_asset(request.asset_id, request.reason)
    if result.get("status") != "RESET":
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/revision/direct-execute", dependencies=[Depends(_require_revision_mode), Depends(verify_api_key)])
def revision_direct_execute(request: CommitRequest):
    # Admission/asset reservations are bypassed; durable execution identity and
    # payload binding are common to all revision comparators, explicitly.
    return _dispatch_claimed(request, _state_machine.claim_direct(
        request.transaction_id, request.asset_id, request.action_sequence))
