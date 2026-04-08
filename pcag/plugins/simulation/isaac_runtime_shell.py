from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value) if key in merged else deepcopy(value)
        return merged
    return deepcopy(override)


def resolve_project_ref(ref: str | None) -> Path | None:
    if not ref:
        return None
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path
    return (PROJECT_ROOT / ref_path).resolve()


def _resolve_shell_ref(shell_dir: Path, ref: str | None) -> Path | None:
    if not ref:
        return None
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path
    return (shell_dir / ref_path).resolve()


def load_runtime_shell_bundle(runtime_context: dict[str, Any]) -> dict[str, Any]:
    shell_config_ref = runtime_context.get("shell_config_ref")
    if not shell_config_ref:
        raise ValueError("runtime_context.shell_config_ref is required")

    shell_config_path = resolve_project_ref(shell_config_ref)
    if shell_config_path is None or not shell_config_path.exists():
        raise FileNotFoundError(f"Shell config not found: {shell_config_ref}")

    shell_config = json.loads(shell_config_path.read_text(encoding="utf-8"))
    shell_dir = shell_config_path.parent

    runtime_type = runtime_context.get("runtime_type") or shell_config.get("runtime_type")
    runtime_asset_path: Path | None = None
    scene_path: Path | None = None

    scene_ref = runtime_context.get("scene_ref")
    patch_world_ref = (shell_config.get("simulation_patch") or {}).get("world_ref")
    if scene_ref or patch_world_ref or shell_config.get("scene_file"):
        scene_path = resolve_project_ref(scene_ref) if scene_ref else _resolve_shell_ref(shell_dir, patch_world_ref or shell_config.get("scene_file"))
        if scene_path is None or not scene_path.exists():
            raise FileNotFoundError(f"Scene file not found for runtime_context={runtime_context}")
    elif runtime_type == "map_config":
        runtime_asset_path = (
            resolve_project_ref(runtime_context.get("map_ref"))
            if runtime_context.get("map_ref")
            else _resolve_shell_ref(shell_dir, shell_config.get("map_file"))
        )
        if runtime_asset_path is None or not runtime_asset_path.exists():
            raise FileNotFoundError(f"Map file not found for runtime_context={runtime_context}")
    elif runtime_type in {"process_profile", "parameter_profile"}:
        runtime_asset_path = (
            resolve_project_ref(runtime_context.get("profile_ref"))
            if runtime_context.get("profile_ref")
            else _resolve_shell_ref(shell_dir, shell_config.get("profile_file"))
        )
        if runtime_asset_path is None or not runtime_asset_path.exists():
            raise FileNotFoundError(f"Profile file not found for runtime_context={runtime_context}")

    return {
        "shell_config_path": shell_config_path,
        "shell_dir": shell_dir,
        "shell_config": shell_config,
        "runtime_type": runtime_type,
        "scene_path": scene_path,
        "runtime_asset_path": runtime_asset_path,
    }


def _spawn_runtime_colliders(world, physics_specs: list[dict[str, Any]]):
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


def _spawn_franka(world, shell_config: dict[str, Any]):
    robot_spawn = shell_config.get("robot_spawn") or {}
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
        raise RuntimeError("Failed to spawn a Franka articulation for benchmark runtime.")

    return robot, position


def create_robot_benchmark_world(runtime_context: dict[str, Any], *, headless: bool) -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_runtime_shell_bundle(runtime_context)
    shell_config = bundle["shell_config"]
    scene_path = bundle["scene_path"]
    if scene_path is None:
        raise RuntimeError("Robot benchmark runtime requires a scene_path-backed shell")

    try:
        from isaacsim.core.api import World
    except ImportError:
        from omni.isaac.core import World

    from omni.isaac.core.utils.stage import add_reference_to_stage

    world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0)
    world.scene.add_default_ground_plane()
    add_reference_to_stage(usd_path=str(scene_path), prim_path="/World/BenchmarkEnvironment")
    _spawn_runtime_colliders(world, shell_config.get("runtime_physics_objects") or [])
    robot, robot_position = _spawn_franka(world, shell_config)
    world.reset()

    for _ in range(10):
        world.step(render=not headless)

    runtime_meta = {
        "runtime_id": shell_config.get("runtime_id") or runtime_context.get("runtime_id"),
        "shell_config_path": str(bundle["shell_config_path"]),
        "scene_path": str(scene_path),
        "shell_config": shell_config,
        "robot_spawn_position": [float(x) for x in robot_position],
    }
    return world, robot, runtime_meta


def _pad_joint_positions(values: list[float], joint_count: int) -> list[float]:
    padded = list(values[:joint_count])
    if len(padded) < joint_count:
        padded.extend([0.0] * (joint_count - len(padded)))
    return padded


def apply_initial_state(world, robot, initial_state: dict[str, Any] | None, *, headless: bool, settle_steps: int = 20) -> list[float]:
    if not initial_state:
        return [float(x) for x in robot.get_joint_positions()]

    joint_positions = initial_state.get("joint_positions") or []
    joint_count = len(robot.get_joint_positions())
    padded = _pad_joint_positions(joint_positions, joint_count)
    robot.set_joint_positions(np.array(padded, dtype=float))

    for _ in range(settle_steps):
        world.step(render=not headless)

    return [float(x) for x in robot.get_joint_positions()]


def build_runtime_sim_config(base_sim_config: dict[str, Any], runtime_context: dict[str, Any] | None) -> dict[str, Any]:
    if not runtime_context:
        return deepcopy(base_sim_config)

    merged = deepcopy(base_sim_config)
    bundle = load_runtime_shell_bundle(runtime_context)
    shell_config = bundle["shell_config"]
    sim_patch = deepcopy(shell_config.get("simulation_patch") or {})
    runtime_override = runtime_context.get("simulation_override") or {}
    effective_patch = _deep_merge(sim_patch, runtime_override)
    merged = _deep_merge(merged, effective_patch)

    if bundle.get("scene_path") is not None:
        merged["world_ref"] = str(bundle["scene_path"])
    elif bundle.get("runtime_asset_path") is not None:
        merged["runtime_artifact_ref"] = str(bundle["runtime_asset_path"])

    collision = deepcopy(merged.get("collision") or {})
    safety_probe = shell_config.get("safety_probe") or {}
    if safety_probe:
        collision["enabled"] = True if collision.get("enabled") is None else collision.get("enabled")
        collision["mode"] = collision.get("mode") or "end_effector_sphere"
        if safety_probe.get("end_effector_probe_radius") is not None:
            collision["probe_radius_m"] = float(safety_probe["end_effector_probe_radius"])
        if safety_probe.get("forbidden_fixture_ids") is not None:
            runtime_objects = shell_config.get("runtime_physics_objects") or []
            object_index = {obj.get("id"): obj for obj in runtime_objects if isinstance(obj, dict) and obj.get("id")}
            collision["forbidden_objects"] = [
                {
                    "object_id": fixture_id,
                    "center": object_index[fixture_id].get("center"),
                    "scale": object_index[fixture_id].get("scale"),
                }
                for fixture_id in list(safety_probe["forbidden_fixture_ids"])
                if fixture_id in object_index
            ]
    if collision:
        merged["collision"] = collision

    merged["runtime_context"] = deepcopy(runtime_context)
    return merged
