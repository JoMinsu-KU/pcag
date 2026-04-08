from __future__ import annotations

import argparse
import json

from common import load_shell_config, print_banner, resolve_relative_ref


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standalone Isaac Sim smoke test for the "
            "robot_pick_place_cell benchmark shell."
        )
    )
    parser.add_argument(
        "--headless",
        default="false",
        choices=("true", "false"),
        help="Run Isaac Sim in headless mode. Default: true",
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


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", "robot_pick_place_cell")
    headless = args.headless == "true"
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))

    print_banner("PCAG IJAMT Robot Shell Standalone Smoke Test")
    print(f"Shell directory: {shell_dir}")
    print(f"USD shell: {world_ref}")
    print("This script must be run from the pcag-isaac environment.")

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

        joint_count = len(robot.get_joint_positions())
        initial = _pad_positions(config["default_initial_state"]["joint_positions"], joint_count)
        target = _pad_positions([0.12, -0.72, 0.10, -2.05, -0.05, 1.72, 0.88], joint_count)

        robot.set_joint_positions(initial)
        for _ in range(10):
            world.step(render=not headless)

        actual_initial = robot.get_joint_positions()

        robot.set_joint_positions(target)
        for _ in range(30):
            world.step(render=not headless)

        actual_target = robot.get_joint_positions()

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "world_ref": world_ref,
            "headless": headless,
            "initial_command": initial,
            "initial_actual": [round(float(x), 4) for x in actual_initial],
            "target_command": target,
            "target_actual": [round(float(x), 4) for x in actual_target],
        }

        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print("[PASS] Robot shell loaded, Franka spawned, and joint motion executed.")
        return 0

    except Exception as exc:
        print(f"[FAIL] Robot shell smoke test failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
