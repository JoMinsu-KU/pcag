from __future__ import annotations

import argparse
import json
import time

import numpy as np

from common import load_shell_config, print_banner, resolve_relative_ref


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a NVIDIA-controller-backed Franka pick-and-place smoke test on "
            "the robot_stack_cell manufacturing shell."
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
            "How long to keep the window open after the task finishes. "
            "Defaults to 20 seconds in non-headless mode."
        ),
    )
    parser.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="Keep the final frame open until Enter is pressed.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=1800,
        help="Maximum simulation steps before failing. Default: 1800",
    )
    parser.add_argument(
        "--frame-sleep-ms",
        type=float,
        default=10.0,
        help=(
            "Sleep per rendered frame in GUI mode, in milliseconds. "
            "Set to 0 for fastest playback. Default: 10"
        ),
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


def _try_hide_visual_proxy(prim_path: str) -> bool:
    try:
        from pxr import UsdGeom
        from isaacsim.core.utils.prims import get_prim_at_path

        prim = get_prim_at_path(prim_path)
        if prim is None or not prim.IsValid():
            return False
        UsdGeom.Imageable(prim).MakeInvisible()
        return True
    except Exception:
        return False


def _hide_shell_proxy_cubes() -> None:
    candidate_paths = (
        "/World/BenchmarkEnvironment/Environment/SourceCube_A",
        "/World/BenchmarkEnvironment/Environment/SourceCube_B",
        "/World/BenchmarkEnvironment/World/Environment/SourceCube_A",
        "/World/BenchmarkEnvironment/World/Environment/SourceCube_B",
    )
    for path in candidate_paths:
        _try_hide_visual_proxy(path)


def _create_physics_material(PhysicsMaterial, prim_path: str, *, static_friction: float, dynamic_friction: float):
    return PhysicsMaterial(
        prim_path=prim_path,
        static_friction=static_friction,
        dynamic_friction=dynamic_friction,
        restitution=0.0,
    )


def _spawn_runtime_physics_objects(world, FixedCuboid, physics_specs: list[dict], support_material):
    spawned: dict[str, dict] = {}
    for spec in physics_specs:
        if spec.get("kind") != "fixed_cuboid":
            continue
        collider = world.scene.add(
            FixedCuboid(
                prim_path=spec["prim_path"],
                name=spec["id"],
                position=np.array(spec["center"], dtype=float),
                scale=np.array(spec["scale"], dtype=float),
                size=1.0,
                visible=bool(spec.get("visible", False)),
                color=np.array(spec.get("color", [0.30, 0.56, 0.82]), dtype=float),
                physics_material=support_material,
            )
        )
        spawned[spec["id"]] = {"object": collider, "spec": spec}
    return spawned


def _surface_top_z(spec: dict) -> float:
    return float(spec["center"][2]) + float(spec["scale"][2]) / 2.0


def _resolve_supported_position(base_position: np.ndarray, cube_size: float, support_entry: dict | None) -> np.ndarray:
    resolved = np.array(base_position, dtype=float)
    if support_entry is not None:
        resolved[2] = _surface_top_z(support_entry["spec"]) + cube_size / 2.0
    return resolved


def main() -> int:
    args = parse_args()
    shell_dir, config = load_shell_config("robot", "robot_stack_cell")
    headless = args.headless == "true"
    hold_seconds = args.hold_seconds if args.hold_seconds is not None else (20.0 if not headless else 0.0)
    frame_sleep_s = 0.0 if headless else max(0.0, args.frame_sleep_ms) / 1000.0
    world_ref = resolve_relative_ref(shell_dir, config["simulation_patch"].get("world_ref"))
    hints = config.get("nvidia_pick_place_hints") or {}

    print_banner("PCAG IJAMT Robot Pick-and-Place NVIDIA Smoke Test")
    print(f"Shell directory: {shell_dir}")
    print(f"USD shell: {world_ref}")
    print("This smoke uses NVIDIA Franka pick-place controller/task semantics.")
    print("Run this script from the pcag-isaac environment.")
    if not headless:
        print(f"Window hold: {hold_seconds:.1f}s")
        if args.wait_for_enter:
            print("Window hold mode: wait for Enter")

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
            from isaacsim.core.api.materials.physics_material import PhysicsMaterial
            from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
            from isaacsim.robot.manipulators.examples.franka import Franka
            from isaacsim.robot.manipulators.examples.franka.controllers.pick_place_controller import (
                PickPlaceController,
            )
        except ImportError:
            from omni.isaac.core import World
            from omni.isaac.core.materials.physics_material import PhysicsMaterial
            from omni.isaac.core.objects import DynamicCuboid, FixedCuboid
            from omni.isaac.franka import Franka
            from omni.isaac.franka.controllers.pick_place_controller import PickPlaceController

        from omni.isaac.core.utils.stage import add_reference_to_stage

        world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(usd_path=world_ref, prim_path="/World/BenchmarkEnvironment")
        _hide_shell_proxy_cubes()

        physics_specs = config.get("runtime_physics_objects") or []
        support_material = _create_physics_material(
            PhysicsMaterial,
            prim_path="/World/BenchmarkRuntime/Materials/SupportMaterial",
            static_friction=1.5,
            dynamic_friction=1.2,
        )
        cube_material = _create_physics_material(
            PhysicsMaterial,
            prim_path="/World/BenchmarkRuntime/Materials/CubeMaterial",
            static_friction=1.8,
            dynamic_friction=1.4,
        )
        spawned_objects = _spawn_runtime_physics_objects(world, FixedCuboid, physics_specs, support_material)

        pickup_support = spawned_objects.get(hints.get("pickup_support_id"))
        place_support = spawned_objects.get(hints.get("place_support_id"))
        cube_spec = hints.get("cube") or {}
        controller_spec = hints.get("controller") or {}
        if pickup_support is None or place_support is None:
            raise RuntimeError(
                "Shell config is missing runtime physics support ids for pickup/place. "
                "Expected collider-backed support surfaces before running the NVIDIA smoke."
            )

        cube_size = float(cube_spec["size"])
        initial_cube_position = _resolve_supported_position(cube_spec["initial_position"], cube_size, pickup_support)
        target_position = _resolve_supported_position(cube_spec["target_position"], cube_size, place_support)
        cube = world.scene.add(
            DynamicCuboid(
                prim_path="/World/BenchmarkRuntime/Workpiece",
                name="workpiece",
                position=initial_cube_position,
                scale=np.array([cube_size, cube_size, cube_size], dtype=float),
                size=1.0,
                color=np.array(cube_spec["color"], dtype=float),
                physics_material=cube_material,
                mass=0.04,
            )
        )

        robot_spawn = config.get("robot_spawn") or {}
        robot_position = np.array(robot_spawn.get("position", [0.0, 0.0, 0.0]), dtype=float)
        robot_orientation = np.array(robot_spawn.get("orientation", [1.0, 0.0, 0.0, 0.0]), dtype=float)
        robot = world.scene.add(
            Franka(
                prim_path="/World/Franka",
                name="franka",
                position=robot_position,
                orientation=robot_orientation,
            )
        )
        world.reset()
        articulation_controller = robot.get_articulation_controller()
        for _ in range(int(controller_spec.get("settle_steps_after_reset", 60))):
            world.step(render=not headless)
            if frame_sleep_s > 0:
                time.sleep(frame_sleep_s)

        camera_applied = False
        if not headless:
            camera_applied = _configure_capture_view(config)

        controller = PickPlaceController(
            name="pcag_pick_place_controller",
            gripper=robot.gripper,
            robot_articulation=robot,
            end_effector_initial_height=float(controller_spec.get("end_effector_initial_height", 0.78)),
            events_dt=hints.get("controller_events_dt"),
        )

        end_effector_offset = np.array(controller_spec.get("end_effector_offset", [0.0, 0.0, 0.0]), dtype=float)
        initial_cube_position, _ = cube.get_local_pose()

        done = False
        final_event = None
        last_event = None
        event_trace: list[int] = []
        min_gripper_width = float("inf")
        for step_idx in range(args.max_steps):
            current_cube_position, _ = cube.get_local_pose()
            current_joint_positions = robot.get_joint_positions()
            if current_joint_positions is not None and len(current_joint_positions) >= 9:
                gripper_width = float(current_joint_positions[7] + current_joint_positions[8])
                min_gripper_width = min(min_gripper_width, gripper_width)

            actions = controller.forward(
                picking_position=current_cube_position,
                placing_position=target_position,
                current_joint_positions=current_joint_positions,
                end_effector_offset=end_effector_offset,
            )
            articulation_controller.apply_action(actions)
            world.step(render=not headless)
            final_event = controller.get_current_event()
            if final_event != last_event:
                event_trace.append(final_event)
                last_event = final_event
            if frame_sleep_s > 0:
                time.sleep(frame_sleep_s)

            if controller.is_done():
                done = True
                for _ in range(int(controller_spec.get("settle_steps_after_done", 90))):
                    world.step(render=not headless)
                    if frame_sleep_s > 0:
                        time.sleep(frame_sleep_s)
                break

        final_cube_position, _ = cube.get_local_pose()
        final_joint_positions = robot.get_joint_positions()
        final_end_effector_position, _ = robot.end_effector.get_world_pose()
        xy_error = float(np.linalg.norm(final_cube_position[:2] - target_position[:2]))
        z_error = float(abs(final_cube_position[2] - target_position[2]))
        moved_distance = float(np.linalg.norm(final_cube_position - initial_cube_position))
        success_xy_tolerance = float(controller_spec.get("success_xy_tolerance", 0.08))
        success_z_tolerance = float(controller_spec.get("success_z_tolerance", 0.05))
        placement_success = done and xy_error <= success_xy_tolerance and z_error <= success_z_tolerance

        summary = {
            "shell_runtime_id": config["runtime_id"],
            "world_ref": world_ref,
            "headless": headless,
            "camera_applied": camera_applied,
            "capture_camera": config.get("capture_camera"),
            "controller": "NVIDIA PickPlaceController",
            "task_style": "dynamic cube + Franka manipulation",
            "robot_spawn_position": [round(float(x), 5) for x in robot_position],
            "done": done,
            "placement_success": placement_success,
            "final_event": final_event,
            "event_trace": event_trace,
            "max_steps": args.max_steps,
            "support_ids": {
                "pickup": hints.get("pickup_support_id"),
                "place": hints.get("place_support_id"),
            },
            "cube_size": cube_size,
            "initial_cube_position": [round(float(x), 5) for x in initial_cube_position],
            "final_cube_position": [round(float(x), 5) for x in final_cube_position],
            "target_position": [round(float(x), 5) for x in target_position],
            "moved_distance": round(moved_distance, 5),
            "xy_error": round(xy_error, 5),
            "z_error": round(z_error, 5),
            "success_xy_tolerance": success_xy_tolerance,
            "success_z_tolerance": success_z_tolerance,
            "min_gripper_width": round(min_gripper_width, 5) if min_gripper_width != float("inf") else None,
            "final_end_effector_position": [round(float(x), 5) for x in final_end_effector_position],
            "final_joint_positions": [round(float(x), 5) for x in final_joint_positions],
        }

        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not headless:
            _hold_final_frame(world, hold_seconds, args.wait_for_enter)

        if placement_success:
            print("[PASS] NVIDIA pick-place controller completed and the workpiece reached the stack target.")
            return 0

        if done:
            print("[FAIL] Controller finished, but the workpiece did not reach the target tolerance.")
            return 1

        print("[FAIL] NVIDIA pick-place controller did not finish within the step budget.")
        return 1

    except Exception as exc:
        print(f"[FAIL] NVIDIA pick-place smoke test failed: {exc}")
        return 1
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
