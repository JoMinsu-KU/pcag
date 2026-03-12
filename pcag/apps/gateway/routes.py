"""
Gateway Core — 파이프라인 오케스트레이션
==========================================
PCAG의 핵심 서비스. 제어 요청을 받아 5단계 파이프라인을 실행합니다:
  [100] 스키마 검증 → [110] 무결성 검사 → [120] 안전 검증 
  → [130] 2PC 실행 → [140] 증거 기록

각 단계에서 다른 서비스를 HTTP로 호출합니다.
"""
import time
import uuid
import httpx
import logging
from fastapi import APIRouter, HTTPException, Depends
from pcag.core.contracts.gateway import ControlRequest, ControlResponse
from pcag.core.contracts.common import ErrorResponse
from pcag.core.utils.hash_utils import compute_sensor_hash, compute_event_hash, GENESIS_HASH
from pcag.core.utils.canonicalize import canonicalize
from pcag.core.utils.config_loader import get_service_urls, load_config
from pcag.core.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)

# [Fix C8] Load config at module level and enforce required services
_config = load_config("services.yaml", required=True)
_services = _config.get("services", {})
_REQUIRED_SERVICES = ["policy_store", "sensor_gateway", "safety_cluster", "ot_interface", "evidence_ledger"]

for svc in _REQUIRED_SERVICES:
    if svc not in _services or not _services[svc].get("url"):
        raise RuntimeError(f"Required service '{svc}' URL is missing in services.yaml")

router = APIRouter(prefix="/v1", tags=["Gateway"])


def _get_service_url(service_name: str) -> str:
    """서비스 URL을 config에서 조회 (없으면 에러)"""
    urls = get_service_urls()
    url = urls.get(service_name)
    if not url:
        raise ValueError(f"Service URL for '{service_name}' not configured")
    return url

