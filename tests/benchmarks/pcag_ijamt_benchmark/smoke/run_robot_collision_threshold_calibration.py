from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from common import BENCHMARK_ROOT, load_shell_config, print_banner, resolve_relative_ref
from run_robot_collision_profile_search import (
    _clamp_to_joint_limits,
    _configure_capture_view,
    _evaluate_candidate,
    _hold_final_frame,
    _pad_positions,
    _spawn_franka,
    _spawn_runtime_colliders,
)


RESULTS_DIR = BENCHMARK_ROOT / "smoke" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calibrate a shell-specific collision threshold by binary-searching "
            "between a known-safe target and a known-hit collision target."
        )
    )
    parser.add_argument(
        "--shell-id",
        default="robot_stack_cell",
        choices=("robot_stack_cell", "robot_pick_place_cell"),
        help="Robot shell to calibrate. Default: robot_stack_cell",
    )
    parser.add_argument(
        "--headless",
        default="true",
        choices=("true", "false"),
        help="Run Isaac Sim in headless mode. Default: true",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Binary-search iterations. Default: 10",
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
        "--margin-alpha",
        type=float,
        default=0.03,
        help="Margin around the estimated threshold for recommended safe/unsafe targets. Default: 0.03",
    )
    parser.add_argument(
        "--safe-target-joints-json",
        default=None,
        help="Optional explicit lower-bound safe target as a JSON vector.",
    )
    parser.add_argument(
        "--hit-target-joints-json",
        default=None,
        help="Optional explicit upper-bound hit target as a JSON vector.",
    )
    parser.add_argument(
        "--search-result-path",
        default=None,
        help="Optional explicit path to a collision-search JSON file. Defaults to the latest file for the shell.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=None,
        help="How long to keep the window open in GUI mode after calibration.",
    )
    parser.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="Keep the final frame open until Enter is pressed.",
    )
    return parser.parse_args()


def _default_search_result_path(shell_id: str) -> Path:
    return RESULTS_DIR / f"{shell_id}_collision_search_latest.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_targets(args: argparse.Namespace, config: dict, joint_count: int) -> tuple[list[float], list[float], Path | None]:
    profiles = config.get("safety_motion_profiles") or {}
    safe_profile = profiles.get("safe") or {}
    safe_sequence = safe_profile.get("target_sequence") or []
    if not safe_sequence:
        raise ValueError(f"Shell {config['runtime_id']} does not define a safe motion profile.")

    safe_target = _pad_positions(safe_sequence[-1], joint_count)
    if args.safe_target_joints_json:
        safe_target = _pad_positions(json.loads(args.safe_target_joints_json), joint_count)

    hit_target = None
    search_result_path = None
    if args.hit_target_joints_json:
        hit_target = _pad_positions(json.loads(args.hit_target_joints_json), joint_count)
    else:
        search_result_path = Path(args.search_result_path) if args.search_result_path else _default_search_result_path(args.shell_id)
        if not search_result_path.exists():
            raise FileNotFoundError(
                f"No collision search result found for {args.shell_id}: {search_result_path}. "
                "Run run_robot_collision_profile_search.py first or pass --hit-target-joints-json."
            )
        search_result = _load_json(search_result_path)
        first_hit = search_result.get("first_hit") or {}
        hit_target = first_hit.get("candidate_target")
        if not hit_target:
            raise ValueError(
                f"Collision search result does not contain first_hit.candidate_target: {search_result_path}"
            )
        hit_target = _pad_positions(hit_target, joint_count)

    return safe_target, hit_target, search_result_path


def _lerp(lower: list[float], upper: list[float], alpha: float) -> list[float]:
    lower_np = np.array(lower, dtype=float)
    upper_np = np.array(upper, dtype=float)
    return [float(x) for x in ((1.0 - alpha) * lower_np + alpha * upper_np)]


def _expand_hit_upper_bound(
    safe_target: list[float],
    hit_target: list[float],
    joint_limits: dict[str, list[float]],
) -> list[list[float]]:
    safe_np = np.array(safe_target, dtype=float)
    hit_np = np.array(hit_target, dtype=float)
    direction = hit_np - safe_np
    expansion_alphas = (1.01, 1.02, 1.05, 1.08, 1.12, 1.2, 1.35, 1.5, 1.75, 2.0)
    candidates: list[list[float]] = []
    for alpha in expansion_alphas:
        expanded = safe_np + (direction * alpha)
        candidates.append(_clamp_to_joint_limits(expanded, joint_limits))
    return candidates


