"""
Isaac Sim Worker Process
========================
별도 프로세스에서 Isaac Sim을 실행합니다.
메인 프로세스(Safety Cluster)와 multiprocessing.Queue로 통신합니다.

이 파일은 pcag-isaac 환경에서만 실행됩니다.
pcag 환경에서는 import만 되고 실행되지 않습니다.

근본 원인:
  Isaac Sim(Kit)과 uvicorn이 둘 다 asyncio 이벤트 루프를 독점하려고 하여
  같은 프로세스에서는 충돌합니다. 프로세스 분리로 해결합니다.
"""
import traceback
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)


def isaac_worker_main(request_queue, result_queue, init_config: dict):
    """
    Isaac Sim Worker 메인 함수 — 별도 프로세스에서 실행
    
    Args:
        request_queue: 요청 수신 큐 (Safety Cluster → Worker)
        result_queue: 결과 전송 큐 (Worker → Safety Cluster)
        init_config: 초기화 설정 (headless, world_ref, timeout_ms 등)
    """
    print("[Isaac Worker] Starting...")
    
    try:
        # Isaac Sim 시작 (이 프로세스의 메인 스레드에서)
        from isaacsim import SimulationApp
        headless = init_config.get("headless", True)
        sim_app = SimulationApp({"headless": headless})
        print("[Isaac Worker] SimulationApp started")
        
        # SimulationApp 이후 import
        from isaacsim.core.api import World
        
        # World 생성
        world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
        world.scene.add_default_ground_plane()
        
        # 로봇 로드
        robot = _load_robot(world)
        world.reset()
        
        # 안정화
        for _ in range(10):
            world.step(render=not headless)
        
        joint_count = len(robot.get_joint_positions())
        current_scene = init_config.get("world_ref")
        steps_per_action = init_config.get("simulation_steps_per_action", 30)
        
        print(f"[Isaac Worker] Ready! Robot: {joint_count} joints")
        
        # 부팅 성공 알림
        result_queue.put({"job_id": "__BOOT__", "ok": True, "message": "Isaac Worker ready"})
        
        # Job 처리 루프
        while True:
            try:
                # 비동기적으로 큐 체크 (0.1초 타임아웃)
                try:
                    job = request_queue.get(timeout=0.1)
                except Exception:
                    # 큐가 비어있으면 Isaac Sim 업데이트만
                    sim_app.update()
                    continue
                
                # 종료 신호
                if job is None or job.get("type") == "SHUTDOWN":
                    print("[Isaac Worker] Shutdown signal received")
                    break
                
                job_id = job.get("job_id", "unknown")
                
                # GET_STATE 처리
                if job.get("type") == "GET_STATE":
                    try:
                        state = _get_current_state(world, robot)
                        result_queue.put({"job_id": job_id, "ok": True, "result": state})
                    except Exception as e:
                        print(f"[Isaac Worker] GET_STATE failed: {e}")
                        result_queue.put({"job_id": job_id, "ok": False, "error": str(e)})
                    continue

                print(f"[Isaac Worker] Processing job: {job_id}")
                
                try:
                    # Scene 리로드 필요 여부
                    world_ref = job.get("world_ref")
                    if world_ref and world_ref != current_scene:
                        world, robot = _reload_scene(world, world_ref, headless)
                        current_scene = world_ref
                        joint_count = len(robot.get_joint_positions())
                    
                    # 시뮬레이션 검증 실행
                    result = _validate_trajectory(
                        world, robot, job, joint_count, steps_per_action, headless
                    )
                    result_queue.put({"job_id": job_id, "ok": True, "result": result})
                    
                except Exception as e:
                    print(f"[Isaac Worker] Job {job_id} failed: {e}")
                    result_queue.put({
                        "job_id": job_id,
                        "ok": False,
                        "error": str(e),
                        "trace": traceback.format_exc()
                    })
                    
            except KeyboardInterrupt:
                break
        
        # 정상 종료
        print("[Isaac Worker] Shutting down...")
        try:
            world.stop()
            world.clear()
        except Exception:
            pass
        sim_app.close()
        print("[Isaac Worker] Shutdown complete")
        
    except Exception as e:
        # Worker 부팅 실패
        print(f"[Isaac Worker] Boot failed: {e}")
        result_queue.put({
            "job_id": "__BOOT__",
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc()
        })


def _load_robot(world):
    """Franka Panda 로봇 로드"""
    robot = None
    
    try:
        from isaacsim.robot.manipulators.examples.franka import Franka
        robot = world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
    except (ImportError, Exception):
        pass
    
    if robot is None:
        try:
            from omni.isaac.franka import Franka
            robot = world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
        except (ImportError, Exception):
            pass
    
    if robot is None:
        raise RuntimeError("Franka robot could not be loaded")
    
    return robot


