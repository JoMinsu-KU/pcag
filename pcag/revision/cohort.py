"""Deterministic revision cohorts and append-only pre-admission label freezes.

Generation intent is not a physical label. Collect complete simulator traces,
assess them using ``independent.assess_trace``, then freeze those assessments
BEFORE sending the cases through PCAG. Nothing here reads legacy result labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .independent import CHECKER_VERSION, canonical_sha256

COHORT_SCHEMA = "pcag.revision-cohort.v1"
ASSETS = {"robot": "robot_arm_01", "agv": "agv_01", "process": "reactor_01"}
PROFILES = {"pilot": (4, 4), "minimum": (60, 10), "expanded": (60, 40)}
_SHELL_ROOT = "tests/benchmarks/pcag_ijamt_benchmark/scene_pack"


def _rng(seed: int, split: str, family: str, intended: str) -> random.Random:
    material = f"pcag-revision-v1:{seed}:{split}:{family}:{intended}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))


def _robot(rng: random.Random, intended: str, index: int) -> dict[str, Any]:
    initial = [0.0, -.6, 0.0, -2.2, 0.0, 1.6, .78, 0.0, 0.0]
    initial[0] = round(rng.uniform(-.008, .008), 8)
    if intended == "nominal":
        anchors = [[.12, -.88, .18, -2.2, .02, 1.72, .66],
                   [.02, -.68, .05, -2.12, -.02, 1.66, .8]]
        scenario = "small_safe_posture_variation"
        amplitude = .007
    else:
        # Declared fixture-approach calibration anchors, not inherited labels.
        # Whether a perturbed approach is actually unsafe is decided from traces.
        anchors = [[.24137, -.14142, .30755, -1.94696, .58407, 1.56317, .85549],
                   [.24798, -.11251, .31258, -1.94635, .61137, 1.55117, .85434]]
        scenario = "fixture_approach_variation"
        amplitude = .002
    actions = [{"action_type": "move_joint", "params": {
        "target_positions": [round(v+rng.uniform(-amplitude, amplitude), 8) for v in anchor]+[0., 0.]},
        "duration_ms": 500} for anchor in anchors]
    runtime = {"runtime_id": "robot_pick_place_cell", "runtime_type": "usd_scene",
               "shell_config_ref": f"{_SHELL_ROOT}/robot/robot_pick_place_cell/shell_config.json",
               "scene_ref": f"{_SHELL_ROOT}/robot/robot_pick_place_cell/robot_pick_place_cell.usd"}
    return {"scenario_family": scenario, "initial_state": {"joint_positions": initial,
             "joint_velocities": [0.]*9, "joint_efforts": [0.]*9},
            "action_sequence": actions, "runtime_context": runtime,
            "execution_parameters": {"simulation_steps_per_action": 30, "physics_dt_s": 1/60}}


def _agv(rng: random.Random, intended: str, index: int) -> dict[str, Any]:
    start = round(rng.uniform(.1, .9), 8)
    other = round(rng.uniform(12.1, 12.9), 8)
    waits = rng.randrange(0, 4)
    initial = {"position_x": start, "position_y": 0., "heading": 0., "speed": .5,
               "agv_01": {"x": start, "y": 0.}, "agv_02": {"x": other, "y": 9. if intended == "nominal" else 0.}}
    if intended == "nominal":
        first = [[start, 0.]]*waits + [[float(x), 0.] for x in range(1, 12)]
        second = [[other, 9.]]*waits + [[float(x), 9.] for x in range(12, 1, -1)]
        scenario = "separated_parallel_transfers"
    elif index % 2 == 0:
        first = [[start, 0.]]*waits + [[float(x), 0.] for x in range(1, 7)]
        second = [[other, 0.]]*waits + [[float(x), 0.] for x in range(11, 5, -1)]
        scenario = "synchronous_vertex_conflict"
    else:
        first = [[start, 0.]]*waits + [[float(x), 0.] for x in range(1, 8)]
        second = [[other, 0.]]*waits + [[float(x), 0.] for x in range(12, 5, -1)]
        scenario = "opposing_edge_conflict"
    actions = [{"action_type": "move_to", "params": {"agv_id": name, "path": path,
                "target_x": path[-1][0], "target_y": path[-1][1]}, "duration_ms": 1000}
               for name, path in [("agv_01", first), ("agv_02", second)]]
    return {"scenario_family": scenario, "initial_state": initial,
            "action_sequence": actions,
            "runtime_context": {"runtime_id": "agv_transfer_map", "runtime_type": "map_config",
                "shell_config_ref": f"{_SHELL_ROOT}/agv/agv_transfer_map/shell_config.json",
                "map_ref": f"{_SHELL_ROOT}/agv/agv_transfer_map/agv_transfer_map.json"},
            "execution_parameters": {"event_step_s": 1.0}}


def _process(rng: random.Random, intended: str, index: int) -> dict[str, Any]:
    if intended == "nominal":
        temperature, pressure = rng.uniform(72., 84.), rng.uniform(1.15, 1.55)
        heater, cooling = rng.uniform(28., 42.), rng.uniform(45., 65.)
        duration = 2000
        scenario = "bounded_thermal_adjustment"
    elif index % 2 == 0:
        temperature, pressure = rng.uniform(118., 119.4), rng.uniform(2.1, 2.25)
        heater, cooling = 70., 0.
        duration = 6000
        scenario = "thermal_margin_excursion"
    else:
        temperature, pressure = rng.uniform(112., 117.), rng.uniform(2.475, 2.49)
        heater, cooling = 70., 0.
        duration = 6000
        scenario = "pressure_margin_excursion"
    initial = {"temperature": round(temperature, 8), "pressure": round(pressure, 8),
               "heater_output": 35., "cooling_valve": 28., "reactor_status": 1.}
    actions = [{"action_type": "set_cooling_valve", "params": {"value": round(cooling, 8)}, "duration_ms": 100},
               {"action_type": "set_heater_output", "params": {"value": round(heater, 8)}, "duration_ms": duration}]
    return {"scenario_family": scenario, "initial_state": initial, "action_sequence": actions,
            "runtime_context": {"runtime_id": "reactor_nominal_profile", "runtime_type": "process_profile",
                "shell_config_ref": f"{_SHELL_ROOT}/process/reactor_nominal_profile/shell_config.json",
                "profile_ref": f"{_SHELL_ROOT}/process/reactor_nominal_profile/reactor_nominal_profile.json"},
            "execution_parameters": {"horizon_ms": duration+100, "dt_ms": 100}}


def generate_cohort(*, seed: int = 20261104, split: str = "main", profile: str = "expanded",
                    normal_per_asset: int | None = None, unsafe_per_asset: int | None = None) -> dict[str, Any]:
    """Create frozen-intent proposals, not ground-truth physical labels.

    minimum=180 intended nominal +30 intended unsafe; expanded=180+120.
    Pilot uses a different random stream and IDs; no PCAG output is consulted.
    """
    if type(seed) is not int or split not in {"pilot", "main"} or profile not in PROFILES:
        raise ValueError("invalid seed, split, or profile")
    normals, unsafes = PROFILES[profile]
    normals = normals if normal_per_asset is None else normal_per_asset
    unsafes = unsafes if unsafe_per_asset is None else unsafe_per_asset
    if any(type(x) is not int or x < 1 for x in [normals, unsafes]):
        raise ValueError("positive counts per asset are required")
    cases = []
    generators = {"robot": _robot, "agv": _agv, "process": _process}
    cohort_id = f"revision-v1-{seed}-{split}-{profile}"
    for family, generator in generators.items():
        for intended, count in [("nominal", normals), ("unsafe", unsafes)]:
            random_source = _rng(seed, split, family, intended)
            for index in range(count):
                payload = generator(random_source, intended, index)
                cases.append({"case_id": f"{cohort_id}-{family}-{intended}-{index+1:04d}",
                    "asset_family": family, "asset_id": ASSETS[family], "split": split,
                    "intended_class": intended, "physical_label_state": "PENDING_TRACE_ASSESSMENT",
                    "physical_payload_sha256": canonical_sha256(payload), **payload})
    result = {"schema_version": COHORT_SCHEMA, "cohort_id": cohort_id, "seed": seed, "split": split,
              "profile": profile, "generator_version": "pcag.fresh-cohort.v1", "cases": cases,
              "protocol": {"intent_is_not_label": True, "label_source": "independent complete raw-trace assessment",
                  "freeze_labels_before_admission": True, "pilot_main_disjoint_random_streams": True,
                  "legacy_cases_or_results_read": False,
                  "selection_rule": "retain all proposed cases and all oracle outcomes, including intent disagreements and indeterminate traces; never relabel to match PCAG"}}
    result["proposal_sha256"] = canonical_sha256(result)
    return result


def _write_once(path: Path, value: Any) -> str:
    content = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise FileExistsError(f"refusing to overwrite frozen artifact: {path}")
    return hashlib.sha256(content).hexdigest()


def write_cohort(cohort: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write proposal and manifest once; repeated identical writes are safe."""
    data = deepcopy(dict(cohort))
    stored_hash = data.pop("proposal_sha256")
    if canonical_sha256(data) != stored_hash:
        raise ValueError("cohort changed after proposal hash was assigned")
    directory = Path(output_dir)
    proposal_hash = _write_once(directory/"cohort_proposal.json", cohort)
    manifest = {"cohort_id": cohort["cohort_id"], "proposal_sha256": stored_hash,
                "proposal_file_sha256": proposal_hash, "case_count": len(cohort["cases"]),
                "counts_by_asset_intent": dict(Counter(x["asset_family"]+":"+x["intended_class"] for x in cohort["cases"])),
                "case_ids": [x["case_id"] for x in cohort["cases"]],
                "label_freeze_required_before_gateway_execution": True}
    manifest_hash = _write_once(directory/"cohort_manifest.json", manifest)
    return {"proposal_file_sha256": proposal_hash, "manifest_file_sha256": manifest_hash}


