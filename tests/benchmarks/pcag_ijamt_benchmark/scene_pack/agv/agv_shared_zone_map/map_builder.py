"""
Build the canonical `agv_shared_zone_map` benchmark shell.

This script generates:

- `agv_shared_zone_map.json`
- `shell_config.json`

The output is aligned with the current discrete-event simulation backend used by
PCAG for AGV validation.
"""

from __future__ import annotations

import json
from pathlib import Path


SHELL_ID = "agv_shared_zone_map"
MAP_FILE = f"{SHELL_ID}.json"
CONFIG_FILE = "shell_config.json"


def build_map_payload() -> dict:
    return {
        "runtime_id": SHELL_ID,
        "runtime_type": "map_config",
        "asset_family": "agv",
        "asset_id": "agv_01",
        "grid": {
            "width": 12,
            "height": 10,
            "obstacles": [
                [0, 0], [0, 9], [11, 0], [11, 9],
                [4, 3], [4, 7], [8, 3], [8, 7],
            ],
            "intersections": [[6, 5], [6, 4], [6, 6], [5, 5], [7, 5]],
            "stations": {
                "west_entry": [2, 5],
                "shared_zone": [6, 5],
                "east_exit": [9, 5],
                "north_queue": [6, 8],
            },
            "zones": {
                "shared_intersection": [[5, 5], [6, 5], [7, 5], [6, 4], [6, 6]],
                "west_lane": [[2, 5], [3, 5], [4, 5], [5, 5]],
                "east_lane": [[7, 5], [8, 5], [9, 5]],
                "north_lane": [[6, 8], [6, 7], [6, 6]],
            },
        },
        "agvs": {
            "agv_01": {"position": [2, 5], "speed": 1.0},
            "agv_02": {"position": [10, 8], "speed": 1.0},
        },
        "min_distance": 1.0,
        "source_alignment": {
            "primary_motifs": ["shared_zone_entry", "intersection_conflict"],
            "upstream_sources": ["warehouse_world_curated"],
        },
        "recommended_case_roles": [
            "shared_zone_nominal",
            "shared_zone_clear_crossing",
            "shared_zone_conflict_unsafe",
            "shared_zone_fault_case",
        ],
        "notes": [
            "This shell models a safety-critical shared intersection with optional background traffic.",
            "It is intended for minimum-distance and occupancy-conflict benchmark cases.",
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
            "position_x": 2,
            "position_y": 5,
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
