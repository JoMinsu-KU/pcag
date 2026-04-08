from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from common import load_shell_config, print_banner, resolve_relative_ref


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a safety-oriented robot shell smoke test on a canonical robot benchmark shell. "
            "This script evaluates joint-limit, workspace, and fixture-penetration "
            "signals for benchmark-style joint targets."
        )
    )
    parser.add_argument(
        "--shell-id",
        default="robot_stack_cell",
        choices=("robot_stack_cell", "robot_pick_place_cell"),
        help="Robot shell to evaluate. Default: robot_stack_cell",
    )
    parser.add_argument(
        "--headless",
        default="true",
        choices=("true", "false"),
        help="Run Isaac Sim in headless mode. Default: true",
    )
    parser.add_argument(
        "--profile",
        default="safe",
        help="Built-in profile declared by the shell config. Default: safe",
    )
    parser.add_argument(
        "--target-joints-json",
        default=None,
        help=(
            "JSON list of target joint vectors, e.g. "
            "'[[0.2,-0.6,0.1,-2.1,0.0,1.7,0.7],[...]]'. "
            "Overrides --profile when provided."
        ),
    )
    parser.add_argument(
        "--target-joints-file",
        default=None,
        help="Path to a JSON file containing a list of target joint vectors.",
    )
    parser.add_argument(
        "--phase-frames",
        type=int,
        default=90,
        help="Interpolation frames per target phase. Default: 90",
    )
    parser.add_argument(
        "--frame-sleep-ms",
        type=float,
        default=10.0,
        help="Sleep per rendered frame in GUI mode, in milliseconds. Default: 10",
    )
    parser.add_argument(
        "--expect",
        default="auto",
        choices=("auto", "safe", "unsafe", "any"),
        help="Expected verdict for exit code handling. Default: auto",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=None,
        help="How long to keep the window open after evaluation. Defaults to 20 seconds in GUI mode.",
    )
    parser.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="Keep the final frame open until Enter is pressed.",
    )
    return parser.parse_args()


def _configure_capture_view(config: dict) -> bool:
    camera = config.get("capture_camera") or {}
    eye = camera.get("eye")
    target = camera.get("target")
    if not eye or not target:
        return False

    for module_name in (
        "isaacsim.core.utils.viewports",
        "omni.isaac.core.utils.viewports",
    ):
        try:
            module = __import__(module_name, fromlist=["set_camera_view"])
            set_camera_view = getattr(module, "set_camera_view", None)
            if set_camera_view is None:
                continue
            set_camera_view(eye=eye, target=target, camera_prim_path="/OmniverseKit_Persp")
            return True
        except Exception:
            continue

    return False


def _hold_final_frame(world, seconds: float, wait_for_enter: bool) -> None:
    if wait_for_enter:
        print("Press Enter to close the Isaac Sim window...")
        input()
        return

    if seconds <= 0:
        return

    deadline = time.time() + seconds
    while time.time() < deadline:
        world.step(render=True)
        time.sleep(1.0 / 30.0)


def _spawn_franka(world, config: dict):
    robot_spawn = config.get("robot_spawn") or {}
    position = np.array(robot_spawn.get("position", [0.0, 0.0, 0.0]), dtype=float)
    orientation = np.array(robot_spawn.get("orientation", [1.0, 0.0, 0.0, 0.0]), dtype=float)

    robot = None

    try:
        from isaacsim.robot.manipulators.examples.franka import Franka

        robot = world.scene.add(
            Franka(
                prim_path="/World/Franka",
                name="franka",
                position=position,
                orientation=orientation,
            )
        )
    except (ImportError, Exception):
        pass

    if robot is None:
        try:
            from omni.isaac.franka import Franka

            robot = world.scene.add(
                Franka(
                    prim_path="/World/Franka",
                    name="franka",
                    position=position,
                    orientation=orientation,
                )
            )
        except (ImportError, Exception):
            pass

    if robot is None:
        raise RuntimeError("Failed to spawn a Franka articulation.")

    return robot, position


