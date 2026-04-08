from __future__ import annotations

import json
from pathlib import Path

from pcag.plugins.simulation.ode_solver import ODESolverBackend


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESS_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "scene_pack" / "process"


def _load_profile(runtime_id: str) -> dict:
    return json.loads((PROCESS_ROOT / runtime_id / f"{runtime_id}.json").read_text(encoding="utf-8"))


def _backend_for(runtime_id: str) -> tuple[ODESolverBackend, dict]:
    profile = _load_profile(runtime_id)
    backend = ODESolverBackend()
    backend.initialize({**profile["simulation_defaults"], "params": profile["params"]})
    return backend, profile


def test_nominal_profile_non_multiple_duration_stays_safe() -> None:
    backend, profile = _backend_for("reactor_nominal_profile")
    result = backend.validate_trajectory(
        profile["initial_state"],
        [
            {"action_type": "set_heater_output", "params": {"value": 32.0}, "duration_ms": 1450},
            {"action_type": "set_cooling_valve", "params": {"value": 42.0}, "duration_ms": 1550},
        ],
        {"ruleset": profile["nominal_ruleset"]},
    )
    assert result["verdict"] == "SAFE"
    assert result["common"]["steps_completed"] > 0


def test_high_heat_profile_overshoot_turns_unsafe() -> None:
    backend, profile = _backend_for("reactor_high_heat_profile")
    result = backend.validate_trajectory(
        profile["initial_state"],
        [
            {"action_type": "set_cooling_valve", "params": {"value": 8.0}, "duration_ms": 1600},
            {"action_type": "set_heater_output", "params": {"value": 68.0}, "duration_ms": 1400},
        ],
        {"ruleset": profile["nominal_ruleset"]},
    )
    assert result["verdict"] == "UNSAFE"
    assert result["details"]["violations"]


def test_disturbance_profile_recovery_stays_safe() -> None:
    backend, profile = _backend_for("reactor_disturbance_profile")
    result = backend.validate_trajectory(
        profile["initial_state"],
        [
            {"action_type": "set_heater_output", "params": {"value": 22.0}, "duration_ms": 1200},
            {"action_type": "set_cooling_valve", "params": {"value": 58.0}, "duration_ms": 1600},
        ],
        {"ruleset": profile["nominal_ruleset"]},
    )
    assert result["verdict"] == "SAFE"
    assert not result["details"]["violations"]
