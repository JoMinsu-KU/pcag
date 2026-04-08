from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy
from pcag.plugins.simulation.discrete_event import DiscreteEventBackend
from pcag.plugins.simulation.isaac_runtime_shell import build_runtime_sim_config
from pcag.plugins.simulation.ode_solver import ODESolverBackend

DATASET_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "releases"
    / "integrated_benchmark_release_v2"
    / "pcag_execution_dataset.json"
)
POLICY_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "policies"
    / "pcag_benchmark_policy_v1.json"
)
INDEPENDENT_RESULTS_DIR = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "results"
    / "independent_validation"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dataset(path: Path = DATASET_PATH) -> dict[str, Any]:
    return load_json(path)


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return load_json(path)


def normalize_action_sequence(action_spec: Any) -> list[dict[str, Any]]:
    if action_spec is None:
        return []
    if isinstance(action_spec, list):
        return json.loads(json.dumps(action_spec))
    if isinstance(action_spec, dict):
        return [json.loads(json.dumps(action_spec))]
    raise TypeError(f"Unsupported action_sequence type: {type(action_spec)!r}")


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = json.loads(json.dumps(base))
        for key, value in override.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = json.loads(json.dumps(value))
        return merged
    if isinstance(override, list):
        return json.loads(json.dumps(override))
    if override is not None:
        return json.loads(json.dumps(override))
    return json.loads(json.dumps(base))