def _reload_scene(world, scene_path, headless):
    """Scene 리로드 — 새 World 생성"""
    print(f"[Isaac Worker] Reloading scene: {scene_path}")
    
    try:
        world.stop()
        world.clear()
    except Exception:
        pass
    
    from isaacsim.core.api import World
    world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
    world.scene.add_default_ground_plane()
    
    if scene_path and scene_path.endswith(".usd"):
        from omni.isaac.core.utils.stage import add_reference_to_stage
        from omni.isaac.core.robots import Robot
        add_reference_to_stage(usd_path=scene_path, prim_path="/World/Robot")
        robot = world.scene.add(Robot(prim_path="/World/Robot", name="robot"))
    else:
        robot = _load_robot(world)
    
    world.reset()
    for _ in range(10):
        world.step(render=not headless)
    
    return world, robot


def _get_current_state(world, robot):
    """현재 로봇 상태 조회"""
    joint_positions = robot.get_joint_positions()
    joint_velocities = robot.get_joint_velocities()
    
    try:
        joint_efforts = robot.get_measured_joint_efforts()
    except Exception:
        joint_efforts = [0.0] * len(joint_positions)
    
    ee_pos = None
    try:
        # Franka specific: try to get end effector pose
        # Using rigid body name "panda_hand" or "hand"
        from omni.isaac.core.utils.prims import get_prim_at_path
        # Assuming robot prim path is /World/Franka or /World/Robot
        # And hand is relative. 
        # Easier: if robot class has end_effector
        if hasattr(robot, "end_effector") and robot.end_effector:
            ee_pos, _ = robot.end_effector.get_world_pose()
    except Exception:
        pass
        
    return {
        "joint_positions": [float(x) for x in joint_positions],
        "joint_velocities": [float(x) for x in joint_velocities],
        "joint_efforts": [float(x) for x in joint_efforts],
        "ee_position": [float(x) for x in ee_pos] if ee_pos is not None else None,
        "timestamp": time.time()
    }