def _spawn_runtime_colliders(world, physics_specs: list[dict]):
    try:
        from isaacsim.core.api.materials.physics_material import PhysicsMaterial
        from isaacsim.core.api.objects import FixedCuboid
    except ImportError:
        from omni.isaac.core.materials.physics_material import PhysicsMaterial
        from omni.isaac.core.objects import FixedCuboid

    support_material = PhysicsMaterial(
        prim_path="/World/BenchmarkRuntime/Materials/SafetyProbeMaterial",
        static_friction=1.0,
        dynamic_friction=0.8,
        restitution=0.0,
    )

    spawned = {}
    for spec in physics_specs:
        if spec.get("kind") != "fixed_cuboid":
            continue
        spawned[spec["id"]] = world.scene.add(
            FixedCuboid(
                prim_path=spec["prim_path"],
                name=spec["id"],
                position=np.array(spec["center"], dtype=float),
                scale=np.array(spec["scale"], dtype=float),
                size=1.0,
                visible=bool(spec.get("visible", False)),
                color=np.array(spec.get("color", [0.3, 0.56, 0.82]), dtype=float),
                physics_material=support_material,
            )
        )
    return spawned


def _pad_positions(values: list[float], joint_count: int) -> list[float]:
    padded = list(values[:joint_count])
    if len(padded) < joint_count:
        padded.extend([0.0] * (joint_count - len(padded)))
    return padded


def _sphere_intersects_aabb(center: np.ndarray, radius: float, box_center: np.ndarray, box_scale: np.ndarray) -> bool:
    box_min = box_center - (box_scale / 2.0)
    box_max = box_center + (box_scale / 2.0)
    closest = np.minimum(np.maximum(center, box_min), box_max)
    distance = np.linalg.norm(center - closest)
    return float(distance) <= float(radius)


def _evaluate_step(
    joint_positions: np.ndarray,
    ee_position: np.ndarray,
    joint_limits: dict,
    workspace_limits: list,
    safety_probe: dict,
    physics_specs: list[dict],
):
    violation_reasons: list[str] = []
    joint_limit_exceeded = False
    workspace_violation = False
    penetrated_fixture_ids: list[str] = []
    min_joint_margin = float("inf")
    min_workspace_margin = float("inf")

    for joint_idx_str, limits in joint_limits.items():
        joint_idx = int(joint_idx_str)
        if joint_idx >= len(joint_positions):
            continue
        low, high = limits
        value = float(joint_positions[joint_idx])
        margin = min(value - low, high - value)
        min_joint_margin = min(min_joint_margin, margin)
        if value < low or value > high:
            joint_limit_exceeded = True

    if joint_limit_exceeded:
        violation_reasons.append("joint_limit")

    if workspace_limits:
        for axis, bounds in enumerate(workspace_limits):
            low, high = bounds
            value = float(ee_position[axis])
            margin = min(value - low, high - value)
            min_workspace_margin = min(min_workspace_margin, margin)
            if value < low or value > high:
                workspace_violation = True
        if workspace_violation:
            violation_reasons.append("workspace")

    probe_radius = float(safety_probe.get("end_effector_probe_radius", 0.045))
    forbidden_ids = set(safety_probe.get("forbidden_fixture_ids", []))
    for spec in physics_specs:
        if spec.get("id") not in forbidden_ids:
            continue
        if _sphere_intersects_aabb(
            ee_position,
            probe_radius,
            np.array(spec["center"], dtype=float),
            np.array(spec["scale"], dtype=float),
        ):
            penetrated_fixture_ids.append(spec["id"])

    if penetrated_fixture_ids:
        violation_reasons.append("fixture_penetration")

    return {
        "joint_limit_exceeded": joint_limit_exceeded,
        "workspace_violation": workspace_violation,
        "penetrated_fixture_ids": sorted(set(penetrated_fixture_ids)),
        "violation_reasons": violation_reasons,
        "min_joint_margin_rad": None if min_joint_margin == float("inf") else float(min_joint_margin),
        "min_workspace_margin_m": None if min_workspace_margin == float("inf") else float(min_workspace_margin),
    }


