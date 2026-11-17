"""
Gateway Core의 주 실행 파이프라인.

이 모듈은 외부 에이전트가 보낸 제어 요청을 받아 아래 순서로 처리한다.

1. 스키마 적합성 확인
2. 정책/타임스탬프/센서 해시 기반 무결성 검증
3. Safety Cluster 다중 검증기 결과 수집
4. OT Interface와 2PC(PREPARE/REVERIFY/COMMIT) 수행
5. Evidence Ledger에 단계별 증거 이벤트 기록

즉, PCAG 전체의 "안전 실행 게이트" 역할을 하는 가장 핵심적인 엔트리포인트다.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from pcag.core.contracts.gateway import ControlRequest, ControlResponse
from pcag.core.middleware.auth import verify_api_key
from pcag.core.models.common import DivergenceThreshold
from pcag.core.services.alternative_action import generate_alternative_actions
from pcag.core.services.integrity_service import check_integrity
from pcag.core.utils.config_loader import get_service_urls, load_config
from pcag.core.utils.hash_utils import GENESIS_HASH, compute_event_hash, compute_sensor_hash

logger = logging.getLogger(__name__)

_config = load_config("services.yaml", required=True)
_services = _config.get("services", {})
_REQUIRED_SERVICES = ["policy_store", "sensor_gateway", "safety_cluster", "ot_interface", "evidence_ledger"]

for svc in _REQUIRED_SERVICES:
    if svc not in _services or not _services[svc].get("url"):
        raise RuntimeError(f"Required service '{svc}' URL is missing in services.yaml")

router = APIRouter(prefix="/v1", tags=["Gateway"])

# Revision comparators share this HTTP boundary and the same downstream
# executors. Disabled stages are never executed merely to discard their result.
_REVISION_PROFILES = {
    "B0": {"integrity": False, "validators": [], "prepare": False, "reverify": False},
    "B1": {"integrity": True, "validators": ["rules"], "prepare": False, "reverify": False},
    "B2": {"integrity": True, "validators": ["rules", "cbf"], "prepare": False, "reverify": False},
    "B3": {"integrity": True, "validators": ["rules", "simulation"], "prepare": False, "reverify": False},
    "E1": {"integrity": False, "validators": ["simulation"], "prepare": False, "reverify": False},
    "B4": {"integrity": True, "validators": ["rules", "cbf", "simulation"], "prepare": True, "reverify": False},
    "B5": {"integrity": True, "validators": ["rules", "cbf", "simulation"], "prepare": True, "reverify": True},
}


def _require_revision_mode() -> None:
    if os.environ.get("PCAG_REVISION_MODE", "false").lower() not in {"true", "1", "yes"}:
        raise HTTPException(status_code=403, detail="Revision controls are disabled")


def _revision_clean(state: dict) -> bool:
    if state.get("schema_version", 0) >= 3:
        # A bounded list can omit a blocking orphan lock. The complete counts
        # and explicit observation verdict must agree before declaring clean.
        if not (state.get("clean") is True
                and state.get("active_operation_count") == 0
                and state.get("legacy_locked_count") == 0
                and state.get("unresolved_asset_lock_count") == 0):
            return False
    return (state.get("active_operations") == 0
            and all(slot.get("phase") == "FREE" and slot.get("transaction_id") is None
                    for slot in state.get("asset_locks", [])))


@router.get("/revision/state", dependencies=[Depends(_require_revision_mode), Depends(verify_api_key)])
async def revision_state(asset_id: str | None = None, api_key: str = Depends(verify_api_key)):
    async with httpx.AsyncClient(timeout=30.0, headers={"X-API-Key": api_key}) as client:
        result = await client.get(f"{_get_service_url('ot_interface')}/v1/revision/state", params={"asset_id": asset_id} if asset_id else {})
        if result.status_code != 200:
            raise HTTPException(status_code=result.status_code, detail=result.text)
        state = result.json()
        return {**state, "revision_mode": True, "clean": _revision_clean(state)}


@router.post("/revision/reset", dependencies=[Depends(_require_revision_mode), Depends(verify_api_key)])
async def revision_reset(payload: dict, api_key: str = Depends(verify_api_key)):
    if not payload.get("asset_id") or not str(payload.get("reason", "")).strip():
        raise HTTPException(status_code=422, detail="asset_id and explicit cleanup reason are required")
    async with httpx.AsyncClient(timeout=30.0, headers={"X-API-Key": api_key}) as client:
        url = f"{_get_service_url('ot_interface')}/v1/revision"
        before_resp = await client.get(f"{url}/state", params={"asset_id": payload["asset_id"]})
        before_resp.raise_for_status()
        result = await client.post(f"{url}/reset", json=payload)
        if result.status_code != 200:
            raise HTTPException(status_code=result.status_code, detail=result.text)
        after_resp = await client.get(f"{url}/state", params={"asset_id": payload["asset_id"]})
        after_resp.raise_for_status()
        after = after_resp.json()
        return {"revision_mode": True, "before": before_resp.json(), "reset": result.json(),
                "after": {**after, "clean": _revision_clean(after)}, "clean": _revision_clean(after)}


def _get_service_url(service_name: str) -> str:
    urls = get_service_urls()
    url = urls.get(service_name)
    if not url:
        raise ValueError(f"Service URL for '{service_name}' not configured")
    return url


def _response(
    transaction_id: str,
    status: str,
    *,
    reason: str | None = None,
    reason_code: str | None = None,
    evidence_ref: str | None = None,
    alternative_actions: list[dict[str, Any]] | None = None,
) -> ControlResponse:
    # Gateway 응답은 단일 대체 행동과 후보 목록을 동시에 담을 수 있다.
    # 하위 호환을 위해 첫 번째 후보는 alternative_action에도 복제해 둔다.
    first_action = alternative_actions[0] if alternative_actions else None
    return ControlResponse(
        transaction_id=transaction_id,
        status=status,
        reason=reason,
        reason_code=reason_code,
        evidence_ref=evidence_ref,
        alternative_action=first_action,
        alternative_actions=alternative_actions or None,
    )


def _build_divergence_thresholds(raw_thresholds: list[dict] | None) -> list[DivergenceThreshold]:
    thresholds: list[DivergenceThreshold] = []
    for item in raw_thresholds or []:
        try:
            thresholds.append(DivergenceThreshold(**item))
        except Exception as exc:
            logger.warning("Ignoring invalid divergence threshold %s: %s", item, exc)
    return thresholds


def _extract_runtime_context(proof: dict[str, Any]) -> dict[str, Any] | None:
    runtime_context = proof.get("runtime_context")
    return runtime_context if isinstance(runtime_context, dict) else None


def _extract_fault_injection(proof: dict[str, Any]) -> dict[str, Any] | None:
    fault_injection = proof.get("fault_injection")
    return fault_injection if isinstance(fault_injection, dict) else None


def _fault_enabled(fault_injection: dict[str, Any] | None, fault_family: str) -> bool:
    if not fault_injection:
        return False
    return fault_injection.get("fault_family") == fault_family


def _force_hash_mismatch(sensor_hash: str) -> str:
    if len(sensor_hash) != 64:
        return "f" * 64
    last = sensor_hash[-1].lower()
    replacement = "0" if last != "0" else "1"
    return sensor_hash[:-1] + replacement


async def _fetch_asset_profile(client: httpx.AsyncClient, policy_version: str, asset_id: str) -> dict:
    resp = await client.get(f"{_get_service_url('policy_store')}/v1/policies/{policy_version}/assets/{asset_id}")
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception:
            detail = f"HTTP {resp.status_code}"
        raise RuntimeError(f"Policy Store asset profile error: {detail}")
    return resp.json().get("profile", {})


async def _abort_transaction(client: httpx.AsyncClient, tx_id: str, asset_id: str, reason: str) -> dict:
    resp = await client.post(
        f"{_get_service_url('ot_interface')}/v1/abort",
        json={"transaction_id": tx_id, "asset_id": asset_id, "reason": reason},
    )
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception:
            detail = f"HTTP {resp.status_code}"
        raise RuntimeError(f"OT abort failed: {detail}")
    payload = resp.json()
    if payload.get("status") not in {"ABORTED", "ALREADY_ABORTED"}:
        raise RuntimeError(payload.get("reason") or f"Unexpected OT abort status: {payload.get('status')}")
    return payload


async def _submit_revision_control_request(request: ControlRequest, api_key: str) -> ControlResponse:
    """Explicit experimental admission ablations; normal admission is unchanged.

    Execution identity, evidence writes and transport overhead are common to all
    profiles. Legacy synthetic failures remain tagged as such in the evidence.
    """
    _require_revision_mode()
    proof = request.proof_package.model_dump(exclude_none=True)
    profile_id = proof.get("revision_profile")
    if profile_id not in _REVISION_PROFILES:
        raise HTTPException(status_code=422, detail="Unknown revision_profile")
    profile = _REVISION_PROFILES[profile_id]
    test_control = proof.get("revision_test_control") or {}
    if not isinstance(test_control, dict):
        raise HTTPException(status_code=422, detail="revision_test_control must be an object")
    pause_ms = test_control.get("pause_after_prepare_ms", 0)
    if isinstance(pause_ms, bool) or not isinstance(pause_ms, int) or not 0 <= pause_ms <= 3000:
        raise HTTPException(status_code=422, detail="pause_after_prepare_ms must be an integer in 0..3000")
    tx_id, asset_id = request.transaction_id, request.asset_id
    actions = proof.get("action_sequence", [])
    fault = _extract_fault_injection(proof)
    runtime_context = _extract_runtime_context(proof)
    prepared = False
    dispatched = False
    seq, previous = 0, GENESIS_HASH
    async with httpx.AsyncClient(timeout=120.0, headers={"X-API-Key": api_key}) as client:
        async def emit(stage: str, payload: dict) -> None:
            nonlocal seq, previous
            previous = await _log_evidence(client, tx_id, seq, stage, payload, previous)
            seq += 1

        async def abort_reserved(reason: str) -> dict:
            nonlocal prepared
            result = await _abort_transaction(client, tx_id, asset_id, reason)
            prepared = False
            return result

        async def post_json(service: str, path: str, payload: dict) -> dict:
            response = await client.post(f"{_get_service_url(service)}{path}", json=payload)
            response.raise_for_status()
            return response.json()

        try:
            # A retry never restarts evidence at sequence zero or issues a new
            # physical command. Resolve an existing receipt explicitly first.
            operation_resp = await client.get(f"{_get_service_url('ot_interface')}/v1/operations/{tx_id}")
            evidence_resp = await client.get(f"{_get_service_url('evidence_ledger')}/v1/transactions/{tx_id}")
            if operation_resp.status_code not in {200, 404} or evidence_resp.status_code not in {200, 404}:
                return _response(tx_id, "ERROR", reason="Cannot inspect durable retry state", reason_code="DURABLE_STATE_UNAVAILABLE")
            operation = operation_resp.json() if operation_resp.status_code == 200 else None
            existing = evidence_resp.json() if evidence_resp.status_code == 200 else {}
            existing_events = existing.get("events", [])
            if operation:
                payload_digest = hashlib.sha256(json.dumps({"asset_id":asset_id, "action_sequence":actions},
                    ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
                if operation.get("asset_id") != asset_id or operation.get("payload_digest") != payload_digest:
                    return _response(tx_id, "ERROR", reason="Transaction identity is bound to another payload", reason_code="PAYLOAD_CONFLICT")
                state = operation.get("operation_state")
                if state in {"UNKNOWN", "DISPATCHING", "RECONCILING", "ACCEPTED"}:
                    return _response(tx_id, "ERROR", reason="Existing executor outcome needs reconciliation", reason_code="EXECUTION_OUTCOME_UNKNOWN")
                if state == "COMPLETED" and existing.get("chain_valid") is True and existing_events and existing_events[-1].get("stage") == "COMMIT_ACK":
                    return _response(tx_id, "COMMITTED", evidence_ref=f"/v1/transactions/{tx_id}")
                return _response(tx_id, "ERROR", reason="Existing durable transaction is retained; reconcile instead of restarting", reason_code="REVISION_RECONCILIATION_REQUIRED")
            if existing_events:
                return _response(tx_id, "ERROR", reason="Existing evidence is retained; transaction cannot restart", reason_code="EVIDENCE_TRANSACTION_EXISTS")

            await emit("RECEIVED", {"proof_package_hash":compute_sensor_hash(proof), "revision_profile":profile_id,
                "enabled_stages":profile, "schema_version":proof["schema_version"], "policy_version_id":proof["policy_version_id"]})
            await emit("SCHEMA_VALIDATED", {"revision_profile":profile_id, "schema_model":"ProofPackage"})
            active_resp = await client.get(f"{_get_service_url('policy_store')}/v1/policies/active")
            active_resp.raise_for_status()
            version = active_resp.json()["policy_version_id"]
            asset_profile = await _fetch_asset_profile(client, version, asset_id)
            sensor_resp = await client.get(f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest")
            sensor_resp.raise_for_status()
            sensor = sensor_resp.json()
            snapshot, current_hash = sensor["sensor_snapshot"], sensor["sensor_snapshot_hash"]
            integrity_config = asset_profile.get("integrity") or {}
            if profile["integrity"]:
                began = time.perf_counter()
                ok, reason = check_integrity(proof_policy_version=proof["policy_version_id"], active_policy_version=version,
                    proof_timestamp_ms=proof["timestamp_ms"], current_timestamp_ms=int(time.time()*1000),
                    timestamp_max_age_ms=integrity_config.get("timestamp_max_age_ms", 5000),
                    proof_sensor_snapshot=proof.get("sensor_snapshot") or {}, current_sensor_snapshot=snapshot,
                    divergence_thresholds=_build_divergence_thresholds(integrity_config.get("sensor_divergence_thresholds")) if proof.get("sensor_snapshot") else [],
                    proof_sensor_snapshot_hash=proof.get("sensor_snapshot_hash"), current_sensor_snapshot_hash=current_hash)
                await emit("INTEGRITY_PASSED" if ok else "INTEGRITY_REJECTED", {"reason":reason,
                    "policy_version":version, "sensor_hash":current_hash, "duration_ms":(time.perf_counter()-began)*1000})
                if not ok:
                    return _response(tx_id, "REJECTED", reason=f"Integrity verification failed: {reason}", reason_code=reason)
            else:
                await emit("INTEGRITY_BYPASSED", {"revision_profile":profile_id, "executed":False})

            validators = profile["validators"]
            if validators:
                began = time.perf_counter()
                safety = await post_json("safety_cluster", "/v1/validate", {"transaction_id":tx_id, "asset_id":asset_id,
                    "policy_version_id":version, "action_sequence":actions, "current_sensor_snapshot":snapshot,
                    "runtime_context":runtime_context, "revision_enabled_validators":validators})
                # Fail closed if a misconfigured server silently ran a different
                # subset. The selected runtime must be auditable, not inferred.
                if safety.get("enabled_validators") != validators or set(safety.get("validators", {})) != set(validators):
                    await emit("SAFETY_CONFIGURATION_ERROR", {"expected_validators":validators, "details":safety})
                    return _response(tx_id, "ERROR", reason="Safety validator subset differs from frozen profile", reason_code="REVISION_VALIDATOR_MISMATCH")
                safe = safety.get("final_verdict") == "SAFE"
                await emit("SAFETY_PASSED" if safe else "SAFETY_UNSAFE", {"verdict":safety.get("final_verdict"), "details":safety,
                    "enabled_validators":validators, "duration_ms":(time.perf_counter()-began)*1000})
                if not safe:
                    return _response(tx_id, "UNSAFE", reason="Safety validation failed", reason_code="SAFETY_UNSAFE",
                                     alternative_actions=generate_alternative_actions(asset_profile, "SAFETY_UNSAFE"))
            else:
                await emit("SAFETY_BYPASSED", {"revision_profile":profile_id, "enabled_validators":[], "executed":False})

            prepare_result = {}
            if profile["prepare"]:
                ttl = (asset_profile.get("execution") or {}).get("lock_ttl_ms", 5000)
                if _fault_enabled(fault, "lock_denied"):
                    prepare_result = {"status":"LOCK_DENIED", "reason":"Injected legacy benchmark lock denial", "synthetic":True}
                else:
                    prepare_result = await post_json("ot_interface", "/v1/prepare", {"transaction_id":tx_id, "asset_id":asset_id,
                                                                                  "lock_ttl_ms":ttl, "action_sequence":actions})
                if prepare_result.get("status") != "LOCK_GRANTED":
                    await emit("PREPARE_LOCK_DENIED", prepare_result)
                    return _response(tx_id, "ABORTED", reason="Lock denied", reason_code="LOCK_DENIED")
                prepared = True
                await emit("PREPARE_LOCK_GRANTED", {**prepare_result, "case_token":test_control.get("case_token"),
                    "prepared_at_ms":int(time.time()*1000), "prepared_monotonic_ns":time.monotonic_ns()})
                if pause_ms:
                    await emit("REVISION_PREPARE_PAUSE", {"case_token":test_control.get("case_token"), "pause_ms":pause_ms,
                        "started_at_ms":int(time.time()*1000), "started_monotonic_ns":time.monotonic_ns()})
                    await asyncio.sleep(pause_ms / 1000.0)
            else:
                await emit("PREPARE_BYPASSED", {"revision_profile":profile_id, "executed":False})

            if profile["reverify"]:
                try:
                    reverify_resp = await client.get(f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest")
                    reverify_resp.raise_for_status()
                    reverify_hash = reverify_resp.json()["sensor_snapshot_hash"]
                except Exception as exc:
                    aborted = await abort_reserved(f"TOCTOU reverify failed: {exc}")
                    await emit("REVERIFY_FAILED", {"error":str(exc), "abort_status":aborted.get("status")})
                    return _response(tx_id, "ABORTED", reason=str(exc), reason_code="TOCTOU_REVERIFY_FAILED")
                if _fault_enabled(fault, "reverify_hash_mismatch"):
                    reverify_hash = _force_hash_mismatch(current_hash)
                reverify_payload = {"original_hash":current_hash, "reverify_hash":reverify_hash,
                    "case_token":test_control.get("case_token"), "reverified_at_ms":int(time.time()*1000),
                    "reverified_monotonic_ns":time.monotonic_ns(), "synthetic":_fault_enabled(fault, "reverify_hash_mismatch")}
                if reverify_hash != current_hash:
                    aborted = await abort_reserved("TOCTOU reverify hash mismatch")
                    await emit("REVERIFY_FAILED", {**reverify_payload, "reason":"REVERIFY_HASH_MISMATCH", "abort_status":aborted.get("status")})
                    return _response(tx_id, "ABORTED", reason="Sensor state changed after PREPARE", reason_code="REVERIFY_HASH_MISMATCH")
                await emit("REVERIFY_PASSED", reverify_payload)
            else:
                await emit("REVERIFY_BYPASSED", {"revision_profile":profile_id, "executed":False,
                    "case_token":test_control.get("case_token"), "bypassed_at_ms":int(time.time()*1000)})

            # Synthetic commit faults only exist in the preregistered legacy
            # subset. They do not claim a real dispatch or physical recovery.
            if any(_fault_enabled(fault, family) for family in ("commit_timeout", "commit_failed_recovered", "ot_interface_error")):
                family = fault["fault_family"]
                aborted = await abort_reserved(f"Legacy synthetic fault: {family}") if prepared else {}
                stage, status, code = {"commit_timeout":("COMMIT_TIMEOUT", "ABORTED", "COMMIT_TIMEOUT"),
                    "commit_failed_recovered":("COMMIT_FAILED", "ABORTED", "COMMIT_FAILED"),
                    "ot_interface_error":("COMMIT_ERROR", "ERROR", "OT_INTERFACE_ERROR")}[family]
                await emit(stage, {"synthetic":True, "fault_family":family, "dispatch_attempted":False,
                    "physical_recovery_observed":False, "abort_status":aborted.get("status")})
                return _response(tx_id, status, reason=f"Injected legacy benchmark {family}", reason_code=code)

            endpoint = "/v1/commit" if profile["prepare"] else "/v1/revision/direct-execute"
            dispatch_payload = {"transaction_id":tx_id, "asset_id":asset_id, "action_sequence":actions}
            if profile["prepare"]:
                dispatch_payload["lock_token"] = prepare_result.get("lock_token")
            # Set before the transport call: a lost reply does not prove the
            # executor never accepted this command.
            dispatched = True
            try:
                result = await post_json("ot_interface", endpoint, dispatch_payload)
            except Exception as exc:
                await emit("COMMIT_OUTCOME_UNKNOWN", {"error":str(exc), "dispatch_attempted":True})
                return _response(tx_id, "ERROR", reason="Dispatch outcome requires receipt reconciliation", reason_code="EXECUTION_OUTCOME_UNKNOWN")
            outcome = result.get("status")
            if outcome in {"UNKNOWN", "IN_PROGRESS"}:
                await emit("COMMIT_OUTCOME_UNKNOWN", result)
                return _response(tx_id, "ERROR", reason=result.get("reason") or "Execution outcome unknown", reason_code="EXECUTION_OUTCOME_UNKNOWN")
            if outcome == "EXECUTION_FAILED":
                await emit("COMMIT_FAILED", result)
                return _response(tx_id, "ABORTED" if result.get("safe_state_executed") else "ERROR", reason=result.get("reason"), reason_code="COMMIT_FAILED")
            if outcome not in {"ACK", "ALREADY_COMMITTED"}:
                # A known pre-dispatch timeout can release its reservation.
                if prepared:
                    await abort_reserved(f"Commit rejected before dispatch: {outcome}")
                await emit("COMMIT_TIMEOUT", result)
                return _response(tx_id, "ABORTED", reason=f"Commit status: {outcome}", reason_code="COMMIT_TIMEOUT")
            await emit("COMMIT_ACK", result)
            return _response(tx_id, "COMMITTED", evidence_ref=f"/v1/transactions/{tx_id}")
        except Exception as exc:
            logger.exception("Revision request %s failed", tx_id)
            return _response(tx_id, "ERROR", reason=str(exc), reason_code="REVISION_PIPELINE_ERROR")
        finally:
            if prepared and not dispatched:
                try:
                    await abort_reserved("Revision request exited before dispatch")
                except Exception:
                    logger.critical("Revision PREPARE cleanup failed for %s", tx_id, exc_info=True)


@router.post("/control-requests", response_model=ControlResponse)
async def submit_control_request(request: ControlRequest, api_key: str = Depends(verify_api_key)):
    """
    하나의 제어 요청을 Gateway 전체 파이프라인으로 처리한다.

    이 함수는 "성공 시 COMMITTED, 아니면 fail-closed"라는 운영 semantics를
    실제 코드로 구현하는 곳이다. 각 단계가 끝날 때마다 Evidence Ledger에
    증거를 남기므로, 사후 감사 시 어떤 이유로 거부/중단되었는지 역추적할 수 있다.
    """
    start_total = time.time()
    tx_id = request.transaction_id
    asset_id = request.asset_id
    proof = request.proof_package.model_dump(exclude_none=True)
    if "revision_profile" in proof or "revision_test_control" in proof:
        return await _submit_revision_control_request(request, api_key)
    runtime_context = _extract_runtime_context(proof)
    fault_injection = _extract_fault_injection(proof)
    evidence_seq = 0
    prev_hash = GENESIS_HASH
    asset_profile: dict | None = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        # [100] Schema validation
        # Pydantic이 1차 타입 검증을 끝낸 상태이므로, 여기서는
        # "논문/운영 계약상 핵심 필드가 모두 들어왔는지"를 증거로 남기는 역할이 크다.
        t0 = time.time()
        required_fields = [
            "schema_version",
            "policy_version_id",
            "timestamp_ms",
            "sensor_snapshot_hash",
            "sensor_reliability_index",
            "action_sequence",
            "safety_verification_summary",
        ]

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "RECEIVED",
            {
                "proof_package_hash": compute_sensor_hash(proof),
                "schema_version": proof["schema_version"],
                "policy_version_id": proof["policy_version_id"],
            },
            prev_hash,
        )
        evidence_seq += 1

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "SCHEMA_VALIDATED",
            {"fields_checked": required_fields},
            prev_hash,
        )
        evidence_seq += 1
        logger.info("[100] Schema Validation: PASSED (%.0fms)", (time.time() - t0) * 1000)

        # [110] Integrity verification
        # Proof Package가 "현재 활성 정책 + 최신 센서 상태"와 여전히 정합한지 확인한다.
        # 여기서 틀리면 안전 검증으로 가지 않고 바로 REJECTED 처리한다.
        t0 = time.time()
        try:
            policy_resp = await client.get(f"{_get_service_url('policy_store')}/v1/policies/active")
            if policy_resp.status_code != 200:
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"Policy Store returned HTTP {policy_resp.status_code}",
                    reason_code="POLICY_STORE_ERROR",
                )
            active_version = policy_resp.json()["policy_version_id"]
        except Exception as exc:
            logger.error("[SYSTEM_ERROR] Policy Store connection failed: %s", exc, exc_info=True)
            return _response(tx_id, "ERROR", reason=f"Policy Store error: {exc}", reason_code="POLICY_STORE_UNREACHABLE")

        try:
            sensor_resp = await client.get(f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest")
            if sensor_resp.status_code != 200:
                try:
                    error_detail = sensor_resp.json().get("detail", f"HTTP {sensor_resp.status_code}")
                except Exception:
                    error_detail = f"HTTP {sensor_resp.status_code}"
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"Sensor Gateway error: {error_detail}",
                    reason_code="SENSOR_GATEWAY_ERROR",
                )
            sensor_data = sensor_resp.json()
            current_snapshot = sensor_data["sensor_snapshot"]
            current_hash = sensor_data["sensor_snapshot_hash"]
        except Exception as exc:
            logger.error("[SYSTEM_ERROR] Sensor Gateway connection failed: %s", exc, exc_info=True)
            return _response(tx_id, "ERROR", reason=f"Sensor Gateway error: {exc}", reason_code="SENSOR_GATEWAY_ERROR")

        try:
            asset_profile = await _fetch_asset_profile(client, active_version, asset_id)
        except Exception as exc:
            logger.error("[SYSTEM_ERROR] Failed to load asset profile: %s", exc, exc_info=True)
            return _response(tx_id, "ERROR", reason=str(exc), reason_code="POLICY_STORE_ERROR")

        integrity_config = asset_profile.get("integrity", {}) or {}
        execution_config = asset_profile.get("execution", {}) or {}
        timestamp_max_age_ms = integrity_config.get("timestamp_max_age_ms", 5000)
        divergence_thresholds = _build_divergence_thresholds(integrity_config.get("sensor_divergence_thresholds"))
        proof_snapshot = proof.get("sensor_snapshot") or {}
        sensor_match = proof.get("sensor_snapshot_hash", "") == current_hash

        integrity_ok, integrity_reason = check_integrity(
            proof_policy_version=proof["policy_version_id"],
            active_policy_version=active_version,
            proof_timestamp_ms=proof["timestamp_ms"],
            current_timestamp_ms=int(time.time() * 1000),
            timestamp_max_age_ms=timestamp_max_age_ms,
            proof_sensor_snapshot=proof_snapshot,
            current_sensor_snapshot=current_snapshot,
            divergence_thresholds=divergence_thresholds if proof_snapshot else [],
            proof_sensor_snapshot_hash=proof.get("sensor_snapshot_hash"),
            current_sensor_snapshot_hash=current_hash,
        )

        if not integrity_ok:
            duration = (time.time() - t0) * 1000
            logger.warning("[110] Integrity Check: FAILED (%.0fms) | reason=%s", duration, integrity_reason)
            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "INTEGRITY_REJECTED",
                {
                    "reason": integrity_reason,
                    "policy_version": active_version,
                    "sensor_hash": current_hash,
                    "sensor_hash_match": sensor_match,
                },
                prev_hash,
            )
            return _response(
                tx_id,
                "REJECTED",
                reason=f"Integrity verification failed: {integrity_reason}",
                reason_code=integrity_reason,
            )

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "INTEGRITY_PASSED",
            {
                "policy_version": active_version,
                "sensor_hash": current_hash,
                "sensor_hash_match": sensor_match,
                "sensor_reliability_index": proof["sensor_reliability_index"],
                "timestamp_max_age_ms": timestamp_max_age_ms,
            },
            prev_hash,
        )
        evidence_seq += 1
        logger.info(
            "[110] Integrity Check: PASSED (%.0fms) | policy=%s sensor_hash_match=%s",
            (time.time() - t0) * 1000,
            active_version,
            str(sensor_match).lower(),
        )

        # [120] Safety validation
        # Safety Cluster는 Rules / CBF / Simulation을 수행한 뒤
        # SIL 기반 consensus로 최종 SAFE / UNSAFE를 반환한다.
        t0 = time.time()
        try:
            safety_resp = await client.post(
                f"{_get_service_url('safety_cluster')}/v1/validate",
                json={
                    "transaction_id": tx_id,
                    "asset_id": asset_id,
                    "policy_version_id": active_version,
                    "action_sequence": proof.get("action_sequence", []),
                    "current_sensor_snapshot": current_snapshot,
                    "runtime_context": runtime_context,
                },
            )
            if safety_resp.status_code != 200:
                try:
                    error_detail = safety_resp.json().get("detail", f"HTTP {safety_resp.status_code}")
                except Exception:
                    error_detail = f"HTTP {safety_resp.status_code}"
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"Safety Cluster error: {error_detail}",
                    reason_code="SAFETY_CLUSTER_ERROR",
                )
            safety_result = safety_resp.json()
        except Exception as exc:
            logger.error("[SYSTEM_ERROR] Safety Cluster connection failed: %s", exc, exc_info=True)
            return _response(tx_id, "ERROR", reason=f"Safety Cluster error: {exc}", reason_code="SAFETY_CLUSTER_UNREACHABLE")

        if safety_result["final_verdict"] != "SAFE":
            duration = (time.time() - t0) * 1000
            alternative_actions = generate_alternative_actions(asset_profile, "SAFETY_UNSAFE")
            logger.warning("[120] Safety Verification: UNSAFE (%.0fms)", duration)

            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "SAFETY_UNSAFE",
                {
                    "verdict": safety_result["final_verdict"],
                    "details": safety_result,
                    "alternative_actions": alternative_actions,
                },
                prev_hash,
            )

            reason_parts: list[str] = []
            rules_detail = safety_result.get("validators", {}).get("rules", {})
            if rules_detail.get("verdict") == "UNSAFE":
                for violation in rules_detail.get("details", {}).get("violated_rules", []):
                    reason_parts.append(f"Rule '{violation.get('rule_id')}': {violation.get('reason')}")

            cbf_detail = safety_result.get("validators", {}).get("cbf", {})
            if cbf_detail.get("verdict") == "UNSAFE":
                reason_parts.append(f"CBF barrier h={cbf_detail.get('details', {}).get('min_barrier_value', 'N/A')} < 0")

            sim_detail = safety_result.get("validators", {}).get("simulation", {})
            if sim_detail.get("verdict") == "UNSAFE":
                sim_violations = sim_detail.get("details", {}).get("violations", [])
                reason_parts.append(f"Simulation: {len(sim_violations)} violations detected")

            detailed_reason = (
                "Safety validation failed: " + "; ".join(reason_parts[:5])
                if reason_parts
                else "Safety validation failed (consensus threshold not met)"
            )
            if len(reason_parts) > 5:
                detailed_reason += f" (+{len(reason_parts) - 5} more)"

            return _response(
                tx_id,
                "UNSAFE",
                reason=detailed_reason,
                reason_code="SAFETY_UNSAFE",
                alternative_actions=alternative_actions,
            )

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "SAFETY_PASSED",
            {"verdict": "SAFE", "consensus": safety_result.get("consensus_details", {})},
            prev_hash,
        )
        evidence_seq += 1
        logger.info(
            "[120] Safety Verification: SAFE (%.0fms) | consensus=%s",
            (time.time() - t0) * 1000,
            safety_result.get("consensus_details", {}).get("score", 0.0),
        )

        # [130-1] PREPARE
        # 실제 물리 명령을 보내기 전에 OT 쪽 입력 억제 잠금을 먼저 획득한다.
        # 여기서 잠금에 실패하면 같은 자산에 대한 다른 트랜잭션과 충돌 중인 상태다.
        t0 = time.time()
        lock_ttl_ms = execution_config.get("lock_ttl_ms", 5000)
        if _fault_enabled(fault_injection, "lock_denied"):
            prepare_result = {"status": "LOCK_DENIED", "reason": "Injected benchmark lock denial"}
        else:
            try:
                prepare_resp = await client.post(
                    f"{_get_service_url('ot_interface')}/v1/prepare",
                    json={"transaction_id": tx_id, "asset_id": asset_id, "lock_ttl_ms": lock_ttl_ms,
                          "action_sequence": proof.get("action_sequence", [])},
                )
                prepare_result = prepare_resp.json()
            except Exception as exc:
                logger.error("[SYSTEM_ERROR] OT Interface PREPARE failed: %s", exc, exc_info=True)
                return _response(tx_id, "ERROR", reason=f"OT Interface error: {exc}", reason_code="OT_INTERFACE_UNREACHABLE")

        if prepare_result["status"] != "LOCK_GRANTED":
            alternative_actions = generate_alternative_actions(asset_profile, "LOCK_DENIED")
            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "PREPARE_LOCK_DENIED",
                {"reason": prepare_result.get("reason", "unknown"), "alternative_actions": alternative_actions},
                prev_hash,
            )
            return _response(
                tx_id,
                "ABORTED",
                reason="Lock denied",
                reason_code="LOCK_DENIED",
                alternative_actions=alternative_actions,
            )

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "PREPARE_LOCK_GRANTED",
            {
                "lock_expires_at_ms": prepare_result.get("lock_expires_at_ms"),
                "lock_ttl_ms": lock_ttl_ms,
            },
            prev_hash,
        )
        evidence_seq += 1
        logger.info("[130] 2PC Prepare: LOCKED (%.0fms) | tx_id=%s", (time.time() - t0) * 1000, tx_id)

        # [130-2] REVERIFY
        # PREPARE 후 COMMIT 직전에 센서 해시를 다시 읽어 TOCTOU를 검사한다.
        # 이 단계가 fail-closed여야 "잠금은 잡았지만 현장 상태가 바뀐 경우"를 막을 수 있다.
        t0 = time.time()
        try:
            reverify_resp = await client.get(f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest")
            if reverify_resp.status_code != 200:
                try:
                    error_detail = reverify_resp.json().get("detail", f"HTTP {reverify_resp.status_code}")
                except Exception:
                    error_detail = f"HTTP {reverify_resp.status_code}"
                raise RuntimeError(f"Sensor Gateway returned {reverify_resp.status_code}: {error_detail}")
            reverify_data = reverify_resp.json()
            reverify_hash = reverify_data.get("sensor_snapshot_hash", "")
        except Exception as exc:
            alternative_actions = generate_alternative_actions(asset_profile, "TOCTOU_REVERIFY_FAILED")
            try:
                abort_result = await _abort_transaction(client, tx_id, asset_id, f"TOCTOU reverify failed: {exc}")
            except Exception as abort_exc:
                logger.critical("[%s] ABORT also failed after TOCTOU failure: %s", tx_id, abort_exc, exc_info=True)
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"Sensor re-verification failed and abort failed: {abort_exc}",
                    reason_code="OT_ABORT_FAILED",
                    alternative_actions=alternative_actions,
                )

            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "REVERIFY_FAILED",
                {
                    "error": str(exc),
                    "abort_status": abort_result.get("status"),
                    "alternative_actions": alternative_actions,
                },
                prev_hash,
            )
            evidence_seq += 1
            return _response(
                tx_id,
                "ABORTED",
                reason=f"Sensor re-verification failed: {exc}",
                reason_code="TOCTOU_REVERIFY_FAILED",
                alternative_actions=alternative_actions,
            )

        if _fault_enabled(fault_injection, "reverify_hash_mismatch"):
            reverify_hash = _force_hash_mismatch(current_hash)

        if reverify_hash != current_hash:
            alternative_actions = generate_alternative_actions(asset_profile, "REVERIFY_HASH_MISMATCH")
            try:
                abort_result = await _abort_transaction(
                    client,
                    tx_id,
                    asset_id,
                    f"TOCTOU reverify hash mismatch: original={current_hash}, reverify={reverify_hash}",
                )
            except Exception as abort_exc:
                logger.critical("[%s] ABORT failed after hash mismatch: %s", tx_id, abort_exc, exc_info=True)
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"TOCTOU mismatch detected but abort failed: {abort_exc}",
                    reason_code="OT_ABORT_FAILED",
                    alternative_actions=alternative_actions,
                )

            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "REVERIFY_FAILED",
                {
                    "reason": "REVERIFY_HASH_MISMATCH",
                    "original_hash": current_hash,
                    "reverify_hash": reverify_hash,
                    "abort_status": abort_result.get("status"),
                    "alternative_actions": alternative_actions,
                },
                prev_hash,
            )
            evidence_seq += 1
            logger.warning(
                "[130] TOCTOU Reverify: FAILED (%.0fms) | hash_match=false",
                (time.time() - t0) * 1000,
            )
            return _response(
                tx_id,
                "ABORTED",
                reason="Sensor state changed after PREPARE; commit aborted",
                reason_code="REVERIFY_HASH_MISMATCH",
                alternative_actions=alternative_actions,
            )

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "REVERIFY_PASSED",
            {"original_hash": current_hash, "reverify_hash": reverify_hash},
            prev_hash,
        )
        evidence_seq += 1
        logger.info("[130] TOCTOU Reverify: PASSED (%.0fms) | hash_match=true", (time.time() - t0) * 1000)

        # [130-3] COMMIT
        # COMMIT은 OT Interface 내부 executor가 실제 장비에 명령을 적용한 뒤에만 성공한다.
        # 따라서 ACK는 "실행 확정" 의미이고, 그 외 상태는 모두 중단/오류로 다룬다.
        t0 = time.time()
        try:
            if _fault_enabled(fault_injection, "commit_timeout"):
                commit_result = {"status": "TIMEOUT", "reason": "Injected benchmark commit timeout"}
            elif _fault_enabled(fault_injection, "commit_failed_recovered"):
                commit_result = {
                    "status": "EXECUTION_FAILED",
                    "reason": "Injected benchmark recovered commit failure",
                    "safe_state_executed": True,
                }
            elif _fault_enabled(fault_injection, "ot_interface_error"):
                raise RuntimeError("Injected benchmark OT interface error")
            else:
                commit_resp = await client.post(
                    f"{_get_service_url('ot_interface')}/v1/commit",
                    json={
                        "transaction_id": tx_id,
                        "asset_id": asset_id,
                        "action_sequence": proof.get("action_sequence", []),
                        "lock_token": prepare_result.get("lock_token"),
                    },
                )
                if commit_resp.status_code != 200:
                    try:
                        error_detail = commit_resp.json().get("detail", f"HTTP {commit_resp.status_code}")
                    except Exception:
                        error_detail = f"HTTP {commit_resp.status_code}"
                    raise RuntimeError(f"OT Interface COMMIT returned {commit_resp.status_code}: {error_detail}")
                commit_result = commit_resp.json()
        except Exception as exc:
            logger.error("[SYSTEM_ERROR] OT Interface COMMIT failed: %s", exc, exc_info=True)
            error_reason_code = "OT_INTERFACE_ERROR" if _fault_enabled(fault_injection, "ot_interface_error") else "COMMIT_ERROR"
            alternative_actions = generate_alternative_actions(asset_profile, "COMMIT_ERROR")
            try:
                abort_result = await _abort_transaction(client, tx_id, asset_id, str(exc))
            except Exception as abort_exc:
                return _response(
                    tx_id,
                    "ERROR",
                    reason=f"Commit failed and abort failed: {abort_exc}",
                    reason_code="OT_ABORT_FAILED",
                    alternative_actions=alternative_actions,
                )
            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "COMMIT_ERROR",
                {
                    "reason": str(exc),
                    "reason_code": error_reason_code,
                    "abort_status": abort_result.get("status"),
                    "alternative_actions": alternative_actions,
                },
                prev_hash,
            )
            evidence_seq += 1
            return _response(
                tx_id,
                "ERROR",
                reason=f"Commit failed: {exc}",
                reason_code=error_reason_code,
                alternative_actions=alternative_actions,
            )

        commit_status = commit_result["status"]

        if commit_status in {"UNKNOWN", "IN_PROGRESS"}:
            await _log_evidence(client, tx_id, evidence_seq, "COMMIT_OUTCOME_UNKNOWN", commit_result, prev_hash)
            return _response(tx_id, "ERROR", reason=commit_result.get("reason") or "Execution outcome needs reconciliation",
                             reason_code="EXECUTION_OUTCOME_UNKNOWN")

        if _fault_enabled(fault_injection, "commit_timeout") or _fault_enabled(fault_injection, "commit_failed_recovered"):
            try:
                await _abort_transaction(client, tx_id, asset_id, "Synthetic benchmark result; release unused PREPARE reservation")
            except Exception as exc:
                return _response(tx_id, "ERROR", reason=str(exc), reason_code="OT_ABORT_FAILED")

        if commit_status == "EXECUTION_FAILED":
            alternative_actions = generate_alternative_actions(asset_profile, "COMMIT_FAILED")
            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "COMMIT_FAILED",
                {
                    "status": commit_status,
                    "reason": commit_result.get("reason"),
                    "safe_state_executed": commit_result.get("safe_state_executed"),
                    "alternative_actions": alternative_actions,
                },
                prev_hash,
            )
            evidence_seq += 1
            response_status = "ABORTED" if commit_result.get("safe_state_executed") else "ERROR"
            return _response(
                tx_id,
                response_status,
                reason=f"Commit execution failed: {commit_result.get('reason', 'unknown')}",
                reason_code="COMMIT_FAILED",
                alternative_actions=alternative_actions,
            )

        if commit_status == "ALREADY_COMMITTED":
            logger.info("[130] 2PC Commit: ALREADY_COMMITTED (%.0fms)", (time.time() - t0) * 1000)
        elif commit_status != "ACK":
            alternative_actions = generate_alternative_actions(asset_profile, "COMMIT_TIMEOUT")
            prev_hash = await _log_evidence(
                client,
                tx_id,
                evidence_seq,
                "COMMIT_TIMEOUT",
                {"status": commit_status, "reason": commit_result.get("reason"), "alternative_actions": alternative_actions},
                prev_hash,
            )
            return _response(
                tx_id,
                "ABORTED",
                reason=f"Commit status: {commit_status}",
                reason_code="COMMIT_TIMEOUT",
                alternative_actions=alternative_actions,
            )

        if commit_status == "ACK":
            logger.info("[130] 2PC Commit: COMMITTED (%.0fms)", (time.time() - t0) * 1000)

        prev_hash = await _log_evidence(
            client,
            tx_id,
            evidence_seq,
            "COMMIT_ACK",
            {
                "executed_at_ms": commit_result.get("executed_at_ms"),
                "status": commit_status,
            },
            prev_hash,
        )
        evidence_seq += 1

        logger.info("[140] Evidence: %s events recorded", evidence_seq)
        logger.info("TOTAL: %.0fms | COMMITTED", (time.time() - start_total) * 1000)

        return _response(tx_id, "COMMITTED", evidence_ref=f"/v1/transactions/{tx_id}")


async def _log_evidence(client: httpx.AsyncClient, tx_id: str, seq: int, stage: str, payload: dict, prev_hash: str) -> str:
    """
    Evidence Ledger에 단일 이벤트를 append하고, 다음 단계가 사용할 event hash를 반환한다.

    prev_hash -> event_hash 체인을 유지하므로, 이 함수가 실패하면 단순 로그 손실이 아니라
    감사 체인 단절로 간주한다. 그래서 호출부는 이 함수를 fail-hard로 취급한다.
    """
    input_hash = compute_sensor_hash(payload)
    event_hash = compute_event_hash(prev_hash, payload)

    try:
        resp = await client.post(
            f"{_get_service_url('evidence_ledger')}/v1/events/append",
            json={
                "transaction_id": tx_id,
                "sequence_no": seq,
                "stage": stage,
                "timestamp_ms": int(time.time() * 1000),
                "payload": payload,
                "input_hash": input_hash,
                "prev_hash": prev_hash,
                "event_hash": event_hash,
            },
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            try:
                detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            except Exception:
                detail = f"HTTP {resp.status_code}"
            raise RuntimeError(f"Evidence Ledger append failed: {detail}")
    except Exception as exc:
        logger.critical("[SYSTEM_ERROR] Evidence Ledger failure: %s", exc, exc_info=True)
        raise

    return event_hash