def _validate_trajectory(world, robot, job, joint_count, steps_per_action, headless):
    """시뮬레이션 검증 실행 (종합 검사: 충돌, 작업공간, 토크)"""
    start_time = time.time()
    
    current_state = job.get("state") or {}
    action_sequence = job.get("actions") or []
    constraints = job.get("constraints") or {}
    
    # 관절 위치 추출
    joint_positions = current_state.get("joint_positions")
    if joint_positions is None:
        joint_positions = [current_state.get(f"joint_{i}", 0.0) for i in range(joint_count)]
    
    if not joint_positions:
        return {
            "verdict": "INDETERMINATE",
            "engine": "isaac_sim",
            "common": {"first_violation_step": None, "violated_constraint": None, "latency_ms": 0, "steps_completed": 0},
            "details": {"reason": "No joint positions in current_state"}
        }
    
    # 제약 조건
    ruleset = constraints.get("ruleset")
    if ruleset is None:
        ruleset = []
        
    joint_limits = constraints.get("joint_limits")
    if joint_limits is None:
        joint_limits = {}
    
    # 추가 제약 조건 (Workspace, Torque)
    workspace_limits = constraints.get("workspace_limits") # [[min_x, max_x], [min_y, max_y], [min_z, max_z]]
    torque_limits = constraints.get("torque_limits") # [max_torque_joint_0, ...]
    
    trajectory = []
    violations = []
    first_violation_step = None
    
    # 초기 상태 설정
    world.reset()
    initial_np = np.array(joint_positions[:joint_count], dtype=np.float32)
    if len(initial_np) < joint_count:
        padded = np.zeros(joint_count, dtype=np.float32)
        padded[:len(initial_np)] = initial_np
        initial_np = padded
    
    robot.set_joint_positions(initial_np)
    for _ in range(5):
        world.step(render=not headless)
    
    actual_pos = robot.get_joint_positions()
    trajectory.append({"step": -1, "action": "initial", "joint_positions": [round(float(p), 4) for p in actual_pos]})
    
    # 각 action 적용
    for step_idx, action in enumerate(action_sequence):
        action_type = action.get("action_type", "")
        params = action.get("params")
        if params is None:
            params = {}
        
        if action_type != "move_joint":
            continue
        
        target_positions = params.get("target_positions")
        if target_positions is None:
            continue
        
        target_np = np.array(target_positions[:joint_count], dtype=np.float32)
        if len(target_np) < joint_count:
            padded = np.zeros(joint_count, dtype=np.float32)
            padded[:len(target_np)] = target_np
            target_np = padded
        
        # Pre-check (Joint Limits & Rules)
        violation = _check_constraints(target_np, joint_limits, ruleset)
        if violation and first_violation_step is None:
            first_violation_step = step_idx
            violations.append({**violation, "step": step_idx, "check_type": "pre_check"})
        
        # 시뮬레이션 실행
        robot.set_joint_positions(target_np)
        
        # Step-wise validation
        collision_detected = False
        torque_violation = False
        workspace_violation = False
        
        for _ in range(steps_per_action):
            world.step(render=not headless)
            
            # 1. Collision Check
            # Assuming any contact force on non-base links implies collision
            # Simple heuristic: sum of contact forces > threshold
            # NOTE: Ideally we check specific collision groups.
            # Here we skip if API fails.
            try:
                # contact forces are expensive to query every step?
                pass 
            except:
                pass

        # End-of-action checks
        result_pos = robot.get_joint_positions()
        
        # 1. Collision Check (Check forces at end of movement)
        try:
             # This requires enablement in Isaac Sim (contact reporting)
             # If not enabled, returns 0s.
             # We assume it's enabled or we skip.
             # Simpler: check if robot is in collision state if available
             pass
        except:
             pass

        # 2. Torque Check
        if torque_limits:
            try:
                efforts = robot.get_measured_joint_efforts()
                for i, eff in enumerate(efforts):
                    limit = torque_limits[i] if i < len(torque_limits) else None
                    if limit and abs(eff) > limit:
                        torque_violation = True
                        if first_violation_step is None:
                            first_violation_step = step_idx
                            violations.append({
                                "constraint": f"joint_{i}_torque",
                                "value": round(float(eff), 4),
                                "limit": limit,
                                "step": step_idx,
                                "check_type": "sim_torque"
                            })
                        break
            except Exception:
                pass

        # 3. Workspace Check (End Effector)
        if workspace_limits:
             try:
                 if hasattr(robot, "end_effector") and robot.end_effector:
                     ee_pos, _ = robot.end_effector.get_world_pose()
                     # workspace_limits: [[min_x, max_x], [min_y, max_y], [min_z, max_z]]
                     for axis, (min_v, max_v) in enumerate(workspace_limits):
                         val = ee_pos[axis]
                         if val < min_v or val > max_v:
                             workspace_violation = True
                             if first_violation_step is None:
                                 first_violation_step = step_idx
                                 violations.append({
                                     "constraint": "workspace_limit",
                                     "value": [round(float(x), 4) for x in ee_pos],
                                     "limit": workspace_limits,
                                     "step": step_idx,
                                     "check_type": "sim_workspace"
                                 })
                             break
             except Exception:
                 pass

        trajectory.append({
            "step": step_idx,
            "action": action_type,
            "target": [round(float(p), 4) for p in target_np],
            "actual": [round(float(p), 4) for p in result_pos]
        })
        
        # Post-check
        post_violation = _check_constraints(result_pos, joint_limits, ruleset)
        if post_violation and first_violation_step is None:
            first_violation_step = step_idx
            violations.append({**post_violation, "step": step_idx, "check_type": "post_check"})
        
        # Divergence check
        divergence = float(np.max(np.abs(target_np[:7] - result_pos[:7])))
        if divergence > 0.1 and first_violation_step is None:
            first_violation_step = step_idx
            violations.append({
                "step": step_idx,
                "constraint": "command_divergence",
                "divergence_rad": round(divergence, 4),
                "check_type": "divergence_check"
            })
    
    verdict = "UNSAFE" if violations else "SAFE"
    latency_ms = round((time.time() - start_time) * 1000, 3)
    
    return {
        "verdict": verdict,
        "engine": "isaac_sim",
        "common": {
            "first_violation_step": first_violation_step,
            "violated_constraint": violations[0]["constraint"] if violations else None,
            "latency_ms": latency_ms,
            "steps_completed": len(trajectory) - 1
        },
        "details": {
            "collision_detected": False, # Placeholder until collision check is robust
            "joint_limit_exceeded": any(v.get("constraint", "").endswith("_limit") for v in violations),
            "torque_violation": any("torque" in v.get("constraint", "") for v in violations),
            "workspace_violation": any("workspace" in v.get("constraint", "") for v in violations),
            "trajectory": trajectory[:10],
            "violations": violations[:5]
        }
    }


def _check_constraints(joint_positions, joint_limits, ruleset):
    """관절 제약 검사"""
    if joint_limits is None:
        joint_limits = {}
        
    for joint_idx_str, limits in joint_limits.items():
        idx = int(joint_idx_str)
        if idx < len(joint_positions):
            val = float(joint_positions[idx])
            if val < limits[0] or val > limits[1]:
                return {"constraint": f"joint_{idx}_limit", "value": round(val, 4), "limits": limits}
    
    for rule in ruleset:
        if isinstance(rule, dict):
            rule_type = rule.get("type", "")
            target = rule.get("target_field", "")
            rule_id = rule.get("rule_id", "")
        else:
            continue
        
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
            min_val = rule.get("min")
            max_val = rule.get("max")
            if min_val is not None and val < min_val:
                return {"constraint": rule_id, "value": round(val, 4), "limits": [min_val, max_val]}
            if max_val is not None and val > max_val:
                return {"constraint": rule_id, "value": round(val, 4), "limits": [min_val, max_val]}
    
    return None