def _load_target_sequence(args: argparse.Namespace, config: dict, joint_count: int) -> tuple[str, list[list[float]]]:
    if args.target_joints_json:
        payload = json.loads(args.target_joints_json)
        return "custom_json", [_pad_positions(item, joint_count) for item in payload]

    if args.target_joints_file:
        payload = json.loads(Path(args.target_joints_file).read_text(encoding="utf-8"))
        return "custom_file", [_pad_positions(item, joint_count) for item in payload]

    profiles = config.get("safety_motion_profiles") or {}
    if args.profile not in profiles:
        raise ValueError(f"Unknown shell profile '{args.profile}'. Available: {', '.join(sorted(profiles))}")

    profile = profiles[args.profile]
    if profile.get("target_sequence"):
        return args.profile, [_pad_positions(item, joint_count) for item in profile["target_sequence"]]

    if profile.get("joint_limit_target"):
        initial = _pad_positions(config["default_initial_state"]["joint_positions"], joint_count)
        target = initial.copy()
        target_meta = profile["joint_limit_target"]
        joint_index = int(target_meta["joint_index"])
        joint_limits = config["simulation_patch"]["joint_limits"]
        low, high = joint_limits[str(joint_index)]
        overrun = float(target_meta.get("overrun", 0.0))
        bound = target_meta["bound"]
        target[joint_index] = (float(high) + overrun) if bound == "upper" else (float(low) - overrun)
        return args.profile, [target]

    raise ValueError(f"Profile '{args.profile}' does not declare a target sequence or joint-limit mutation.")


