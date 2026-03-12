"""
Discrete Event Simulation Backend 테스트 (AGV 교차로)
=====================================================
2D 그리드에서 AGV 경로 충돌 예측을 검증합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_discrete_event.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pcag.plugins.simulation.discrete_event import DiscreteEventBackend
from pcag.core.ports.simulation_backend import ISimulationBackend


@pytest.fixture
def simulator():
    backend = DiscreteEventBackend()
    backend.initialize({
        "grid": {"width": 10, "height": 10, "obstacles": [[5, 5]], "intersections": []},
        "agvs": {
            "agv_01": {"position": [0, 0], "speed": 1.0},
            "agv_02": {"position": [9, 9], "speed": 1.0}
        },
        "min_distance": 1.0
    })
    return backend


def test_implements_interface():
    """ISimulationBackend 인터페이스 구현"""
    backend = DiscreteEventBackend()
    assert isinstance(backend, ISimulationBackend)


def test_initialize():
    """초기화"""
    backend = DiscreteEventBackend()
    backend.initialize({"grid": {"width": 5, "height": 5}})
    assert backend._initialized == True
    assert backend._width == 5


def test_safe_no_collision(simulator):
    """충돌 없는 경로 → SAFE"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}, "agv_02": {"x": 9, "y": 9}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0],[3,0]]}},
            {"action_type": "move_to", "params": {"agv_id": "agv_02", "path": [[8,9],[7,9],[6,9]]}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "SAFE"
    assert result["engine"] == "discrete_event"
    assert len(result["details"]["collision_pairs"]) == 0


def test_collision_same_cell(simulator):
    """같은 셀에 도달 → UNSAFE (충돌)"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}, "agv_02": {"x": 4, "y": 0}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0],[3,0]]}},
            {"action_type": "move_to", "params": {"agv_id": "agv_02", "path": [[3,0],[2,0],[1,0]]}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "UNSAFE"
    assert len(result["details"]["collision_pairs"]) > 0


def test_obstacle_collision(simulator):
    """장애물 셀 진입 → UNSAFE"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 4, "y": 5}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[5,5]]}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "UNSAFE"
    assert any(v["constraint"] == "obstacle_collision" for v in result["details"]["violations"])


def test_grid_boundary(simulator):
    """그리드 경계 초과 → UNSAFE"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 9, "y": 0}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[10,0]]}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "UNSAFE"
    assert any(v["constraint"] == "grid_boundary" for v in result["details"]["violations"])


def test_target_coordinates_path_generation(simulator):
    """목표 좌표로 자동 경로 생성"""
    result = simulator.validate_trajectory(
        current_state={"position_x": 0, "position_y": 0},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "target_x": 3, "target_y": 2}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "SAFE"
    assert result["common"]["steps_completed"] > 0


def test_no_actions_safe(simulator):
    """액션 없음 → SAFE (이동 없음)"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}},
        action_sequence=[],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "SAFE"


def test_event_log_recorded(simulator):
    """이벤트 로그가 기록되는지"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0]]}}
        ],
        constraints={"ruleset": []}
    )
    assert len(result["details"]["event_log"]) > 0
    assert "t_step" in result["details"]["event_log"][0]


def test_ruleset_position_bounds(simulator):
    """ruleset으로 위치 범위 검사"""
    ruleset = [
        {"rule_id": "x_bounds", "type": "range", "target_field": "position_x", "min": 0, "max": 5},
        {"rule_id": "y_bounds", "type": "range", "target_field": "position_y", "min": 0, "max": 5}
    ]
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0],[3,0],[4,0],[5,0],[6,0]]}}
        ],
        constraints={"ruleset": ruleset}
    )
    # x=6 > max=5 → UNSAFE
    assert result["verdict"] == "UNSAFE"


def test_multiple_agvs_independent_paths(simulator):
    """여러 AGV 독립 경로 — 충돌 없음"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}, "agv_02": {"x": 0, "y": 9}},
        action_sequence=[
            {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0]]}},
            {"action_type": "move_to", "params": {"agv_id": "agv_02", "path": [[1,9],[2,9]]}}
        ],
        constraints={"ruleset": []}
    )
    assert result["verdict"] == "SAFE"


def test_latency_recorded(simulator):
    """시뮬레이션 소요 시간 기록"""
    result = simulator.validate_trajectory(
        current_state={"agv_01": {"x": 0, "y": 0}},
        action_sequence=[],
        constraints={"ruleset": []}
    )
    assert result["common"]["latency_ms"] >= 0


def test_shutdown(simulator):
    """shutdown 호출"""
    simulator.shutdown()
    assert simulator._initialized == False
