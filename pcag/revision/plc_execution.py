"""Revision PLC dispatch receipts around actual Modbus TCP writes.

Completion refers to receiving every write response from ModRSsim, not a
manufacturing process finishing. Lost responses remain UNKNOWN; readback of the
same value is never treated as proof of one execution.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from pcag.apps.plc_adapter.service import CommandEncodingRejected, PlcAdapterService
from pcag.revision.durable_json import publish_durable_json

_lock = threading.Lock()


def _path(tx):
    base = Path(os.environ["PCAG_REVISION_PLC_RECEIPT_DIR"])
    base.mkdir(parents=True, exist_ok=True)
    return base / (hashlib.sha256(tx.encode()).hexdigest() + ".json")


def _save(path, value):
    publish_durable_json(path, value, ensure_ascii=True)


def query(tx, asset):
    path = _path(tx)
    if not path.exists():
        return {"status": "UNKNOWN", "accepted": False, "completed": False, "transaction_id": tx, "asset_id": asset, "ack_boundary": "no_durable_receipt"}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value["asset_id"] != asset:
        raise ValueError("Operation key asset mismatch")
    if value["status"] == "ACCEPTED":
        value = {**value, "status": "UNKNOWN"}
    return value


def execute(service, tx, asset, actions):
    payload = {"asset_id": asset, "action_sequence": actions}
    digest_scope = "exact_json_command"
    try:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except ValueError:
        # Nonstandard JSON NaN/Infinity can reach this Python entry point, but
        # never execute. Use a distinct rejection-only fingerprint, not the
        # valid-command digest domain used by OT dispatch claims.
        canonical = "pcag.nonstandard-json-rejection.v1\0" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True)
        digest_scope = "nonstandard_json_rejection_fingerprint"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with _lock:
        path = _path(tx)
        if path.exists():
            receipt = query(tx, asset)
            if receipt["payload_digest"] != digest:
                raise ValueError("Operation key payload mismatch")
            return receipt
        value = {"transaction_id":tx, "asset_id":asset, "payload_digest":digest,
                 "payload_digest_scope":digest_scope, "completed":False,
                 "physical_completion":"unobserved", "transport":"tcp",
                 "dispatch_count":0, "adapter_operation_count":0,
                 "dispatch_count_scope":"New accepted adapter operation, not TCP frames or physical effects; duplicate requests are excluded",
                 "write_call_intent_count":0, "write_call_returned_count":0, "write_ack_count":0,
                 "write_counter_scope":"Adapter Python write-helper boundaries: durable pre-call intent and observed helper returns/normal write responses; not wire-send or physical-effect counts",
                 "write_counter_persistence_scope":"Latest durable observations only. A crash can occur after intent but before the helper call, or after a returned response but before its journal update.",
                 "phase":"preflight"}
        try:
            prepare = getattr(service, "prepare_revision_plan", None)
            # Historical tests inject a minimal execute_actions model. It still
            # receives complete canonical mapping preflight, with its limited
            # execution observability stated explicitly in the receipt.
            plan = prepare(asset, actions) if callable(prepare) else PlcAdapterService().prepare_revision_plan(asset, actions)
            if digest_scope != "exact_json_command":
                raise CommandEncodingRejected("payload", "NaN/Infinity", "standard JSON with finite numeric values", "Nonstandard numeric JSON envelope")
        except CommandEncodingRejected as exc:
            value.update(status="REJECTED", accepted=False, definitive=True,
                         effects_may_have_occurred=False, reason="COMMAND_ENCODING_REJECTED",
                         reason_detail=str(exc), validation=exc.validation,
                         ack_boundary="pre_dispatch_transport_validation", phase="pre_dispatch_rejected")
            _save(path, value)
            return value
        value.update(status="ACCEPTED", accepted=True, accepted_at_ms=int(time.time()*1000),
                     dispatch_count=1, adapter_operation_count=1,
                     ack_boundary="modbus_tcp_write_response", phase="accepted_before_write_calls",
                     planned_write_count=len(plan["writes"]), validation=plan["validation"],
                     low_level_plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",", ":"),allow_nan=False).encode()).hexdigest())
        _save(path, value)
        try:
            execute_plan = getattr(service, "execute_revision_plan", None)
            if callable(execute_plan):
                def progress(observation):
                    value.update(observation)
                    _save(path, value)
                success, reason, connection_key = execute_plan(tx, asset, plan, progress)
            else:
                value.update(write_counter_scope="Legacy injected service model has no write-helper observations",
                             write_call_intent_count=None, write_call_returned_count=None, write_ack_count=None)
                success, reason, connection_key = service.execute_actions(tx, asset, actions)
            value.update(status="COMPLETED" if success else "UNKNOWN", completed=bool(success), reason=reason, connection_key=connection_key, completed_at_ms=int(time.time()*1000) if success else None)
            value.update(phase="all_write_responses_received" if success else "outcome_unknown",
                         effects_may_have_occurred=True)
            if connection_key.startswith("virtual:"):
                value.update(status="UNKNOWN", completed=False, reason="Revision TCP executor unexpectedly used memory register image", transport="memory")
        except Exception as exc:
            value.update(status="UNKNOWN", reason=str(exc), completed=False, phase="outcome_unknown", effects_may_have_occurred=True)
        _save(path, value)
        return value
