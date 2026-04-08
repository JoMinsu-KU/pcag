from __future__ import annotations

import argparse
import json
import time

from common import load_shell_config, print_banner, resolve_relative_ref


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standalone Isaac Sim smoke test for the Franka-aligned "
            "robot_stack_cell benchmark shell."
        )
    )
    parser.add_argument(
        "--headless",
        default="true",
        choices=("true", "false"),
        help="Run Isaac Sim in headless mode. Default: true",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=None,
        help=(
            "How long to keep the window open after the motion finishes. "
            "Defaults to 20 seconds in non-headless mode."
        ),
    )
    parser.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="Keep the final frame open until Enter is pressed.",
    )
    parser.add_argument(
        "--phase-frames",
        type=int,
        default=70,
        help="Interpolation frames per motion phase. Default: 70",
    )
    parser.add_argument(
        "--frame-sleep-ms",
        type=float,
        default=18.0,
        help=(
            "Sleep per rendered frame in GUI mode, in milliseconds. "
            "Set to 0 for fastest playback. Default: 18"
        ),
    )
    return parser.parse_args()


def _spawn_franka(world):
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
        raise RuntimeError(
            "Failed to spawn a Franka articulation. Check the pcag-isaac environment."
        )

    return robot


def _pad_positions(values: list[float], joint_count: int) -> list[float]:
    padded = list(values[:joint_count])
    if len(padded) < joint_count:
        padded.extend([0.0] * (joint_count - len(padded)))
    return padded


def _animate_joint_motion(
    world,
    robot,
    start_positions: list[float],
    target_positions: list[float],
    frames: int,
    render: bool,
    sleep_s: float,
):
    if frames <= 1:
        robot.set_joint_positions(target_positions)
        world.step(render=render)
        if sleep_s > 0:
            time.sleep(sleep_s)
        return robot.get_joint_positions()

    for frame_idx in range(1, frames + 1):
        alpha = frame_idx / frames
        blended = [
            float(start + (target - start) * alpha)
            for start, target in zip(start_positions, target_positions)
        ]
        robot.set_joint_positions(blended)
        world.step(render=render)
        if sleep_s > 0:
            time.sleep(sleep_s)

    return robot.get_joint_positions()


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


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", "robot_stack_cell")
    headless = args.headless == "true"
    hold_seconds = args.hold_seconds if args.hold_seconds is not None else (20.0 if not headless else 0.0)
    phase_frames = max(2, int(args.phase_frames))
    frame_sleep_s = 0.0 if headless else max(0.0, args.frame_sleep_ms) / 1000.0
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))

    print_banner("PCAG IJAMT Robot Stack Shell Smoke Test")
    print(f"Shell directory: {shell_dir}")
    print(f"USD shell: {world_ref}")
    print("This is the preferred Franka-first robot smoke path for dataset construction.")
    print("Run this script from the pcag-isaac environment.")
    if not headless:
        print(f"Window hold: {hold_seconds:.1f}s")
        if args.wait_for_enter:
            print("Window hold mode: wait for Enter")
        print(f"Motion phase frames: {phase_frames}")
        print(f"Frame sleep: {frame_sleep_s:.3f}s")

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

        robot = _spawn_franka(world)
        world.reset()
        camera_applied = False
        if not headless:
            camera_applied = _configure_capture_view(config)

        joint_count = len(robot.get_joint_positions())
        initial = _pad_positions(config["default_initial_state"]["joint_positions"], joint_count)
        conveyor_pick = _pad_positions([0.28, -0.86, 0.22, -2.18, -0.18, 1.74, 0.58], joint_count)
        transfer = _pad_positions([0.18, -0.54, 0.08, -2.06, 0.10, 1.70, 0.82], joint_count)
        stack_place = _pad_positions([0.46, -0.44, 0.22, -1.90, 0.18, 1.57, 1.08], joint_count)
        retreat = _pad_positions([0.04, -0.30, -0.04, -2.10, 0.04, 1.82, 0.28], joint_count)

        robot.set_joint_positions(initial)
        for _ in range(20):
            world.step(render=not headless)
            if frame_sleep_s > 0:
                time.sleep(frame_sleep_s)
        actual_initial = robot.get_joint_positions()

        actual_pick = _animate_joint_motion(
            world,
            robot,
            initial,
            conveyor_pick,
            frames=phase_frames,
            render=not headless,
            sleep_s=frame_sleep_s,
        )
        actual_transfer = _animate_joint_motion(
            world,
            robot,
            conveyor_pick,
            transfer,
            frames=phase_frames,
            render=not headless,
            sleep_s=frame_sleep_s,
        )
        actual_stack = _animate_joint_motion(
            world,
            robot,
            transfer,
            stack_place,
            frames=phase_frames,
            render=not headless,
            sleep_s=frame_sleep_s,
        )
        actual_retreat = _animate_joint_motion(
            world,
            robot,
            stack_place,
            retreat,
            frames=phase_frames,
            render=not headless,
            sleep_s=frame_sleep_s,
        )

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "source_alignment": config["source_alignment"],
            "world_ref": world_ref,
            "headless": headless,
            "camera_applied": camera_applied,
            "capture_camera": config.get("capture_camera"),
            "animation_mode": "interpolated_joint_motion",
            "phase_frames": phase_frames,
            "initial_command": initial,
            "initial_actual": [round(float(x), 4) for x in actual_initial],
            "conveyor_pick_command": conveyor_pick,
            "conveyor_pick_actual": [round(float(x), 4) for x in actual_pick],
            "transfer_command": transfer,
            "transfer_actual": [round(float(x), 4) for x in actual_transfer],
            "stack_place_command": stack_place,
            "stack_place_actual": [round(float(x), 4) for x in actual_stack],
            "retreat_command": retreat,
            "retreat_actual": [round(float(x), 4) for x in actual_retreat],
        }

        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not headless:
            _hold_final_frame(world, hold_seconds, args.wait_for_enter)

        print("[PASS] Franka-aligned stack shell loaded and executed staged joint motions.")
        return 0

    except Exception as exc:
        print(f"[FAIL] Robot stack shell smoke test failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
