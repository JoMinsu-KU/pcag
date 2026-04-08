from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[4]
BASELINE_RESULTS_DIR = (
    ROOT_DIR / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results" / "baselines"
)
DATASET_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "releases"
    / "integrated_benchmark_release_v2"
    / "pcag_execution_dataset.json"
)
PROFILES_PATH = (
    ROOT_DIR
    / "tests"
    / "benchmarks"
    / "pcag_ijamt_benchmark"
    / "baselines"
    / "baseline_profiles.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_profiles() -> list[dict[str, Any]]:
    payload = _load_json(PROFILES_PATH)
    return list(payload.get("profiles", []))


def _load_expected_distribution() -> dict[str, Any]:
    dataset = _load_json(DATASET_PATH)
    cases = dataset.get("cases", [])
    semantic_counts: dict[str, int] = {}
    asset_counts: dict[str, int] = {}
    expected_status_counts: dict[str, int] = {}
    for case in cases:
        expected = case.get("expected", {})
        status = expected.get("status")
        semantic_group = case.get("case_group")
        asset_id = case.get("asset_id")
        if status:
            expected_status_counts[status] = expected_status_counts.get(status, 0) + 1
        if semantic_group:
            semantic_counts[semantic_group] = semantic_counts.get(semantic_group, 0) + 1
        if asset_id:
            asset_counts[asset_id] = asset_counts.get(asset_id, 0) + 1
    return {
        "total_cases": len(cases),
        "expected_status_counts": expected_status_counts,
        "semantic_group_counts": semantic_counts,
        "asset_counts": asset_counts,
    }


def _safe_rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 4)


def _asset_breakdown(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["asset_id"], []).append(result)
    rows: list[dict[str, Any]] = []
    for asset_id, items in sorted(grouped.items()):
        nominal = [item for item in items if item.get("semantic_group") == "nominal"]
        unsafe = [item for item in items if item.get("semantic_group") == "unsafe"]
        rows.append(
            {
                "asset_id": asset_id,
                "total_cases": len(items),
                "exact_match_rate": _safe_rate(
                    sum(1 for item in items if item["normalized_final_status"] == item["expected_status"]),
                    len(items),
                ),
                "safe_pass_rate": _safe_rate(
                    sum(1 for item in nominal if item["normalized_final_status"] == "COMMITTED"),
                    len(nominal),
                ),
                "unsafe_interception_rate": _safe_rate(
                    sum(1 for item in unsafe if item["normalized_final_status"] != "COMMITTED"),
                    len(unsafe),
                ),
                "unsafe_commit_count": sum(
                    1
                    for item in items
                    if item.get("semantic_group") in {"unsafe", "integrity_fault", "transaction_fault", "execution_fault"}
                    and item["normalized_final_status"] == "COMMITTED"
                ),
            }
        )
    return rows


def _semantic_breakdown(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["semantic_group"], []).append(result)
    rows: list[dict[str, Any]] = []
    for semantic_group, items in sorted(grouped.items()):
        status_counts: dict[str, int] = {}
        for item in items:
            status = item["normalized_final_status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        rows.append(
            {
                "semantic_group": semantic_group,
                "total_cases": len(items),
                "exact_match_rate": _safe_rate(
                    sum(1 for item in items if item["normalized_final_status"] == item["expected_status"]),
                    len(items),
                ),
                "status_counts": status_counts,
            }
        )
    return rows


