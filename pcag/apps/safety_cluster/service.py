"""
Safety Validation Cluster 서비스 로직
======================================
3개의 검증기를 실행하고 Consensus Engine으로 최종 판정합니다.

PCAG 파이프라인 [120]:
  Rules Validator (121) ─┐
  CBF Safety Filter (122) ├─→ Consensus Engine (124) → 최종 판정
  Simulation (123) ───────┘

conda pcag 환경에서 실행.
"""
import time
import logging
import httpx
import os
from typing import List, Dict, Any, Union

from pcag.core.services.rules_validator import validate_rules
from pcag.core.services.cbf_validator import StaticCBFValidator
from pcag.core.services.consensus_engine import evaluate_consensus
from pcag.plugins.simulation.none_backend import NoneBackend
from pcag.core.models.common import (
    Rule, ValidatorVerdict, ConsensusConfig, ConsensusMode
)
from pcag.core.utils.config_loader import get_cbf_mappings, get_service_urls

logger = logging.getLogger(__name__)

# CBF Validator 인스턴스 (서버 수명 동안 유지)
_cbf_validator = StaticCBFValidator()

# Simulation Backend 초기화
# PCAG_SIMULATION_BACKEND 환경 변수에 따라 백엔드 선택
sim_backend_type = os.environ.get("PCAG_SIMULATION_BACKEND", "none").lower()

# 여기서는 초기화만 하고 실제 사용은 run_safety_validation에서 처리
# Isaac Sim은 전역 싱글톤을 사용하므로 여기서 초기화하지 않음
_sim_backend = NoneBackend()
if sim_backend_type != "isaac":
    logger.info("Using NoneBackend (simulation disabled).")
    _sim_backend.initialize({})

def _get_policy_store_url():
    urls = get_service_urls()
    url = urls.get("policy_store")
    if not url:
        raise RuntimeError("Policy Store URL not configured in services.yaml")
    return url



