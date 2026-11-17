"""Durable command ownership and executor observations, revision schema v2.

A committed database claim suppresses concurrent duplicate OT dispatches.
This is not a proof of exactly-once physical actuation. Uncertain dispatches
remain quarantined until an executor status query resolves them.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Callable

from sqlalchemy import select

from pcag.apps.ot_interface.repository import TxRepository
from pcag.core.database.engine import SessionLocal
from pcag.core.database.models import OperationReceiptRecord, TransactionRecord

logger = logging.getLogger(__name__)
UNCERTAIN_STATES = {"DISPATCHING", "UNKNOWN", "RECONCILING"}
SUCCESS_STATES = {"ACCEPTED", "COMPLETED"}


def compute_operation_digest(asset_id: str, action_sequence: list[dict]) -> str:
    """Bind exact JSON command values; never round action floats as sensor hashes do."""
    payload = json.dumps({"asset_id": asset_id, "action_sequence": action_sequence},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PersistentTxStateMachine:
    def __init__(self, session_factory=None, time_provider: Callable[[], int] | None = None):
        self._session_factory = session_factory
        self._time_provider = time_provider

    def _session(self):
        return (self._session_factory or SessionLocal)()

    def _get_time(self) -> int:
        return int(self._time_provider()) if self._time_provider else int(time.time() * 1000)

    @staticmethod
    def _snapshot(op, *, status: str | None = None, replayed: bool = False):
        receipt = dict(op.receipt or {})
        commit_status = {"PREPARED":"READY", "DISPATCHING":"IN_PROGRESS", "UNKNOWN":"UNKNOWN",
                         "RECONCILING":"UNKNOWN", "ACCEPTED":"ALREADY_COMMITTED",
                         "COMPLETED":"ALREADY_COMMITTED", "FAILED":"EXECUTION_FAILED", "ABORTED":"REJECTED"}[op.state]
        return {"transaction_id":op.transaction_id, "asset_id":op.asset_id,
                "status":status or commit_status, "operation_state":op.state,
                "payload_digest":op.payload_digest, "lock_token":op.fencing_token,
                "dispatch_count":op.dispatch_count, "accepted_at_ms":op.accepted_at_ms,
                "completed_at_ms":op.completed_at_ms, "ack_boundary":op.ack_boundary,
                "accepted":receipt.get("accepted"), "completed":op.state == "COMPLETED",
                "execution_confirmed":receipt.get("execution_confirmed", False),
                "effects_may_have_occurred":op.dispatch_count > 0,
                "receipt":receipt, "reason":op.reason, "replayed":replayed}

    def prepare(self, transaction_id: str, asset_id: str, lock_ttl_ms: int,
                action_sequence: list[dict] | None = None, payload_digest: str | None = None) -> dict:
        session = self._session()
        try:
            if lock_ttl_ms <= 0:
                raise ValueError("lock_ttl_ms must be positive")
            digest = compute_operation_digest(asset_id, action_sequence) if action_sequence is not None else None
            if payload_digest is not None:
                payload_digest = payload_digest.lower()
                if len(payload_digest) != 64 or any(c not in "0123456789abcdef" for c in payload_digest):
                    raise ValueError("Invalid payload digest")
                if digest is not None and digest != payload_digest:
                    return {"status":"PREPARE_REJECTED", "reason":"PAYLOAD_DIGEST_MISMATCH"}
                digest = payload_digest
            now, repo = self._get_time(), TxRepository(session)
            legacy = repo.get_transaction(transaction_id)
            if legacy and legacy.asset_id != asset_id:
                return {"status":"PREPARE_REJECTED", "reason":"ASSET_MISMATCH"}
            op = repo.ensure_operation(transaction_id, asset_id, now, digest, action_sequence)
            if op.asset_id != asset_id:
                session.rollback()
                return {"status":"PREPARE_REJECTED", "reason":"ASSET_MISMATCH"}
            if op.payload_digest is not None and digest is not None and op.payload_digest != digest:
                session.rollback()
                return {"status":"PREPARE_REJECTED", "reason":"PAYLOAD_CONFLICT"}
            if op.state != "PREPARED":
                result = {**self._snapshot(op, replayed=True), "status":"PREPARE_REJECTED",
                          "reason":f"Operation already {op.state}"}
                session.rollback()
                return result
            if legacy and legacy.status != "LOCKED":
                session.rollback()
                return {"status":"PREPARE_REJECTED", "reason":f"Legacy transaction already {legacy.status}"}
            old_lock = repo.get_active_lock(asset_id, now)
            if old_lock and old_lock.transaction_id != transaction_id and repo.get_asset_slot(asset_id) is None:
                reason = f"Legacy asset lock owned by {old_lock.transaction_id}"
                session.rollback()
                return {"status":"LOCK_DENIED", "reason":reason}
            slot = repo.reserve_asset(asset_id, transaction_id, now, now + lock_ttl_ms)
            if slot is None:
                blocker = repo.get_asset_slot(asset_id)
                reason = f"Asset reserved by {blocker.transaction_id} ({blocker.phase})" if blocker else "Asset ownership denied"
                session.rollback()
                return {"status":"LOCK_DENIED", "reason":reason}
            values = {"fencing_token":slot.fencing_token, "updated_at_ms":now}
            if digest is not None:
                values["payload_digest"] = digest
            if action_sequence is not None:
                values["action_sequence"] = action_sequence
            repo.transition_operation(transaction_id, ["PREPARED"], values)
            if legacy is None:
                repo.create_lock(transaction_id, asset_id, now + lock_ttl_ms)
            else:
                repo.extend_lock(transaction_id, now + lock_ttl_ms)
            session.commit()
            return {**self._snapshot(repo.get_operation(transaction_id), status="LOCK_GRANTED"),
                    "lock_expires_at_ms":now + lock_ttl_ms}
        except Exception as exc:
            session.rollback()
            logger.error("PREPARE failed closed: %s", exc)
            return {"status":"PREPARE_REJECTED", "reason":str(exc)}
        finally:
            session.close()

    def check_commit_ready(self, transaction_id: str, asset_id: str,
                           action_sequence: list[dict] | None = None, lock_token: int | None = None) -> dict:
        """A supplied command atomically claims dispatch; the legacy shape only inspects."""
        if action_sequence is not None:
            return self.claim_commit(transaction_id, asset_id, action_sequence, lock_token=lock_token)
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id)
            if op is None:
                return {"status":"REJECTED", "reason":"Operation receipt not found"}
            if op.asset_id != asset_id:
                return {"status":"REJECTED", "reason":"ASSET_MISMATCH"}
            if op.state != "PREPARED":
                return self._snapshot(op, replayed=True)
            slot = repo.get_asset_slot(asset_id)
            if not slot or slot.transaction_id != transaction_id or slot.fencing_token != op.fencing_token or (slot.lease_expires_at_ms or 0) <= self._get_time():
                return {"status":"TIMEOUT", "reason":"Reservation expired or fenced out"}
            return {**self._snapshot(op), "read_only":True}
        finally:
            session.close()

    def claim_commit(self, transaction_id: str, asset_id: str, action_sequence: list[dict],
                     *, lock_token: int | None = None) -> dict:
        return self._claim(transaction_id, asset_id, action_sequence, direct=False, lock_token=lock_token)

    def claim_direct(self, transaction_id: str, asset_id: str, action_sequence: list[dict]) -> dict:
        """Revision ablation: bypass asset admission, retain common durable identity guard."""
        return self._claim(transaction_id, asset_id, action_sequence, direct=True)

    def _claim(self, transaction_id, asset_id, action_sequence, *, direct, lock_token=None):
        session = self._session()
        try:
            digest, repo, now = compute_operation_digest(asset_id, action_sequence), TxRepository(session), self._get_time()
            if direct:
                legacy = repo.get_transaction(transaction_id)
                if legacy and repo.get_operation(transaction_id) is None:
                    return {"status":"REJECTED", "reason":"Legacy operation has no payload-bound receipt"}
                op = repo.ensure_operation(transaction_id, asset_id, now, digest, action_sequence)
            else:
                op = repo.get_operation(transaction_id, for_update=True)
            if op is None:
                return {"status":"REJECTED", "reason":"Operation receipt not found; PREPARE required"}
            if op.asset_id != asset_id:
                return {"status":"REJECTED", "reason":"ASSET_MISMATCH"}
            if op.payload_digest is not None and op.payload_digest != digest:
                return {"status":"REJECTED", "reason":"PAYLOAD_CONFLICT", "operation_state":op.state}
            if lock_token is not None and lock_token != op.fencing_token:
                return {"status":"REJECTED", "reason":"STALE_FENCING_TOKEN"}
            if op.state != "PREPARED":
                return self._snapshot(op, replayed=True)
            if direct and op.fencing_token != 0:
                return {"status":"REJECTED", "reason":"Prepared operation cannot change to direct mode"}
            claim = uuid.uuid4().hex
            changed = repo.transition_operation(transaction_id, ["PREPARED"], {
                "state":"DISPATCHING", "payload_digest":digest, "action_sequence":action_sequence,
                "claim_token":claim, "dispatch_count":OperationReceiptRecord.dispatch_count + 1,
                "dispatched_at_ms":now, "updated_at_ms":now,
            })
            if changed != 1 or (not direct and not repo.claim_asset_dispatch(asset_id, transaction_id, op.fencing_token, now)):
                session.rollback()
                return {"status":"TIMEOUT", "reason":"Reservation expired or fenced out"}
            if direct and repo.get_transaction(transaction_id) is None:
                repo.create_lock(transaction_id, asset_id, now)
            repo.update_status(transaction_id, "DISPATCHING")
            session.commit()
            result = self._snapshot(repo.get_operation(transaction_id), status="READY")
            result["claim_token"] = claim
            return result
        except Exception as exc:
            session.rollback()
            logger.error("COMMIT claim failed closed: %s", exc)
            return {"status":"REJECTED", "reason":str(exc)}
        finally:
            session.close()

    def _finish(self, transaction_id: str, asset_id: str, receipt: dict,
                *, claim_token: str | None, reconcile: bool, success: bool) -> dict:
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id, for_update=True)
            if op is None or op.asset_id != asset_id:
                return {"status":"REJECTED", "reason":"Operation not found or asset mismatch"}
            if receipt.get("payload_digest") is not None and receipt["payload_digest"] != op.payload_digest:
                return {"status":"UNKNOWN", "reason":"EXECUTOR_PAYLOAD_CONFLICT", "operation_state":op.state}
            for key, expected in [("transaction_id", transaction_id), ("asset_id", asset_id)]:
                if receipt.get(key) is not None and receipt[key] != expected:
                    return {"status":"UNKNOWN", "reason":"EXECUTOR_IDENTITY_CONFLICT", "operation_state":op.state}
            if op.state in {"COMPLETED", "FAILED", "ABORTED"} or (op.state == "ACCEPTED" and not reconcile):
                return self._snapshot(op, replayed=True)
            if op.state not in UNCERTAIN_STATES | ({"ACCEPTED"} if reconcile else set()):
                return {"status":"REJECTED", "reason":"No dispatch claim"}
            if not reconcile and (claim_token is None or claim_token != op.claim_token):
                return {"status":"REJECTED", "reason":"DISPATCH_CLAIM_REQUIRED"}
            receipt_status = str(receipt.get("status", "UNKNOWN")).upper()
            if success and (receipt_status not in {"ACCEPTED", "COMPLETED"}
                            or receipt.get("accepted") is False
                            or (receipt_status == "COMPLETED" and receipt.get("completed") is False)):
                return {"status":"UNKNOWN", "reason":"CONTRADICTORY_EXECUTOR_RECEIPT", "operation_state":op.state}
            now = self._get_time()
            completed = receipt.get("completed") is True or receipt_status == "COMPLETED"
            state = ("COMPLETED" if completed else "ACCEPTED") if success else "FAILED"
            stored = {**dict(op.receipt or {}), **receipt, "transaction_id":transaction_id,
                      "asset_id":asset_id, "payload_digest":op.payload_digest}
            accepted_at = receipt.get("accepted_at_ms") or op.accepted_at_ms or (now if success else None)
            completed_at = receipt.get("completed_at_ms") or (now if success and completed else None)
            changed = repo.transition_operation(transaction_id, [op.state], {
                "state":state, "receipt":stored, "ack_boundary":receipt.get("ack_boundary", "executor_report"),
                "accepted_at_ms":accepted_at, "completed_at_ms":completed_at,
                "reason":receipt.get("reason"), "updated_at_ms":now,
            }, claim_token=None if reconcile else claim_token)
            if changed != 1:
                session.rollback()
                return {"status":"UNKNOWN", "reason":"Receipt state changed concurrently"}
            repo.update_status(transaction_id, "COMMITTED" if success else "ABORTED", clear_lock=True)
            repo.release_asset(asset_id, transaction_id, op.fencing_token, now)
            session.commit()
            return self._snapshot(repo.get_operation(transaction_id), status="COMMITTED" if success else "EXECUTION_FAILED")
        except Exception as exc:
            session.rollback()
            logger.error("Receipt persistence failed; outcome is not confirmed: %s", exc)
            return {"status":"UNKNOWN", "operation_state":"UNKNOWN", "reason":f"RECEIPT_PERSIST_FAILED: {exc}"}
        finally:
            session.close()

    def finalize_commit(self, transaction_id: str, asset_id: str, *, claim_token: str | None = None,
                        executor_receipt: dict | None = None) -> dict:
        return self._finish(transaction_id, asset_id, executor_receipt or {
            "status":"ACCEPTED", "accepted":True, "completed":False,
            "execution_confirmed":False, "ack_boundary":"legacy_executor_ack",
        }, claim_token=claim_token, reconcile=False, success=True)

    def finalize_failure(self, transaction_id: str, asset_id: str, *, claim_token: str | None,
                         executor_receipt: dict | None = None, reason: str = "Executor reported failure") -> dict:
        return self._finish(transaction_id, asset_id, executor_receipt or {
            "status":"FAILED", "completed":False, "reason":reason,
            "effects_may_have_occurred":True, "ack_boundary":"executor_failure_report",
        }, claim_token=claim_token, reconcile=False, success=False)

    def mark_unknown(self, transaction_id: str, asset_id: str, reason: str,
                     *, claim_token: str | None = None) -> dict:
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id, for_update=True)
            if op is None or op.asset_id != asset_id:
                return {"status":"REJECTED", "reason":"Operation not found or asset mismatch"}
            if op.state not in UNCERTAIN_STATES:
                return self._snapshot(op, replayed=True)
            if claim_token is not None and claim_token != op.claim_token:
                return {"status":"REJECTED", "reason":"DISPATCH_CLAIM_REQUIRED"}
            now = self._get_time()
            changed = repo.transition_operation(transaction_id, list(UNCERTAIN_STATES), {
                "state":"UNKNOWN", "reason":reason, "updated_at_ms":now,
            }, claim_token=claim_token)
            if changed != 1:
                # A receipt may have finalized after our read on a backend
                # without row locks. Do not overwrite its legacy status or
                # quarantine/release a newer asset owner after a failed CAS.
                session.rollback()
                latest = repo.get_operation(transaction_id)
                return self._snapshot(latest, replayed=True) if latest else {"status":"UNKNOWN", "reason":"Operation disappeared during reconciliation"}
            repo.quarantine_asset(asset_id, transaction_id, op.fencing_token, now)
            repo.update_status(transaction_id, "UNKNOWN")
            session.commit()
            return self._snapshot(repo.get_operation(transaction_id), status="UNKNOWN")
        except Exception as exc:
            session.rollback()
            return {"status":"UNKNOWN", "reason":f"Unknown-outcome persistence failed: {exc}"}
        finally:
            session.close()

    def reconcile(self, transaction_id: str, asset_id: str, executor_receipt: dict | None) -> dict:
        """Persist a queried executor fact; never authorize another dispatch."""
        if not isinstance(executor_receipt, dict):
            return self.mark_unknown(transaction_id, asset_id, "Executor has no queryable receipt")
        outcome = str(executor_receipt.get("status", "UNKNOWN")).upper()
        if outcome in {"ACCEPTED", "COMPLETED"}:
            return self._finish(transaction_id, asset_id, executor_receipt, claim_token=None, reconcile=True, success=True)
        if outcome in {"FAILED", "REJECTED"} or (outcome == "NOT_ACCEPTED" and executor_receipt.get("definitive") is True):
            return self._finish(transaction_id, asset_id, executor_receipt, claim_token=None, reconcile=True, success=False)
        # NOT_FOUND may be eventual consistency or a request still in transit.
        return self.mark_unknown(transaction_id, asset_id, f"Executor outcome remains {outcome}")

    def record_safe_state(self, transaction_id: str, safe_state_executed: bool) -> None:
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id, for_update=True)
            if op:
                receipt = {**dict(op.receipt or {}), "safe_state_executed":bool(safe_state_executed)}
                repo.transition_operation(transaction_id, [op.state], {"receipt":receipt, "updated_at_ms":self._get_time()})
                session.commit()
        finally:
            session.close()

    def get_operation_status(self, transaction_id: str) -> dict:
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id)
            if op is None:
                legacy = repo.get_transaction(transaction_id)
                return {"status":"NOT_FOUND", "transaction_id":transaction_id,
                        "reason":"Legacy transaction has no revision receipt" if legacy else "Operation not found"}
            return self._snapshot(op, status=op.state)
        finally:
            session.close()

    def abort(self, transaction_id: str, asset_id: str) -> dict:
        session = self._session()
        try:
            repo = TxRepository(session)
            op = repo.get_operation(transaction_id, for_update=True)
            if op is None:
                legacy = repo.get_transaction(transaction_id)
                if legacy is None or legacy.asset_id != asset_id:
                    return {"status":"ABORT_REJECTED", "reason":"Operation not found or asset mismatch"}
                if legacy.status == "ABORTED":
                    return {"status":"ALREADY_ABORTED"}
                if legacy.status != "LOCKED":
                    return {"status":"ABORT_REJECTED", "reason":"Legacy outcome cannot be aborted"}
                repo.update_status(transaction_id, "ABORTED", clear_lock=True)
                session.commit()
                return {"status":"ABORTED", "reason":"Legacy reservation explicitly aborted"}
            if op.asset_id != asset_id:
                return {"status":"ABORT_REJECTED", "reason":"ASSET_MISMATCH"}
            if op.state in {"ABORTED", "FAILED"}:
                return {**self._snapshot(op), "status":"ALREADY_ABORTED"}
            if op.state != "PREPARED":
                return {**self._snapshot(op), "status":"ABORT_REJECTED",
                        "reason":"Dispatch may have occurred; query/reconcile the executor instead"}
            now = self._get_time()
            if repo.transition_operation(transaction_id, ["PREPARED"], {"state":"ABORTED", "updated_at_ms":now}) != 1:
                session.rollback()
                return {"status":"ABORT_REJECTED", "reason":"Dispatch raced with abort"}
            repo.update_status(transaction_id, "ABORTED", clear_lock=True)
            repo.release_asset(asset_id, transaction_id, op.fencing_token, now)
            session.commit()
            return {"status":"ABORTED", "operation_state":"ABORTED"}
        except Exception as exc:
            session.rollback()
            return {"status":"ABORT_REJECTED", "reason":str(exc)}
        finally:
            session.close()

    def estop(self, asset_id: str) -> dict:
        # The route attempts safe-state dispatch even if this bookkeeping fails.
        state = self.revision_state(asset_id)
        for op in state["operations"]:
            if op["operation_state"] == "PREPARED":
                self.abort(op["transaction_id"], asset_id)
            elif op["operation_state"] in UNCERTAIN_STATES:
                self.mark_unknown(op["transaction_id"], asset_id, "E-Stop requested while dispatch outcome was unresolved")
        return {"status":"ESTOP_EXECUTED"}

    def revision_state(self, asset_id: str | None = None) -> dict:
        """Bounded observation of active ownership, never a receipt-history dump.

        Complete aggregate counts determine cleanliness. Lists are explicitly
        truncated witnesses and cannot be interpreted as the whole journal.
        Terminal receipts, actions and raw simulator traces remain in storage.
        """
        from sqlalchemy import case, func, or_
        from pcag.core.database.models import AssetExecutionLockRecord

        session = self._session()
        try:
            # All queries in this observation share a PostgreSQL snapshot.
            if session.get_bind().dialect.name == "postgresql":
                session.connection(execution_options={"isolation_level":"REPEATABLE READ"})
            limit = 100
            active_states = UNCERTAIN_STATES | {"PREPARED", "ACCEPTED"}
            op_scope = [OperationReceiptRecord.asset_id == asset_id] if asset_id is not None else []
            counts = dict(session.execute(select(OperationReceiptRecord.state, func.count())
                .where(*op_scope).group_by(OperationReceiptRecord.state)).all())
            active_count = sum(counts.get(state, 0) for state in active_states)
            op_columns = [OperationReceiptRecord.transaction_id, OperationReceiptRecord.asset_id,
                OperationReceiptRecord.state, OperationReceiptRecord.payload_digest,
                OperationReceiptRecord.fencing_token, OperationReceiptRecord.dispatch_count,
                OperationReceiptRecord.created_at_ms, OperationReceiptRecord.updated_at_ms,
                OperationReceiptRecord.dispatched_at_ms, OperationReceiptRecord.accepted_at_ms,
                OperationReceiptRecord.completed_at_ms, OperationReceiptRecord.ack_boundary]
            # Explicit columns exclude receipt/action JSON and arbitrarily large
            # reason strings. Only ownership/observation metadata enters witness.
            rows = session.execute(select(*op_columns).where(*op_scope,
                OperationReceiptRecord.state.in_(active_states)).order_by(
                OperationReceiptRecord.updated_at_ms, OperationReceiptRecord.transaction_id).limit(limit+1)).mappings().all()
            operations = [{"transaction_id":row["transaction_id"], "asset_id":row["asset_id"],
                "status":row["state"], "operation_state":row["state"],
                "payload_digest":row["payload_digest"], "lock_token":row["fencing_token"],
                "dispatch_count":row["dispatch_count"], "created_at_ms":row["created_at_ms"],
                "updated_at_ms":row["updated_at_ms"], "dispatched_at_ms":row["dispatched_at_ms"],
                "accepted_at_ms":row["accepted_at_ms"], "completed_at_ms":row["completed_at_ms"],
                "ack_boundary":row["ack_boundary"], "effects_may_have_occurred":row["dispatch_count"] > 0}
                for row in rows[:limit]]

            lock_scope = [AssetExecutionLockRecord.asset_id == asset_id] if asset_id is not None else []
            unresolved_lock = or_(AssetExecutionLockRecord.phase != "FREE",
                                  AssetExecutionLockRecord.transaction_id.is_not(None))
            lock_count = session.execute(select(func.count()).select_from(AssetExecutionLockRecord)
                .where(*lock_scope)).scalar_one()
            unresolved_lock_count = session.execute(select(func.count()).select_from(AssetExecutionLockRecord)
                .where(*lock_scope, unresolved_lock)).scalar_one()
            lock_rows = session.execute(select(AssetExecutionLockRecord.asset_id,
                AssetExecutionLockRecord.transaction_id, AssetExecutionLockRecord.phase,
                AssetExecutionLockRecord.fencing_token, AssetExecutionLockRecord.lease_expires_at_ms)
                .where(*lock_scope).order_by(case((unresolved_lock, 0), else_=1),
                    AssetExecutionLockRecord.asset_id).limit(limit+1)).mappings().all()
            slots = [{"asset_id":row["asset_id"], "transaction_id":row["transaction_id"],
                "phase":row["phase"], "lock_token":row["fencing_token"],
                "lease_expires_at_ms":row["lease_expires_at_ms"]} for row in lock_rows[:limit]]

            # A LOCKED legacy row without an operation receipt is still active.
            # Do not double count the compatibility row of a prepared v2 op.
            legacy_scope = [TransactionRecord.status == "LOCKED", ~select(
                OperationReceiptRecord.transaction_id).where(
                    OperationReceiptRecord.transaction_id == TransactionRecord.transaction_id).exists()]
            if asset_id is not None:
                legacy_scope.append(TransactionRecord.asset_id == asset_id)
            legacy_count = session.execute(select(func.count()).select_from(TransactionRecord)
                .where(*legacy_scope)).scalar_one()
            legacy_rows = session.execute(select(TransactionRecord.transaction_id, TransactionRecord.asset_id,
                TransactionRecord.status, TransactionRecord.lock_expires_at_ms).where(*legacy_scope)
                .order_by(TransactionRecord.transaction_id).limit(limit+1)).mappings().all()
            legacy = [dict(row) for row in legacy_rows[:limit]]

            # Conservative list checks also protect readers on SQLite's legacy
            # transaction mode if a concurrent row appears between SELECTs.
            active_count = max(active_count, len(operations))
            legacy_count = max(legacy_count, len(legacy))
            unresolved_lock_count = max(unresolved_lock_count,
                sum(slot["phase"] != "FREE" or slot["transaction_id"] is not None for slot in slots))
            truncated = {"operations":len(rows)>limit, "asset_locks":len(lock_rows)>limit,
                         "legacy_locks":len(legacy_rows)>limit}
            result = {"schema_version":3, "observed_at_ms":self._get_time(),
                "observation_scope":{"asset_id":asset_id, "selection":"exact_asset" if asset_id is not None else "all_assets",
                    "counts_cover":"all matching operation/legacy-lock rows", "operations_list":"active metadata only",
                    "list_limit":limit, "terminal_history_included":False, "receipt_or_action_payloads_included":False,
                    "clean_basis":"complete aggregate counts plus conservative observed-list checks",
                    "witness_hash_scope":"this bounded observation including complete aggregate counts; not a hash of historical receipts"},
                "total_operations":sum(counts.values()), "counts_by_operation_state":counts,
                "active_operation_count":active_count, "legacy_locked_count":legacy_count,
                "active_operations":active_count+legacy_count, "total_asset_locks":lock_count,
                "unresolved_asset_lock_count":unresolved_lock_count,
                "operations":operations, "asset_locks":slots, "legacy_locks":legacy,
                "has_more":any(truncated.values()), "truncated":truncated,
                "clean":active_count == 0 and legacy_count == 0 and unresolved_lock_count == 0}
            result["witness_sha256"] = hashlib.sha256(json.dumps(result, ensure_ascii=False,
                sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
            return result
        finally:
            session.close()

    def reset_prepared_asset(self, asset_id: str, reason: str) -> dict:
        """Revision-only explicit cleanup. It never clears unresolved dispatches."""
        session = self._session()
        try:
            repo = TxRepository(session)
            operations = session.execute(select(OperationReceiptRecord.transaction_id,
                OperationReceiptRecord.state, OperationReceiptRecord.fencing_token).where(
                OperationReceiptRecord.asset_id == asset_id,
                OperationReceiptRecord.state.in_(UNCERTAIN_STATES | {"PREPARED", "ACCEPTED"}))).all()
            blockers = [o for o in operations if o.state in UNCERTAIN_STATES | {"ACCEPTED"}]
            if blockers:
                return {"status":"RESET_REJECTED", "asset_id":asset_id,
                        "reason":"Unresolved or accepted-but-incomplete operations must be reconciled",
                        "blocking_operations":[o.transaction_id for o in blockers]}
            now, aborted = self._get_time(), []
            for op in operations:
                if op.state != "PREPARED":
                    continue
                if repo.transition_operation(op.transaction_id, ["PREPARED"], {
                    "state":"ABORTED", "reason":f"Explicit revision cleanup: {reason}", "updated_at_ms":now,
                }) != 1:
                    session.rollback()
                    return {"status":"RESET_REJECTED", "reason":"Dispatch raced with cleanup", "asset_id":asset_id}
                repo.update_status(op.transaction_id, "ABORTED", clear_lock=True)
                repo.release_asset(asset_id, op.transaction_id, op.fencing_token, now)
                aborted.append(op.transaction_id)
            legacy = session.execute(select(TransactionRecord).where(
                TransactionRecord.asset_id == asset_id, TransactionRecord.status == "LOCKED",
            )).scalars().all()
            for tx in legacy:
                if repo.get_operation(tx.transaction_id) is None:
                    repo.update_status(tx.transaction_id, "ABORTED", clear_lock=True)
                    aborted.append(tx.transaction_id)
            session.commit()
            return {"status":"RESET", "asset_id":asset_id, "aborted_operations":aborted, "reason":reason}
        except Exception as exc:
            session.rollback()
            return {"status":"RESET_REJECTED", "asset_id":asset_id, "reason":str(exc)}
        finally:
            session.close()
