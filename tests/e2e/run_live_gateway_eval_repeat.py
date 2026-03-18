"""
Repeat runner for the live Gateway E2E dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.e2e.live_gateway_eval_support import DATASET_PATH, RESULTS_DIR, load_dataset, run_all_cases


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return round(math.sqrt(variance), 4)


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 4)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _snapshot_path(prefix: str, run_index: int) -> Path:
    return RESULTS_DIR / f"{prefix}_run{run_index:02d}.json"


def _expected_status_map(dataset: dict[str, Any]) -> dict[str, str | None]:
    return {
        case["case_id"]: case.get("expected", {}).get("status")
        for case in dataset.get("cases", [])
    }


def _summarize_runs(
    dataset: dict[str, Any],
    run_reports: list[dict[str, Any]],
    *,
    requested_runs: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    case_count = len(dataset.get("cases", []))
    total_case_executions = len(run_reports) * case_count
    passed_case_executions = sum(report["passed"] for report in run_reports)
    failed_case_executions = total_case_executions - passed_case_executions
    expected_status_by_case = _expected_status_map(dataset)

    run_accuracies: list[float] = []
    failed_runs: list[int] = []
    per_run: list[dict[str, Any]] = []
    case_stats: dict[str, dict[str, Any]] = {}
    status_groups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})

    for run_index, report in enumerate(run_reports, start=1):
        run_accuracy_pct = _percent(report["passed"], report["total"])
        run_accuracies.append(run_accuracy_pct)
        failed_case_ids = [result["case_id"] for result in report["results"] if not result["passed"]]
        if failed_case_ids:
            failed_runs.append(run_index)

        per_run.append(
            {
                "run_index": run_index,
                "generated_at_ms": report["generated_at_ms"],
                "passed": report["passed"],
                "failed": report["failed"],
                "total": report["total"],
                "accuracy_pct": run_accuracy_pct,
                "failed_case_ids": failed_case_ids,
                "snapshot_path": str(_snapshot_path("live_gateway_eval_repeat", run_index)),
            }
        )

        for result in report["results"]:
            case_id = result["case_id"]
            expected_status = expected_status_by_case.get(case_id)
            if case_id not in case_stats:
                case_stats[case_id] = {
                    "case_id": case_id,
                    "asset_id": result.get("asset_id"),
                    "expected_status": expected_status,
                    "total_runs": 0,
                    "passed_runs": 0,
                    "failed_runs": 0,
                    "durations_ms": [],
                    "actual_status_counts": defaultdict(int),
                    "failure_examples": [],
                }

            stats = case_stats[case_id]
            stats["total_runs"] += 1
            stats["durations_ms"].append(float(result.get("duration_ms", 0.0)))

            response_json = result.get("response_json") or {}
            actual_status = response_json.get("status") if isinstance(response_json, dict) else None
            if actual_status is None:
                actual_status = f"HTTP_{result.get('response_status_code')}"
            stats["actual_status_counts"][str(actual_status)] += 1

            group_key = expected_status or "HTTP_ONLY"
            status_groups[group_key]["total"] += 1
            if result["passed"]:
                stats["passed_runs"] += 1
                status_groups[group_key]["passed"] += 1
            else:
                stats["failed_runs"] += 1
                status_groups[group_key]["failed"] += 1
                if len(stats["failure_examples"]) < 3:
                    stats["failure_examples"].append(
                        {
                            "run_index": run_index,
                            "response_status_code": result.get("response_status_code"),
                            "response_json": result.get("response_json"),
                            "errors": result.get("errors", []),
                        }
                    )

    per_case: list[dict[str, Any]] = []
    flaky_cases: list[dict[str, Any]] = []
    for case_id, stats in case_stats.items():
        pass_rate_pct = _percent(stats["passed_runs"], stats["total_runs"])
        case_summary = {
            "case_id": case_id,
            "asset_id": stats["asset_id"],
            "expected_status": stats["expected_status"],
            "total_runs": stats["total_runs"],
            "passed_runs": stats["passed_runs"],
            "failed_runs": stats["failed_runs"],
            "pass_rate_pct": pass_rate_pct,
            "loss_rate_pct": round(100.0 - pass_rate_pct, 4),
            "mean_duration_ms": round(sum(stats["durations_ms"]) / len(stats["durations_ms"]), 2),
            "min_duration_ms": round(min(stats["durations_ms"]), 2),
            "max_duration_ms": round(max(stats["durations_ms"]), 2),
            "actual_status_counts": dict(stats["actual_status_counts"]),
            "failure_examples": stats["failure_examples"],
        }
        per_case.append(case_summary)
        if 0 < stats["passed_runs"] < stats["total_runs"]:
            flaky_cases.append(case_summary)

    per_case.sort(key=lambda item: (item["pass_rate_pct"], item["case_id"]))
    flaky_cases.sort(key=lambda item: (item["pass_rate_pct"], item["case_id"]))

    status_group_rows = []
    for group_name, stats in sorted(status_groups.items()):
        accuracy_pct = _percent(stats["passed"], stats["total"])
        status_group_rows.append(
            {
                "expected_status": group_name,
                "total_case_executions": stats["total"],
                "passed_case_executions": stats["passed"],
                "failed_case_executions": stats["failed"],
                "accuracy_pct": accuracy_pct,
                "loss_rate_pct": round(100.0 - accuracy_pct, 4),
            }
        )

    overall_accuracy_pct = _percent(passed_case_executions, total_case_executions)
    successful_runs = sum(1 for report in run_reports if report["failed"] == 0)

    return {
        "generated_at_ms": int(time.time() * 1000),
        "dataset_name": dataset.get("meta", {}).get("name", DATASET_PATH.name),
        "dataset_path": str(DATASET_PATH),
        "requested_runs": requested_runs,
        "runs": len(run_reports),
        "sleep_seconds_between_runs": sleep_seconds,
        "case_count_per_run": case_count,
        "total_case_executions": total_case_executions,
        "passed_case_executions": passed_case_executions,
        "failed_case_executions": failed_case_executions,
        "overall_accuracy_pct": overall_accuracy_pct,
        "loss_rate_pct": round(100.0 - overall_accuracy_pct, 4),
        "run_success_rate_pct": _percent(successful_runs, len(run_reports)),
        "metrics": {
            "mean_run_accuracy_pct": _mean(run_accuracies),
            "min_run_accuracy_pct": round(min(run_accuracies), 4) if run_accuracies else 0.0,
            "max_run_accuracy_pct": round(max(run_accuracies), 4) if run_accuracies else 0.0,
            "stddev_run_accuracy_pct": _stddev(run_accuracies),
        },
        "per_run": per_run,
        "per_case": per_case,
        "status_groups": status_group_rows,
        "failed_runs": failed_runs,
        "flaky_cases": flaky_cases,
        "run_reports": [
            {
                "run_index": index,
                "generated_at_ms": report["generated_at_ms"],
                "snapshot_path": str(_snapshot_path("live_gateway_eval_repeat", index)),
            }
            for index, report in enumerate(run_reports, start=1)
        ],
    }


def run_repeated_live_eval(runs: int = 10, sleep_seconds: float = 0.0) -> dict[str, Any]:
    dataset = load_dataset()
    run_reports: list[dict[str, Any]] = []

    for run_index in range(1, runs + 1):
        report = run_all_cases(dataset=dataset)
        run_reports.append(report)
        _write_json(_snapshot_path("live_gateway_eval_repeat", run_index), report)
        if run_index < runs and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return _summarize_runs(dataset, run_reports, requested_runs=runs, sleep_seconds=sleep_seconds)


def write_repeat_report(summary: dict[str, Any]) -> Path:
    return _write_json(RESULTS_DIR / "live_gateway_eval_repeat_latest.json", summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repeat the live Gateway E2E dataset and aggregate stability metrics.")
    parser.add_argument("--runs", type=int, default=10, help="Number of repeated live runs. Default: 10")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between runs. Default: 0.0")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    summary = run_repeated_live_eval(runs=args.runs, sleep_seconds=args.sleep_seconds)
    output_path = write_repeat_report(summary)

    print(f"Dataset: {summary['dataset_name']}")
    print(f"Runs: {summary['runs']}")
    print(f"Case executions: {summary['passed_case_executions']}/{summary['total_case_executions']}")
    print(f"Overall accuracy: {summary['overall_accuracy_pct']}%")
    print(f"Loss rate: {summary['loss_rate_pct']}%")
    print(f"Run success rate: {summary['run_success_rate_pct']}%")
    print(f"Results: {output_path}")

    if summary["failed_case_executions"]:
        print("Cases with failures:")
        for case in summary["per_case"]:
            if case["failed_runs"]:
                print(
                    f"- {case['case_id']}: pass_rate={case['pass_rate_pct']}% "
                    f"({case['passed_runs']}/{case['total_runs']})"
                )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