def run_safety_validation(
    transaction_id: str,
    asset_id: str,
    policy_version_id: str,
    action_sequence: list[dict],
    current_sensor_snapshot: dict
) -> dict:
    """
    안전 검증 실행 — 3개 검증기 + Consensus
    
    1. Policy Store에서 AssetPolicyProfile 조회
    2. Rules Validator 실행
    3. CBF Safety Filter 실행
    4. Simulation Validator 실행
    5. Consensus Engine으로 최종 판정
    
    Returns:
        SafetyValidateResponse 형태의 dict.
        Contains detailed breakdown for structured reasoning:
          - validators.rules.details.violated_rules
          - validators.cbf.details.min_barrier_value
          - validators.simulation.details.violations
          - consensus_details (score, explanation)
    """
    start_time = time.time()
    
    # ============================================================
    # 1. Policy Store에서 AssetPolicyProfile 조회
    # ============================================================
    try:
        policy_resp = httpx.get(
            f"{_get_policy_store_url()}/v1/policies/{policy_version_id}/assets/{asset_id}",
            timeout=5.0
        )
        if policy_resp.status_code != 200:
            logger.critical(f"[SYSTEM_ERROR] Policy Store error {policy_resp.status_code} for {asset_id}", exc_info=True)
            raise RuntimeError(f"Policy Store returned {policy_resp.status_code}")
            
        asset_profile = policy_resp.json().get("profile", {})
    except Exception as e:
        logger.critical(f"[SYSTEM_ERROR] Policy Store unreachable: {e}", exc_info=True)
        raise e  # Fail-Hard: Do not return UNSAFE, let system error propagate
    
    # Validate action_types
    allowed_actions = asset_profile.get("allowed_action_types", [])
    if allowed_actions:  # Only validate if the policy defines allowed types
        for action in action_sequence:
            action_type = action.get("action_type", "")
            if action_type not in allowed_actions:
                logger.error(f"Invalid action_type '{action_type}' for asset {asset_id}. "
                            f"Allowed: {allowed_actions}")
                return {
                    "transaction_id": transaction_id,
                    "final_verdict": "UNSAFE",
                    "validators": {},
                    "consensus_details": {
                        "mode": "FAIL_CLOSED",
                        "explanation": f"Invalid action_type '{action_type}'. Allowed: {allowed_actions}"
                    }
                }

    # 프로필에서 설정 추출
    sil_level = asset_profile.get("sil_level", 2)
    consensus_config_dict = asset_profile.get("consensus", {})
    ruleset_raw = asset_profile.get("ruleset", [])
    
    # Ruleset을 Rule 객체로 변환
    # rules_validator는 Rule 객체 리스트를 기대함 (속성 접근 사용)
    ruleset = []
    if ruleset_raw:
        for r in ruleset_raw:
            if isinstance(r, dict):
                try:
                    ruleset.append(Rule(**r))
                except Exception as e:
                    logger.warning(f"Skipping invalid rule in profile: {e}")
            else:
                ruleset.append(r)
    
    # CBF 매핑 (config에서 로드)
    cbf_state_mappings = _get_cbf_state_mappings()
    if not cbf_state_mappings:
        logger.critical("[SYSTEM_ERROR] CBF mappings not found in config", exc_info=True)
        raise RuntimeError("CBF mappings configuration missing")
    
    # ============================================================
    # 2. Rules Validator (121) 실행
    # ============================================================
    t0 = time.time()
    rules_result = validate_rules(
        sensor_snapshot=current_sensor_snapshot,
        action_sequence=action_sequence,
        ruleset=ruleset
    )
    rules_duration = (time.time() - t0) * 1000
    
    rules_verdict = {
        "verdict": rules_result.verdict,
        "details": rules_result.details
    }
    
    logger.info(f"[Validator] Rules: {rules_result.verdict} ({rules_duration:.1f}ms)", 
                extra={"extra_fields": {"validator": "rules", "verdict": rules_result.verdict, "duration_ms": rules_duration}})
    
    # ============================================================
    # 3. CBF Safety Filter (122) 실행
    # ============================================================
    t0 = time.time()
    cbf_result = _cbf_validator.validate_safety(
        current_state=current_sensor_snapshot,
        action_sequence=action_sequence,
        ruleset=ruleset,
        cbf_state_mappings=cbf_state_mappings
    )
    cbf_duration = (time.time() - t0) * 1000
    
    cbf_verdict = {
        "verdict": cbf_result["verdict"],
        "details": cbf_result.get("details", {})
    }
    
    h_val = cbf_result.get("details", {}).get("h_value", "N/A")
    logger.info(f"[Validator] CBF: {cbf_result['verdict']} ({cbf_duration:.1f}ms) | h={h_val}",
                extra={"extra_fields": {"validator": "cbf", "verdict": cbf_result['verdict'], "duration_ms": cbf_duration, "h_value": h_val}})
    
    # ============================================================
    # 4. Simulation Validator (123) 실행
    # ============================================================
    t0 = time.time()
    # Get simulation engine from policy
    sim_config = asset_profile.get("simulation", {})
    sim_engine = sim_config.get("engine", "none")

    try:
        if sim_engine == "ode_solver":
            from pcag.plugins.simulation.ode_solver import ODESolverBackend
            sim_backend = ODESolverBackend()
            sim_backend.initialize(sim_config)
        elif sim_engine == "isaac_sim":
            from pcag.apps.safety_cluster.main import get_isaac_backend
            isaac = get_isaac_backend()
            if isaac and isaac.is_initialized():
                sim_backend = isaac
                # logger.info("Using Isaac Sim Worker process (proxy)") # Too verbose
            else:
                logger.critical("Isaac Sim required but not available. FAIL-HARD.")
                raise RuntimeError("Simulation engine 'isaac_sim' requested but backend not connected")
        elif sim_engine == "discrete_event":
            from pcag.plugins.simulation.discrete_event import DiscreteEventBackend
            sim_backend = DiscreteEventBackend()
            sim_backend.initialize(sim_config)
        elif sim_engine == "none":
            # Explicitly requested 'none' backend
            sim_backend = _sim_backend
        else:
            # [Fix D12] Do not silently fallback to NoneBackend. Raise error for unknown engines.
            logger.critical(f"Unknown simulation engine '{sim_engine}' requested. FAIL-HARD.")
            raise RuntimeError(f"Simulation engine '{sim_engine}' is not supported. Use 'ode_solver', 'isaac_sim', 'discrete_event', or 'none'.")
    except Exception as e:
        logger.critical(f"[SYSTEM_ERROR] Failed to initialize simulation backend '{sim_engine}': {e}", exc_info=True)
        raise e  # Fail-Hard: Do not fallback

    try:
        # Convert ruleset to dicts for serialization (especially for multiprocessing queues)
        ruleset_dicts = []
        for r in ruleset:
            if hasattr(r, "model_dump"):
                ruleset_dicts.append(r.model_dump())
            elif hasattr(r, "dict"):
                ruleset_dicts.append(r.dict())
            else:
                ruleset_dicts.append(r)

        sim_constraints = {
            "ruleset": ruleset_dicts,
            "world_ref": sim_config.get("world_ref"),
            "workspace_limits": sim_config.get("workspace_limits"),
            "torque_limits": sim_config.get("torque_limits"),
            "joint_limits": sim_config.get("joint_limits")
        }
        
        sim_result = sim_backend.validate_trajectory(
            current_state=current_sensor_snapshot,
            action_sequence=action_sequence,
            constraints=sim_constraints
        )
    except Exception as e:
        logger.critical(f"[SYSTEM_ERROR] Simulation validation failed: {e}", exc_info=True)
        raise e  # Fail-Hard

    sim_duration = (time.time() - t0) * 1000
    sim_verdict = {
        "verdict": sim_result["verdict"],
        "details": sim_result.get("details", sim_result.get("common", {}))
    }
    
    logger.info(f"[Validator] Sim: {sim_result['verdict']} ({sim_duration:.1f}ms) | engine={sim_engine}",
                extra={"extra_fields": {"validator": "sim", "verdict": sim_result['verdict'], "duration_ms": sim_duration, "engine": sim_engine}})
    
    # ============================================================
    # 5. Consensus Engine (124) 실행
    # ============================================================
    # ValidatorVerdict 객체 생성
    rules_vv = ValidatorVerdict(verdict=rules_verdict["verdict"], details=rules_verdict["details"])
    cbf_vv = ValidatorVerdict(verdict=cbf_verdict["verdict"], details=cbf_verdict["details"])
    sim_vv = ValidatorVerdict(verdict=sim_verdict["verdict"], details=sim_verdict["details"])
    
    # ConsensusConfig 생성
    consensus_mode_str = consensus_config_dict.get("mode", "AUTO")
    weights = consensus_config_dict.get("weights", {"rules": 0.4, "cbf": 0.35, "sim": 0.25})
    threshold = consensus_config_dict.get("threshold", 0.5)
    on_sim_indet = consensus_config_dict.get("on_sim_indeterminate", "RENORMALIZE")
    
    # Enum 변환 안전 처리
    try:
        consensus_mode = ConsensusMode(consensus_mode_str)
    except ValueError:
        logger.warning(f"Invalid consensus mode {consensus_mode_str}, defaulting to AUTO")
        consensus_mode = ConsensusMode.AUTO

    consensus_config = ConsensusConfig(
        mode=consensus_mode,
        weights=weights,
        threshold=threshold,
        on_sim_indeterminate=on_sim_indet
    )
    
    consensus_result = evaluate_consensus(
        sil_level=sil_level,
        config=consensus_config,
        rules_verdict=rules_vv,
        cbf_verdict=cbf_vv,
        sim_verdict=sim_vv
    )
    
    total_time = (time.time() - start_time) * 1000
    
    # Detailed Consensus Log
    logger.info(f"Consensus: {consensus_result.final_verdict} (score={consensus_result.score:.2f}) | {transaction_id}", extra={"extra_fields": {
        "transaction_id": transaction_id,
        "final_verdict": consensus_result.final_verdict,
        "total_duration_ms": total_time,
        "rules": rules_verdict["verdict"],
        "cbf": cbf_verdict["verdict"],
        "sim": sim_verdict["verdict"],
        "score": round(consensus_result.score, 2),
        "threshold": threshold
    }})
    
    return {
        "transaction_id": transaction_id,
        "final_verdict": consensus_result.final_verdict,
        "validators": {
            "rules": rules_verdict,
            "cbf": cbf_verdict,
            "simulation": sim_verdict
        },
        "consensus_details": {
            "mode": consensus_result.mode_used,
            "weights_used": consensus_result.weights_used,
            "score": consensus_result.score,
            "threshold": consensus_result.threshold,
            "explanation": consensus_result.explanation
        }
    }


def _get_default_profile(asset_id: str) -> dict:
    """
    [DEPRECATED] Policy Store 접속 불가 시 사용할 기본 프로필
    Note: Production fix applied to FAIL-CLOSED instead of using defaults.
    """
    raise RuntimeError("Using default profile is forbidden in production (FAIL-CLOSED enforced).")


def _get_cbf_state_mappings():
    """CBF 상태 매핑을 config에서 로드"""
    return get_cbf_mappings()
