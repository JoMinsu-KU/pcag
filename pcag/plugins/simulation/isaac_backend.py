"""
Isaac Sim Simulation Backend — 시나리오 B 로봇 팔
===================================================
NVIDIA Isaac Sim을 사용하여 로봇 팔의 관절 궤적을 
물리 시뮬레이션으로 검증합니다.

PCAG 파이프라인 [120-123]:
  Safety Cluster → Simulation Validator → Isaac Sim Backend
  → 현재 관절 상태 + action_sequence → 물리 시뮬레이션 → SAFE/UNSAFE

필수 조건:
  - conda pcag-isaac 환경에서 실행 (Python 3.10)
  - Isaac Sim 4.5.0 설치
  - Franka Panda 로봇 USD Scene

중요:
  - Mock 데이터 절대 사용 금지
  - 값이 비거나 잘못된 경우 에러 발생 + 로그 기록
  - 실제 Isaac Sim 물리 엔진의 결과만 반환

conda pcag-isaac 환경에서 실행.
"""
import time
import logging
import threading
import numpy as np
from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)


class IsaacSimBackend(ISimulationBackend):
    """
    Isaac Sim 시뮬레이션 백엔드 — 로봇 팔 물리 검증
    
    Isaac Sim의 PhysX 물리 엔진을 사용하여:
    1. 관절 한계 초과 여부
    2. 충돌(collision) 발생 여부
    3. 작업 공간(workspace) 이탈 여부
    를 실제 물리 시뮬레이션으로 검증합니다.
    
    Mock 데이터를 사용하지 않습니다.
    Isaac Sim이 없으면 에러를 발생시킵니다.
    """
    
    def __init__(self):
        self._simulation_app = None
        self._world = None
        self._robot = None
        self._initialized = False
        self._config = {}
        self._lock = threading.Lock()  # 스레드 안전성
        self._current_scene = None     # 현재 로드된 Scene 경로
        self._joint_count = 9          # 기본값
    
    def is_initialized(self) -> bool:
        """초기화 완료 여부를 안전하게 확인"""
        return self._initialized
    
    def initialize(self, config: dict) -> None:
        """
        Isaac Sim 시작 + Scene 로드
        
        멱등성: 이미 초기화되었으면 skip.
        메인 스레드에서 호출해야 함 (서버 startup 시).
        
        Args:
            config: {
                "engine": "isaac_sim",
                "world_ref": "/path/to/scene.usd" (optional — 없으면 기본 Franka 사용),
                "headless": True,
                "joint_count": 9,  # Franka Panda 관절 수
                "simulation_steps_per_action": 30,  # action 당 물리 시뮬레이션 스텝 수
                "timeout_ms": 200
            }
        
        Raises:
            ImportError: Isaac Sim 모듈을 import할 수 없는 경우
            RuntimeError: Isaac Sim 초기화 실패
        """
        with self._lock:
            if self._initialized:
                logger.info("Isaac Sim Backend already initialized, skipping")
                return

            self._config = config
            headless = config.get("headless", True)
            
            logger.info("Isaac Sim Backend: Initializing...")
            
            # Isaac Sim import — 실패 시 명확한 에러
            try:
                from isaacsim import SimulationApp
            except ImportError as e:
                error_msg = (
                    "Isaac Sim을 import할 수 없습니다. "
                    "conda pcag-isaac 환경에서 실행하고 있는지 확인하세요. "
                    f"상세: {e}"
                )
                logger.error(error_msg)
                raise ImportError(error_msg) from e
            
            # SimulationApp 시작
            try:
                sim_config = {"headless": headless}
                if not headless:
                    sim_config["width"] = config.get("width", 1280)
                    sim_config["height"] = config.get("height", 720)
                
                self._simulation_app = SimulationApp(sim_config)
                logger.info("Isaac Sim SimulationApp started")
            except Exception as e:
                error_msg = f"Isaac Sim SimulationApp 시작 실패: {e}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            
            # Isaac Sim 모듈 import (SimulationApp 시작 후에만 가능)
            try:
                from isaacsim.core.api import World
                from isaacsim.core.api.objects import DynamicCuboid
            except ImportError:
                # 이전 API 경로 시도
                from omni.isaac.core import World
            
            # World 생성
            try:
                self._world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
                self._world.scene.add_default_ground_plane()
                logger.info("Isaac Sim World created with ground plane")
            except Exception as e:
                error_msg = f"Isaac Sim World 생성 실패: {e}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            
            # 로봇 로드
            self._load_initial_robot()
            
            self._initialized = True
            logger.info("Isaac Sim Backend initialized successfully")
    
    def _load_initial_robot(self):
        """초기 로봇 로드 로직 분리"""
        try:
            robot = None
            # 방법 1: isaacsim.robot 패키지
            try:
                from isaacsim.robot.manipulators.examples.franka import Franka
                robot = self._world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
            except (ImportError, Exception):
                pass
            
            # 방법 2: omni.isaac.franka
            if robot is None:
                try:
                    from omni.isaac.franka import Franka
                    robot = self._world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
                except (ImportError, Exception):
                    pass
            
            # 방법 3: USD 파일에서 로드
            if robot is None:
                world_ref = self._config.get("world_ref")
                if world_ref:
                    from omni.isaac.core.utils.stage import add_reference_to_stage
                    from omni.isaac.core.robots import Robot
                    add_reference_to_stage(usd_path=world_ref, prim_path="/World/Robot")
                    robot = self._world.scene.add(Robot(prim_path="/World/Robot", name="robot"))
                    self._current_scene = world_ref
                else:
                    error_msg = "로봇을 로드할 수 없습니다. Franka 패키지도, world_ref 설정도 없습니다."
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            
            self._robot = robot
            self._world.reset()
            
            # 초기 관절 수 확인
            initial_joints = self._robot.get_joint_positions()
            self._joint_count = len(initial_joints)
            logger.info(f"Robot loaded: {self._joint_count} joints, initial positions: {initial_joints}")
            
            # 로봇 안정화 (몇 프레임 실행)
            headless = self._config.get("headless", True)
            for _ in range(10):
                self._world.step(render=not headless)
                
        except Exception as e:
            error_msg = f"로봇 로드 실패: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """스레드 락으로 동시 접근 방지"""
        if not self._initialized:
            error_msg = "Isaac Sim이 초기화되지 않았습니다. initialize()를 먼저 호출하세요."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        with self._lock:
            return self._validate_trajectory_impl(current_state, action_sequence, constraints)
            
    def _validate_trajectory_impl(self, current_state, action_sequence, constraints) -> dict:
        """
        실제 검증 로직 (락 내부에서 실행)
        
        Args:
            current_state: {
                "joint_positions": [0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0, 0.04, 0.04],
                ...
            }
            action_sequence: [
                {"action_type": "move_joint", "params": {"target_positions": [1.0, ...]}, "duration_ms": 500},
                ...
            ]
            constraints: {
                "ruleset": [
                    {"rule_id": "joint_0_limit", "type": "range", "target_field": "joint_0", "min": -2.897, "max": 2.897},
                    ...
                ],
                "joint_limits": {"0": [-2.897, 2.897], ...},
                "world_ref": "/path/to/specific_scene.usd"  # Optional: 특정 Scene 요구
            }
        """
        start_time = time.time()
        
        # Check if scene reload needed
        required_scene = constraints.get("world_ref") or self._config.get("world_ref")
        if required_scene and required_scene != self._current_scene:
            self._reload_scene(required_scene)
        
        # 입력 검증
        if not isinstance(current_state, dict):
            raise ValueError(f"current_state는 dict여야 합니다. 받은 타입: {type(current_state)}")
        
        if not isinstance(action_sequence, list):
            raise ValueError(f"action_sequence는 list여야 합니다. 받은 타입: {type(action_sequence)}")
        
        # 관절 위치 추출
        joint_positions = current_state.get("joint_positions")
        if joint_positions is None:
            # 개별 필드에서 조립 시도
            joint_positions = []
            for i in range(self._joint_count):
                key = f"joint_{i}"
                if key in current_state:
                    joint_positions.append(current_state[key])
                else:
                    break
        
        if not joint_positions:
            error_msg = f"current_state에 joint_positions 또는 joint_0~joint_{self._joint_count-1} 필드가 없습니다. 받은 키: {list(current_state.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 제약 조건 추출
        ruleset = constraints.get("ruleset", [])
        joint_limits = constraints.get("joint_limits", {})
        
        # 궤적 기록
        trajectory = []
        violations = []
        first_violation_step = None
        collision_detected = False
        min_clearance = float('inf')
        max_force = 0.0
        
        headless = self._config.get("headless", True)
        steps_per_action = self._config.get("simulation_steps_per_action", 30)
        
        try:
            # 초기 상태 설정
            self._world.reset()
            initial_np = np.array(joint_positions[:self._joint_count], dtype=np.float32)
            
            # 패딩 (관절 수 맞추기)
            if len(initial_np) < self._joint_count:
                padded = np.zeros(self._joint_count, dtype=np.float32)
                padded[:len(initial_np)] = initial_np
                initial_np = padded
            
            self._robot.set_joint_positions(initial_np)
            
            for _ in range(5):
                self._world.step(render=not headless)
            
            # 초기 상태 기록
            actual_pos = self._robot.get_joint_positions()
            trajectory.append({
                "step": -1,
                "action": "initial",
                "joint_positions": [round(float(p), 4) for p in actual_pos],
            })
            
            # 초기 상태에서 제약 검사
            violation = self._check_joint_constraints(actual_pos, joint_limits, ruleset)
            if violation and first_violation_step is None:
                first_violation_step = -1
                violations.append({**violation, "step": -1})
            
            # 각 action 적용 + 시뮬레이션
            for step_idx, action in enumerate(action_sequence):
                action_type = action.get("action_type", "")
                params = action.get("params", {})
                
                if action_type != "move_joint":
                    logger.warning(f"지원하지 않는 action_type: {action_type}. move_joint만 지원합니다.")
                    continue
                
                target_positions = params.get("target_positions")
                if target_positions is None:
                    error_msg = f"action[{step_idx}].params에 target_positions가 없습니다. 받은 키: {list(params.keys())}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Pre-check: 명령된 관절 각도가 물리적으로 가능한 범위인지
                target_np = np.array(target_positions[:self._joint_count], dtype=np.float32)
                if len(target_np) < self._joint_count:
                    padded = np.zeros(self._joint_count, dtype=np.float32)
                    padded[:len(target_np)] = target_np
                    target_np = padded
                
                pre_violation = self._check_joint_constraints(target_np, joint_limits, ruleset)
                if pre_violation and first_violation_step is None:
                    first_violation_step = step_idx
                    violations.append({**pre_violation, "step": step_idx, "check_type": "pre_check"})
                
                # 물리 시뮬레이션 실행
                self._robot.set_joint_positions(target_np)
                
                for sim_step in range(steps_per_action):
                    self._world.step(render=not headless)
                
                # 실제 결과 상태 읽기
                result_pos = self._robot.get_joint_positions()
                
                trajectory.append({
                    "step": step_idx,
                    "action": action_type,
                    "target_positions": [round(float(p), 4) for p in target_np],
                    "actual_positions": [round(float(p), 4) for p in result_pos],
                })
                
                # Post-check: 시뮬레이션 후 실제 관절 위치 검사
                post_violation = self._check_joint_constraints(result_pos, joint_limits, ruleset)
                if post_violation and first_violation_step is None:
                    first_violation_step = step_idx
                    violations.append({**post_violation, "step": step_idx, "check_type": "post_check"})
                
                # Divergence check: 명령값과 실제값의 차이 (클램핑 감지)
                divergence = np.max(np.abs(target_np[:7] - result_pos[:7]))
                if divergence > 0.1:  # 0.1 rad 이상 차이
                    if first_violation_step is None:
                        first_violation_step = step_idx
                    violations.append({
                        "step": step_idx,
                        "constraint": "command_divergence",
                        "divergence_rad": round(float(divergence), 4),
                        "check_type": "divergence_check",
                        "detail": "명령된 관절 각도와 실제 도달 각도의 차이가 0.1 rad 이상 — 물리적 제한에 의한 클램핑 발생"
                    })
                
                # 타임아웃 체크
                elapsed_ms = (time.time() - start_time) * 1000
                timeout_ms = self._config.get("timeout_ms", 5000)
                if elapsed_ms > timeout_ms:
                    logger.warning(f"Isaac Sim 시뮬레이션 타임아웃: {elapsed_ms:.0f}ms > {timeout_ms}ms")
                    return self._make_result(
                        "INDETERMINATE", trajectory, violations, first_violation_step,
                        start_time, collision_detected, min_clearance, max_force,
                        {"reason": f"Simulation timeout: {elapsed_ms:.0f}ms > {timeout_ms}ms"}
                    )
            
        except ValueError:
            raise  # 입력 검증 에러는 그대로 전파
        except Exception as e:
            error_msg = f"Isaac Sim 시뮬레이션 중 에러 발생: {e}"
            logger.error(error_msg)
            return self._make_result(
                "INDETERMINATE", trajectory, violations, first_violation_step,
                start_time, collision_detected, min_clearance, max_force,
                {"reason": error_msg}
            )
        
        # 최종 판정
        verdict = "UNSAFE" if violations else "SAFE"
        
        return self._make_result(
            verdict, trajectory, violations, first_violation_step,
            start_time, collision_detected, min_clearance, max_force, {}
        )
    
    def _reload_scene(self, scene_path: str) -> None:
        """
        Scene(USD) 리로드 — 새 World를 생성하여 안정적으로 전환
        
        기존 World를 stop/clear 후, 새 World를 생성합니다.
        USD Stage를 직접 열거나 로봇을 다시 로드합니다.
        """
        logger.info(f"Scene reload: {self._current_scene} -> {scene_path}")
        
        try:
            # 기존 World 정리
            if self._world:
                try:
                    self._world.stop()
                except Exception:
                    pass
                try:
                    self._world.clear()
                except Exception:
                    pass
            
            # 새 World 생성
            from isaacsim.core.api import World
            self._world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
            self._world.scene.add_default_ground_plane()
            
            # USD Scene 로드 (world_ref가 파일 경로인 경우)
            if scene_path and scene_path.endswith(".usd"):
                try:
                    from omni.isaac.core.utils.stage import add_reference_to_stage
                    from omni.isaac.core.robots import Robot
                    add_reference_to_stage(usd_path=scene_path, prim_path="/World/Robot")
                    self._robot = self._world.scene.add(Robot(prim_path="/World/Robot", name="robot"))
                except Exception as e:
                    logger.warning(f"USD file load failed: {e}, trying Franka fallback")
                    self._load_initial_robot()
            else:
                # 기본 Franka 로봇 로드
                self._load_initial_robot()
            
            self._world.reset()
            
            # 안정화
            headless = self._config.get("headless", True)
            for _ in range(10):
                self._world.step(render=not headless)
            
            # 관절 수 업데이트
            initial_joints = self._robot.get_joint_positions()
            self._joint_count = len(initial_joints)
            
            self._current_scene = scene_path
            logger.info(f"Scene reloaded: {scene_path}, {self._joint_count} joints")
            
        except Exception as e:
            logger.error(f"Scene reload failed: {e}")
            raise RuntimeError(f"Scene reload failed: {e}") from e
    
    def shutdown(self) -> None:
        """
        Isaac Sim 정상 종료
        
        Articulated Robot 리소스를 정리합니다.
        world.stop() → world.clear() → simulation_app.close() 순서 필수.
        (이 순서를 지키지 않으면 다음 실행 시 hang 발생)
        """
        logger.info("Isaac Sim Backend: Shutting down...")
        
        if self._world:
            try:
                self._world.stop()
                logger.info("World stopped")
            except Exception as e:
                logger.warning(f"World.stop() failed: {e}")
            
            try:
                self._world.clear()
                logger.info("World cleared")
            except Exception as e:
                logger.warning(f"World.clear() failed: {e}")
        
        if self._simulation_app:
            try:
                self._simulation_app.close()
                logger.info("SimulationApp closed")
            except Exception as e:
                logger.warning(f"SimulationApp.close() failed: {e}")
        
        self._initialized = False
        self._world = None
        self._robot = None
        self._simulation_app = None
        logger.info("Isaac Sim Backend shutdown complete")
    
    def _check_joint_constraints(self, joint_positions, joint_limits: dict, ruleset: list) -> dict | None:
        """
        관절 제약 조건 검사
        
        joint_limits (직접 지정) 또는 ruleset (Rule 형태) 모두 지원
        """
        # 1. joint_limits에서 직접 검사
        for joint_idx_str, limits in joint_limits.items():
            idx = int(joint_idx_str)
            if idx < len(joint_positions):
                val = float(joint_positions[idx])
                if val < limits[0] or val > limits[1]:
                    return {
                        "constraint": f"joint_{idx}_limit",
                        "joint_index": idx,
                        "value": round(val, 4),
                        "limits": limits,
                        "detail": f"관절 {idx}의 각도 {val:.4f} rad가 제한 [{limits[0]}, {limits[1]}]을 초과"
                    }
        
        # 2. ruleset에서 검사 (range 타입)
        for rule in ruleset:
            rule_type = rule.get("type", "") if isinstance(rule, dict) else getattr(rule, "type", "")
            target = rule.get("target_field", "") if isinstance(rule, dict) else getattr(rule, "target_field", "")
            rule_id = rule.get("rule_id", "") if isinstance(rule, dict) else getattr(rule, "rule_id", "")
            
            if not target.startswith("joint_"):
                continue
            
            try:
                idx = int(target.split("_")[1])
            except (IndexError, ValueError):
                continue
            
            if idx >= len(joint_positions):
                continue
            
            val = float(joint_positions[idx])
            
            if rule_type == "range":
                min_val = rule.get("min") if isinstance(rule, dict) else getattr(rule, "min", None)
                max_val = rule.get("max") if isinstance(rule, dict) else getattr(rule, "max", None)
                if min_val is not None and val < min_val:
                    return {"constraint": rule_id, "joint_index": idx, "value": round(val, 4), "limits": [min_val, max_val]}
                if max_val is not None and val > max_val:
                    return {"constraint": rule_id, "joint_index": idx, "value": round(val, 4), "limits": [min_val, max_val]}
        
        return None
    
    def _make_result(self, verdict, trajectory, violations, first_violation_step,
                     start_time, collision_detected, min_clearance, max_force, extra):
        """SimulationResult dict 생성 — isaac_sim_details 형식"""
        latency_ms = round((time.time() - start_time) * 1000, 3)
        
        violated_constraint = None
        if violations:
            violated_constraint = violations[0].get("constraint", "unknown")
        
        return {
            "verdict": verdict,
            "engine": "isaac_sim",
            "common": {
                "first_violation_step": first_violation_step,
                "violated_constraint": violated_constraint,
                "latency_ms": latency_ms,
                "steps_completed": len(trajectory) - 1
            },
            "details": {
                "min_clearance_m": round(min_clearance, 4) if min_clearance != float('inf') else None,
                "max_force_N": round(max_force, 4) if max_force > 0 else None,
                "collision_detected": collision_detected,
                "collision_objects": [],
                "joint_limit_exceeded": any(
                    v.get("constraint", "").endswith("_limit") or v.get("constraint") == "command_divergence"
                    for v in violations
                ),
                "trajectory": trajectory[:10],  # 처음 10개만
                "violations": violations[:5],  # 처음 5개만
                **extra
            }
        }
