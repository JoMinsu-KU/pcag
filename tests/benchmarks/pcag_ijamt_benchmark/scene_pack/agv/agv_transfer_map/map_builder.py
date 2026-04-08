"""
Build the canonical `agv_transfer_map` benchmark shell.

This script generates:

- `agv_transfer_map.json`
- `shell_config.json`

The output is aligned with the current discrete-event simulation backend used by
PCAG for AGV validation.
"""

from __future__ import annotations

import json
from pathlib import Path


SHELL_ID = "agv_transfer_map"
MAP_FILE = f"{SHELL_ID}.json"
CONFIG_FILE = "shell_config.json"


def build_map_payload() -> dict:
    return {
        "runtime_id": SHELL_ID,
        "runtime_type": "map_config",
        "asset_family": "agv",
        "asset_id": "agv_01",
        "grid": {
            "width": 14,
            "height": 10,
            "obstacles": [
                [4, 2], [4, 3], [4, 4], [4, 5],
                [9, 4], [9, 5], [9, 6],
                [6, 8], [7, 8],
            ],
            "intersections": [[6, 3], [7, 3], [10, 7]],
            "stations": {
                "source_load": [1, 1],
                "transfer_mid": [6, 3],
                "target_drop": [12, 7],
            },
            "zones": {
                "pickup_corridor": [[1, 1], [2, 1], [3, 1], [4, 1]],
                "main_transfer_lane": [[5, 3], [6, 3], [7, 3], [8, 3], [9, 3]],
                "dropoff_lane": [[10, 6], [11, 6], [12, 6], [12, 7]],
            },
        },
        "agvs": {
            "agv_01": {"position": [1, 1], "speed": 1.0},
            "agv_02": {"position": [13, 9], "speed": 1.0},
        },
        "min_distance": 1.0,
        "source_alignment": {
            "primary_motifs": ["station_transfer"],
            "upstream_sources": ["warehouse_world_curated"],
        },
        "recommended_case_roles": [
            "transfer_nominal",
            "transfer_with_path_variant",
            "transfer_boundary_violation",
            "transfer_fault_case",
        ],
        "notes": [
            "This shell models a nominal station-to-station transfer corridor.",
            "The shell is intended for direct use with the discrete-event backend.",
        ],
    }


def build_shell_config(map_payload: dict) -> dict:
    return {
        "runtime_id": SHELL_ID,
        "runtime_type": "map_config",
        "asset_family": "agv",
        "asset_id": "agv_01",
        "map_file": MAP_FILE,
        "source_alignment": map_payload["source_alignment"],
        "recommended_case_roles": map_payload["recommended_case_roles"],
        "simulation_patch": {
            "engine": "discrete_event",
            "grid": map_payload["grid"],
            "agvs": map_payload["agvs"],
            "min_distance": map_payload["min_distance"],
        },
        "default_initial_state": {
            "position_x": 1,
            "position_y": 1,
            "heading": 0.0,
            "speed": 0.0,
        },
        "notes": map_payload["notes"],
    }


def write_artifacts(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    map_payload = build_map_payload()
    (base_dir / MAP_FILE).write_text(
        json.dumps(map_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (base_dir / CONFIG_FILE).write_text(
        json.dumps(build_shell_config(map_payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    write_artifacts(Path(__file__).resolve().parent)
    print(f"[OK] Wrote {MAP_FILE} and {CONFIG_FILE}")


if __name__ == "__main__":
    main()
