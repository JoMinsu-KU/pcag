"""Physical trace assessment without importing any PCAG validator.

Only measured samples and separately supplied numeric constraints enter the
decision. Request labels, admission outputs and simulator verdicts are rejected.
SAFE means that the complete *sampled* trace meets the declared constraints; it
does not assert continuous-time or real-hardware safety.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from itertools import combinations
from typing import Any

CHECKER_VERSION = "pcag.independent-trace.v1"
TRACE_SCHEMA = "pcag.raw-trace.v1"
FORBIDDEN_DECISION_FIELDS = {
    "verdict", "backend_verdict", "expected", "expected_status",
    "expected_verdict", "physical_label", "expected_final_status",
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _numeric(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("expected a finite number")
    return number


def _vector(value: Any, size: int | None = None) -> list[float]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("expected a nonempty numeric vector")
    if size is not None and len(value) != size:
        raise ValueError(f"expected vector length {size}")
    return [_numeric(item) for item in value]


def _bounds(value: Any) -> tuple[float, float]:
    low, high = _vector(value, 2)
    if low > high:
        raise ValueError("lower bound exceeds upper bound")
    return low, high


def _no_decisions(value: Any) -> None:
    if isinstance(value, Mapping):
        if FORBIDDEN_DECISION_FIELDS.intersection(value):
            raise ValueError("decision/expected-label fields are forbidden in physical inputs")
        for item in value.values():
            _no_decisions(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _no_decisions(item)


def _violation(step: int, constraint: str, **details: Any) -> dict[str, Any]:
    return {"step": step, "constraint": constraint, **details}


def _sphere_box_distance(center: list[float], obj: Mapping[str, Any]) -> float:
    box_center = _vector(obj["center"], 3)
    scale = _vector(obj["scale"], 3)
    if any(item <= 0 for item in scale):
        raise ValueError("fixture scale must be positive")
    squared = 0.0
    for c, b, side in zip(center, box_center, scale):
        lower, upper = b - side / 2, b + side / 2
        squared += max(lower - c, 0.0, c - upper) ** 2
    return math.sqrt(squared)


def _robot(samples: list[Mapping[str, Any]], constraints: Mapping[str, Any]) -> list[dict[str, Any]]:
    limits = [_bounds(x) for x in constraints["joint_limits"]]
    efforts = _vector(constraints["effort_limits"])
    if len(efforts) > len(limits):
        raise ValueError("effort constraints name more joints than position constraints")
    workspace = [_bounds(x) for x in constraints["workspace_limits"]]
    if len(workspace) != 3 or any(x < 0 for x in efforts):
        raise ValueError("robot workspace needs three bounds and effort limits must be nonnegative")
    velocity_limits = constraints.get("velocity_limits")
    if velocity_limits is not None:
        velocity_limits = _vector(velocity_limits, len(limits))
        if any(v < 0 for v in velocity_limits):
            raise ValueError("velocity limits must be nonnegative")
    collision = constraints.get("collision") or {"enabled": False}
    objects = collision.get("forbidden_objects") or []
    radius = _numeric(collision.get("probe_radius_m", 0.0))
    if radius < 0:
        raise ValueError("probe radius cannot be negative")
    if collision.get("enabled") and not objects:
        raise ValueError("enabled collision assessment requires forbidden fixtures")
    allowed = set(collision.get("allowed_contact_ids", []))
    forbidden = set()
    for obj in objects:
        object_id = obj.get("object_id") or obj.get("id")
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("every forbidden fixture requires an ID")
        forbidden.add(object_id)
        _sphere_box_distance([0., 0., 0.], obj)  # Validate all boxes, even for an empty trace.
    max_force = collision.get("max_contact_force_n")
    if max_force is not None and _numeric(max_force) < 0:
        raise ValueError("contact-force limit cannot be negative")
    violations = []
    for sample in samples:
        step = sample["step"]
        positions = _vector(sample["joint_positions"])
        measured_efforts = _vector(sample["joint_efforts"])
        if len(positions) < len(limits) or len(measured_efforts) < len(efforts):
            raise ValueError("robot trace omits constrained joints")
        ee = _vector(sample["ee_position"], 3)
        contacts = sample["contacts"]
        if not isinstance(contacts, list):
            raise ValueError("contacts must be a list, including [] when none are observed")
        for joint, ((low, high), pos) in enumerate(zip(limits, positions)):
            if not low <= pos <= high:
                violations.append(_violation(step, "joint_position", joint=joint, value=pos, bounds=[low, high]))
        for joint, (force, force_limit) in enumerate(zip(measured_efforts, efforts)):
            if abs(force) > force_limit:
                violations.append(_violation(step, "joint_effort", joint=joint, value=force, limit=force_limit))
        if velocity_limits is not None:
            velocities = _vector(sample["joint_velocities"])
            if len(velocities) < len(limits):
                raise ValueError("robot trace omits constrained joint velocities")
            for joint, (velocity, limit) in enumerate(zip(velocities, velocity_limits)):
                if abs(velocity) > limit:
                    violations.append(_violation(step, "joint_velocity", joint=joint, value=velocity, limit=limit))
        for axis, ((low, high), coordinate) in enumerate(zip(workspace, ee)):
            if not low <= coordinate <= high:
                violations.append(_violation(step, "workspace", axis=axis, value=coordinate, bounds=[low, high]))
        if collision.get("enabled"):
            for obj in objects:
                distance = _sphere_box_distance(ee, obj)
                if distance <= radius:
                    violations.append(_violation(step, "ee_probe_fixture", object_id=obj.get("object_id") or obj["id"], distance_m=distance, radius_m=radius))
        for contact in contacts:
            object_id = contact["object_id"]
            force = _numeric(contact["force_n"])
            if not isinstance(object_id, str) or force < 0:
                raise ValueError("contacts need a string object_id and nonnegative force_n")
            if object_id in forbidden and object_id not in allowed and force > 0:
                violations.append(_violation(step, "forbidden_contact", object_id=object_id, force_n=force))
            if max_force is not None and force > float(max_force):
                violations.append(_violation(step, "contact_force", object_id=object_id, force_n=force, limit_n=max_force))
    return violations


def _agv(samples: list[Mapping[str, Any]], constraints: Mapping[str, Any]) -> list[dict[str, Any]]:
    grid = constraints["grid"]
    width, height = _numeric(grid["width"]), _numeric(grid["height"])
    minimum = _numeric(constraints["min_distance"])
    if width <= 0 or height <= 0 or minimum < 0:
        raise ValueError("invalid grid or minimum distance")
    obstacles = [tuple(_vector(x, 2)) for x in constraints.get("obstacles", grid.get("obstacles", []))]
    capacities = constraints.get("resource_capacities") or {}
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in capacities.values()):
        raise ValueError("resource capacities must be positive integers")
    required_agents = set(constraints.get("agv_ids") or samples[0]["positions"])
    if not required_agents:
        raise ValueError("no AGVs declared")
    previous = None
    violations = []
    for sample in samples:
        step = sample["step"]
        positions = {name: _vector(value, 2) for name, value in sample["positions"].items()}
        if set(positions) != required_agents:
            raise ValueError("AGV set changes or a required AGV is missing")
        for name, (x, y) in positions.items():
            if not (0 <= x < width and 0 <= y < height):
                violations.append(_violation(step, "grid_bounds", agv_id=name, position=[x, y]))
            if (x, y) in obstacles:
                violations.append(_violation(step, "obstacle", agv_id=name, position=[x, y]))
        for first, second in combinations(sorted(positions), 2):
            distance = math.dist(positions[first], positions[second])
            if distance < minimum or positions[first] == positions[second]:
                violations.append(_violation(step, "occupancy_distance", agv_pair=[first, second], distance=distance, minimum=minimum))
            if previous is not None and previous[first] == positions[second] and previous[second] == positions[first] and previous[first] != previous[second]:
                violations.append(_violation(step, "edge_swap", agv_pair=[first, second]))
        if capacities:
            occupancy = sample["resource_occupancy"]
            if set(occupancy) != set(capacities):
                raise ValueError("resource occupancy omits a declared resource")
            for resource, capacity in capacities.items():
                occupants = occupancy[resource]
                if not isinstance(occupants, list) or len(occupants) != len(set(occupants)) or not set(occupants) <= required_agents:
                    raise ValueError("invalid resource occupant IDs")
                if len(occupants) > capacity:
                    violations.append(_violation(step, "resource_capacity", resource=resource, occupants=occupants, capacity=capacity))
        if previous is not None and constraints.get("check_deadlock_cycles", False):
            old_occupants = {tuple(position): name for name, position in previous.items()}
            graph = {name: old_occupants.get(tuple(position)) for name, position in positions.items() if position != previous[name]}
            seen_cycles = set()
            for start in graph:
                chain = []
                node = start
                while node in graph and node not in chain:
                    chain.append(node)
                    node = graph[node]
                if node in chain:
                    cycle = tuple(sorted(chain[chain.index(node):]))
                    if len(cycle) > 2 and cycle not in seen_cycles:
                        seen_cycles.add(cycle)
                        violations.append(_violation(step, "resource_cycle", agv_cycle=list(cycle)))
        previous = positions
    return violations


def _process(samples: list[Mapping[str, Any]], constraints: Mapping[str, Any]) -> list[dict[str, Any]]:
    bounds = constraints["bounds"]
    if not {"temperature", "pressure"} <= set(bounds):
        raise ValueError("process assessment needs temperature and pressure bounds")
    parsed = {field: _bounds(value) for field, value in bounds.items()}
    violations = []
    for sample in samples:
        for field, (low, high) in parsed.items():
            value = _numeric(sample[field])
            if not low <= value <= high:
                violations.append(_violation(sample["step"], "process_range", field=field, value=value, bounds=[low, high]))
    return violations


def assess_trace(asset_family: str, trace: Mapping[str, Any], constraints: Mapping[str, Any]) -> dict[str, Any]:
    """Assess complete observations; malformed/missing observations are indeterminate.

    ``trace``: schema_version, asset_family, complete, expected_samples, samples.
    Samples: contiguous ``step`` starting at zero and strictly increasing ``t_s``.
    The caller must retain the original trace and constraints matching these hashes.
    """
    result: dict[str, Any] = {"checker_version": CHECKER_VERSION, "asset_family": asset_family,
                             "verdict": "INDETERMINATE", "violations": [], "coverage": {}}
    try:
        result["trace_sha256"] = canonical_sha256(trace)
        result["constraints_sha256"] = canonical_sha256(constraints)
        _no_decisions(trace)
        _no_decisions(constraints)
        if trace["schema_version"] != TRACE_SCHEMA or trace["asset_family"] != asset_family:
            raise ValueError("trace schema or asset family mismatch")
        if trace["complete"] is not True:
            raise ValueError("trace is not declared complete")
        samples = trace["samples"]
        if not isinstance(samples, list) or len(samples) < 2:
            raise ValueError("at least two measured samples are required")
        if type(trace["expected_samples"]) is not int or trace["expected_samples"] != len(samples):
            raise ValueError("sample count does not match expected_samples")
        previous_t = None
        gap = constraints.get("max_sample_gap_s")
        if gap is not None and _numeric(gap) <= 0:
            raise ValueError("max_sample_gap_s must be positive")
        for step, sample in enumerate(samples):
            if type(sample["step"]) is not int or sample["step"] != step:
                raise ValueError("sample steps must be contiguous from zero")
            t = _numeric(sample["t_s"])
            if t < 0 or (previous_t is not None and t <= previous_t):
                raise ValueError("sample timestamps must be nonnegative and increasing")
            if step == 0 and abs(t) > 1e-9:
                raise ValueError("trace timestamps must start at zero")
            if gap is not None and previous_t is not None and t - previous_t > float(gap) + 1e-9:
                raise ValueError("trace has a sampling gap")
            previous_t = t
        functions = {"robot": _robot, "agv": _agv, "process": _process}
        if asset_family not in functions:
            raise ValueError("unsupported asset family")
        contact_observed = False
        if asset_family == "robot":
            observer = trace.get("contact_observer", "not_instrumented")
            if observer not in {"not_instrumented", "physx_contact_sensor"}:
                raise ValueError("unknown physical-contact observer")
            contact_observed = observer == "physx_contact_sensor"
            collision_config = constraints.get("collision") or {}
            if not contact_observed and (constraints.get("require_contact_observation", False)
                                         or collision_config.get("max_contact_force_n") is not None):
                raise ValueError("physical contact observation is required but not instrumented")
        violations = functions[asset_family](samples, constraints)
        result.update(verdict="UNSAFE" if violations else "SAFE", violations=violations,
                      coverage={"complete": True, "samples": len(samples), "duration_s": samples[-1]["t_s"]-samples[0]["t_s"], "scope": "sampled_trace_constraints"})
        if asset_family == "robot":
            result["coverage"].update(physical_contacts=contact_observed,
                position_joints=len(constraints["joint_limits"]), effort_joints=len(constraints["effort_limits"]),
                collision_scope="policy_end_effector_sphere_vs_AABB" if (constraints.get("collision") or {}).get("enabled") else "not_assessed")
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError, IndexError) as exc:
        result["reason"] = str(exc)
    return result


def constraints_from_policy(asset_family: str, asset_profile: Mapping[str, Any], *,
                            simulation_config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Convert declared policy data, never validator outputs, to checker inputs.

    Pass the realized runtime simulation configuration when shell-specific
    fixtures/maps/limits override the profile. This function does not import
    policy services or any simulation backend.
    """
    simulation = deepcopy(dict(simulation_config if simulation_config is not None else asset_profile.get("simulation", {})))
    if asset_family == "robot":
        joint_map = simulation["joint_limits"]
        limits = [joint_map[str(i)] for i in range(len(joint_map))] if isinstance(joint_map, Mapping) else joint_map
        return {"joint_limits": limits, "effort_limits": simulation["torque_limits"],
                "workspace_limits": simulation["workspace_limits"], "collision": simulation.get("collision", {"enabled": False})}
    if asset_family == "agv":
        return {"grid": simulation["grid"], "min_distance": simulation.get("min_distance", 1.0),
                "agv_ids": sorted(simulation.get("agvs", {})), "resource_capacities": simulation.get("resource_capacities", {}),
                "check_deadlock_cycles": bool(simulation.get("check_deadlock_cycles", True))}
    if asset_family == "process":
        bounds = {rule["target_field"]: [rule["min"], rule["max"]]
                  for rule in asset_profile["ruleset"] if rule.get("type") == "range"
                  and rule.get("target_field") in {"temperature", "pressure"}}
        if set(bounds) != {"temperature", "pressure"}:
            raise ValueError("policy does not specify both physical process bounds")
        return {"bounds": bounds}
    raise ValueError("unsupported asset family")
