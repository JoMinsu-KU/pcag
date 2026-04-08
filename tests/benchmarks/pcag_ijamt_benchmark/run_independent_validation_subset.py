from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.benchmarks.pcag_ijamt_benchmark.independent_validation_utils import (
    DATASET_PATH,
    INDEPENDENT_RESULTS_DIR,
    POLICY_PATH,
    build_validation_subset,
    load_dataset,
    load_policy,
    run_oracle_case,
    stratum_key,
    _robot_proxy,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _group_summary(results: list[dict[str, Any]], *, field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item[field]].append(item)
    rows: list[dict[str, Any]] = []
    for key in sorted(grouped.keys()):
        items = grouped[key]
        rows.append(
            {
                field: key,
                "total_cases": len(items),
                "matches": sum(1 for item in items if item["match"]),
                "mismatches": sum(1 for item in items if not item["match"]),
                "match_rate": round(sum(1 for item in items if item["match"]) / len(items), 4) if items else None,
            }
        )
    return rows


def _build_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Independent Validation Subset Report")
    lines.append("")
    lines.append(f"- Generated at: {payload['generated_at']}")
    lines.append(f"- Dataset: `{payload['dataset_path']}`")
    lines.append(f"- Policy: `{payload['policy_path']}`")
    lines.append(f"- Subset size: `{payload['summary']['total_cases']}`")
    lines.append(f"- Matches: `{payload['summary']['matches']}`")
    lines.append(f"- Mismatches: `{payload['summary']['mismatches']}`")
    lines.append(f"- Match rate: `{payload['summary']['match_rate']}`")
    lines.append("")
    lines.append("## Asset-wise Summary")
    lines.append("")
    lines.append("| Asset | Total | Matches | Mismatches | Match Rate |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in payload["asset_summary"]:
        lines.append(
            f"| {row['asset_id']} | {row['total_cases']} | {row['matches']} | {row['mismatches']} | {row['match_rate']:.4f} |"
        )
    lines.append("")
    lines.append("## Status-wise Summary")
    lines.append("")
    lines.append("| Expected Status | Total | Matches | Mismatches | Match Rate |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in payload["status_summary"]:
        lines.append(
            f"| {row['expected_status']} | {row['total_cases']} | {row['matches']} | {row['mismatches']} | {row['match_rate']:.4f} |"
        )
    lines.append("")
    lines.append("## Mismatches")
    lines.append("")
    mismatches = [item for item in payload["results"] if not item["match"]]
    if not mismatches:
        lines.append("- None")
    else:
        for item in mismatches:
            lines.append(
                f"- `{item['case_id']}` ({item['asset_id']}, expected `{item['expected_verdict']}`, observed `{item['oracle_verdict']}`)"
            )
    lines.append("")
    lines.append("## Selected Cases")
    lines.append("")
    lines.append("| Case ID | Asset | Expected Status | Stratum | Oracle Verdict | Match |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in payload["results"]:
        lines.append(
            f"| `{item['case_id']}` | {item['asset_id']} | {item['expected_status']} | `{item['stratum']}` | {item['oracle_verdict']} | {item['match']} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- The same simulation engines were invoked outside the Gateway/Safety-Cluster admission path as independent oracles.")
    lines.append("- No benchmark cases or expected labels were mutated during this validation run.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the independent validation subset outside the PCAG decision pipeline.")
    parser.add_argument("--dataset-path", type=Path, default=DATASET_PATH)
    parser.add_argument("--policy-path", type=Path, default=None)
    parser.add_argument("--per-asset-nominal", type=int, default=20)
    parser.add_argument("--per-asset-unsafe", type=int, default=20)
    parser.add_argument(
        "--asset-id",
        action="append",
        default=[],
        help="Restrict validation to one or more asset ids (repeatable).",
    )
    parser.add_argument(
        "--output-suffix",
        type=str,
        default="",
        help="Optional suffix used for report file names, e.g. robot/agv/process.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_dataset(args.dataset_path)
    policy = load_policy(args.policy_path) if args.policy_path else load_policy()
    subset = build_validation_subset(
        dataset,
        per_asset_nominal=args.per_asset_nominal,
        per_asset_unsafe=args.per_asset_unsafe,
    )
    if args.asset_id:
        allowed_assets = set(args.asset_id)
        subset = [case for case in subset if case["asset_id"] in allowed_assets]

    robot_cases = [case for case in subset if case["asset_id"] == "robot_arm_01"]
    robot_proxy = _robot_proxy() if robot_cases else None
    results: list[dict[str, Any]] = []
    output_suffix = f"_{args.output_suffix.strip()}" if args.output_suffix.strip() else ""
    INDEPENDENT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    progress_log = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_progress.log"
    partial_json = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_partial_latest.json"

    def write_partial() -> None:
        partial_payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dataset_path": str(args.dataset_path),
            "policy_path": str(args.policy_path or POLICY_PATH),
            "selection": {
                "per_asset_nominal": args.per_asset_nominal,
                "per_asset_unsafe": args.per_asset_unsafe,
                "asset_id": args.asset_id,
            },
            "progress": {
                "completed_cases": len(results),
                "remaining_cases": len(subset) - len(results),
            },
            "results": results,
        }
        _write_json(partial_json, partial_payload)

    progress_log.write_text("", encoding="utf-8")

    try:
        for case in subset:
            asset_policy = json.loads(json.dumps(policy["assets"][case["asset_id"]]))
            result = run_oracle_case(case, asset_policy=asset_policy, robot_proxy=robot_proxy)
            result["stratum"] = stratum_key(case)
            result["source_task_family"] = case.get("source_task_family")
            result["shell_role"] = case.get("shell_role")
            results.append(result)
            with progress_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {len(results)}/{len(subset)} | {case['case_id']} | {result['oracle_verdict']} | expected={case['expected_verdict']}\n"
                )
            write_partial()
            print(f"[ORACLE] {case['case_id']} -> {result['oracle_verdict']} (expected {case['expected_verdict']})")
    finally:
        if robot_proxy is not None:
            robot_proxy.shutdown()

    total_cases = len(results)
    matches = sum(1 for item in results if item["match"])
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_path": str(args.dataset_path),
        "policy_path": str(args.policy_path or POLICY_PATH),
        "selection": {
            "per_asset_nominal": args.per_asset_nominal,
            "per_asset_unsafe": args.per_asset_unsafe,
        },
        "summary": {
            "total_cases": total_cases,
            "matches": matches,
            "mismatches": total_cases - matches,
            "match_rate": round(matches / total_cases, 4) if total_cases else None,
        },
        "asset_summary": _group_summary(results, field="asset_id"),
        "status_summary": _group_summary(results, field="expected_status"),
        "results": results,
    }

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    latest_json = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_latest.json"
    archive_json = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_{timestamp}.json"
    latest_md = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_latest.md"
    manifest_json = INDEPENDENT_RESULTS_DIR / f"independent_validation_subset{output_suffix}_manifest_latest.json"

    _write_json(latest_json, payload)
    _write_json(archive_json, payload)
    _write_json(
        manifest_json,
        {
            "generated_at": payload["generated_at"],
            "total_cases": total_cases,
            "case_ids": [item["case_id"] for item in results],
        },
    )
    latest_md.write_text(_build_markdown(payload), encoding="utf-8")
    if partial_json.exists():
        partial_json.unlink()

    print(
        json.dumps(
            {
                "total_cases": total_cases,
                "matches": matches,
                "mismatches": total_cases - matches,
                "report_path": str(latest_json),
                "manifest_path": str(manifest_json),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
