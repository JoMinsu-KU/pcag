from __future__ import annotations

from typing import Any

import numpy as np


def get_end_effector_position(robot) -> np.ndarray | None:
    """Best-effort end-effector pose fetch for Franka-like articulations."""
    try:
        if hasattr(robot, "end_effector") and robot.end_effector:
            ee_pos, _ = robot.end_effector.get_world_pose()
            return np.array(ee_pos, dtype=float)
    except Exception:
        return None
    return None


def sphere_intersects_aabb(
    center: np.ndarray,
    radius: float,
    box_center: np.ndarray,
    box_scale: np.ndarray,
) -> bool:
    """Return True when a sphere intersects an axis-aligned box."""
    box_min = box_center - (box_scale / 2.0)
    box_max = box_center + (box_scale / 2.0)
    closest = np.minimum(np.maximum(center, box_min), box_max)
    distance = np.linalg.norm(center - closest)
    return float(distance) <= float(radius)


def evaluate_collision_probe(
    ee_position: np.ndarray | None,
    collision_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Evaluate a lightweight policy-driven collision probe.

    The current production-ready shape is a spherical probe attached to the
    end-effector and a set of forbidden AABB fixtures declared in policy.
    """
    config = collision_config or {}
    enabled = bool(config.get("enabled", False))
    forbidden_objects = config.get("forbidden_objects") or []
    probe_radius_m = float(config.get("probe_radius_m", 0.045))

    result = {
        "enabled": enabled,
        "probe_radius_m": probe_radius_m if enabled else None,
        "configured_object_count": len(forbidden_objects),
        "collision_detected": False,
        "collided_object_ids": [],
        "probe_unavailable": False,
    }

    if not enabled:
        return result

    if ee_position is None:
        result["probe_unavailable"] = True
        return result

    collided: list[str] = []
    for obj in forbidden_objects:
        object_id = obj.get("object_id") or obj.get("id")
        center = obj.get("center")
        scale = obj.get("scale")
        if not object_id or center is None or scale is None:
            continue
        if len(center) != 3 or len(scale) != 3:
            continue
        if sphere_intersects_aabb(
            np.array(ee_position, dtype=float),
            probe_radius_m,
            np.array(center, dtype=float),
            np.array(scale, dtype=float),
        ):
            collided.append(object_id)

    result["collided_object_ids"] = sorted(set(collided))
    result["collision_detected"] = bool(result["collided_object_ids"])
    return result
