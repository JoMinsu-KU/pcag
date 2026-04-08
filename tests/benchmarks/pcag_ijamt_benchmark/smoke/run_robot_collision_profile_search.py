from __future__ import annotations

import argparse
from datetime import datetime
import json
import time
from pathlib import Path

import numpy as np

from common import BENCHMARK_ROOT, load_shell_config, print_banner, resolve_relative_ref


RESULTS_DIR = BENCHMARK_ROOT / "smoke" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search for a robot joint target that causes fixture penetration in a "
            "canonical robot benchmark shell. This helper is intended to tune "
            "collision_fixture profiles for the frozen benchmark releases."
        )
    )
    parser.add_argument(
        "--shell-id",
        default="robot_stack_cell",
        choices=("robot_stack_cell", "robot_pick_place_cell"),
        help="Robot shell to search against. Default: robot_stack_cell",
    )
    parser.add_argument(
        "--headless",
        default="true",
        choices=("true", "false"),
        help="Run Isaac Sim in headless mode. Default: true",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=48,
        help="Number of random samples to try after deterministic seeds. Default: 48",
    )
    parser.add_argument(
        "--phase-frames",
        type=int,
        default=90,
        help="Interpolation frames per candidate. Default: 90",
    )
    parser.add_argument(
        "--frame-sleep-ms",
        type=float,
        default=0.0,
        help="Sleep per rendered frame in GUI mode, in milliseconds. Default: 0",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for candidate generation. Default: 7",
    )
    parser.add_argument(
        "--stop-on-first-hit",
        action="store_true",
        help="Exit early when the first penetrating target is found.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=None,
        help="How long to keep the window open in GUI mode after the search.",
    )
    parser.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="Keep the final frame open until Enter is pressed.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional explicit JSON output path. Defaults to the benchmark smoke results directory.",
    )
    return parser.parse_args()


def _resolve_summary_paths(shell_id: str, output_path: str | None) -> tuple[Path, Path, Path | None]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_path = RESULTS_DIR / f"{shell_id}_collision_search_latest.json"
    archive_path = RESULTS_DIR / f"{shell_id}_collision_search_{timestamp}.json"
    explicit_path = Path(output_path).expanduser() if output_path else None
    return latest_path, archive_path, explicit_path

def _write_summary_files(summary: dict, latest_path: Path, archive_path: Path, explicit_path: Path | None) -> None:
    payload = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    latest_path.write_text(payload, encoding="utf-8")
    archive_path.write_text(payload, encoding="utf-8")
    if explicit_path is not None:
        explicit_path.parent.mkdir(parents=True, exist_ok=True)
        explicit_path.write_text(payload, encoding="utf-8")


def _configure_capture_view(config: dict) -> bool:
    camera = config.get("capture_camera") or {}
    eye = camera.get("eye")
    target = camera.get("target")
    if not eye or not target:
        return False

    for module_name in ("isaacsim.core.utils.viewports", "omni.isaac.core.utils.viewports"):
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
    return robot


def _spawn_runtime_colliders(world, physics_specs: list[dict]):
    try:
        from isaacsim.core.api.materials.physics_material import PhysicsMaterial
        from isaacsim.core.api.objects import FixedCuboid
    except ImportError:
        from omni.isaac.core.materials.physics_material import PhysicsMaterial
        from omni.isaac.core.objects import FixedCuboid

    material = PhysicsMaterial(
        prim_path="/World/BenchmarkRuntime/Materials/SearchMaterial",
        static_friction=1.0,
        dynamic_friction=0.8,
        restitution=0.0,
    )

    for spec in physics_specs:
        if spec.get("kind") != "fixed_cuboid":
            continue
        world.scene.add(
            FixedCuboid(
                prim_path=spec["prim_path"],
                name=spec["id"],
                position=np.array(spec["center"], dtype=float),
                scale=np.array(spec["scale"], dtype=float),
                size=1.0,
                visible=bool(spec.get("visible", False)),
                color=np.array(spec.get("color", [0.3, 0.56, 0.82]), dtype=float),
                physics_material=material,
            )
        )


def _pad_positions(values: list[float], joint_count: int) -> list[float]:
    padded = list(values[:joint_count])
    if len(padded) < joint_count:
        padded.extend([0.0] * (joint_count - len(padded)))
    return padded


def _distance_point_to_aabb(center: np.ndarray, box_center: np.ndarray, box_scale: np.ndarray) -> float:
    box_min = box_center - (box_scale / 2.0)
    box_max = box_center + (box_scale / 2.0)
    closest = np.minimum(np.maximum(center, box_min), box_max)
    return float(np.linalg.norm(center - closest))


