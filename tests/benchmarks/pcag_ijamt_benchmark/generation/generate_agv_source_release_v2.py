from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from generate_agv_source_release_v1 import (
    BENCHMARK_ROOT,
    PROJECT_ROOT,
    SHELL_ROOT,
    _dump_json,
    _make_nominal_case,
    _make_unsafe_case,
    _validate_cases,
)


RELEASE_DIR = BENCHMARK_ROOT / "releases" / "agv_source_release_v2"
V1_ALL_CASES_PATH = BENCHMARK_ROOT / "releases" / "agv_source_release_v1" / "all_cases.json"


CONCURRENT_BASE_SPECS = [
    {
        "case_id": "agv_nominal_concurrent_shared_zone_staggered_crossing_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_nominal",
        "task_family": "shared_zone_entry",
        "source_unit": "shared_zone_entry::staggered_crossing_with_north_traffic",
        "station_id": "shared_zone",
        "mission_phase": "zone_crossing_concurrent",
        "load_id": "carrier_iota",
        "provenance_note": "Warehouse-world shared-zone motif lifted into a concurrent two-AGV staggered crossing command.",
        "semantic_role": "staggered crossing with dynamic north-lane traffic",
        "target": [9, 5],
        "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [6, 8],
                        "speed": 1.0,
                        "path": [[6, 8], [6, 8], [6, 8], [6, 7], [6, 6], [6, 5], [6, 4]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 6, "y": 8}},
        },
        "unsafe_variant": {
            "rule": "concurrent_same_cell_collision",
            "simulation_expectation": "same_cell_collision",
            "target": [9, 5],
            "path": [[3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [6, 8],
                            "speed": 1.0,
                            "path": [[6, 7], [6, 6], [6, 5], [6, 5]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 6, "y": 8}},
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_transfer_safe_following_001",
        "runtime_id": "agv_transfer_map",
        "shell_role": "transfer_with_path_variant",
        "task_family": "station_transfer",
        "source_unit": "station_transfer::safe_following_with_background_departure",
        "station_id": "transfer_mid",
        "mission_phase": "transfer_concurrent",
        "load_id": "carrier_kappa",
        "provenance_note": "Warehouse-world transfer motif lifted into a concurrent two-AGV corridor-following command.",
        "semantic_role": "safe following behind moving background traffic",
        "target": [6, 3],
        "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [4, 1],
                        "speed": 1.0,
                        "path": [[5, 1], [6, 1], [7, 1], [8, 1], [9, 1]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 4, "y": 1}},
        },
        "unsafe_variant": {
            "rule": "concurrent_head_on_collision",
            "simulation_expectation": "same_cell_collision",
            "target": [6, 3],
            "path": [[2, 1], [3, 1], [4, 1], [5, 1], [5, 2], [5, 3], [6, 3]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [5, 1],
                            "speed": 1.0,
                            "path": [[4, 1], [3, 1], [2, 1]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 5, "y": 1}},
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_shared_zone_priority_sequence_001",
        "runtime_id": "agv_shared_zone_map",
        "shell_role": "shared_zone_clear_crossing",
        "task_family": "intersection_conflict",
        "source_unit": "intersection_conflict::three_agv_priority_release",
        "station_id": "shared_zone",
        "mission_phase": "zone_priority_release",
        "load_id": "carrier_lambda",
        "initial_state_override": {"position_x": 5, "position_y": 5, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world shared intersection motif lifted into a three-AGV priority-release coordination command.",
        "semantic_role": "three-AGV coordinated release with explicit yielding",
        "target": [7, 5],
        "path": [[5, 5], [5, 5], [6, 5], [7, 5]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [6, 5],
                        "speed": 1.0,
                        "path": [[7, 5], [8, 5], [9, 5]],
                    },
                    "agv_03": {
                        "position": [7, 5],
                        "speed": 1.0,
                        "path": [[7, 4], [7, 3], [7, 2]],
                    },
                }
            },
            "sensor_state_overlay": {
                "agv_02": {"x": 6, "y": 5},
                "agv_03": {"x": 7, "y": 5},
            },
        },
        "unsafe_variant": {
            "rule": "deadlock_cycle",
            "simulation_expectation": "deadlock_cycle",
            "target": [6, 5],
            "path": [[6, 5]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [6, 5],
                            "speed": 1.0,
                            "path": [[7, 5]],
                        },
                        "agv_03": {
                            "position": [7, 5],
                            "speed": 1.0,
                            "path": [[5, 5]],
                        },
                    }
                },
                "sensor_state_overlay": {
                    "agv_02": {"x": 6, "y": 5},
                    "agv_03": {"x": 7, "y": 5},
                },
            },
        },
    },
    {
        "case_id": "agv_nominal_concurrent_docking_release_yield_001",
        "runtime_id": "agv_docking_map",
        "shell_role": "dock_alignment_variant",
        "task_family": "docking_approach",
        "source_unit": "docking_approach::docking_release_with_neighbor_departure",
        "station_id": "handoff_dock",
        "mission_phase": "dock_release_concurrent",
        "load_id": "carrier_mu",
        "initial_state_override": {"position_x": 8, "position_y": 2, "heading": 0.0, "speed": 0.0},
        "provenance_note": "Warehouse-world docking motif lifted into a concurrent dock-release command with a neighboring AGV departure.",
        "semantic_role": "dock release with explicit neighbor yield",
        "target": [9, 2],
        "path": [[8, 2], [8, 2], [9, 2]],
        "runtime_context_patch": {
            "simulation_override": {
                "agvs": {
                    "agv_02": {
                        "position": [9, 2],
                        "speed": 1.0,
                        "path": [[9, 3], [9, 4]],
                    }
                }
            },
            "sensor_state_overlay": {"agv_02": {"x": 9, "y": 2}},
        },
        "unsafe_variant": {
            "rule": "edge_swap_conflict",
            "simulation_expectation": "edge_swap_conflict",
            "target": [9, 2],
            "path": [[9, 2]],
            "runtime_context_patch": {
                "simulation_override": {
                    "agvs": {
                        "agv_02": {
                            "position": [9, 2],
                            "speed": 1.0,
                            "path": [[8, 2]],
                        }
                    }
                },
                "sensor_state_overlay": {"agv_02": {"x": 9, "y": 2}},
            },
        },
    },
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _upgrade_case(case: dict[str, Any]) -> dict[str, Any]:
    upgraded = deepcopy(case)
    upgraded["benchmark_release"] = "agv_source_release_v2"
    upgraded["benchmark_version"] = "v2.0"
    return upgraded