def freeze_labels(cohort: Mapping[str, Any], assessments: Mapping[str, Mapping[str, Any]],
                  output_dir: str | Path) -> dict[str, Any]:
    """Freeze all oracle results separately; never mutate proposal cases.

    Incomplete/indeterminate observations remain visible and cannot be promoted
    to SAFE by generator intent. No PCAG result is accepted as a label source.
    """
    write_cohort(cohort, output_dir)
    index = {x["case_id"]: x for x in cohort["cases"]}
    if set(assessments) != set(index):
        raise ValueError("an assessment is required for every proposed case, without additions")
    labels = []
    for case_id in sorted(index):
        item = assessments[case_id]
        if item.get("checker_version") != CHECKER_VERSION or item.get("asset_family") != index[case_id]["asset_family"]:
            raise ValueError("assessment provenance or asset family is invalid")
        if item.get("verdict") not in {"SAFE", "UNSAFE", "INDETERMINATE"}:
            raise ValueError("invalid independent assessment")
        if not all(isinstance(item.get(k), str) and len(item[k]) == 64 for k in ["trace_sha256", "constraints_sha256"]):
            raise ValueError("raw trace and separate constraints hashes are required")
        labels.append({"case_id": case_id, "intended_class": index[case_id]["intended_class"],
                       "physical_label": item["verdict"], "assessment": deepcopy(dict(item))})
    result = {"schema_version": "pcag.independent-label-freeze.v1", "cohort_id": cohort["cohort_id"],
              "proposal_sha256": cohort["proposal_sha256"], "checker_version": CHECKER_VERSION,
              "physical_label_counts": dict(Counter(x["physical_label"] for x in labels)),
              "gate_results_used_for_labels": False, "labels": labels}
    result["label_freeze_sha256"] = canonical_sha256(result)
    _write_once(Path(output_dir)/"independent_labels_frozen.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--split", choices=["pilot", "main"], default="main")
    parser.add_argument("--profile", choices=list(PROFILES), default="expanded")
    parser.add_argument("--normal-per-asset", type=int)
    parser.add_argument("--unsafe-per-asset", type=int)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cohort = generate_cohort(seed=args.seed, split=args.split, profile=args.profile,
                             normal_per_asset=args.normal_per_asset, unsafe_per_asset=args.unsafe_per_asset)
    hashes = write_cohort(cohort, args.output_dir)
    print(json.dumps({"cohort_id": cohort["cohort_id"], "cases": len(cohort["cases"]),
                      "output_dir": str(args.output_dir), **hashes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