def _sphere_intersects_aabb(center: np.ndarray, radius: float, box_center: np.ndarray, box_scale: np.ndarray) -> bool:
    return _distance_point_to_aabb(center, box_center, box_scale) <= float(radius)


def _clamp_to_joint_limits(candidate: np.ndarray, joint_limits: dict[str, list[float]]) -> list[float]:
    clamped = candidate.copy()
    for joint_idx_str, limits in joint_limits.items():
        joint_idx = int(joint_idx_str)
        if joint_idx >= len(clamped):
            continue
        low, high = map(float, limits)
        clamped[joint_idx] = np.clip(clamped[joint_idx], low + 0.02, high - 0.02)
    return [float(x) for x in clamped]


def _build_candidates(config: dict, joint_count: int, samples: int, seed: int) -> list[list[float]]:
    profiles = config.get("safety_motion_profiles") or {}
    safe_profile = profiles.get("safe") or {}
    safe_sequence = safe_profile.get("target_sequence") or []
    base = np.array(_pad_positions(safe_sequence[-1], joint_count), dtype=float)
    joint_limits = config["simulation_patch"]["joint_limits"]
    arm_joint_count = min(len(joint_limits), joint_count)

    deterministic_offsets = [
        [0.30, 0.22, 0.06, 0.16, 0.40, -0.06, 0.18],
        [0.36, 0.30, 0.10, 0.22, 0.52, -0.12, 0.24],
        [0.18, 0.42, -0.04, 0.20, 0.64, -0.18, 0.12],
        [0.46, 0.12, 0.16, 0.10, 0.72, -0.24, 0.30],
        [0.28, -0.06, 0.20, -0.08, 0.84, -0.18, 0.44],
        [0.52, 0.08, 0.24, -0.12, 0.92, -0.30, 0.38],
    ]

    candidates: list[list[float]] = []
    for offset in deterministic_offsets:
        candidate = base.copy()
        candidate[:arm_joint_count] = candidate[:arm_joint_count] + np.array(offset[:arm_joint_count], dtype=float)
        candidates.append(_clamp_to_joint_limits(candidate, joint_limits))

    rng = np.random.default_rng(seed)
    random_scale = np.array([0.45, 0.40, 0.22, 0.20, 0.70, 0.24, 0.38], dtype=float)
    for _ in range(samples):
        offset = rng.normal(loc=0.0, scale=random_scale)
        offset[0] += rng.uniform(0.1, 0.5)
        offset[4] += rng.uniform(0.25, 0.9)
        candidate = base.copy()
        candidate[:arm_joint_count] = candidate[:arm_joint_count] + offset[:arm_joint_count]
        candidates.append(_clamp_to_joint_limits(candidate, joint_limits))

    return candidates