def _build_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "release_id": "agv_source_release_v2",
        "benchmark_scope": "agv_only",
        "benchmark_version": "v2.0",
        "release_date": str(date.today()),
        "generator_script": str(Path(__file__).relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "derived_from_release": "agv_source_release_v1",
        "case_counts": {
            "nominal": sum(1 for case in cases if case["case_group"] == "nominal"),
            "unsafe": sum(1 for case in cases if case["case_group"] == "unsafe"),
            "fault": sum(1 for case in cases if case["case_group"] == "fault"),
            "total": len(cases),
        },
        "case_counts_by_runtime": dict(Counter(case["runtime_context"]["runtime_id"] for case in cases)),
        "case_counts_by_task_family": dict(Counter(case["source_benchmark"]["task_family"] for case in cases)),
        "case_counts_by_expected_status": dict(Counter(case["label"]["expected_final_status"] for case in cases)),
        "case_counts_by_stop_stage": dict(Counter(case["label"]["expected_stop_stage"] for case in cases)),
        "release_artifacts": [
            "nominal_dataset.json",
            "unsafe_dataset.json",
            "fault_dataset.json",
            "all_cases.json",
            "dataset_manifest.json",
            "qc_report.md",
        ],
        "notes": [
            "AGV release v2 preserves the full v1 outcome-complete benchmark and adds concurrent-motion supplement cases.",
            "Concurrent supplement cases introduce dynamic background AGV paths, edge-swap conflicts, and deadlock-cycle counterfactuals.",
            "The public supervisory subset remains move_to and still avoids scenario-specific PCAG branching.",
        ],
    }