def _load_baseline_result(baseline_id: str) -> dict[str, Any]:
    path = BASELINE_RESULTS_DIR / f"{baseline_id.lower()}_latest.json"
    payload = _load_json(path)
    metrics = payload.get("metrics", {})
    status_counts = payload.get("status_counts") or metrics.get("status_counts", {})
    return {
        "baseline_id": baseline_id,
        "display_name": payload.get("display_name", baseline_id),
        "path": str(path),
        "metrics": metrics,
        "status_counts": status_counts,
        "results": payload.get("results", []),
        "asset_breakdown": _asset_breakdown(payload.get("results", [])),
        "semantic_breakdown": _semantic_breakdown(payload.get("results", [])),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


def _format_float(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PCAG Integrated Baseline Evaluation Summary")
    lines.append("")
    lines.append(f"- Generated at: {summary['generated_at']}")
    lines.append(f"- Dataset: `{summary['dataset_path']}`")
    lines.append(f"- Total cases: `{summary['expected_distribution']['total_cases']}`")
    lines.append(f"- Expected final status counts: `{summary['expected_distribution']['expected_status_counts']}`")
    lines.append("")
    lines.append("## Overall Comparison")
    lines.append("")
    lines.append(
        "| Baseline | Exact Match | Safe Pass | Unsafe Interception | Unsafe Commit | Integrity Reject | Tx Fault Non-Commit | Exec Fault Non-Commit | TOCTOU Catch | Median Latency (ms) | P95 Latency (ms) |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for item in summary["baselines"]:
        metrics = item["metrics"]
        lines.append(
            "| {baseline_id} ({display_name}) | {exact_match_rate} | {safe_pass_rate} | {unsafe_interception_rate} | {unsafe_commit_count} | {integrity_reject_rate} | {transaction_fault_noncommit_rate} | {execution_fault_noncommit_rate} | {toctou_catch_rate} | {median_latency_ms} | {p95_latency_ms} |".format(
                baseline_id=item["baseline_id"],
                display_name=item["display_name"],
                exact_match_rate=_format_float(metrics.get("exact_match_rate")),
                safe_pass_rate=_format_float(metrics.get("safe_pass_rate")),
                unsafe_interception_rate=_format_float(metrics.get("unsafe_interception_rate")),
                unsafe_commit_count=_format_float(metrics.get("unsafe_commit_count")),
                integrity_reject_rate=_format_float(metrics.get("integrity_reject_rate")),
                transaction_fault_noncommit_rate=_format_float(metrics.get("transaction_fault_noncommit_rate")),
                execution_fault_noncommit_rate=_format_float(metrics.get("execution_fault_noncommit_rate")),
                toctou_catch_rate=_format_float(metrics.get("toctou_catch_rate")),
                median_latency_ms=_format_float(metrics.get("median_latency_ms")),
                p95_latency_ms=_format_float(metrics.get("p95_latency_ms")),
            )
        )
    lines.append("")
    lines.append("## Final Status Counts")
    lines.append("")
    lines.append("| Baseline | COMMITTED | UNSAFE | REJECTED | ABORTED | ERROR |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for item in summary["baselines"]:
        counts = item["status_counts"]
        lines.append(
            f"| {item['baseline_id']} | {counts.get('COMMITTED', 0)} | {counts.get('UNSAFE', 0)} | {counts.get('REJECTED', 0)} | {counts.get('ABORTED', 0)} | {counts.get('ERROR', 0)} |"
        )
    lines.append("")
    lines.append("## Asset-wise Exact Match")
    lines.append("")
    lines.append("| Baseline | robot_arm_01 | agv_01 | reactor_01 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for item in summary["baselines"]:
        asset_index = {row["asset_id"]: row for row in item["asset_breakdown"]}
        lines.append(
            f"| {item['baseline_id']} | "
            f"{_format_float(asset_index.get('robot_arm_01', {}).get('exact_match_rate'))} | "
            f"{_format_float(asset_index.get('agv_01', {}).get('exact_match_rate'))} | "
            f"{_format_float(asset_index.get('reactor_01', {}).get('exact_match_rate'))} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This summary aggregates only observed results from the live evaluation outputs in `results/baselines` and the live `integrated_pcag_benchmark_latest.json` file.")
    lines.append("- No dataset mutation, label rewriting, mock data injection, or baseline-specific hard-coded case overrides were applied during aggregation.")
    return "\n".join(lines) + "\n"


def build_summary() -> dict[str, Any]:
    profiles = _load_profiles()
    baselines: list[dict[str, Any]] = []
    for profile in profiles:
        baseline_id = profile["baseline_id"]
        result = _load_baseline_result(baseline_id)
        result["display_name"] = profile.get("display_name", baseline_id)
        result["description"] = profile.get("description")
        baselines.append(result)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_path": str(DATASET_PATH),
        "expected_distribution": _load_expected_distribution(),
        "baselines": baselines,
    }


def main() -> int:
    summary = build_summary()
    json_path = BASELINE_RESULTS_DIR / "baseline_summary_latest.json"
    md_path = BASELINE_RESULTS_DIR / "baseline_summary_latest.md"
    csv_path = BASELINE_RESULTS_DIR / "baseline_summary_table_latest.csv"
    asset_csv_path = BASELINE_RESULTS_DIR / "baseline_asset_breakdown_latest.csv"

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(summary), encoding="utf-8")

    table_rows: list[dict[str, Any]] = []
    asset_rows: list[dict[str, Any]] = []
    for item in summary["baselines"]:
        metrics = item["metrics"]
        table_rows.append(
            {
                "baseline_id": item["baseline_id"],
                "display_name": item["display_name"],
                "exact_match_rate": metrics.get("exact_match_rate"),
                "safe_pass_rate": metrics.get("safe_pass_rate"),
                "unsafe_interception_rate": metrics.get("unsafe_interception_rate"),
                "unsafe_commit_count": metrics.get("unsafe_commit_count"),
                "integrity_reject_rate": metrics.get("integrity_reject_rate"),
                "transaction_fault_noncommit_rate": metrics.get("transaction_fault_noncommit_rate"),
                "execution_fault_noncommit_rate": metrics.get("execution_fault_noncommit_rate"),
                "toctou_catch_rate": metrics.get("toctou_catch_rate"),
                "median_latency_ms": metrics.get("median_latency_ms"),
                "p95_latency_ms": metrics.get("p95_latency_ms"),
                "committed": item["status_counts"].get("COMMITTED", 0),
                "unsafe": item["status_counts"].get("UNSAFE", 0),
                "rejected": item["status_counts"].get("REJECTED", 0),
                "aborted": item["status_counts"].get("ABORTED", 0),
                "error": item["status_counts"].get("ERROR", 0),
            }
        )
        for asset_row in item["asset_breakdown"]:
            asset_rows.append(
                {
                    "baseline_id": item["baseline_id"],
                    **asset_row,
                }
            )

    _write_csv(
        csv_path,
        table_rows,
        [
            "baseline_id",
            "display_name",
            "exact_match_rate",
            "safe_pass_rate",
            "unsafe_interception_rate",
            "unsafe_commit_count",
            "integrity_reject_rate",
            "transaction_fault_noncommit_rate",
            "execution_fault_noncommit_rate",
            "toctou_catch_rate",
            "median_latency_ms",
            "p95_latency_ms",
            "committed",
            "unsafe",
            "rejected",
            "aborted",
            "error",
        ],
    )
    _write_csv(
        asset_csv_path,
        asset_rows,
        [
            "baseline_id",
            "asset_id",
            "total_cases",
            "exact_match_rate",
            "safe_pass_rate",
            "unsafe_interception_rate",
            "unsafe_commit_count",
        ],
    )
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "table_csv": str(csv_path),
                "asset_csv": str(asset_csv_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
