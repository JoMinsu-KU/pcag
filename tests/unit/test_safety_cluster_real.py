"""
Safety Cluster 실제 검증기 통합 테스트
=======================================
Rules Validator + CBF + Simulation(None) + Consensus가
실제로 연결되어 올바른 판정을 내리는지 검증합니다.

Policy Store 접속 없이 기본 프로필을 사용합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_safety_cluster_real.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pcag.apps.safety_cluster.service import run_safety_validation


# 화학 반응기 정책 (Policy Store 없이 직접 주입 테스트)
REACTOR_PROFILE = {
    "asset_id": "reactor_01",
    "sil_level": 2,
    "consensus": {
        "mode": "WEIGHTED",
        "weights": {"rules": 0.4, "cbf": 0.35, "sim": 0.25},
        "threshold": 0.5,
        "on_sim_indeterminate": "RENORMALIZE"
    },
    "ruleset": [
        {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0},
        {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 120.0},
        {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.5, "max": 3.0}
    ],
    "simulation": {"engine": "none"}
}


def _run_with_profile(sensor_snapshot, action_sequence, profile=None):
    """프로필을 직접 주입하여 검증 실행 (Policy Store 우회)"""
    from pcag.apps.safety_cluster import service
    
    # Policy Store 조회를 우회하기 위해 기본 프로필 함수를 교체
    original_fn = service._get_default_profile
    
    # run_safety_validation 내부에서 Policy Store 호출 실패 시 _get_default_profile을 호출함.
    # 하지만 첫 호출(Policy Store)이 실패하도록 유도하거나, 
    # mock을 써서 Policy Store 응답을 조작하는 게 정석.
    # 여기서는 간단히 _get_default_profile을 몽키패치하여, Policy Store 실패 시(또는 항상) 이 프로필을 쓰게 함.
    # 다만 run_safety_validation은 Policy Store URL로 요청을 먼저 보냄.
    # 테스트 환경에서 localhost:8002가 없으면 예외 발생 -> catch -> _get_default_profile 호출됨.
    
    if profile:
        service._get_default_profile = lambda asset_id: profile
    
    try:
        # Policy Store가 없으므로(가정) 기본 프로필(여기서는 주입된 profile) 사용됨
        result = run_safety_validation(
            transaction_id="test-tx",
            asset_id="reactor_01",
            policy_version_id="v-test",
            action_sequence=action_sequence,
            current_sensor_snapshot=sensor_snapshot
        )
    finally:
        service._get_default_profile = original_fn
    
    return result


def test_safe_reactor_state():
    """안전한 반응기 상태 → SAFE"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    assert result["final_verdict"] == "SAFE"
    assert result["validators"]["rules"]["verdict"] == "SAFE"
    assert result["validators"]["cbf"]["verdict"] == "SAFE"
    assert result["validators"]["simulation"]["verdict"] == "INDETERMINATE"
    # SIL 2 + RENORMALIZE: sim 제외, rules+cbf만으로 판정


def test_unsafe_temperature_exceeds():
    """온도 초과 → UNSAFE (Rules + CBF 모두 UNSAFE)"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 185.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    assert result["final_verdict"] == "UNSAFE"
    assert result["validators"]["rules"]["verdict"] == "UNSAFE"
    assert result["validators"]["cbf"]["verdict"] == "UNSAFE"


def test_unsafe_pressure_out_of_range():
    """압력 범위 초과 → UNSAFE"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 3.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    assert result["final_verdict"] == "UNSAFE"


def test_consensus_mode_weighted():
    """Consensus 모드가 WEIGHTED로 설정되는가"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    # SIL 2 + WEIGHTED + sim INDETERMINATE → RENORMALIZE
    # Consensus Engine 로직에 따라 AUTO 모드에서 WEIGHTED가 선택되거나, 
    # 명시적 WEIGHTED가 유지됨.
    assert result["consensus_details"]["mode"] in ("WEIGHTED", "AUTO")


def test_simulation_always_indeterminate():
    """현재 Simulation은 None 플러그인 → 항상 INDETERMINATE"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    assert result["validators"]["simulation"]["verdict"] == "INDETERMINATE"


def test_all_three_validators_run():
    """3개 검증기 모두 실행되는가"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    assert "rules" in result["validators"]
    assert "cbf" in result["validators"]
    assert "simulation" in result["validators"]


def test_consensus_details_present():
    """Consensus 상세 정보가 포함되는가"""
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0, "pressure": 1.5},
        action_sequence=[],
        profile=REACTOR_PROFILE
    )
    cd = result["consensus_details"]
    assert "mode" in cd
    assert "explanation" in cd


def test_empty_ruleset_safe():
    """규칙 없는 경우 → SAFE (체크할 것이 없으므로)
    
    주의: WORST_CASE 모드에서는 Simulation이 INDETERMINATE이면 UNSAFE로 판정됩니다.
    NoneBackend는 항상 INDETERMINATE를 반환하므로, WORST_CASE에서는 항상 UNSAFE가 됩니다.
    이 테스트는 Rules Validator와 CBF가 SAFE를 반환하는지 확인하는 데 중점을 둡니다.
    """
    empty_profile = {
        "sil_level": 1,
        "consensus": {"mode": "WORST_CASE"},
        "ruleset": [],
        "simulation": {"engine": "none"}
    }
    result = _run_with_profile(
        sensor_snapshot={"temperature": 150.0},
        action_sequence=[],
        profile=empty_profile
    )
    # Rules: SAFE (no rules), CBF: SAFE (no barriers, min_barrier=0 → h≥0 is safe), Sim: INDETERMINATE
    
    assert result["validators"]["rules"]["verdict"] == "SAFE"
    # CBF Validator는 규칙이 없으면 min_barrier=0으로 설정 → h(x)≥0 이므로 SAFE (경계 포함)
    assert result["validators"]["cbf"]["verdict"] == "SAFE"
    
    # WORST_CASE 모드에서 Sim INDETERMINATE는 UNSAFE로 간주됨
    assert result["final_verdict"] == "UNSAFE"
