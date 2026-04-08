from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.benchmarks.pcag_ijamt_benchmark.generation import (  # noqa: E402
    generate_robot_pcag_execution_dataset_v1 as base_generator,
)


def main() -> None:
    base_generator.SOURCE_RELEASE_ID = "robot_source_release_v3"
    base_generator.EXECUTION_RELEASE_ID = "robot_pcag_execution_release_v3"
    base_generator.EXECUTION_DATASET_NAME = "robot-pcag-execution-dataset-v3"
    base_generator.EXECUTION_VERSION = "3.0"
    base_generator.EXECUTION_DESCRIPTION = (
        "Gateway-facing robot execution dataset derived from the validated robot "
        "release v2 cases plus the initial fixture-insertion supplement in "
        "robot_source_release_v3."
    )
    base_generator.PROOF_ORIGIN = base_generator.EXECUTION_RELEASE_ID
    base_generator.GENERATOR_SCRIPT = str(Path(__file__).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    base_generator.SOURCE_RELEASE_DIR = base_generator.BENCHMARK_ROOT / "releases" / base_generator.SOURCE_RELEASE_ID
    base_generator.SOURCE_ALL_CASES_PATH = base_generator.SOURCE_RELEASE_DIR / "all_cases.json"
    base_generator.OUTPUT_DATASET_PATH = base_generator.SOURCE_RELEASE_DIR / "pcag_execution_dataset.json"
    base_generator.OUTPUT_MANIFEST_PATH = base_generator.SOURCE_RELEASE_DIR / "pcag_execution_manifest.json"
    base_generator.OUTPUT_QC_PATH = base_generator.SOURCE_RELEASE_DIR / "pcag_execution_qc.md"
    base_generator.main()

    source_cases = json.loads(base_generator.SOURCE_ALL_CASES_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(base_generator.OUTPUT_DATASET_PATH.read_text(encoding="utf-8"))
    source_index = {case["case_id"]: case for case in source_cases}

    dataset["libraries"]["action_sequences"] = {
        case_id: source_index[case_id]["action_sequence"] for case_id in source_index
    }
    rebuilt_initial_states: dict[str, object] = {}
    for case in dataset["cases"]:
        case_id = case["case_id"]
        initial_state_ref = f"{case_id}__initial_state"
        case["runtime"]["initial_state_ref"] = initial_state_ref
        rebuilt_initial_states[initial_state_ref] = source_index[case_id]["initial_state"]
    dataset["libraries"]["initial_states"] = rebuilt_initial_states

    manifest = base_generator._manifest(dataset)
    qc_report = base_generator._qc_report(dataset, manifest)

    base_generator._dump_json(base_generator.OUTPUT_DATASET_PATH, dataset)
    base_generator._dump_json(base_generator.OUTPUT_MANIFEST_PATH, manifest)
    base_generator.OUTPUT_QC_PATH.write_text(qc_report, encoding="utf-8")


if __name__ == "__main__":
    main()