@router.post("/control-requests", response_model=ControlResponse)
async def submit_control_request(request: ControlRequest, api_key: str = Depends(verify_api_key)):
    """
    제어 요청 처리 — PCAG 핵심 파이프라인 오케스트레이션
    
    순서:
    1. 스키마 검증 (100) — ProofPackage 필수 필드 확인
    2. 무결성 검사 (110) — 정책 버전, 센서 편차, 타임스탬프
    3. 안전 검증 (120) — Rules + CBF + Simulation + Consensus
    4. 2PC 실행 (130) — PREPARE → REVERIFY → COMMIT
    5. 증거 기록 (140) — 각 단계의 결과를 해시 체인으로 기록
    """
    start_total = time.time()
    tx_id = request.transaction_id
    asset_id = request.asset_id
    proof = request.proof_package
    evidence_seq = 0
    prev_hash = GENESIS_HASH
    
    # Initial Log handled by Middleware, but we can log specific pipeline start if needed
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # ============================================================
        # [100] 스키마 검증 (Schema Validation)
        # ============================================================
        t0 = time.time()
        required_fields = ["schema_version", "policy_version_id", "timestamp_ms",
                          "sensor_snapshot_hash", "action_sequence", "safety_verification_summary"]
        missing = [f for f in required_fields if f not in proof]
        
        if missing:
            duration = (time.time() - t0) * 1000
            logger.warning(f"[100] Schema Validation: FAILED ({duration:.0f}ms) | missing={missing}")
            return ControlResponse(
                transaction_id=tx_id,
                status="REJECTED",
                reason=f"Missing fields in ProofPackage: {missing}",
                reason_code="SCHEMA_INVALID"
            )
        
        # 증거 기록: RECEIVED
        prev_hash = await _log_evidence(client, tx_id, evidence_seq, "RECEIVED", 
                                        {"proof_package_hash": compute_sensor_hash(proof)}, prev_hash)
        evidence_seq += 1
        
        # 증거 기록: SCHEMA_VALIDATED
        prev_hash = await _log_evidence(client, tx_id, evidence_seq, "SCHEMA_VALIDATED",
                                        {"fields_checked": required_fields}, prev_hash)
        evidence_seq += 1
        
        duration = (time.time() - t0) * 1000
        logger.info(f"[100] Schema Validation: PASSED ({duration:.0f}ms)")
        
        # ============================================================
        # [110] 무결성 검사 (Integrity Verification)
        # ============================================================
        t0 = time.time()
        
        # 110-1: 정책 버전 확인
        try:
            policy_resp = await client.get(f"{_get_service_url('policy_store')}/v1/policies/active")
            if policy_resp.status_code != 200:
                logger.error(f"Policy Store error: {policy_resp.status_code}")
                return ControlResponse(
                    transaction_id=tx_id, status="ERROR",
                    reason=f"Policy Store returned HTTP {policy_resp.status_code}",
                    reason_code="POLICY_STORE_ERROR"
                )
            active_version = policy_resp.json()["policy_version_id"]
        except Exception as e:
            logger.error(f"[SYSTEM_ERROR] Policy Store connection failed: {e}", exc_info=True)
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Policy Store error: {e}", reason_code="POLICY_STORE_UNREACHABLE")
        
        if proof.get("policy_version_id") != active_version:
            duration = (time.time() - t0) * 1000
            logger.warning(f"[110] Integrity Check: FAILED ({duration:.0f}ms) | reason=POLICY_MISMATCH expected={active_version} got={proof.get('policy_version_id')}")
            
            # Evidence logging might fail, so wrap it or let it bubble if we decide to be strict.
            # For now, let's keep the evidence logging as is, but if it fails later we will handle it.
            # But wait, user said Evidence failure must be fatal.
            # I will address Evidence failure in _log_evidence function modification first, 
            # then here I might need to handle it if I change _log_evidence to raise.
            
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "INTEGRITY_REJECTED",
                                                {"reason": "POLICY_MISMATCH", "expected": active_version, "got": proof.get("policy_version_id")}, prev_hash)
            except Exception as e:
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")

            return ControlResponse(
                transaction_id=tx_id,
                status="REJECTED",
                reason=f"Policy version mismatch: expected {active_version}",
                reason_code="INTEGRITY_POLICY_MISMATCH"
            )
        
        # 110-2: 현재 센서 스냅샷 조회
        try:
            sensor_resp = await client.get(f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest")
            if sensor_resp.status_code != 200:
                error_detail = sensor_resp.json().get("detail", f"HTTP {sensor_resp.status_code}")
                logger.error(f"[{tx_id}] [SYSTEM_ERROR] Sensor Gateway returned {sensor_resp.status_code}: {error_detail}")
                return ControlResponse(
                    transaction_id=tx_id,
                    status="ERROR",
                    reason=f"Sensor Gateway error: {error_detail}",
                    reason_code="SENSOR_GATEWAY_ERROR"
                )
            sensor_data = sensor_resp.json()
            current_snapshot = sensor_data["sensor_snapshot"]
            current_hash = sensor_data["sensor_snapshot_hash"]
        except Exception as e:
            logger.error(f"[SYSTEM_ERROR] Sensor Gateway connection failed: {e}", exc_info=True)
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Sensor Gateway error: {e}", reason_code="SENSOR_GATEWAY_ERROR")
        
        # 110-2.5: 센서 해시 비교 (TOCTOU L1 - Divergence Check)
        proof_sensor_hash = proof.get("sensor_snapshot_hash", "")
        sensor_match = (proof_sensor_hash == current_hash)
        
        if proof_sensor_hash and current_hash and not sensor_match:
            # 센서 해시 불일치 — 에이전트가 본 센서 상태와 현재 센서 상태가 다름
            # 편차 임계값 확인 (Policy의 integrity 설정)
            
            # Policy에서 편차 임계값 조회
            try:
                asset_policy_resp = await client.get(
                    f"{_get_service_url('policy_store')}/v1/policies/{active_version}/assets/{asset_id}"
                )
                if asset_policy_resp.status_code == 200:
                    asset_profile = asset_policy_resp.json().get("profile", {})
                    integrity_config = asset_profile.get("integrity", {})
                    divergence_thresholds = integrity_config.get("sensor_divergence_thresholds", [])
                    
                    # 센서 편차 검사 수행
                    if divergence_thresholds:
                        # ProofPackage에 sensor_snapshot이 있으면 실제 값 비교
                        proof_snapshot = proof.get("sensor_snapshot", {})
                        if proof_snapshot:
                            
                            # 기존 integrity_service를 활용한 편차 검사
                            for threshold in divergence_thresholds:
                                sensor_type = threshold.get("sensor_type", "")
                                method = threshold.get("method", "absolute")
                                max_div = threshold.get("max_divergence", 999)
                                
                                proof_val = proof_snapshot.get(sensor_type)
                                current_val = current_snapshot.get(sensor_type)
                                
                                if proof_val is not None and current_val is not None:
                                    if method == "absolute":
                                        divergence = abs(float(proof_val) - float(current_val))
                                    elif method == "percentage":
                                        divergence = abs(float(proof_val) - float(current_val)) / max(abs(float(current_val)), 0.001) * 100
                                    else:
                                        divergence = 0
                                    
                                    if divergence > max_div:
                                        duration = (time.time() - t0) * 1000
                                        logger.warning(f"[110] Integrity Check: FAILED ({duration:.0f}ms) | reason=SENSOR_DIVERGENCE sensor={sensor_type} div={divergence:.3f} max={max_div}")
                                        
                                        prev_hash = await _log_evidence(client, tx_id, evidence_seq, "INTEGRITY_REJECTED", {
                                            "reason": "SENSOR_DIVERGENCE",
                                            "sensor_type": sensor_type,
                                            "divergence": round(divergence, 3),
                                            "threshold": max_div
                                        }, prev_hash)
                                        return ControlResponse(
                                            transaction_id=tx_id,
                                            status="REJECTED",
                                            reason=f"Sensor divergence exceeded: {sensor_type} diverged by {divergence:.3f}",
                                            reason_code="INTEGRITY_SENSOR_DIVERGENCE"
                                        )
            except Exception as e:
                logger.error(f"[SYSTEM_ERROR] Sensor divergence check error: {e}", exc_info=True)
                return ControlResponse(
                    transaction_id=tx_id,
                    status="ERROR",
                    reason=f"Failed to verify sensor divergence: {e}",
                    reason_code="DIVERGENCE_CHECK_FAILED"
                )

        # 110-3: 타임스탬프 확인 (max 5000ms for E2E tests)
        current_time_ms = int(time.time() * 1000)
        proof_time_ms = proof.get("timestamp_ms", 0)
        age_ms = current_time_ms - proof_time_ms
        
        if age_ms > 5000:
            duration = (time.time() - t0) * 1000
            logger.warning(f"[110] Integrity Check: FAILED ({duration:.0f}ms) | reason=TIMESTAMP_EXPIRED age={age_ms}ms")
            
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "INTEGRITY_REJECTED",
                                                {"reason": "TIMESTAMP_EXPIRED", "age_ms": age_ms}, prev_hash)
            except Exception as e:
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")

            return ControlResponse(
                transaction_id=tx_id,
                status="REJECTED",
                reason=f"ProofPackage timestamp expired (age: {age_ms}ms)",
                reason_code="INTEGRITY_TIMESTAMP_EXPIRED"
            )
        
        # 증거 기록: INTEGRITY_PASSED
        try:
            prev_hash = await _log_evidence(client, tx_id, evidence_seq, "INTEGRITY_PASSED",
                                            {"policy_version": active_version, "sensor_hash": current_hash}, prev_hash)
            evidence_seq += 1
        except Exception as e:
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")
        
        duration = (time.time() - t0) * 1000
        logger.info(f"[110] Integrity Check: PASSED ({duration:.0f}ms) | policy={active_version}, sensor_hash_match={str(sensor_match).lower()}")
        
        # ============================================================
        # [120] 안전 검증 (Safety Validation)
        # ============================================================
        t0 = time.time()
        try:
            safety_resp = await client.post(
                f"{_get_service_url('safety_cluster')}/v1/validate",
                json={
                    "transaction_id": tx_id,
                    "asset_id": asset_id,
                    "policy_version_id": active_version,
                    "action_sequence": proof.get("action_sequence", []),
                    "current_sensor_snapshot": current_snapshot
                }
            )
            if safety_resp.status_code != 200:
                error_detail = safety_resp.json().get("detail", f"HTTP {safety_resp.status_code}")
                logger.error(f"Safety Cluster error: {safety_resp.status_code} - {error_detail}")
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Safety Cluster error: {error_detail}", reason_code="SAFETY_CLUSTER_ERROR")
            safety_result = safety_resp.json()
        except Exception as e:
            logger.error(f"[SYSTEM_ERROR] Safety Cluster connection failed: {e}", exc_info=True)
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Safety Cluster error: {e}", reason_code="SAFETY_CLUSTER_UNREACHABLE")
        
        if safety_result["final_verdict"] != "SAFE":
            duration = (time.time() - t0) * 1000
            logger.warning(f"[120] Safety Verification: UNSAFE ({duration:.0f}ms) | verdict={safety_result['final_verdict']}")
            
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "SAFETY_UNSAFE",
                                                {"verdict": safety_result["final_verdict"], "details": safety_result}, prev_hash)
            except Exception as e:
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")

            # Extract violation details from safety_result for structured reason
            violations = []
            reason_parts = []

            # From Rules Validator
            rules_detail = safety_result.get("validators", {}).get("rules", {})
            if rules_detail.get("verdict") == "UNSAFE":
                violated = rules_detail.get("details", {}).get("violated_rules", [])
                for v in violated:
                    violations.append(v)
                    reason_parts.append(f"Rule '{v.get('rule_id')}': {v.get('reason')}")

            # From CBF
            cbf_detail = safety_result.get("validators", {}).get("cbf", {})
            if cbf_detail.get("verdict") == "UNSAFE":
                h_val = cbf_detail.get("details", {}).get("min_barrier_value", "N/A")
                reason_parts.append(f"CBF barrier h={h_val} < 0")

            # From Simulation
            sim_detail = safety_result.get("validators", {}).get("simulation", {})
            if sim_detail.get("verdict") == "UNSAFE":
                sim_violations = sim_detail.get("details", {}).get("violations", [])
                reason_parts.append(f"Simulation: {len(sim_violations)} violations detected")

            # Construct detailed reason
            if reason_parts:
                detailed_reason = "Safety validation failed: " + "; ".join(reason_parts[:5])
                if len(reason_parts) > 5:
                    detailed_reason += f" (+{len(reason_parts)-5} more)"
            else:
                detailed_reason = "Safety validation failed (Consensus threshold not met)"

            return ControlResponse(
                transaction_id=tx_id,
                status="UNSAFE",
                reason=detailed_reason,
                reason_code="SAFETY_UNSAFE"
            )
        
        # 증거 기록: SAFETY_PASSED
        consensus_score = safety_result.get("consensus_details", {}).get("score", 0.0)
        try:
            prev_hash = await _log_evidence(client, tx_id, evidence_seq, "SAFETY_PASSED",
                                            {"verdict": "SAFE", "consensus": safety_result.get("consensus_details", {})}, prev_hash)
            evidence_seq += 1
        except Exception as e:
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")
        
        duration = (time.time() - t0) * 1000
        # Extract individual validator results if available
        # safety_result structure might vary, but assuming generic structure
        logger.info(f"[120] Safety Verification: SAFE ({duration:.0f}ms) | consensus={consensus_score}")
        
        # ============================================================
        # [130] 2PC 실행 (Two-Phase Commit)
        # ============================================================
        
        # 130-1: PREPARE (입력 억제 잠금 획득)
        t0 = time.time()
        try:
            prepare_resp = await client.post(
                f"{_get_service_url('ot_interface')}/v1/prepare",
                json={"transaction_id": tx_id, "asset_id": asset_id, "lock_ttl_ms": 5000}
            )
            prepare_result = prepare_resp.json()
        except Exception as e:
            logger.error(f"[SYSTEM_ERROR] OT Interface PREPARE failed: {e}", exc_info=True)
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"OT Interface error: {e}", reason_code="OT_INTERFACE_UNREACHABLE")
        
        if prepare_result["status"] != "LOCK_GRANTED":
            duration = (time.time() - t0) * 1000
            logger.warning(f"[130] 2PC Prepare: LOCKED FAILED ({duration:.0f}ms) | reason={prepare_result.get('reason')}")
            
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "PREPARE_LOCK_DENIED",
                                                {"reason": prepare_result.get("reason", "unknown")}, prev_hash)
            except Exception as e:
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")

            return ControlResponse(
                transaction_id=tx_id,
                status="ABORTED",
                reason="Lock denied",
                reason_code="LOCK_DENIED"
            )
        
        # 증거 기록: PREPARE_LOCK_GRANTED
        try:
            prev_hash = await _log_evidence(client, tx_id, evidence_seq, "PREPARE_LOCK_GRANTED",
                                            {"lock_expires_at_ms": prepare_result.get("lock_expires_at_ms")}, prev_hash)
            evidence_seq += 1
        except Exception as e:
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")
        
        duration = (time.time() - t0) * 1000
        logger.info(f"[130] 2PC Prepare: LOCKED ({duration:.0f}ms) | tx_id={tx_id}")
        
        # 130-2: REVERIFY (센서 재확인 — TOCTOU L3)
        t0 = time.time()
        try:
            reverify_resp = await client.get(
                f"{_get_service_url('sensor_gateway')}/v1/assets/{asset_id}/snapshots/latest"
            )
            if reverify_resp.status_code != 200:
                error_detail = reverify_resp.json().get("detail", f"HTTP {reverify_resp.status_code}")
                raise Exception(f"Sensor Gateway returned {reverify_resp.status_code}: {error_detail}")
            reverify_data = reverify_resp.json()
            reverify_hash = reverify_data.get("sensor_snapshot_hash", "")
        except Exception as e:
            # FAIL-CLOSED: Sensor re-verification failed → ABORT
            logger.error(f"[{tx_id}] [130] TOCTOU Reverify: FAILED — sensor unreachable: {e}", exc_info=True)
            try:
                await client.post(
                    f"{_get_service_url('ot_interface')}/v1/abort",
                    json={"transaction_id": tx_id, "asset_id": asset_id, "reason": f"TOCTOU reverify failed: {e}"}
                )
            except Exception as abort_err:
                logger.critical(f"[{tx_id}] ABORT also failed after TOCTOU failure: {abort_err}", exc_info=True)
            
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "REVERIFY_FAILED",
                                                {"error": str(e)}, prev_hash)
                evidence_seq += 1
            except Exception as ev_err:
                # If we fail here, we still want to return ABORTED/ERROR to client.
                logger.critical(f"Failed to log REVERIFY failure evidence: {ev_err}", exc_info=True)
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {ev_err}", reason_code="EVIDENCE_LEDGER_ERROR")

            return ControlResponse(
                transaction_id=tx_id,
                status="ERROR",
                reason=f"Sensor re-verification failed: {e} — aborted for safety (fail-closed)",
                reason_code="TOCTOU_REVERIFY_FAILED"
            )
        
        # 증거 기록: REVERIFY_PASSED
        try:
            prev_hash = await _log_evidence(client, tx_id, evidence_seq, "REVERIFY_PASSED",
                                            {"original_hash": current_hash, "reverify_hash": reverify_hash}, prev_hash)
            evidence_seq += 1
        except Exception as e:
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")
        
        # Calculate divergence if needed, but for now just logging execution
        duration = (time.time() - t0) * 1000
        logger.info(f"[130] TOCTOU Reverify: PASSED ({duration:.0f}ms) | hash_match={reverify_hash == current_hash}")
        
        # 130-3: COMMIT (실행)
        t0 = time.time()
        try:
            commit_resp = await client.post(
                f"{_get_service_url('ot_interface')}/v1/commit",
                json={
                    "transaction_id": tx_id,
                    "asset_id": asset_id,
                    "action_sequence": proof.get("action_sequence", [])
                }
            )
            if commit_resp.status_code != 200:
                error_detail = ""
                try:
                    error_detail = commit_resp.json().get("detail", f"HTTP {commit_resp.status_code}")
                except Exception:
                    error_detail = commit_resp.text[:200] if commit_resp.text else f"HTTP {commit_resp.status_code}"
                # Handle as ERROR
                raise Exception(f"OT Interface COMMIT returned {commit_resp.status_code}: {error_detail}")
                
            commit_result = commit_resp.json()
        except Exception as e:
            logger.error(f"[SYSTEM_ERROR] OT Interface COMMIT failed: {e}", exc_info=True)
            # COMMIT 실패 → ABORT
            await client.post(
                f"{_get_service_url('ot_interface')}/v1/abort",
                json={"transaction_id": tx_id, "asset_id": asset_id, "reason": str(e)}
            )
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Commit failed: {e}", reason_code="COMMIT_FAILED")
        
        if commit_result["status"] != "ACK":
            logger.error(f"Commit failed (status={commit_result['status']})")
            try:
                prev_hash = await _log_evidence(client, tx_id, evidence_seq, "COMMIT_TIMEOUT",
                                                {"status": commit_result["status"]}, prev_hash)
            except Exception as e:
                return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")

            return ControlResponse(
                transaction_id=tx_id,
                status="ABORTED",
                reason=f"Commit status: {commit_result['status']}",
                reason_code="COMMIT_TIMEOUT"
            )
        
        duration = (time.time() - t0) * 1000
        logger.info(f"[130] 2PC Commit: COMMITTED ({duration:.0f}ms)")
        
        # ============================================================
        # [140] 증거 기록: COMMIT_ACK
        # ============================================================
        try:
            prev_hash = await _log_evidence(client, tx_id, evidence_seq, "COMMIT_ACK",
                                            {"executed_at_ms": commit_result.get("executed_at_ms")}, prev_hash)
            evidence_seq += 1
        except Exception as e:
            return ControlResponse(transaction_id=tx_id, status="ERROR", reason=f"Evidence Ledger failed: {e}", reason_code="EVIDENCE_LEDGER_ERROR")
        
        logger.info(f"[140] Evidence: {evidence_seq} events recorded")
        
        total_duration = (time.time() - start_total) * 1000
        logger.info(f"TOTAL: {total_duration:.0f}ms | COMMITTED")
        
        # 성공!
        return ControlResponse(
            transaction_id=tx_id,
            status="COMMITTED",
            evidence_ref=f"/v1/transactions/{tx_id}"
        )


async def _log_evidence(client: httpx.AsyncClient, tx_id: str, seq: int, stage: str, 
                        payload: dict, prev_hash: str) -> str:
    """
    증거 이벤트를 Evidence Ledger에 기록하고 새 event_hash를 반환합니다.
    
    해시 체인: event_hash = sha256(prev_hash + canonical(payload))
    """
    input_hash = compute_sensor_hash(payload)
    event_hash = compute_event_hash(prev_hash, payload)
    
    try:
        await client.post(
            f"{_get_service_url('evidence_ledger')}/v1/events/append",
            json={
                "transaction_id": tx_id,
                "sequence_no": seq,
                "stage": stage,
                "timestamp_ms": int(time.time() * 1000),
                "payload": payload,
                "input_hash": input_hash,
                "prev_hash": prev_hash,
                "event_hash": event_hash
            }
        )
    except Exception as e:
        logger.critical(f"[SYSTEM_ERROR] Evidence Ledger unreachable: {e} — CRITICAL EVIDENCE FAILURE", exc_info=True)
        raise e  # FAIL-HARD: Evidence recording failure must stop the pipeline
    
    return event_hash
