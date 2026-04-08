from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.benchmarks.pcag_ijamt_benchmark.independent_validation_utils import (
    DATASET_PATH,
    INDEPENDENT_RESULTS_DIR,
    POLICY_PATH,
    load_dataset,
    load_policy,
    materialize_case,
    run_oracle_case,
    select_stratified_cases,
    stratum_key,
    _robot_proxy,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Robot Isaac Execution Evidence")
    lines.append("")
    lines.append(f"- Generated at: {payload['generated_at']}")
    lines.append(f"- Dataset: `{payload['dataset_path']}`")
    lines.append(f"- Policy: `{payload['policy_path']}`")
    lines.append(f"- Total executed cases: `{payload['summary']['total_cases']}`")
    lines.append(f"- SAFE verdicts: `{payload['summary']['safe_cases']}`")
    lines.append(f"- Non-SAFE verdicts: `{payload['summary']['non_safe_cases']}`")
    lines.append("")
    lines.append("## Case Results")
    lines.append("")
    lines.append("| Case ID | Task Family | Shell Role | Oracle Verdict | Latency (ms) |")
    lines.append("| --- | --- | --- | --- | ---: |")
    for item in payload["results"]:
        lines.append(
            f"| `{item['case_id']}` | {item['source_task_family']} | {item['shell_role']} | {item['oracle_verdict']} | {item.get('latency_ms')} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- These runs use the Isaac worker/proxy path directly, outside the Gateway commit acknowledgement path.")
    lines.append("- The purpose is to show that a representative COMMITTED subset executes through the actual Isaac simulation path without safety violations.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a robot execution-evidence subset through the direct Isaac path.")
    parser.add_argument("--dataset-path", type=Path, default=DATASET_PATH)
    parser.add_argument("--policy-path", type=Path, default=POLICY_PATH)
    parser.add_argument("--count", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_dataset(args.dataset_path)
    policy = load_policy(args.policy_path)
    materialized = [materialize_case(case, dataset) for case in dataset.get("cases", [])]
    candidates = [
        case for case in materialized
        if case["asset_id"] == "robot_arm_01" and case["expected_status"] == "COMMITTED"
    ]
    selected = select_stratified_cases(candidates, target_count=args.count)
    robot_policy = json.loads(json.dumps(policy["assets"]["robot_arm_01"]))

    proxy = _robot_proxy()
    results: list[dict[str, Any]] = []
    try:
        for case in selected:
            result = run_oracle_case(case, asset_policy=robot_policy, robot_proxy=proxy)
            result["source_task_family"] = case.get("source_task_family")
            result["shell_role"] = case.get("shell_role")
            result["stratum"] = stratum_key(case)
            results.append(result)
            print(f"[ROBOT-EVIDENCE] {case['case_id']} -> {result['oracle_verdict']}")
    finally:
        proxy.shutdown()

    safe_cases = sum(1 for item in results if item["oracle_verdict"] == "SAFE")
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_path": str(args.dataset_path),
        "policy_path": str(args.policy_path),
        "summary": {
            "total_cases": len(results),
            "safe_cases": safe_cases,
            "non_safe_cases": len(results) - safe_cases,
        },
        "results": results,
    }

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    latest_json = INDEPENDENT_RESULTS_DIR / "robot_execution_evidence_latest.json"
    archive_json = INDEPENDENT_RESULTS_DIR / f"robot_execution_evidence_{timestamp}.json"
    latest_md = INDEPENDENT_RESULTS_DIR / "robot_execution_evidence_latest.md"
    _write_json(latest_json, payload)
    _write_json(archive_json, payload)
    latest_md.write_text(_build_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "total_cases": len(results),
                "safe_cases": safe_cases,
                "non_safe_cases": len(results) - safe_cases,
                "report_path": str(latest_json),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