def _write_summary_files(summary: dict, shell_id: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_path = RESULTS_DIR / f"{shell_id}_collision_threshold_latest.json"
    archive_path = RESULTS_DIR / f"{shell_id}_collision_threshold_{timestamp}.json"
    payload = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    latest_path.write_text(payload, encoding="utf-8")
    archive_path.write_text(payload, encoding="utf-8")
    return latest_path, archive_path


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", args.shell_id)
    headless = args.headless == "true"
    hold_seconds = args.hold_seconds if args.hold_seconds is not None else (15.0 if not headless else 0.0)
    phase_frames = max(2, int(args.phase_frames))
    frame_sleep_s = 0.0 if headless else max(0.0, args.frame_sleep_ms) / 1000.0
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))

    print_banner(f"PCAG Robot Collision Threshold Calibration: {args.shell_id}")
    print(f"USD shell: {world_ref}")
    print("This helper finds the boundary between a safe target and a penetrating target.")

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

        safe_target, hit_target, search_result_path = _resolve_targets(args, config, joint_count)

        safe_eval = _evaluate_candidate(
            world, robot, initial, safe_target, joint_limits, workspace_limits,
            safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
        )
        hit_eval = _evaluate_candidate(
            world, robot, initial, hit_target, joint_limits, workspace_limits,
            safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
        )

        if safe_eval["hit"]:
            raise RuntimeError("The supplied safe target already penetrates a fixture. Pick a safer lower bound.")

        hit_target_source = "supplied"
        recovered_hit_candidates = []
        if not hit_eval["hit"]:
            for expanded_target in _expand_hit_upper_bound(safe_target, hit_target, joint_limits):
                expanded_eval = _evaluate_candidate(
                    world, robot, initial, expanded_target, joint_limits, workspace_limits,
                    safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
                )
                recovered_hit_candidates.append(expanded_eval)
                if expanded_eval["hit"]:
                    hit_target = expanded_eval["candidate_target"]
                    hit_eval = expanded_eval
                    hit_target_source = "expanded_from_search_hit"
                    break

        if not hit_eval["hit"]:
            raise RuntimeError(
                "The supplied hit target did not penetrate a fixture, and automatic upper-bound expansion did not find a stable hit. "
                "Run the search helper again with more aggressive candidates."
            )

        lo = 0.0
        hi = 1.0
        threshold_eval = hit_eval
        threshold_alpha = 1.0
        iteration_trace = []

        for iteration in range(max(1, args.iterations)):
            alpha = (lo + hi) / 2.0
            candidate = _lerp(safe_target, hit_target, alpha)
            mid_eval = _evaluate_candidate(
                world, robot, initial, candidate, joint_limits, workspace_limits,
                safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
            )
            trace_item = {
                "iteration": iteration,
                "alpha": round(alpha, 6),
                "hit": mid_eval["hit"],
                "best_gap_m": mid_eval["best_gap_m"],
                "best_gap_fixture_id": mid_eval["best_gap_fixture_id"],
                "candidate_target": mid_eval["candidate_target"],
            }
            iteration_trace.append(trace_item)
            if mid_eval["hit"]:
                hi = alpha
                threshold_alpha = alpha
                threshold_eval = mid_eval
            else:
                lo = alpha

        safe_alpha = max(0.0, threshold_alpha - args.margin_alpha)
        unsafe_alpha = min(1.0, threshold_alpha + args.margin_alpha)
        recommended_safe_target = _lerp(safe_target, hit_target, safe_alpha)
        recommended_unsafe_target = _lerp(safe_target, hit_target, unsafe_alpha)

        recommended_safe_eval = _evaluate_candidate(
            world, robot, initial, recommended_safe_target, joint_limits, workspace_limits,
            safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
        )
        recommended_unsafe_eval = _evaluate_candidate(
            world, robot, initial, recommended_unsafe_target, joint_limits, workspace_limits,
            safety_probe, physics_specs, phase_frames, frame_sleep_s, headless
        )

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "world_ref": world_ref,
            "headless": headless,
            "camera_applied": camera_applied,
            "source_search_result": None if search_result_path is None else str(search_result_path),
            "safe_lower_bound_target": safe_eval["candidate_target"],
            "hit_upper_bound_target": hit_eval["candidate_target"],
            "hit_upper_bound_source": hit_target_source,
            "upper_bound_recovery_attempts": recovered_hit_candidates,
            "threshold_alpha": round(float(threshold_alpha), 6),
            "margin_alpha": args.margin_alpha,
            "threshold_eval": threshold_eval,
            "recommended_safe_alpha": round(float(safe_alpha), 6),
            "recommended_unsafe_alpha": round(float(unsafe_alpha), 6),
            "recommended_safe_eval": recommended_safe_eval,
            "recommended_unsafe_eval": recommended_unsafe_eval,
            "recommended_safe_target_joints_json": json.dumps([recommended_safe_eval["candidate_target"]]),
            "recommended_unsafe_target_joints_json": json.dumps([recommended_unsafe_eval["candidate_target"]]),
            "iteration_trace": iteration_trace,
        }
        latest_path, archive_path = _write_summary_files(summary, args.shell_id)
        summary["result_files"] = {"latest": str(latest_path), "archive": str(archive_path)}
        payload = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
        latest_path.write_text(payload, encoding="utf-8")
        archive_path.write_text(payload, encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not headless:
            _hold_final_frame(world, hold_seconds, args.wait_for_enter)

        if recommended_unsafe_eval["hit"]:
            print("[PASS] Collision threshold calibrated and unsafe recommendation still penetrates.")
            return 0

        print("[FAIL] Calibration completed, but the recommended unsafe target did not penetrate.")
        return 1
    except Exception as exc:
        print(f"[FAIL] Collision threshold calibration failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
