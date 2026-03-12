"""
ODE Solver Simulation Backend 테스트
======================================
화학 반응기의 온도/압력 예측 시뮬레이션을 검증합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_ode_solver.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pcag.plugins.simulation.ode_solver import ODESolverBackend
from pcag.core.ports.simulation_backend import ISimulationBackend


# 테스트용 반응기 안전 규칙
REACTOR_RULESET = [
    {"rule_id": "max_temperature", "type": "threshold", "target_field": "temperature", "operator": "lte", "value": 180.0},
    {"rule_id": "min_temperature", "type": "threshold", "target_field": "temperature", "operator": "gte", "value": 120.0},
    {"rule_id": "safe_pressure", "type": "range", "target_field": "pressure", "min": 0.5, "max": 3.0},
]

# 안전한 현재 상태
SAFE_STATE = {"temperature": 150.0, "pressure": 1.5, "heater_output": 50.0, "cooling_valve": 80.0}


@pytest.fixture
def solver():
    backend = ODESolverBackend()
    backend.initialize({
        "horizon_ms": 5000,
        "dt_ms": 100,
        "timeout_ms": 5000  # 테스트 시 넉넉한 타임아웃
    })
    return backend


def test_implements_interface():
    """ISimulationBackend 인터페이스 구현 확인"""
    backend = ODESolverBackend()
    assert isinstance(backend, ISimulationBackend)


def test_initialize_default_params():
    """기본 파라미터로 초기화"""
    backend = ODESolverBackend()
    backend.initialize({})
    assert backend._initialized == True


def test_initialize_custom_params():
    """커스텀 파라미터로 초기화"""
    backend = ODESolverBackend()
    backend.initialize({
        "params": {
            "mass_kg": 200.0,
            "heater_max_power_w": 20000.0
        }
    })
    assert backend._params["mass_kg"] == 200.0
    assert backend._params["heater_max_power_w"] == 20000.0
    assert backend._params["specific_heat_j_kg_k"] == 4186.0  # 기본값 유지


def test_safe_steady_state(solver):
    """안전한 정상 상태 — 변화 없이 유지 → SAFE"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[],  # 액션 없음 — 현재 제어 입력 유지
        constraints={"ruleset": REACTOR_RULESET}
    )
    assert result["verdict"] == "SAFE"
    assert result["engine"] == "ode_solver"
    assert len(result["details"]["state_trajectory"]) > 1


def test_safe_moderate_heater(solver):
    """적당한 히터 출력(70%) → 온도 상승하지만 안전 범위 내 → SAFE"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 70}, "duration_ms": 2000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    assert result["verdict"] == "SAFE"
    # 온도가 약간 상승하지만 180°C 이내
    trajectory = result["details"]["state_trajectory"]
    final_temp = trajectory[-1]["temperature"]
    assert final_temp > 150.0  # 히터 올렸으니 온도 상승
    assert final_temp <= 180.0  # 안전 범위 내


def test_unsafe_full_heater(solver):
    """히터 100% + 냉각 0% → 온도 급상승 → 180°C 초과 → UNSAFE"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 100}, "duration_ms": 5000},
            {"action_type": "set_cooling_valve", "params": {"value": 0}, "duration_ms": 5000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    # 히터 100% + 냉각 0% → 온도가 반드시 상승하여 180°C 초과
    assert result["verdict"] == "UNSAFE"
    assert result["common"]["violated_constraint"] == "max_temperature"
    assert result["common"]["first_violation_step"] is not None


def test_unsafe_heater_no_cooling(solver):
    """히터 90% + 냉각 10% 장시간 → 온도 초과 → UNSAFE"""
    result = solver.validate_trajectory(
        current_state={"temperature": 170.0, "pressure": 1.8, "heater_output": 50.0, "cooling_valve": 80.0},
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 90}, "duration_ms": 10000},
            {"action_type": "set_cooling_valve", "params": {"value": 10}, "duration_ms": 10000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    # 이미 170°C에서 시작, 히터 90% + 냉각 10% → 180°C 초과 예상
    assert result["verdict"] == "UNSAFE"


def test_cooling_brings_temp_down(solver):
    """높은 온도에서 냉각 최대 → 온도 하강 → SAFE"""
    result = solver.validate_trajectory(
        current_state={"temperature": 175.0, "pressure": 2.0, "heater_output": 10.0, "cooling_valve": 100.0},
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 10}, "duration_ms": 5000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    # 히터 10% + 냉각 100% → 온도 하강
    trajectory = result["details"]["state_trajectory"]
    final_temp = trajectory[-1]["temperature"]
    assert final_temp < 175.0  # 온도 하강 확인
    assert result["verdict"] == "SAFE"


def test_trajectory_has_timestamps(solver):
    """궤적에 시간 정보가 포함되는지"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 60}, "duration_ms": 1000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    trajectory = result["details"]["state_trajectory"]
    assert len(trajectory) > 1
    assert "t_ms" in trajectory[0]
    assert "temperature" in trajectory[0]
    assert "pressure" in trajectory[0]


def test_max_values_recorded(solver):
    """최대값이 기록되는지"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 70}, "duration_ms": 2000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    assert "max_value" in result["details"]
    assert "temperature" in result["details"]["max_value"]


def test_latency_recorded(solver):
    """시뮬레이션 소요 시간이 기록되는지"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[],
        constraints={"ruleset": REACTOR_RULESET}
    )
    assert result["common"]["latency_ms"] >= 0


def test_empty_ruleset_safe(solver):
    """규칙 없이 시뮬레이션 → SAFE (체크할 제약 없음)"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 100}, "duration_ms": 5000}
        ],
        constraints={"ruleset": []}  # 빈 규칙
    )
    assert result["verdict"] == "SAFE"  # 제약 없으므로 위반 없음


def test_multiple_actions_sequential(solver):
    """여러 액션 순차 적용"""
    result = solver.validate_trajectory(
        current_state=SAFE_STATE,
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 60}, "duration_ms": 1000},
            {"action_type": "set_cooling_valve", "params": {"value": 90}, "duration_ms": 1000},
            {"action_type": "set_heater_output", "params": {"value": 50}, "duration_ms": 1000},
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    assert result["verdict"] == "SAFE"
    assert result["common"]["steps_completed"] > 0


def test_pressure_out_of_range(solver):
    """압력이 범위를 벗어나는 경우 → UNSAFE"""
    # 매우 높은 히터 출력으로 온도와 함께 압력도 급상승
    result = solver.validate_trajectory(
        current_state={"temperature": 175.0, "pressure": 2.8, "heater_output": 50.0, "cooling_valve": 10.0},
        action_sequence=[
            {"action_type": "set_heater_output", "params": {"value": 100}, "duration_ms": 10000}
        ],
        constraints={"ruleset": REACTOR_RULESET}
    )
    # 온도 초과가 먼저 잡히거나 압력 초과가 잡힘
    assert result["verdict"] == "UNSAFE"


def test_shutdown(solver):
    """shutdown 호출"""
    solver.shutdown()
    assert solver._initialized == False
