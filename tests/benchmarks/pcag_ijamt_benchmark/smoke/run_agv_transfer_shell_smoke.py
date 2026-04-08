from __future__ import annotations

import json
import sys

from common import load_shell_config, print_banner

from pcag.plugins.simulation.discrete_event import DiscreteEventBackend


def main() -> int:
    shell_dir, config = load_shell_config("agv", "agv_transfer_map")
    print_banner("PCAG IJAMT AGV Shell Smoke Test")
    print(f"Shell directory: {shell_dir}")

    backend = DiscreteEventBackend()
    backend.initialize(config["simulation_patch"])

    current_state = dict(config["default_initial_state"])
    action_sequence = [
        {
            "action_type": "move_to",
            "params": {
                "agv_id": "agv_01",
                "target_x": 12,
                "target_y": 7,
            },
        }
    ]

    result = backend.validate_trajectory(
        current_state=current_state,
        action_sequence=action_sequence,
        constraints={"ruleset": []},
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("verdict") != "SAFE":
        print("[FAIL] Expected SAFE verdict for the nominal AGV transfer shell.")
        return 1

    print("[PASS] AGV transfer shell produced a SAFE nominal result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

