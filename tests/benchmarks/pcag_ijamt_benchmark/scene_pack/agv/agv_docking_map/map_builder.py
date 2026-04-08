"""
Build the canonical `agv_docking_map` benchmark shell.

This script generates:

- `agv_docking_map.json`
- `shell_config.json`

The output is aligned with the current discrete-event simulation backend used by
PCAG for AGV validation.
"""

from __future__ import annotations

import json
from pathlib import Path


SHELL_ID = "agv_docking_map"
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
            "height": 8,
            "obstacles": [
                [7, 1], [7, 3],
                [10, 1], [10, 3],
                [11, 1], [11, 2], [11, 3],
                [5, 6], [6, 6], [7, 6],
            ],
            "intersections": [[8, 4], [9, 2]],
            "stations": {
                "approach_queue": [1, 5],
                "alignment_gate": [8, 4],
                "handoff_dock": [9, 2],
            },
            "zones": {
                "final_approach_corridor": [[6, 5], [7, 5], [8, 5], [8, 4], [8, 3], [8, 2], [9, 2]],
                "dock_clearance": [[9, 2], [9, 3], [10, 2]],
            },
        },
        "agvs": {
            "agv_01": {"position": [1, 5], "speed": 0.8},
            "agv_02": {"position": [0, 0], "speed": 0.8},
        },
        "min_distance": 1.0,
        "source_alignment": {
            "primary_motifs": ["docking_approach", "handoff_alignment"],
            "upstream_sources": ["warehouse_world_curated"],
        },
        "recommended_case_roles": [
            "dock_nominal",
            "dock_alignment_variant",
            "dock_overshoot_unsafe",
            "dock_fault_case",
        ],
        "notes": [
            "This shell models a narrow final-approach and docking corridor.",
            "It is intended for docking-safe versus overshoot-style AGV cases.",
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
