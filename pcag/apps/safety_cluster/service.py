"""
Safety Cluster의 오케스트레이션 계층.

이 모듈은 자산 정책을 읽고, Rules / CBF / Simulation 검증기를 실행한 뒤
SIL 기반 consensus로 최종 SAFE / UNSAFE를 계산한다.

중요한 점은 "병렬 검증"과 "Isaac Sim 제약"을 동시에 만족시키는 구조라는 점이다.
- Rules / CBF는 로컬 스레드에서 병렬 실행
- Simulation은 백엔드 종류에 따라 분기
- Isaac Sim은 반드시 별도 worker/process 경유
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from pcag.core.models.common import ConsensusConfig, ConsensusMode, Rule, ValidatorVerdict
from pcag.core.services.cbf_validator import StaticCBFValidator
from pcag.core.services.consensus_engine import evaluate_consensus
from pcag.core.services.rules_validator import validate_rules
from pcag.core.utils.config_loader import get_cbf_mappings, get_service_urls
from pcag.plugins.simulation.none_backend import NoneBackend
from pcag.plugins.simulation.isaac_runtime_shell import build_runtime_sim_config

logger = logging.getLogger(__name__)

sim_backend_type = os.environ.get("PCAG_SIMULATION_BACKEND", "none").lower()
_sim_backend = NoneBackend()
if sim_backend_type != "isaac":
    logger.info("Using NoneBackend (simulation disabled).")
    _sim_backend.initialize({})


def _get_policy_store_url() -> str:
    urls = get_service_urls()
    url = urls.get("policy_store")
    if not url:
        raise RuntimeError("Policy Store URL not configured in services.yaml")
    return url


def _fetch_asset_profile(policy_version_id: str, asset_id: str) -> dict[str, Any]:
    policy_resp = httpx.get(
        f"{_get_policy_store_url()}/v1/policies/{policy_version_id}/assets/{asset_id}",
        timeout=5.0,
    )
    if policy_resp.status_code != 200:
        logger.critical("[SYSTEM_ERROR] Policy Store error %s for %s", policy_resp.status_code, asset_id)
        raise RuntimeError(f"Policy Store returned {policy_resp.status_code}")
    return policy_resp.json().get("profile", {})


def _build_ruleset(ruleset_raw: list[Any]) -> list[Rule | dict[str, Any]]:
    ruleset: list[Rule | dict[str, Any]] = []
    for item in ruleset_raw or []:
        if isinstance(item, dict):
            try:
                ruleset.append(Rule(**item))
            except Exception as exc:
                logger.warning("Skipping invalid rule in profile: %s", exc)
        else:
            ruleset.append(item)
    return ruleset


def _serialize_ruleset(ruleset: list[Rule | dict[str, Any]]) -> list[dict[str, Any] | Any]:
    serialized: list[dict[str, Any] | Any] = []
    for rule in ruleset:
        if hasattr(rule, "model_dump"):
            serialized.append(rule.model_dump())
        elif hasattr(rule, "dict"):
            serialized.append(rule.dict())
        else:
            serialized.append(rule)
    return serialized


def _resolve_simulation_backend(sim_config: dict[str, Any]) -> tuple[Any, str]:
    # simulation.engine은 정책 문서가 선언하는 실행 방식이다.
    # 여기서 잘못된 엔진을 허용하면 Safety Cluster 전체 semantics가 흔들리므로 fail-hard로 처리한다.
    sim_engine = sim_config.get("engine", "none")

    if sim_engine == "ode_solver":
        from pcag.plugins.simulation.ode_solver import ODESolverBackend

        sim_backend = ODESolverBackend()
        sim_backend.initialize(sim_config)
        return sim_backend, sim_engine

    if sim_engine == "isaac_sim":
        from pcag.apps.safety_cluster.main import get_isaac_backend

        isaac = get_isaac_backend()
        if isaac and isaac.is_initialized():
            return isaac, sim_engine
        logger.critical("Isaac Sim required but not available. FAIL-HARD.")
        raise RuntimeError("Simulation engine 'isaac_sim' requested but backend not connected")

    if sim_engine == "discrete_event":
        from pcag.plugins.simulation.discrete_event import DiscreteEventBackend

        sim_backend = DiscreteEventBackend()
        sim_backend.initialize(sim_config)
        return sim_backend, sim_engine

    if sim_engine == "none":
        return _sim_backend, sim_engine

    logger.critical("Unknown simulation engine '%s' requested. FAIL-HARD.", sim_engine)
    raise RuntimeError(
        f"Simulation engine '{sim_engine}' is not supported. Use 'ode_solver', 'isaac_sim', 'discrete_event', or 'none'."
    )


def _run_rules_validator(
    current_sensor_snapshot: dict[str, Any],
    action_sequence: list[dict[str, Any]],
    ruleset: list[Rule | dict[str, Any]],
) -> dict[str, Any]:
    # Rules 검증은 정책 ruleset을 현재 센서값/행동 파라미터에 직접 대조하는
    # 가장 설명 가능한 1차 안전 필터다.
    started = time.time()
    result = validate_rules(
        sensor_snapshot=current_sensor_snapshot,
        action_sequence=action_sequence,
        ruleset=ruleset,
    )
    duration_ms = (time.time() - started) * 1000
    verdict = {"verdict": result.verdict, "details": result.details}
    logger.info(
        "[Validator] Rules: %s (%.1fms)",
        result.verdict,
        duration_ms,
        extra={"extra_fields": {"validator": "rules", "verdict": result.verdict, "duration_ms": duration_ms}},
    )
    return verdict


def _run_cbf_validator(
    current_sensor_snapshot: dict[str, Any],
    action_sequence: list[dict[str, Any]],
    ruleset: list[Rule | dict[str, Any]],
    cbf_state_mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    # CBF 검증은 연속 상태를 barrier 관점에서 본다.
    # 전역 싱글턴 공유 대신 요청마다 validator를 새로 만들어 병렬 실행 시 상태 충돌을 피한다.
    started = time.time()
    validator = StaticCBFValidator()
    result = validator.validate_safety(
        current_state=current_sensor_snapshot,
        action_sequence=action_sequence,
        ruleset=ruleset,
        cbf_state_mappings=cbf_state_mappings,
    )
    duration_ms = (time.time() - started) * 1000
    verdict = {"verdict": result["verdict"], "details": result.get("details", {})}
    min_barrier = verdict["details"].get("min_barrier_value", "N/A")
    logger.info(
        "[Validator] CBF: %s (%.1fms) | min_barrier=%s",
        result["verdict"],
        duration_ms,
        min_barrier,
        extra={
            "extra_fields": {
                "validator": "cbf",
                "verdict": result["verdict"],
                "duration_ms": duration_ms,
                "min_barrier_value": min_barrier,
            }
        },
    )
    return verdict


def _run_simulation_validator(
    current_sensor_snapshot: dict[str, Any],
    action_sequence: list[dict[str, Any]],
    ruleset: list[Rule | dict[str, Any]],
    sim_config: dict[str, Any],
    runtime_context: dict[str, Any] | None,
) -> dict[str, Any]:
    # Simulation 검증은 가장 비용이 큰 단계다.
    # 하지만 trajectory 수준의 위험을 잡을 수 있어서, Rules/CBF와 성격이 다르다.
    started = time.time()
    effective_sim_config = build_runtime_sim_config(sim_config, runtime_context)
    sim_backend, sim_engine = _resolve_simulation_backend(effective_sim_config)
    sim_constraints = {
        "ruleset": _serialize_ruleset(ruleset),
        "world_ref": effective_sim_config.get("world_ref"),
        "workspace_limits": effective_sim_config.get("workspace_limits"),
        "torque_limits": effective_sim_config.get("torque_limits"),
        "joint_limits": effective_sim_config.get("joint_limits"),
        "collision": effective_sim_config.get("collision"),
        "runtime_context": runtime_context,
    }
    result = sim_backend.validate_trajectory(
        current_state=current_sensor_snapshot,
        action_sequence=action_sequence,
        constraints=sim_constraints,
    )
    duration_ms = (time.time() - started) * 1000
    verdict = {"verdict": result["verdict"], "details": result.get("details", result.get("common", {}))}
    logger.info(
        "[Validator] Sim: %s (%.1fms) | engine=%s",
        result["verdict"],
        duration_ms,
        sim_engine,
        extra={
            "extra_fields": {
                "validator": "sim",
                "verdict": result["verdict"],
                "duration_ms": duration_ms,
                "engine": sim_engine,
            }
        },
    )
    return verdict


def _run_validators_parallel(
    *,
    asset_id: str,
    current_sensor_snapshot: dict[str, Any],
    action_sequence: list[dict[str, Any]],
    ruleset: list[Rule | dict[str, Any]],
    cbf_state_mappings: list[dict[str, Any]],
    sim_config: dict[str, Any],
    runtime_context: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    # fan-out / fan-in 구조:
    # - 세 검증기를 동시에 시작해 전체 지연을 줄이고
    # - 하나라도 내부 예외가 나면 결과를 조합하지 않고 즉시 fail-hard 처리한다.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix=f"pcag-safety-{asset_id}") as executor:
        futures = {
            "rules": executor.submit(_run_rules_validator, current_sensor_snapshot, action_sequence, ruleset),
            "cbf": executor.submit(_run_cbf_validator, current_sensor_snapshot, action_sequence, ruleset, cbf_state_mappings),
            "simulation": executor.submit(
                _run_simulation_validator,
                current_sensor_snapshot,
                action_sequence,
                ruleset,
                sim_config,
                runtime_context,
            ),
        }

        results: dict[str, dict[str, Any]] = {}
        failures: list[tuple[str, Exception]] = []

        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                failures.append((name, exc))

    if failures:
        failing_validator, exc = failures[0]
        logger.critical(
            "[SYSTEM_ERROR] Validator '%s' failed during parallel execution: %s",
            failing_validator,
            exc,
            exc_info=True,
        )
        raise exc

    return results


def _build_consensus_config(consensus_config_dict: dict[str, Any]) -> tuple[ConsensusConfig, float | None]:
    # 정책 문서가 비정상 값을 넣어도 Safety Cluster가 조용히 이상 동작하지 않도록
    # 잘못된 mode는 AUTO로 되돌린다.
    consensus_mode_str = consensus_config_dict.get("mode", "AUTO")
    weights = consensus_config_dict.get("weights", {"rules": 0.4, "cbf": 0.35, "sim": 0.25})
    threshold = consensus_config_dict.get("threshold", 0.5)
    on_sim_indet = consensus_config_dict.get("on_sim_indeterminate", "RENORMALIZE")

    try:
        consensus_mode = ConsensusMode(consensus_mode_str)
    except ValueError:
        logger.warning("Invalid consensus mode %s, defaulting to AUTO", consensus_mode_str)
        consensus_mode = ConsensusMode.AUTO

    return (
        ConsensusConfig(
            mode=consensus_mode,
            weights=weights,
            threshold=threshold,
            on_sim_indeterminate=on_sim_indet,
        ),
        threshold,
    )


def run_safety_validation(
    transaction_id: str,
    asset_id: str,
    policy_version_id: str,
    action_sequence: list[dict[str, Any]],
    current_sensor_snapshot: dict[str, Any],
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run safety validation and return a Gateway-facing response payload.

    Flow:
      1. Load the asset policy profile.
      2. Validate requested action types.
      3. Run rules, CBF, and simulation validators in parallel.
      4. Apply SIL-based consensus to the collected verdicts.
    """
    start_time = time.time()

    try:
        asset_profile = _fetch_asset_profile(policy_version_id, asset_id)
    except Exception as exc:
        logger.critical("[SYSTEM_ERROR] Policy Store unreachable: %s", exc, exc_info=True)
        raise

    # action_type 화이트리스트는 규칙 검증보다 앞에서 막는다.
    # 허용되지 않은 명령을 validator까지 보내지 않는 것이 fail-closed 측면에서 더 안전하다.
    allowed_actions = asset_profile.get("allowed_action_types", [])
    if allowed_actions:
        for action in action_sequence:
            action_type = action.get("action_type", "")
            if action_type not in allowed_actions:
                logger.error(
                    "Invalid action_type '%s' for asset %s. Allowed: %s",
                    action_type,
                    asset_id,
                    allowed_actions,
                )
                return {
                    "transaction_id": transaction_id,
                    "final_verdict": "UNSAFE",
                    "validators": {},
                    "consensus_details": {
                        "mode": "FAIL_CLOSED",
                        "explanation": f"Invalid action_type '{action_type}'. Allowed: {allowed_actions}",
                    },
                }

    sil_level = asset_profile.get("sil_level", 2)
    consensus_config_dict = asset_profile.get("consensus", {})
    ruleset = _build_ruleset(asset_profile.get("ruleset", []))
    sim_config = asset_profile.get("simulation", {})

    # CBF state mapping은 센서 필드를 barrier 상태벡터에 매핑하는 계약이다.
    # 이 설정이 없으면 CBF 결과 자체가 의미 없어지므로 바로 중단한다.
    cbf_state_mappings = _get_cbf_state_mappings()
    if not cbf_state_mappings:
        logger.critical("[SYSTEM_ERROR] CBF mappings not found in config")
        raise RuntimeError("CBF mappings configuration missing")

    validators = _run_validators_parallel(
        asset_id=asset_id,
        current_sensor_snapshot=current_sensor_snapshot,
        action_sequence=action_sequence,
        ruleset=ruleset,
        cbf_state_mappings=cbf_state_mappings,
        sim_config=sim_config,
        runtime_context=runtime_context,
    )

    # 개별 validator 결과를 공통 계약(ValidatorVerdict)으로 다시 감싼 뒤
    # consensus 엔진에 넘긴다.
    rules_vv = ValidatorVerdict(verdict=validators["rules"]["verdict"], details=validators["rules"]["details"])
    cbf_vv = ValidatorVerdict(verdict=validators["cbf"]["verdict"], details=validators["cbf"]["details"])
    sim_vv = ValidatorVerdict(verdict=validators["simulation"]["verdict"], details=validators["simulation"]["details"])

    consensus_config, threshold = _build_consensus_config(consensus_config_dict)
    consensus_result = evaluate_consensus(
        sil_level=sil_level,
        config=consensus_config,
        rules_verdict=rules_vv,
        cbf_verdict=cbf_vv,
        sim_verdict=sim_vv,
    )

    total_time = (time.time() - start_time) * 1000
    logger.info(
        "Consensus: %s (score=%.2f) | %s",
        consensus_result.final_verdict,
        consensus_result.score,
        transaction_id,
        extra={
            "extra_fields": {
                "transaction_id": transaction_id,
                "final_verdict": consensus_result.final_verdict,
                "total_duration_ms": total_time,
                "rules": validators["rules"]["verdict"],
                "cbf": validators["cbf"]["verdict"],
                "sim": validators["simulation"]["verdict"],
                "score": round(consensus_result.score, 2),
                "threshold": threshold,
            }
        },
    )

    return {
        "transaction_id": transaction_id,
        "final_verdict": consensus_result.final_verdict,
        "validators": validators,
        "consensus_details": {
            "mode": consensus_result.mode_used,
            "weights_used": consensus_result.weights_used,
            "score": consensus_result.score,
            "threshold": consensus_result.threshold,
            "explanation": consensus_result.explanation,
        },
    }


def _get_default_profile(asset_id: str) -> dict[str, Any]:
    """
    [DEPRECATED] Legacy fallback hook kept for compatibility with older tests.
    """
    raise RuntimeError("Using default profile is forbidden in production (FAIL-CLOSED enforced).")


def _get_cbf_state_mappings() -> list[dict[str, Any]]:
    """Load CBF mappings from configuration."""
    return get_cbf_mappings()