def _expected_outcome(args: argparse.Namespace, profile_name: str, config: dict) -> str:
    if args.expect != "auto":
        return args.expect
    profiles = config.get("safety_motion_profiles") or {}
    profile = profiles.get(profile_name) or {}
    return profile.get("expected_outcome", "safe")


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", args.shell_id)
    headless = args.headless == "true"
    hold_seconds = args.hold_seconds if args.hold_seconds is not None else (20.0 if not headless else 0.0)
    phase_frames = max(2, int(args.phase_frames))
    frame_sleep_s = 0.0 if headless else max(0.0, args.frame_sleep_ms) / 1000.0
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))

    print_banner(f"PCAG IJAMT Robot Shell Safety Smoke Test: {args.shell_id}")
    print(f"Shell directory: {shell_dir}")
    print(f"USD shell: {world_ref}")
    print("This smoke evaluates robot-shell safety signals, not task completion.")
    print("Signals: joint-limit, workspace, and fixture-penetration.")
    print("Run this script from the pcag-isaac environment.")

    try:
        from isaacsim import SimulationApp
    except ImportError as exc:
        print(f"[FAIL] Isaac Sim is not importable in this environment: {exc}")
        return 1

    app = None
    try:
        app = SimulationApp({"headless": headless, "width": 1280, "height": 720})

        try:
            from isaacsim.core.api import World
            from isaacsim.core.utils.types import ArticulationAction
        except ImportError:
            from omni.isaac.core import World
            from omni.isaac.core.utils.types import ArticulationAction

        from omni.isaac.core.utils.stage import add_reference_to_stage

        world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(usd_path=world_ref, prim_path="/World/BenchmarkEnvironment")
        _spawn_runtime_colliders(world, config.get("runtime_physics_objects") or [])
        robot, robot_position = _spawn_franka(world, config)
        world.reset()

        camera_applied = False
        if not headless:
            camera_applied = _configure_capture_view(config)

        joint_count = len(robot.get_joint_positions())
        initial = _pad_positions(config["default_initial_state"]["joint_positions"], joint_count)
        profile_name, target_sequence = _load_target_sequence(args, config, joint_count)
        expected_outcome = _expected_outcome(args, profile_name, config)

        articulation_controller = robot.get_articulation_controller()
        robot.set_joint_positions(initial)
        for _ in range(20):
            world.step(render=not headless)
            if frame_sleep_s > 0:
                time.sleep(frame_sleep_s)

        joint_limits = config["simulation_patch"].get("joint_limits") or {}
        workspace_limits = config["simulation_patch"].get("workspace_limits") or []
        safety_probe = config.get("safety_probe") or {}
        physics_specs = config.get("runtime_physics_objects") or []

        executed_trace = []
        first_violation = None
        aggregate_fixture_ids: set[str] = set()
        aggregate_joint_limit_exceeded = False
        aggregate_workspace_violation = False
        min_joint_margin = float("inf")
        min_workspace_margin = float("inf")

        current_positions = np.array(initial, dtype=float)
        for phase_index, target in enumerate(target_sequence):
            target_np = np.array(target, dtype=float)
            for frame_idx in range(1, phase_frames + 1):
                alpha = frame_idx / phase_frames
                blended = (1.0 - alpha) * current_positions + alpha * target_np
                articulation_controller.apply_action(ArticulationAction(joint_positions=blended.tolist()))
                world.step(render=not headless)
                if frame_sleep_s > 0:
                    time.sleep(frame_sleep_s)

                actual_joints = np.array(robot.get_joint_positions(), dtype=float)
                ee_position, _ = robot.end_effector.get_world_pose()
                ee_position = np.array(ee_position, dtype=float)
                step_eval = _evaluate_step(
                    actual_joints,
                    ee_position,
                    joint_limits,
                    workspace_limits,
                    safety_probe,
                    physics_specs,
                )
                aggregate_fixture_ids.update(step_eval["penetrated_fixture_ids"])
                aggregate_joint_limit_exceeded = (
                    aggregate_joint_limit_exceeded or step_eval["joint_limit_exceeded"]
                )
                aggregate_workspace_violation = (
                    aggregate_workspace_violation or step_eval["workspace_violation"]
                )
                if step_eval["min_joint_margin_rad"] is not None:
                    min_joint_margin = min(min_joint_margin, step_eval["min_joint_margin_rad"])
                if step_eval["min_workspace_margin_m"] is not None:
                    min_workspace_margin = min(min_workspace_margin, step_eval["min_workspace_margin_m"])

                trace_item = {
                    "phase_index": phase_index,
                    "frame_index": frame_idx,
                    "target_joint_positions": [round(float(x), 5) for x in target_np],
                    "actual_joint_positions": [round(float(x), 5) for x in actual_joints],
                    "end_effector_position": [round(float(x), 5) for x in ee_position],
                    "joint_limit_exceeded": step_eval["joint_limit_exceeded"],
                    "workspace_violation": step_eval["workspace_violation"],
                    "penetrated_fixture_ids": step_eval["penetrated_fixture_ids"],
                }
                if len(executed_trace) < 40 or step_eval["violation_reasons"]:
                    executed_trace.append(trace_item)
                if first_violation is None and step_eval["violation_reasons"]:
                    first_violation = trace_item | {"violation_reasons": step_eval["violation_reasons"]}

            current_positions = target_np

        verdict = "UNSAFE" if first_violation is not None else "SAFE"
        success = (
            expected_outcome == "any"
            or (expected_outcome == "safe" and verdict == "SAFE")
            or (expected_outcome == "unsafe" and verdict == "UNSAFE")
        )

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "world_ref": world_ref,
            "headless": headless,
            "camera_applied": camera_applied,
            "profile": profile_name,
            "expected_outcome": expected_outcome,
            "verdict": verdict,
            "robot_spawn_position": [round(float(x), 5) for x in robot_position],
            "phase_frames": phase_frames,
            "joint_limit_exceeded": aggregate_joint_limit_exceeded,
            "workspace_violation": aggregate_workspace_violation,
            "fixture_penetration_detected": bool(aggregate_fixture_ids),
            "penetrated_fixture_ids": sorted(aggregate_fixture_ids),
            "min_joint_margin_rad": None if min_joint_margin == float("inf") else round(float(min_joint_margin), 5),
            "min_workspace_margin_m": None if min_workspace_margin == float("inf") else round(float(min_workspace_margin), 5),
            "first_violation": first_violation,
            "executed_trace_preview": executed_trace,
        }

        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not headless:
            _hold_final_frame(world, hold_seconds, args.wait_for_enter)

        if success:
            print(f"[PASS] Robot safety smoke matched expected outcome: {expected_outcome}.")
            return 0

        print(f"[FAIL] Robot safety smoke verdict {verdict} did not match expected outcome {expected_outcome}.")
        return 1

    except Exception as exc:
        print(f"[FAIL] Robot safety smoke failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
