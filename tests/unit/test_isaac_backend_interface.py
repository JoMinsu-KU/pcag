"""
Isaac Sim Backend 인터페이스 + 에러 처리 테스트
================================================
Isaac Sim이 설치되지 않은 환경에서도 실행 가능한 테스트.
인터페이스 준수, 에러 메시지, 입력 검증을 확인합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_isaac_backend_interface.py -v

Isaac Sim이 필요한 실제 물리 테스트는:
  conda activate pcag-isaac && python tests/isaac_sim/test_scenario_b_robot_arm.py
"""
import sys, os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pcag.core.ports.simulation_backend import ISimulationBackend
from pcag.plugins.simulation.isaac_backend import IsaacSimBackend
from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy

# ==========================================
# 1. IsaacSimBackend (Worker Logic) Tests
# ==========================================

def test_implements_interface():
    """IsaacSimBackend가 ISimulationBackend를 구현하는가"""
    backend = IsaacSimBackend()
    assert isinstance(backend, ISimulationBackend)


def test_not_initialized_error():
    """초기화 없이 validate_trajectory 호출 → RuntimeError"""
    backend = IsaacSimBackend()
    # _initialized = False인 상태
    with pytest.raises(RuntimeError, match="초기화되지 않았습니다"):
        backend.validate_trajectory(
            current_state={"joint_positions": [0.0]},
            action_sequence=[],
            constraints={}
        )


def test_invalid_current_state_type():
    """current_state가 dict가 아닌 경우 → ValueError"""
    backend = IsaacSimBackend()
    backend._initialized = True  # 직접 설정 (초기화 우회)
    backend._joint_count = 9
    backend._config = {}
    
    with pytest.raises(ValueError, match="dict여야"):
        backend.validate_trajectory(
            current_state="not a dict",
            action_sequence=[],
            constraints={}
        )


def test_invalid_action_sequence_type():
    """action_sequence가 list가 아닌 경우 → ValueError"""
    backend = IsaacSimBackend()
    backend._initialized = True
    backend._joint_count = 9
    backend._config = {}
    
    with pytest.raises(ValueError, match="list여야"):
        backend.validate_trajectory(
            current_state={"joint_positions": [0.0]*9},
            action_sequence="not a list",
            constraints={}
        )


def test_missing_joint_positions():
    """current_state에 joint_positions가 없는 경우 → ValueError"""
    backend = IsaacSimBackend()
    backend._initialized = True
    backend._joint_count = 9
    backend._config = {}
    backend._world = None
    backend._robot = None
    
    with pytest.raises(ValueError, match="joint_positions"):
        backend.validate_trajectory(
            current_state={"temperature": 150.0},  # 잘못된 데이터
            action_sequence=[],
            constraints={}
        )


def test_missing_target_positions_in_action():
    """action에 target_positions가 없는 경우 → ValueError"""
    backend = IsaacSimBackend()
    backend._initialized = True
    backend._joint_count = 9
    backend._config = {}
    backend._world = type('MockWorld', (), {
        'reset': lambda self: None,
        'step': lambda self, render=True: None
    })()
    backend._robot = type('MockRobot', (), {
        'set_joint_positions': lambda self, pos: None,
        'get_joint_positions': lambda self: [0.0]*9,
    })()
    
    with pytest.raises(ValueError, match="target_positions"):
        backend.validate_trajectory(
            current_state={"joint_positions": [0.0]*9},
            action_sequence=[
                {"action_type": "move_joint", "params": {"wrong_key": [1.0]}}
            ],
            constraints={}
        )


def test_initialize_without_isaacsim():
    """Isaac Sim이 설치되지 않은 환경에서 initialize → ImportError"""
    backend = IsaacSimBackend()
    
    # pcag 환경에서는 isaacsim이 없으므로 ImportError 발생해야 함
    # 하지만 isaac_backend.py 내부에서 import하므로, 실제 호출 시 에러 발생
    try:
        backend.initialize({"headless": True})
        # Isaac Sim이 설치된 환경에서는 성공할 수 있음
        backend.shutdown()
    except ImportError as e:
        # 기대한 에러 — 메시지 확인
        assert "Isaac Sim" in str(e) or "isaacsim" in str(e)
    except RuntimeError:
        # Isaac Sim 초기화 실패도 허용
        pass


def test_shutdown_without_init():
    """초기화 없이 shutdown 호출 → 에러 없어야 함"""
    backend = IsaacSimBackend()
    backend.shutdown()  # 에러 없이 완료
    assert backend.is_initialized() == False


def test_result_format():
    """결과 형식이 isaac_sim_details 스키마를 따르는가 (내부 함수 테스트)"""
    backend = IsaacSimBackend()
    
    result = backend._make_result(
        verdict="SAFE",
        trajectory=[{"step": 0, "action": "initial", "joint_positions": [0.0]*9}],
        violations=[],
        first_violation_step=None,
        start_time=time.time(),
        collision_detected=False,
        min_clearance=float('inf'),
        max_force=0.0,
        extra={}
    )
    
    # 결과 구조 검증
    assert result["verdict"] == "SAFE"
    assert result["engine"] == "isaac_sim"
    assert "common" in result
    assert "details" in result
    assert result["common"]["first_violation_step"] is None
    assert result["details"]["collision_detected"] == False
    assert result["details"]["joint_limit_exceeded"] == False


def test_is_initialized_method():
    """is_initialized() public getter 테스트"""
    backend = IsaacSimBackend()
    assert backend.is_initialized() == False
    # After manual flag set
    backend._initialized = True
    assert backend.is_initialized() == True


# ==========================================
# 2. IsaacSimProxy Tests
# ==========================================

def test_proxy_implements_interface():
    """IsaacSimProxy가 ISimulationBackend를 구현하는가"""
    from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy
    proxy = IsaacSimProxy()
    assert isinstance(proxy, ISimulationBackend)

def test_proxy_not_initialized_returns_indeterminate():
    """초기화 안 된 proxy는 INDETERMINATE 반환"""
    from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy
    proxy = IsaacSimProxy()
    result = proxy.validate_trajectory(
        current_state={"joint_positions": [0.0]*9},
        action_sequence=[],
        constraints={}
    )
    assert result["verdict"] == "INDETERMINATE"

def test_proxy_shutdown_safe():
    """초기화 없이 shutdown 호출 — 에러 없어야 함"""
    from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy
    proxy = IsaacSimProxy()
    proxy.shutdown()
    assert not proxy.is_initialized()