def _evaluate_candidate(
    world,
    robot,
    initial: list[float],
    candidate: list[float],
    joint_limits: dict,
    workspace_limits: list,
    safety_probe: dict,
    physics_specs: list[dict],
    phase_frames: int,
    frame_sleep_s: float,
    headless: bool,
) -> dict:
    try:
        from isaacsim.core.utils.types import ArticulationAction
    except ImportError:
        from omni.isaac.core.utils.types import ArticulationAction

    articulation_controller = robot.get_articulation_controller()
    robot.set_joint_positions(initial)
    for _ in range(12):
        world.step(render=not headless)
        if frame_sleep_s > 0:
            time.sleep(frame_sleep_s)

    current_positions = np.array(initial, dtype=float)
    target_np = np.array(candidate, dtype=float)
    probe_radius = float(safety_probe.get("end_effector_probe_radius", 0.045))
    forbidden_ids = set(safety_probe.get("forbidden_fixture_ids", []))

    best_gap = float("inf")
    best_gap_fixture = None
    first_violation = None
    final_ee_position = None

    for frame_idx in range(1, phase_frames + 1):
        alpha = frame_idx / phase_frames
        blended = (1.0 - alpha) * current_positions + alpha * target_np
        articulation_controller.apply_action(ArticulationAction(joint_positions=blended.tolist()))
        world.step(render=not headless)
        if frame_sleep_s > 0:
            time.sleep(frame_sleep_s)

        ee_position, _ = robot.end_effector.get_world_pose()
        ee_position = np.array(ee_position, dtype=float)
        final_ee_position = ee_position

        for spec in physics_specs:
            if spec.get("id") not in forbidden_ids:
                continue
            gap = _distance_point_to_aabb(
                ee_position,
                np.array(spec["center"], dtype=float),
                np.array(spec["scale"], dtype=float),
            ) - probe_radius
            if gap < best_gap:
                best_gap = gap
                best_gap_fixture = spec["id"]
            if _sphere_intersects_aabb(
                ee_position,
                probe_radius,
                np.array(spec["center"], dtype=float),
                np.array(spec["scale"], dtype=float),
            ):
                first_violation = {
                    "frame_index": frame_idx,
                    "penetrated_fixture_id": spec["id"],
                    "end_effector_position": [round(float(x), 5) for x in ee_position],
                    "target_joint_positions": [round(float(x), 5) for x in target_np],
                }
                break
        if first_violation is not None:
            break

    return {
        "candidate_target": [round(float(x), 5) for x in candidate],
        "hit": first_violation is not None,
        "first_violation": first_violation,
        "best_gap_m": round(float(best_gap), 5) if best_gap != float("inf") else None,
        "best_gap_fixture_id": best_gap_fixture,
        "final_end_effector_position": None
        if final_ee_position is None
        else [round(float(x), 5) for x in final_ee_position],
    }


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", args.shell_id)
    headless = args.headless == "true"
    hold_seconds = args.hold_seconds if args.hold_seconds is not None else (15.0 if not headless else 0.0)
    phase_frames = max(2, int(args.phase_frames))
    frame_sleep_s = 0.0 if headless else max(0.0, args.frame_sleep_ms) / 1000.0
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))

    print_banner(f"PCAG Robot Collision Profile Search: {args.shell_id}")
    print(f"USD shell: {world_ref}")
    print("This helper searches for a target joint vector that triggers fixture penetration.")

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
        except ImportError:
            from omni.isaac.core import World
        from omni.isaac.core.utils.stage import add_reference_to_stage

        world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(usd_path=world_ref, prim_path="/World/BenchmarkEnvironment")
        _spawn_runtime_colliders(world, config.get("runtime_physics_objects") or [])
        robot = _spawn_franka(world, config)
        world.reset()

        camera_applied = False
        if not headless:
            camera_applied = _configure_capture_view(config)

        joint_count = len(robot.get_joint_positions())
        initial = _pad_positions(config["default_initial_state"]["joint_positions"], joint_count)
        joint_limits = config["simulation_patch"].get("joint_limits") or {}
        workspace_limits = config["simulation_patch"].get("workspace_limits") or []
        safety_probe = config.get("safety_probe") or {}
        physics_specs = config.get("runtime_physics_objects") or []

        candidates = _build_candidates(config, joint_count, args.samples, args.seed)
        results = []
        first_hit = None
        best_candidate = None

        for index, candidate in enumerate(candidates):
            result = _evaluate_candidate(
                world,
                robot,
                initial,
                candidate,
                joint_limits,
                workspace_limits,
                safety_probe,
                physics_specs,
                phase_frames,
                frame_sleep_s,
                headless,
            )
            result["candidate_index"] = index
            results.append(result)

            if result["hit"] and first_hit is None:
                first_hit = result
                if args.stop_on_first_hit:
                    break

            if best_candidate is None:
                best_candidate = result
            else:
                best_gap = best_candidate["best_gap_m"]
                result_gap = result["best_gap_m"]
                if result_gap is not None and (best_gap is None or result_gap < best_gap):
                    best_candidate = result

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "world_ref": world_ref,
            "headless": headless,
            "camera_applied": camera_applied,
            "candidate_count": len(results),
            "first_hit": first_hit,
            "best_candidate": best_candidate,
            "suggested_target_joints_json": None
            if first_hit is None
            else json.dumps([first_hit["candidate_target"]]),
            "results_preview": results[: min(len(results), 12)],
        }
        latest_path, archive_path, explicit_path = _resolve_summary_paths(args.shell_id, args.output_path)
        summary["result_files"] = {
            "latest": str(latest_path),
            "archive": str(archive_path),
            "explicit": None if explicit_path is None else str(explicit_path),
        }
        _write_summary_files(summary, latest_path, archive_path, explicit_path)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not headless:
            _hold_final_frame(world, hold_seconds, args.wait_for_enter)

        if first_hit is not None:
            print("[PASS] Found a candidate that penetrates a forbidden fixture.")
            return 0

        print("[FAIL] No penetrating candidate was found in this search run.")
        return 1
    except Exception as exc:
        print(f"[FAIL] Collision profile search failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