def materialize_case(case: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    libraries = dataset.get("libraries", {})
    runtime_contexts = libraries.get("runtime_contexts", {})
    initial_states = libraries.get("initial_states", {})
    action_sequences = libraries.get("action_sequences", {})

    runtime = case.get("runtime") or {}
    proof = case.get("proof") or {}

    runtime_ref = runtime.get("runtime_context_ref")
    initial_state_ref = runtime.get("initial_state_ref")
    action_ref = proof.get("action_sequence_ref")

    runtime_context = deep_merge(
        runtime_contexts.get(runtime_ref) or {},
        proof.get("runtime_context") or {},
    )
    initial_state = json.loads(json.dumps(initial_states.get(initial_state_ref) or {}))
    action_sequence = normalize_action_sequence(action_sequences.get(action_ref))

    return {
        "case_id": case["case_id"],
        "asset_id": case["asset_id"],
        "case_group": case.get("case_group"),
        "scenario_family": case.get("scenario_family"),
        "expected_status": (case.get("expected") or {}).get("status"),
        "expected_reason_code": (case.get("expected") or {}).get("reason_code"),
        "source_task_family": ((case.get("source_benchmark") or {}).get("task_family")),
        "shell_role": ((case.get("operation_context") or {}).get("shell_role")),
        "mission_phase": ((case.get("operation_context") or {}).get("mission_phase")),
        "description": case.get("description"),
        "runtime_context": runtime_context,
        "initial_state": initial_state,
        "action_sequence": action_sequence,
        "expected_verdict": "SAFE" if (case.get("expected") or {}).get("status") == "COMMITTED" else "UNSAFE",
    }


def stratum_key(case: dict[str, Any]) -> str:
    return "::".join(
        [
            case.get("source_task_family") or "unknown_task",
            case.get("shell_role") or "unknown_role",
            case.get("mission_phase") or "unknown_phase",
        ]
    )


def select_stratified_cases(
    cases: list[dict[str, Any]],
    *,
    target_count: int,
    key_fn: Callable[[dict[str, Any]], str] = stratum_key,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in sorted(cases, key=lambda item: item["case_id"]):
        buckets[key_fn(case)].append(case)

    selected: list[dict[str, Any]] = []
    bucket_names = sorted(buckets.keys())
    while len(selected) < target_count and bucket_names:
        next_bucket_names: list[str] = []
        for bucket_name in bucket_names:
            bucket = buckets[bucket_name]
            if bucket and len(selected) < target_count:
                selected.append(bucket.pop(0))
            if bucket:
                next_bucket_names.append(bucket_name)
        bucket_names = next_bucket_names
    return selected


def build_validation_subset(
    dataset: dict[str, Any],
    *,
    per_asset_nominal: int = 20,
    per_asset_unsafe: int = 20,
) -> list[dict[str, Any]]:
    materialized = [materialize_case(case, dataset) for case in dataset.get("cases", [])]
    selected: list[dict[str, Any]] = []
    for asset_id in ("robot_arm_01", "agv_01", "reactor_01"):
        nominal_cases = [
            case for case in materialized
            if case["asset_id"] == asset_id and case["expected_status"] == "COMMITTED"
        ]
        unsafe_cases = [
            case for case in materialized
            if case["asset_id"] == asset_id and case["expected_status"] == "UNSAFE"
        ]
        selected.extend(select_stratified_cases(nominal_cases, target_count=per_asset_nominal))
        selected.extend(select_stratified_cases(unsafe_cases, target_count=per_asset_unsafe))
    return selected


def _robot_proxy() -> IsaacSimProxy:
    os.environ["PCAG_ENABLE_ISAAC"] = "true"
    proxy = IsaacSimProxy()
    proxy.initialize({"headless": True, "timeout_ms": 120000, "simulation_steps_per_action": 30})
    if not proxy.is_initialized():
        raise RuntimeError("IsaacSimProxy failed to initialize for independent validation")
    return proxy


def _effective_constraints(asset_policy: dict[str, Any], runtime_context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sim_config = json.loads(json.dumps(asset_policy.get("simulation") or {}))
    effective_sim_config = build_runtime_sim_config(sim_config, runtime_context)
    constraints = {
        "ruleset": json.loads(json.dumps(asset_policy.get("ruleset") or [])),
        "world_ref": effective_sim_config.get("world_ref"),
        "workspace_limits": effective_sim_config.get("workspace_limits"),
        "torque_limits": effective_sim_config.get("torque_limits"),
        "joint_limits": effective_sim_config.get("joint_limits"),
        "collision": effective_sim_config.get("collision"),
        "runtime_context": runtime_context,
    }
    return effective_sim_config, constraints


def run_oracle_case(
    case: dict[str, Any],
    *,
    asset_policy: dict[str, Any],
    robot_proxy: IsaacSimProxy | None = None,
) -> dict[str, Any]:
    runtime_context = json.loads(json.dumps(case.get("runtime_context") or {}))
    initial_state = json.loads(json.dumps(case.get("initial_state") or {}))
    action_sequence = json.loads(json.dumps(case.get("action_sequence") or []))
    effective_sim_config, constraints = _effective_constraints(asset_policy, runtime_context)

    if case["asset_id"] == "robot_arm_01":
        if robot_proxy is None:
            raise ValueError("robot_proxy is required for robot oracle execution")
        preload_result = robot_proxy.preload_runtime(runtime_context, initial_state)
        current_state = json.loads(json.dumps(preload_result.get("current_state") or initial_state))
        oracle_result = robot_proxy.validate_trajectory(current_state, action_sequence, constraints)
        return {
            "case_id": case["case_id"],
            "asset_id": case["asset_id"],
            "expected_status": case["expected_status"],
            "expected_verdict": case["expected_verdict"],
            "oracle_verdict": oracle_result.get("verdict"),
            "match": oracle_result.get("verdict") == case["expected_verdict"],
            "engine": oracle_result.get("engine"),
            "latency_ms": ((oracle_result.get("common") or {}).get("latency_ms")),
            "preload_result": preload_result,
            "oracle_result": oracle_result,
        }

    if case["asset_id"] == "agv_01":
        backend = DiscreteEventBackend()
        backend.initialize(effective_sim_config)
    elif case["asset_id"] == "reactor_01":
        backend = ODESolverBackend()
        backend.initialize(effective_sim_config)
    else:
        raise ValueError(f"Unsupported asset_id for oracle execution: {case['asset_id']}")

    oracle_result = backend.validate_trajectory(initial_state, action_sequence, constraints)
    return {
        "case_id": case["case_id"],
        "asset_id": case["asset_id"],
        "expected_status": case["expected_status"],
        "expected_verdict": case["expected_verdict"],
        "oracle_verdict": oracle_result.get("verdict"),
        "match": oracle_result.get("verdict") == case["expected_verdict"],
        "engine": oracle_result.get("engine"),
        "latency_ms": ((oracle_result.get("common") or {}).get("latency_ms")),
        "preload_result": None,
        "oracle_result": oracle_result,
    }
