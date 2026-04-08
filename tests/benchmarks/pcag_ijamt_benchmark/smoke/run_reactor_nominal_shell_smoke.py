from __future__ import annotations

import json
import sys

from common import load_shell_config, print_banner

from pcag.plugins.simulation.ode_solver import ODESolverBackend


def main() -> int:
    shell_dir, config = load_shell_config("process", "reactor_nominal_profile")
    print_banner("PCAG IJAMT Reactor Shell Smoke Test")
    print(f"Shell directory: {shell_dir}")

    backend = ODESolverBackend()
    backend.initialize(config["simulation_patch"])

    current_state = dict(config["default_initial_state"])
    action_sequence = [
        {
            "action_type": "set_heater_output",
            "params": {"value": 42.0},
            "duration_ms": 1500,
        },
        {
            "action_type": "set_cooling_valve",
            "params": {"value": 35.0},
            "duration_ms": 1500,
        },
    ]

    result = backend.validate_trajectory(
        current_state=current_state,
        action_sequence=action_sequence,
        constraints={"ruleset": config["ruleset_patch"]},
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("verdict") != "SAFE":
        print("[FAIL] Expected SAFE verdict for the nominal reactor profile shell.")
        return 1

    print("[PASS] Reactor nominal shell produced a SAFE nominal result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