def _build_qc_report(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# AGV Source Release v2 QC Report",
        "",
        f"Release date: `{manifest['release_date']}`",
        "",
        "## Scope",
        "",
        "- Release type: `agv_only`",
        "- Base release: `agv_source_release_v1`",
        "- Added supplement: `concurrent multi-AGV motion, edge-swap conflict, deadlock-cycle risk`",
        "",
        "## Counts",
        "",
        f"- Nominal cases: `{manifest['case_counts']['nominal']}`",
        f"- Unsafe cases: `{manifest['case_counts']['unsafe']}`",
        f"- Fault cases: `{manifest['case_counts']['fault']}`",
        f"- Total cases: `{manifest['case_counts']['total']}`",
        f"- Final-status coverage: `{', '.join(f'{key}={value}' for key, value in manifest['case_counts_by_expected_status'].items())}`",
        "",
        "## Concurrency supplement",
        "",
        "- `agv_nominal_concurrent_shared_zone_staggered_crossing_001`: two AGVs move concurrently with time separation.",
        "- `agv_nominal_concurrent_transfer_safe_following_001`: background AGV moves ahead in the same corridor while the primary AGV follows safely.",
        "- `agv_nominal_concurrent_shared_zone_priority_sequence_001`: three AGVs coordinate priority release through the shared zone.",
        "- `agv_nominal_concurrent_docking_release_yield_001`: docking release waits for a neighboring AGV to clear.",
        "",
        "## Unsafe concurrency mutations",
        "",
        "- `concurrent_same_cell_collision` introduces dynamic center-cell occupancy collision.",
        "- `concurrent_head_on_collision` introduces head-on same-cell collision in the transfer corridor.",
        "- `deadlock_cycle` introduces a three-AGV wait-for cycle.",
        "- `edge_swap_conflict` introduces simultaneous cell-swap conflict at the docking release point.",
        "",
        "## Notes",
        "",
        "- v2 keeps the v1 fault families intact so full PCAG outcome coverage remains available.",
        "- The new concurrency cases are intended to align the benchmark more closely with the original multi-AGV planning scenario in the project document.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    v1_cases = [_upgrade_case(case) for case in _load_json(V1_ALL_CASES_PATH)]
    supplement_nominal = [_upgrade_case(_make_nominal_case(spec)) for spec in CONCURRENT_BASE_SPECS]
    supplement_unsafe = [
        _upgrade_case(_make_unsafe_case(case, spec))
        for case, spec in zip(supplement_nominal, CONCURRENT_BASE_SPECS, strict=True)
    ]

    all_cases = v1_cases + supplement_nominal + supplement_unsafe
    _validate_cases(all_cases)

    nominal_cases = [case for case in all_cases if case["case_group"] == "nominal"]
    unsafe_cases = [case for case in all_cases if case["case_group"] == "unsafe"]
    fault_cases = [case for case in all_cases if case["case_group"] == "fault"]

    manifest = _build_manifest(all_cases)
    qc_report = _build_qc_report(all_cases, manifest)

    _dump_json(RELEASE_DIR / "nominal_dataset.json", nominal_cases)
    _dump_json(RELEASE_DIR / "unsafe_dataset.json", unsafe_cases)
    _dump_json(RELEASE_DIR / "fault_dataset.json", fault_cases)
    _dump_json(RELEASE_DIR / "all_cases.json", all_cases)
    _dump_json(RELEASE_DIR / "dataset_manifest.json", manifest)
    (RELEASE_DIR / "qc_report.md").write_text(qc_report, encoding="utf-8")

    print(f"Wrote AGV benchmark release to: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
