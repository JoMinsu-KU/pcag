"""
Dedicated Isaac Sim worker process used by the Safety Cluster.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any

import numpy as np

from pcag.plugins.simulation.isaac_collision import evaluate_collision_probe, get_end_effector_position

logger = logging.getLogger(__name__)


def isaac_worker_main(request_queue, result_queue, init_config: dict):
    print("[Isaac Worker] Starting...")

    try:
        from isaacsim import SimulationApp

        headless = init_config.get("headless", True)
        sim_app = SimulationApp({"headless": headless})
        print("[Isaac Worker] SimulationApp started")

        from isaacsim.core.api import World

        world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
        world.scene.add_default_ground_plane()
        robot = _load_robot(world)
        world.reset()
        for _ in range(10):
            world.step(render=not headless)

        joint_count = len(robot.get_joint_positions())
        current_scene = init_config.get("world_ref")
        current_runtime_id = None
        current_runtime_meta: dict[str, Any] = {}
        steps_per_action = init_config.get("simulation_steps_per_action", 30)

        print(f"[Isaac Worker] Ready! Robot: {joint_count} joints")
        result_queue.put({"job_id": "__BOOT__", "ok": True, "message": "Isaac Worker ready"})

        while True:
            try:
                try:
                    job = request_queue.get(timeout=0.1)
                except Exception:
                    time.sleep(0.01)
                    continue

                if job is None or job.get("type") == "SHUTDOWN":
                    print("[Isaac Worker] Shutdown signal received")
                    break

                job_id = job.get("job_id", "unknown")
                job_type = job.get("type")

                if job_type == "GET_STATE":
                    state = _get_current_state(world, robot, current_runtime_meta)
                    result_queue.put({"job_id": job_id, "ok": True, "result": state})
                    continue

                if job_type == "PRELOAD_RUNTIME":
                    world, robot, preload_result = _preload_runtime_scene(
                        world=world,
                        runtime_context=job.get("runtime_context") or {},
                        initial_state=job.get("initial_state") or {},
                        headless=headless,
                    )
                    current_scene = preload_result.get("scene_path")
                    current_runtime_id = preload_result.get("runtime_id")
                    current_runtime_meta = preload_result
                    joint_count = len(robot.get_joint_positions())
                    result_queue.put({"job_id": job_id, "ok": True, "result": preload_result})
                    continue

                runtime_context = (job.get("constraints") or {}).get("runtime_context") or job.get("runtime_context")
                if runtime_context:
                    desired_runtime_id = runtime_context.get("runtime_id")
                    desired_scene = runtime_context.get("scene_ref") or job.get("world_ref")
                    if desired_runtime_id != current_runtime_id or (
                        desired_scene and str(desired_scene) != str(current_scene)
                    ):
                        world, robot, preload_result = _preload_runtime_scene(
                            world=world,
                            runtime_context=runtime_context,
                            initial_state=job.get("initial_state") or {},
                            headless=headless,
                        )
                        current_scene = preload_result.get("scene_path")
                        current_runtime_id = preload_result.get("runtime_id")
                        current_runtime_meta = preload_result
                        joint_count = len(robot.get_joint_positions())
                else:
                    world_ref = job.get("world_ref")
                    if world_ref and str(world_ref) != str(current_scene):
                        world, robot = _reload_scene(world, world_ref, headless)
                        current_scene = world_ref
                        current_runtime_id = None
                        current_runtime_meta = {}
                        joint_count = len(robot.get_joint_positions())

                result = _validate_trajectory(
                    world=world,
                    robot=robot,
                    job=job,
                    joint_count=joint_count,
                    steps_per_action=steps_per_action,
                    headless=headless,
                )
                result_queue.put({"job_id": job_id, "ok": True, "result": result})
            except Exception as exc:
                print(f"[Isaac Worker] Job failed: {exc}")
                result_queue.put(
                    {
                        "job_id": job.get("job_id", "unknown") if isinstance(job, dict) else "unknown",
                        "ok": False,
                        "error": str(exc),
                        "trace": traceback.format_exc(),
                    }
                )

        print("[Isaac Worker] Shutting down...")
        try:
            world.stop()
            world.clear()
        except Exception:
            pass
        sim_app.close()
        print("[Isaac Worker] Shutdown complete")
    except Exception as exc:
        print(f"[Isaac Worker] Boot failed: {exc}")
        result_queue.put(
            {
                "job_id": "__BOOT__",
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(),
            }
        )


def _load_robot(world):
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


def _reload_scene(world, scene_path: str, headless: bool):
    print(f"[Isaac Worker] Reloading scene: {scene_path}")

    try:
        world.stop()
        world.clear()
    except Exception:
        pass

    from isaacsim.core.api import World

    world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
    world.scene.add_default_ground_plane()

    if scene_path and scene_path.endswith(".usd"):
        from omni.isaac.core.robots import Robot
        from omni.isaac.core.utils.stage import add_reference_to_stage

        add_reference_to_stage(usd_path=scene_path, prim_path="/World/Robot")
        robot = world.scene.add(Robot(prim_path="/World/Robot", name="robot"))
    else:
        robot = _load_robot(world)

    world.reset()
    for _ in range(10):
        world.step(render=not headless)
    return world, robot


def _preload_runtime_scene(world, runtime_context: dict[str, Any], initial_state: dict[str, Any], headless: bool):
    try:
        world.stop()
        world.clear()
    except Exception:
        pass

    from pcag.plugins.simulation.isaac_runtime_shell import apply_initial_state, create_robot_benchmark_world

    created_world, robot, runtime_meta = create_robot_benchmark_world(runtime_context, headless=headless)
    applied_initial = apply_initial_state(
        created_world,
        robot,
        initial_state,
        headless=headless,
    )
    runtime_meta["applied_initial_joint_positions"] = applied_initial
    runtime_meta["current_state"] = _get_current_state(created_world, robot, runtime_meta)
    runtime_meta["status"] = "READY"
    return created_world, robot, runtime_meta


def _extract_joint_positions(state: dict[str, Any], joint_count: int) -> np.ndarray:
    joint_positions = state.get("joint_positions")
    if joint_positions is None:
        joint_positions = [state.get(f"joint_{idx}", 0.0) for idx in range(joint_count)]
    joint_np = np.array(joint_positions[:joint_count], dtype=np.float32)
    if len(joint_np) < joint_count:
        padded = np.zeros(joint_count, dtype=np.float32)
        padded[: len(joint_np)] = joint_np
        joint_np = padded
    return joint_np


def _extract_joint_velocities(state: dict[str, Any], joint_count: int) -> np.ndarray | None:
    joint_velocities = state.get("joint_velocities")
    if joint_velocities is None:
        candidate = []
        for idx in range(joint_count):
            key = f"joint_{idx}_velocity" if idx < 7 else None
            if key is None or key not in state:
                return None
            candidate.append(state[key])
        joint_velocities = candidate

    velocity_np = np.array(joint_velocities[:joint_count], dtype=np.float32)
    if len(velocity_np) < joint_count:
        padded = np.zeros(joint_count, dtype=np.float32)
        padded[: len(velocity_np)] = velocity_np
        velocity_np = padded
    return velocity_np


def _restore_robot_state(world, robot, state: dict[str, Any], joint_count: int):
    baseline_positions = _extract_joint_positions(state, joint_count)
    robot.set_joint_positions(baseline_positions)

    baseline_velocities = _extract_joint_velocities(state, joint_count)
    if baseline_velocities is not None and hasattr(robot, "set_joint_velocities"):
        try:
            robot.set_joint_velocities(baseline_velocities)
        except Exception:
            pass


def _get_current_state(world, robot, runtime_meta: dict[str, Any] | None = None):
    joint_positions = robot.get_joint_positions()
    joint_velocities = robot.get_joint_velocities()

    try:
        joint_efforts = robot.get_measured_joint_efforts()
    except Exception:
        joint_efforts = [0.0] * len(joint_positions)

    ee_pos = get_end_effector_position(robot)

    state = {
        "joint_positions": [float(x) for x in joint_positions],
        "joint_velocities": [float(x) for x in joint_velocities],
        "joint_efforts": [float(x) for x in joint_efforts],
        "ee_position": [float(x) for x in ee_pos] if ee_pos is not None else None,
        "timestamp": time.time(),
    }
    if runtime_meta:
        state["runtime_id"] = runtime_meta.get("runtime_id")
        state["scene_path"] = runtime_meta.get("scene_path")
    return state


def _validate_trajectory(world, robot, job, joint_count: int, steps_per_action: int, headless: bool):
    start_time = time.time()

    current_state = job.get("state") or {}
    action_sequence = job.get("actions") or []
    constraints = job.get("constraints") or {}

    joint_positions = current_state.get("joint_positions")
    if joint_positions is None:
        joint_positions = [current_state.get(f"joint_{i}", 0.0) for i in range(joint_count)]

    if not joint_positions:
        return {
            "verdict": "INDETERMINATE",
            "engine": "isaac_sim",
            "common": {
                "first_violation_step": None,
                "violated_constraint": None,
                "latency_ms": 0,
                "steps_completed": 0,
            },
            "details": {"reason": "No joint positions in current_state"},
        }

    ruleset = constraints.get("ruleset") or []
    joint_limits = constraints.get("joint_limits") or {}
    workspace_limits = constraints.get("workspace_limits")
    torque_limits = constraints.get("torque_limits")
    collision_config = constraints.get("collision") or {}

    trajectory = []
    violations = []
    first_violation_step = None
    collision_detected = False
    collision_probe_unavailable = False
    collided_object_ids = set()
    collision_violation_recorded = False
    collision_probe_violation_recorded = False

    world.reset()
    initial_np = _extract_joint_positions(current_state, joint_count)
    robot.set_joint_positions(initial_np)
    baseline_velocities = _extract_joint_velocities(current_state, joint_count)
    if baseline_velocities is not None and hasattr(robot, "set_joint_velocities"):
        try:
            robot.set_joint_velocities(baseline_velocities)
        except Exception:
            pass

    for _ in range(5):
        world.step(render=not headless)

    try:
        actual_pos = robot.get_joint_positions()
        trajectory.append({"step": -1, "action": "initial", "joint_positions": [round(float(p), 4) for p in actual_pos]})

        for step_idx, action in enumerate(action_sequence):
            if action.get("action_type", "") != "move_joint":
                continue

            params = action.get("params") or {}
            target_positions = params.get("target_positions")
            if target_positions is None:
                continue

            target_np = np.array(target_positions[:joint_count], dtype=np.float32)
            if len(target_np) < joint_count:
                padded = np.zeros(joint_count, dtype=np.float32)
                padded[: len(target_np)] = target_np
                target_np = padded

            violation = _check_constraints(target_np, joint_limits, ruleset)
            if violation and first_violation_step is None:
                first_violation_step = step_idx
                violations.append({**violation, "step": step_idx, "check_type": "pre_check"})

            robot.set_joint_positions(target_np)

            for _ in range(steps_per_action):
                world.step(render=not headless)
                if collision_config.get("enabled"):
                    collision_eval = evaluate_collision_probe(get_end_effector_position(robot), collision_config)
                    if collision_eval["probe_unavailable"] and not collision_probe_unavailable:
                        collision_probe_unavailable = True
                        if first_violation_step is None:
                            first_violation_step = step_idx
                        if not collision_probe_violation_recorded:
                            violations.append(
                                {
                                    "constraint": "collision_probe_unavailable",
                                    "step": step_idx,
                                    "check_type": "sim_collision",
                                    "detail": "Collision policy is enabled but end-effector pose is unavailable.",
                                }
                            )
                            collision_probe_violation_recorded = True
                    if collision_eval["collision_detected"]:
                        collision_detected = True
                        collided_object_ids.update(collision_eval["collided_object_ids"])
                        if first_violation_step is None:
                            first_violation_step = step_idx
                        if not collision_violation_recorded:
                            violations.append(
                                {
                                    "constraint": "fixture_collision",
                                    "step": step_idx,
                                    "check_type": "sim_collision",
                                    "objects": collision_eval["collided_object_ids"],
                                    "probe_radius_m": collision_eval["probe_radius_m"],
                                }
                            )
                            collision_violation_recorded = True

            result_pos = robot.get_joint_positions()

            if torque_limits:
                try:
                    efforts = robot.get_measured_joint_efforts()
                    for idx, effort in enumerate(efforts):
                        limit = torque_limits[idx] if idx < len(torque_limits) else None
                        if limit and abs(effort) > limit:
                            if first_violation_step is None:
                                first_violation_step = step_idx
                                violations.append(
                                    {
                                        "constraint": f"joint_{idx}_torque",
                                        "value": round(float(effort), 4),
                                        "limit": limit,
                                        "step": step_idx,
                                        "check_type": "sim_torque",
                                    }
                                )
                            break
                except Exception:
                    pass

            if workspace_limits:
                ee_pos = get_end_effector_position(robot)
                if ee_pos is not None:
                    for axis, (min_v, max_v) in enumerate(workspace_limits):
                        value = ee_pos[axis]
                        if value < min_v or value > max_v:
                            if first_violation_step is None:
                                first_violation_step = step_idx
                                violations.append(
                                    {
                                        "constraint": "workspace_limit",
                                        "value": [round(float(x), 4) for x in ee_pos],
                                        "limit": workspace_limits,
                                        "step": step_idx,
                                        "check_type": "sim_workspace",
                                    }
                                )
                            break

            trajectory.append(
                {
                    "step": step_idx,
                    "action": "move_joint",
                    "target": [round(float(p), 4) for p in target_np],
                    "actual": [round(float(p), 4) for p in result_pos],
                }
            )

            post_violation = _check_constraints(result_pos, joint_limits, ruleset)
            if post_violation and first_violation_step is None:
                first_violation_step = step_idx
                violations.append({**post_violation, "step": step_idx, "check_type": "post_check"})

            divergence = float(np.max(np.abs(target_np[:7] - result_pos[:7])))
            if divergence > 0.1 and first_violation_step is None:
                first_violation_step = step_idx
                violations.append(
                    {
                        "step": step_idx,
                        "constraint": "command_divergence",
                        "divergence_rad": round(divergence, 4),
                        "check_type": "divergence_check",
                    }
                )
    finally:
        _restore_robot_state(world, robot, current_state, joint_count)

    verdict = "UNSAFE" if violations else "SAFE"
    latency_ms = round((time.time() - start_time) * 1000, 3)
    return {
        "verdict": verdict,
        "engine": "isaac_sim",
        "common": {
            "first_violation_step": first_violation_step,
            "violated_constraint": violations[0]["constraint"] if violations else None,
            "latency_ms": latency_ms,
            "steps_completed": len(trajectory) - 1,
        },
        "details": {
            "collision_detected": collision_detected,
            "collision_probe_unavailable": collision_probe_unavailable,
            "collision_objects": sorted(collided_object_ids),
            "joint_limit_exceeded": any(v.get("constraint", "").endswith("_limit") for v in violations),
            "torque_violation": any("torque" in v.get("constraint", "") for v in violations),
            "workspace_violation": any("workspace" in v.get("constraint", "") for v in violations),
            "trajectory": trajectory[:10],
            "violations": violations[:5],
        },
    }


def _check_constraints(joint_positions, joint_limits, ruleset):
    for joint_idx_str, limits in (joint_limits or {}).items():
        idx = int(joint_idx_str)
        if idx < len(joint_positions):
            value = float(joint_positions[idx])
            if value < limits[0] or value > limits[1]:
                return {"constraint": f"joint_{idx}_limit", "value": round(value, 4), "limits": limits}

    for rule in ruleset:
        if not isinstance(rule, dict):
            continue
        rule_type = rule.get("type", "")
        target = rule.get("target_field", "")
        rule_id = rule.get("rule_id", "")
        if not target.startswith("joint_"):
            continue
        try:
            idx = int(target.split("_")[1])
        except (IndexError, ValueError):
            continue
        if idx >= len(joint_positions):
            continue

        value = float(joint_positions[idx])
        if rule_type == "range":
            min_val = rule.get("min")
            max_val = rule.get("max")
            if min_val is not None and value < min_val:
                return {"constraint": rule_id, "value": round(value, 4), "limits": [min_val, max_val]}
            if max_val is not None and value > max_val:
                return {"constraint": rule_id, "value": round(value, 4), "limits": [min_val, max_val]}
    return None
