from __future__ import annotations

import csv
import json
import shutil
import subprocess
import textwrap
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


REPO_ROOT = Path(__file__).resolve().parent
MANUSCRIPT_DIR = Path(
    r"C:\Users\choiLee\Dropbox\경남대학교\논문\IJAMT\IJAMT_Format\sn-article-template"
)
OUTPUT_DIR = MANUSCRIPT_DIR / "online_resources"

STATUS_ORDER = ["COMMITTED", "UNSAFE", "REJECTED", "ABORTED", "ERROR"]
FAULT_MAPPING = [
    ("policy_mismatch", "REJECTED", "INTEGRITY_REJECTED"),
    ("sensor_hash_mismatch", "REJECTED", "INTEGRITY_REJECTED"),
    ("timestamp_expired", "REJECTED", "INTEGRITY_REJECTED"),
    ("sensor_divergence", "REJECTED", "INTEGRITY_REJECTED"),
    ("lock_denied", "ABORTED", "PREPARE_LOCK_DENIED"),
    ("reverify_hash_mismatch", "ABORTED", "REVERIFY_FAILED"),
    ("commit_timeout", "ABORTED", "COMMIT_TIMEOUT"),
    ("commit_failed_recovered", "ABORTED", "COMMIT_FAILED"),
    ("ot_interface_error", "ERROR", "COMMIT_ERROR"),
]


def repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def tex_escape(text: object) -> str:
    value = "" if text is None else str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def tex_path(text: object) -> str:
    value = "" if text is None else str(text)
    return value.replace("\\", "/")


def latex_document(title: str, body: str) -> str:
    return textwrap.dedent(
        rf"""
        \documentclass[11pt]{{article}}
        \usepackage[margin=1in]{{geometry}}
        \usepackage{{booktabs}}
        \usepackage{{longtable}}
        \usepackage{{array}}
        \usepackage{{tabularx}}
        \usepackage{{ragged2e}}
        \usepackage{{hyperref}}
        \usepackage{{enumitem}}
        \usepackage{{xurl}}
        \hypersetup{{colorlinks=true,linkcolor=black,urlcolor=blue}}
        \newcolumntype{{Y}}{{>{{\RaggedRight\arraybackslash}}X}}
        \setlength{{\parindent}}{{0pt}}
        \setlength{{\parskip}}{{0.55em}}
        \setlength{{\emergencystretch}}{{2em}}
        \begin{{document}}
        \begin{{center}}
        {{\Large \textbf{{{tex_escape(title)}}}}}\\[0.5em]
        {{\normalsize PCAG IJAMT supplementary package}}\\[0.25em]
        {{\small Generated from the frozen benchmark and repository artifacts}}
        \end{{center}}
        {body}
        \end{{document}}
        """
    ).strip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_simple_pdf(path: Path, title: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin_x = 54
    margin_y = 54
    line_height = 13
    title_height = 18
    c = canvas.Canvas(str(path), pagesize=A4)
    y = page_height - margin_y

    def new_page() -> float:
        c.showPage()
        return page_height - margin_y

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_x, y, title)
    y -= title_height
    c.setFont("Helvetica", 10)

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        wrapped = textwrap.wrap(line, width=106, break_long_words=False, break_on_hyphens=False) or [""]
        for segment in wrapped:
            if y < margin_y:
                y = new_page()
                c.setFont("Helvetica", 10)
            c.drawString(margin_x, y, segment)
            y -= line_height
    c.save()


def build_paths() -> dict[str, Path]:
    base = REPO_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
    return {
        "dataset": base / "releases" / "integrated_benchmark_release_v2" / "pcag_execution_dataset.json",
        "dataset_manifest": base / "releases" / "integrated_benchmark_release_v2" / "dataset_manifest.json",
        "integrated_results": base / "results" / "integrated_pcag_benchmark_latest.json",
        "baseline_summary": base / "results" / "baselines" / "baseline_summary_table_latest.csv",
        "baseline_asset_breakdown": base / "results" / "baselines" / "baseline_asset_breakdown_latest.csv",
        "independent_validation": base / "results" / "independent_validation" / "independent_validation_subset_latest.json",
        "robot_execution_evidence": base / "results" / "independent_validation" / "robot_execution_evidence_latest.json",
        "policy": base / "policies" / "pcag_benchmark_policy_v1.json",
        "policy_readme": base / "policies" / "README.md",
        "hash_utils": REPO_ROOT / "pcag" / "core" / "utils" / "hash_utils.py",
        "canonicalize": REPO_ROOT / "pcag" / "core" / "utils" / "canonicalize.py",
        "integrity_service": REPO_ROOT / "pcag" / "core" / "services" / "integrity_service.py",
        "proof_contract": REPO_ROOT / "pcag" / "core" / "contracts" / "proof_package.py",
        "gateway_contract": REPO_ROOT / "pcag" / "core" / "contracts" / "gateway.py",
        "evidence_contract": REPO_ROOT / "pcag" / "core" / "contracts" / "evidence.py",
        "figure_script": MANUSCRIPT_DIR / "generate_pcag_paper_figures.py",
        "figure_dir": MANUSCRIPT_DIR / "pcag-figures",
        "manuscript": MANUSCRIPT_DIR / "pcag_ijamt_submission.tex",
    }


def flatten_manifest_rows(dataset: dict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case in dataset["cases"]:
        proof = case.get("proof", {})
        source = case.get("source_benchmark", {})
        runtime = case.get("runtime", {})
        label = case.get("label", {})
        notes = case.get("notes", {})
        fault = case.get("fault_injection") or {}
        rows.append(
            {
                "case_id": case.get("case_id"),
                "asset_id": case.get("asset_id"),
                "scenario_family": case.get("scenario_family"),
                "case_group": case.get("case_group"),
                "source_name": source.get("source_name"),
                "source_id": source.get("source_id"),
                "source_task_family": source.get("task_family"),
                "runtime_context_ref": runtime.get("runtime_context_ref"),
                "policy_version_id": proof.get("policy_version_id"),
                "proof_origin": proof.get("proof_origin"),
                "expected_final_status": label.get("expected_final_status"),
                "expected_stop_stage": label.get("expected_stop_stage"),
                "expected_reason_code": label.get("expected_reason_code"),
                "fault_family": fault.get("fault_family"),
                "fault_stage": fault.get("target_stage"),
                "paper_role": notes.get("paper_role"),
                "description": case.get("description"),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows available for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[dict[str, object]], sheet_name: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header) for header in headers])
    for column_cells in ws.columns:
        max_len = max(len("" if cell.value is None else str(cell.value)) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 48)
    wb.save(path)


def select_sample_cases(results: dict) -> dict[str, dict]:
    preferred = {
        "COMMITTED": ("robot_arm_01", "COMMIT_ACK"),
        "ABORTED": ("agv_01", "PREPARE_LOCK_DENIED"),
        "UNSAFE": ("reactor_01", "SAFETY_UNSAFE"),
        "REJECTED": ("agv_01", "INTEGRITY_REJECTED"),
        "ERROR": ("reactor_01", "COMMIT_ERROR"),
    }
    selected: dict[str, dict] = {}
    by_status: dict[str, list[dict]] = {status: [] for status in STATUS_ORDER}
    for record in results["results"]:
        status = record.get("response_json", {}).get("status")
        if status in by_status and record.get("evidence", {}).get("events"):
            by_status[status].append(record)
    for status in STATUS_ORDER:
        asset_pref, stage_pref = preferred[status]
        choice = None
        for record in by_status[status]:
            asset_id = record.get("asset_id")
            stage = record["evidence"]["events"][-1]["stage"]
            if asset_id == asset_pref and stage == stage_pref:
                choice = record
                break
        if choice is None:
            for record in by_status[status]:
                if record.get("asset_id") == asset_pref:
                    choice = record
                    break
        if choice is None and by_status[status]:
            choice = by_status[status][0]
        if choice is not None:
            selected[status] = choice
    return selected


def flatten_evidence_rows(sample_cases: dict[str, dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    display_order = ["COMMITTED", "ABORTED", "UNSAFE", "REJECTED", "ERROR"]
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        evidence = record["evidence"]
        for event in evidence["events"]:
            rows.append(
                {
                    "sample_status": status,
                    "case_id": record["case_id"],
                    "asset_id": record["asset_id"],
                    "transaction_id": evidence["transaction_id"],
                    "sequence_no": event["sequence_no"],
                    "stage": event["stage"],
                    "timestamp_ms": event["timestamp_ms"],
                    "created_at": event["created_at"],
                    "input_hash": event["input_hash"],
                    "prev_hash": event["prev_hash"],
                    "event_hash": event["event_hash"],
                    "payload_json": json.dumps(event["payload"], ensure_ascii=False, sort_keys=True),
                }
            )
    return rows


def build_or1_tex(dataset: dict, policy: dict, paths: dict[str, Path]) -> str:
    sample_case = dataset["cases"][0]
    case_fields = [
        ("case_id", "Stable frozen benchmark identifier."),
        ("asset_id", "Physical asset under the shared gateway contract."),
        ("scenario_family", "Paper-facing family label used for asset-level grouping."),
        ("source_benchmark", "Normalized provenance metadata for the upstream benchmark or source shell."),
        ("operation_context", "Cell, station, or mission-phase context used by the command."),
        ("runtime", "Runtime context, initial state, and preload rule."),
        ("proof", "Structured proof package carried into the gateway."),
        ("fault_injection", "Optional fault mutation descriptor for protocol-stress cases."),
        ("label", "Frozen gateway-final triplet: status, stop stage, and reason code."),
        ("expected", "HTTP and evidence expectations used in exact-match checking."),
        ("module_expectations", "Expected validator and consensus outputs when applicable."),
        ("readiness", "Implementation-facing notes shared across normalized cases."),
        ("notes", "Paper role, release lineage, and counterfactual metadata."),
    ]
    proof_fields = [
        "schema_version",
        "policy_version_id",
        "timestamp_ms",
        "sensor_snapshot_hash",
        "sensor_reliability_index",
        "action_sequence",
        "safety_verification_summary",
    ]
    optional_proof_fields = [
        "sensor_snapshot",
        "agent_id",
        "intent_id",
        "proof_generated_at_ms",
        "proof_origin",
    ]
    gateway_response_fields = [
        "transaction_id",
        "status",
        "reason",
        "reason_code",
        "evidence_ref",
        "alternative_action",
        "alternative_actions",
    ]
    evidence_fields = [
        "transaction_id",
        "sequence_no",
        "stage",
        "timestamp_ms",
        "created_at",
        "payload",
        "input_hash",
        "prev_hash",
        "event_hash",
    ]
    body: list[str] = []
    body.append(
        r"\section*{Purpose}"
        "\nThis document records the frozen benchmark case format, the policy document layout, and the integrity-hash construction used by the present IJAMT submission. "
        "The authoritative machine-readable artifacts remain in the public repository; this PDF is the paper-facing reference."
    )
    body.append(
        r"\section*{Frozen benchmark case layout}"
        "\nThe integrated release stores one JSON object with top-level keys "
        r"\texttt{meta}, \texttt{defaults}, \texttt{libraries}, and \texttt{cases}. "
        f"The frozen release contains {len(dataset['cases'])} cases."
    )
    case_rows = "\n".join(rf"{tex_escape(name)} & {tex_escape(desc)} \\" for name, desc in case_fields)
    body.append(
        r"\begin{longtable}{p{0.24\textwidth}p{0.68\textwidth}}"
        "\n\\toprule\nField & Meaning \\\\\n\\midrule\n\\endhead\n"
        + case_rows
        + "\n\\bottomrule\n\\end{longtable}"
    )
    body.append(
        "Required proof-package fields are "
        + ", ".join(rf"\texttt{{{tex_escape(field)}}}" for field in proof_fields)
        + ". Optional traceability fields retained in the live stack are "
        + ", ".join(rf"\texttt{{{tex_escape(field)}}}" for field in optional_proof_fields)
        + "."
    )
    body.append(
        "The canonical proof-package contract is stored at "
        rf"\texttt{{{tex_escape(repo_relative(paths['proof_contract'], REPO_ROOT))}}}."
    )
    body.append(
        r"\section*{Gateway and evidence contracts}"
        "\nThe gateway response exposes the fields "
        + ", ".join(rf"\texttt{{{tex_escape(field)}}}" for field in gateway_response_fields)
        + ". The evidence ledger appends event records with fields "
        + ", ".join(rf"\texttt{{{tex_escape(field)}}}" for field in evidence_fields)
        + "."
    )
    body.append(
        "The corresponding code-level contracts are stored at "
        rf"\texttt{{{tex_escape(repo_relative(paths['gateway_contract'], REPO_ROOT))}}} and "
        rf"\texttt{{{tex_escape(repo_relative(paths['evidence_contract'], REPO_ROOT))}}}."
    )
    policy_fields = [
        ("policy_version_id", "Stable paper-facing version identifier."),
        ("global_policy.hash.algorithm", policy["global_policy"]["hash"]["algorithm"]),
        ("global_policy.hash.canonicalization_version", policy["global_policy"]["hash"]["canonicalization_version"]),
        ("global_policy.defaults.timestamp_max_age_ms", policy["global_policy"]["defaults"]["timestamp_max_age_ms"]),
        ("assets.robot_arm_01", "Robot profile with Isaac-backed sensing and mock-backed commit."),
        ("assets.agv_01", "AGV profile with Modbus sensing and PLC-adapter-backed execution."),
        ("assets.reactor_01", "Process profile with Modbus sensing and PLC-adapter-backed execution."),
    ]
    policy_rows = "\n".join(rf"{tex_escape(name)} & {tex_escape(value)} \\" for name, value in policy_fields)
    body.append(
        r"\section*{Unified benchmark policy format}"
        "\n"
        r"\begin{longtable}{p{0.38\textwidth}p{0.54\textwidth}}"
        "\n\\toprule\nPolicy field & Value or role \\\\\n\\midrule\n\\endhead\n"
        + policy_rows
        + "\n\\bottomrule\n\\end{longtable}"
    )
    body.append(
        "The machine-readable policy artifact is stored at "
        rf"\texttt{{{tex_escape(repo_relative(paths['policy'], REPO_ROOT))}}}. "
        "Repository notes for policy seeding and asset-specific execution semantics are recorded in "
        rf"\texttt{{{tex_escape(repo_relative(paths['policy_readme'], REPO_ROOT))}}}."
    )
    body.append(
        r"\section*{Integrity hash construction}"
        "\nThe benchmark uses SHA-256 for both sensor snapshots and stage-wise evidence events. "
        "Canonicalization follows a deterministic JSON serialization rule: dictionary keys are sorted, "
        "whitespace is removed, lists are serialized in order, and floating-point values are rounded to three decimals."
    )
    body.append(
        r"\begin{itemize}[leftmargin=1.5em]"
        "\n\\item Sensor hash: \\texttt{SHA256(Canonicalize(sensor\\_snapshot))}."
        "\n\\item Event hash: \\texttt{SHA256(prev\\_hash + Canonicalize(payload))}."
        "\n\\item Genesis hash: SHA-256 of the empty byte string."
        "\n\\item Integrity rejection is triggered by policy-version mismatch, sensor-hash mismatch, timestamp expiry/future skew, or sensor divergence beyond the policy thresholds."
        "\n\\end{itemize}"
    )
    body.append(
        "The implementation sources are "
        rf"\texttt{{{tex_escape(repo_relative(paths['canonicalize'], REPO_ROOT))}}}, "
        rf"\texttt{{{tex_escape(repo_relative(paths['hash_utils'], REPO_ROOT))}}}, and "
        rf"\texttt{{{tex_escape(repo_relative(paths['integrity_service'], REPO_ROOT))}}}."
    )
    example_fields = {
        "case_id": sample_case["case_id"],
        "asset_id": sample_case["asset_id"],
        "scenario_family": sample_case["scenario_family"],
        "runtime_context_ref": sample_case["runtime"]["runtime_context_ref"],
        "policy_version_id": sample_case["proof"]["policy_version_id"],
        "expected_final_status": sample_case["label"]["expected_final_status"],
        "expected_stop_stage": sample_case["label"]["expected_stop_stage"],
    }
    example_rows = "\n".join(rf"{tex_escape(k)} & {tex_escape(v)} \\" for k, v in example_fields.items())
    body.append(
        r"\section*{Representative frozen case}"
        "\n"
        r"\begin{tabular}{p{0.34\textwidth}p{0.54\textwidth}}"
        "\n\\toprule\nField & Value \\\\\n\\midrule\n"
        + example_rows
        + "\n\\bottomrule\n\\end{tabular}"
    )
    return latex_document(
        "Online Resource 1: Benchmark schema, policy format, and integrity-hash construction",
        "\n\n".join(body),
    )


def build_or3_tex(sample_cases: dict[str, dict], csv_name: str) -> str:
    body: list[str] = []
    body.append(
        r"\section*{Purpose}"
        "\nThis document provides representative append-only evidence traces sampled from the frozen integrated benchmark execution results. "
        "The primary samples are aligned with the representative walkthroughs described in the main manuscript: a nominal robot case, an AGV transaction-fault case, and a process unsafe case. "
        "Additional samples are retained for the REJECTED and ERROR terminal outcomes. The companion CSV file contains the flattened event rows for the same sample transactions."
    )
    body.append("The companion CSV file is " + rf"\path{{{tex_path(csv_name)}}}.")
    rows = []
    case_map_lines = []
    sample_no = 1
    display_order = ["COMMITTED", "ABORTED", "UNSAFE", "REJECTED", "ERROR"]
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        evidence = record["evidence"]
        terminal_stage = evidence["events"][-1]["stage"]
        sample_id = f"S{sample_no}"
        rows.append(
            (
                sample_id,
                status,
                record["asset_id"],
                rf"\texttt{{{tex_escape(terminal_stage)}}}",
                len(evidence["events"]),
                "Yes" if evidence["chain_valid"] else "No",
            )
        )
        case_map_lines.append(rf"\item \textbf{{{sample_id}}}: \path{{{tex_path(record['case_id'])}}}")
        sample_no += 1
    table_rows = "\n".join(
        rf"{tex_escape(sample_id)} & {tex_escape(status)} & \texttt{{{tex_escape(asset_id)}}} & {stage} & {count} & {tex_escape(chain)} \\"
        for sample_id, status, asset_id, stage, count, chain in rows
    )
    body.append(
        r"\section*{Sampled transactions}"
        "\n"
        r"\small"
        "\n"
        r"\begin{tabularx}{\textwidth}{p{0.08\textwidth}p{0.14\textwidth}p{0.14\textwidth}Yp{0.07\textwidth}p{0.10\textwidth}}"
        "\n\\toprule\nSample & Status & Asset & Terminal stage & Events & Chain valid \\\\\n\\midrule\n"
        + table_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize"
    )
    body.append(r"\section*{Sample-to-case mapping}")
    body.append(r"\begin{itemize}[leftmargin=1.5em]" + "\n" + "\n".join(case_map_lines) + "\n\\end{itemize}")
    body.append(
        "Samples \\textbf{S1}, \\textbf{S2}, and \\textbf{S3} correspond directly to the representative nominal, transaction-fault, and unsafe walkthroughs discussed in the manuscript results section."
    )
    body.append(r"\section*{Representative stage sequences}")
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        stages = " $\\rightarrow$ ".join(rf"\texttt{{{tex_escape(event['stage'])}}}" for event in record["evidence"]["events"])
        body.append(rf"\textbf{{{tex_escape(status)}}} --- \path{{{tex_path(record['case_id'])}}}\\")
        body.append(r"{\small " + stages + "}")
    body.append(
        r"\section*{Interpretation}"
        "\nThe sampled traces illustrate the stage-level semantics used by the paper. "
        "A committed case traverses schema validation, integrity, safety, PREPARE, REVERIFY, and COMMIT\\_ACK. "
        "Rejected, unsafe, aborted, and error cases terminate earlier while preserving the append-only chain."
    )
    return latex_document(
        "Online Resource 3: Sample evidence logs and terminal-stage traces",
        "\n\n".join(body),
    )


def build_or4_tex(dataset: dict, paths: dict[str, Path]) -> str:
    statuses = Counter()
    stages = Counter()
    reasons = Counter()
    fault_families = Counter()
    for case in dataset["cases"]:
        label = case.get("label", {})
        fault = case.get("fault_injection") or {}
        statuses[label.get("expected_final_status")] += 1
        stages[label.get("expected_stop_stage")] += 1
        reasons[label.get("expected_reason_code")] += 1
        fault_families[fault.get("fault_family")] += 1
    status_rows = "\n".join(
        rf"{tex_escape(status)} & {statuses.get(status, 0)} \\"
        for status in STATUS_ORDER
    )
    stage_rows = "\n".join(
        rf"\texttt{{{tex_escape(stage)}}} & {count} \\"
        for stage, count in stages.items()
    )
    reason_rows = "\n".join(
        rf"\texttt{{{tex_escape(reason if reason is not None else 'NONE')}}} & {count} \\"
        for reason, count in reasons.items()
    )
    fault_rows = "\n".join(
        rf"\texttt{{{tex_escape(name)}}} & {fault_families.get(name, 0)} & {tex_escape(status)} & \texttt{{{tex_escape(stage)}}} \\"
        for name, status, stage in FAULT_MAPPING
    )
    status_summary = ", ".join(
        rf"{count} {tex_escape(status)}"
        for status, count in sorted(statuses.items(), key=lambda item: STATUS_ORDER.index(item[0]))
    )
    body: list[str] = []
    body.append(
        r"\section*{Purpose}"
        "\nThis document records the gateway-final labeling rule used by the frozen benchmark, the benchmark fault-injection families, and the reason-code taxonomy reported in the manuscript."
    )
    body.append(
        r"\section*{Gateway-final labeling rule}"
        "\nLabels are frozen according to the actual final gateway outcome produced by the full PCAG path, "
        "not according to the originally intended fault family. Earlier-stage failures therefore pre-empt later-stage targets when the protocol terminates before reaching them."
    )
    body.append(
        r"\begin{enumerate}[leftmargin=1.7em]"
        "\n\\item Integrity validation."
        "\n\\item Rules, barrier-style validation, and simulation-backed validation."
        "\n\\item Conservative safety consensus."
        "\n\\item PREPARE."
        "\n\\item REVERIFY."
        "\n\\item COMMIT, ABORT, or ERROR."
        "\n\\item Evidence append and chain validation."
        "\n\\end{enumerate}"
    )
    body.append(r"\section*{Final-status summary}")
    body.append(
        r"\small"
        "\n"
        r"\begin{tabularx}{0.62\textwidth}{Yp{0.14\textwidth}}"
        "\n\\toprule\nFinal status & Count \\\\\n\\midrule\n"
        + status_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize"
    )
    body.append("The frozen integrated benchmark contains " + status_summary + ".")
    body.append(r"\section*{Terminal-stage taxonomy}")
    body.append(
        r"\small"
        "\n"
        r"\begin{tabularx}{0.72\textwidth}{Yp{0.14\textwidth}}"
        "\n\\toprule\nTerminal stage & Count \\\\\n\\midrule\n"
        + stage_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize"
    )
    body.append(r"\section*{Reason-code taxonomy}")
    body.append(
        r"\small"
        "\n"
        r"\begin{tabularx}{0.78\textwidth}{Yp{0.14\textwidth}}"
        "\n\\toprule\nReason code & Count \\\\\n\\midrule\n"
        + reason_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize"
    )
    body.append(
        r"\section*{Fault-injection families}"
        "\n"
        r"\small"
        "\n"
        r"\begin{tabularx}{\textwidth}{Yp{0.08\textwidth}p{0.18\textwidth}Y}"
        "\n\\toprule\nFault family & Count & Target final status & Typical terminal stage \\\\\n\\midrule\n"
        + fault_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize"
    )
    body.append(
        "The fault families are used for failure-semantics coverage rather than for industrial frequency estimation. "
        "The frozen benchmark therefore balances integrity, transaction, and execution-side failures under one gateway-final contract."
    )
    body.append(r"\section*{Repository references}")
    body.append(
        r"\begin{itemize}[leftmargin=1.5em]"
        "\n\\item Dataset release: "
        rf"\path{{{tex_path(repo_relative(paths['dataset'], REPO_ROOT))}}}"
        "\n\\item Dataset manifest: "
        rf"\path{{{tex_path(repo_relative(paths['dataset_manifest'], REPO_ROOT))}}}"
        "\n\\item Integrity service: "
        rf"\path{{{tex_path(repo_relative(paths['integrity_service'], REPO_ROOT))}}}"
        "\n\\end{itemize}"
    )
    return latex_document(
        "Online Resource 4: Gateway-final labeling, fault-injection, and reason-code specification",
        "\n\n".join(body),
    )


def build_or5_md(paths: dict[str, Path]) -> str:
    mappings = [
        ("Frozen benchmark dataset", paths["dataset"]),
        ("Dataset manifest", paths["dataset_manifest"]),
        ("Integrated benchmark results", paths["integrated_results"]),
        ("Unified benchmark policy", paths["policy"]),
        ("Policy notes", paths["policy_readme"]),
        ("Baseline summary table", paths["baseline_summary"]),
        ("Baseline asset breakdown", paths["baseline_asset_breakdown"]),
        ("Independent validation subset", paths["independent_validation"]),
        ("Robot direct-execution evidence", paths["robot_execution_evidence"]),
        ("Hash construction utility", paths["hash_utils"]),
        ("Canonicalization utility", paths["canonicalize"]),
        ("Integrity service", paths["integrity_service"]),
        ("Proof package contract", paths["proof_contract"]),
        ("Gateway contract", paths["gateway_contract"]),
        ("Evidence contract", paths["evidence_contract"]),
        ("Figure-generation script", paths["figure_script"]),
        ("Manuscript source", paths["manuscript"]),
    ]
    lines = [
        "# Online Resource 5: Anonymized reproducibility manifest and repository map",
        "",
        "This manifest records the repository-facing artifacts used by the IJAMT submission.",
        "All paths are anonymized to `repository_root/` or `manuscript_root/` form.",
        "",
        "## Repository map",
        "",
    ]
    for label, path in mappings:
        if str(path).startswith(str(MANUSCRIPT_DIR)):
            rel = repo_relative(path, MANUSCRIPT_DIR)
            lines.append(f"- {label}: `manuscript_root/{rel}`")
        else:
            rel = repo_relative(path, REPO_ROOT)
            lines.append(f"- {label}: `repository_root/{rel}`")
    lines.extend(
        [
            "",
            "## Manuscript artifact map",
            "",
            "- Section 4 provenance and normalization: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/pcag_execution_dataset.json`, `repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/dataset_manifest.json`, and `repository_root/tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`.",
            "- Table 4 integrated benchmark composition: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/dataset_manifest.json` and the frozen dataset release.",
            "- Figure 3 integrated outcome distribution: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json` together with `manuscript_root/generate_pcag_paper_figures.py`.",
            "- Table 8 and Figure 4 baseline comparison: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/baselines/baseline_summary_table_latest.csv`, `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/baselines/baseline_asset_breakdown_latest.csv`, and `manuscript_root/generate_pcag_paper_figures.py`.",
            "- Section 7.4 independent validation subset: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/independent_validation/independent_validation_subset_latest.json`.",
            "- Section 7.5 robot direct Isaac evidence: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/independent_validation/robot_execution_evidence_latest.json`.",
            "- Figure 5 terminal-stage distribution and evidence completeness: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json`.",
            "- Figure 6 latency by asset family: `repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json` and `manuscript_root/generate_pcag_paper_figures.py`.",
        ]
    )
    lines.extend(
        [
            "",
            "## Regeneration map",
            "",
            "- Online Resource 1 is generated from the frozen dataset, policy, and contract utilities.",
            "- Online Resource 2 is generated from the frozen 368-case release.",
            "- Online Resource 3 is generated from the integrated execution results and evidence chains.",
            "- Online Resource 4 is generated from the frozen dataset labels and fault descriptors.",
            "- Main manuscript figures are regenerated with `manuscript_root/generate_pcag_paper_figures.py`.",
            "",
            "## Notes",
            "",
            "- The frozen benchmark release is treated as the authoritative source for case definitions.",
            "- Supplementary PDFs are paper-facing summaries of the machine-readable repository artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_or5_tex(paths: dict[str, Path]) -> str:
    mappings = [
        ("Frozen benchmark dataset", rf"\path{{repository_root/{tex_path(repo_relative(paths['dataset'], REPO_ROOT))}}}"),
        ("Dataset manifest", rf"\path{{repository_root/{tex_path(repo_relative(paths['dataset_manifest'], REPO_ROOT))}}}"),
        ("Integrated benchmark results", rf"\path{{repository_root/{tex_path(repo_relative(paths['integrated_results'], REPO_ROOT))}}}"),
        ("Unified benchmark policy", rf"\path{{repository_root/{tex_path(repo_relative(paths['policy'], REPO_ROOT))}}}"),
        ("Baseline summary table", rf"\path{{repository_root/{tex_path(repo_relative(paths['baseline_summary'], REPO_ROOT))}}}"),
        ("Independent validation subset", rf"\path{{repository_root/{tex_path(repo_relative(paths['independent_validation'], REPO_ROOT))}}}"),
        ("Robot direct-execution evidence", rf"\path{{repository_root/{tex_path(repo_relative(paths['robot_execution_evidence'], REPO_ROOT))}}}"),
        ("Figure-generation script", rf"\path{{manuscript_root/{tex_path(repo_relative(paths['figure_script'], MANUSCRIPT_DIR))}}}"),
        ("Manuscript source", rf"\path{{manuscript_root/{tex_path(repo_relative(paths['manuscript'], MANUSCRIPT_DIR))}}}"),
    ]
    table_rows = "\n".join(
        rf"{tex_escape(label)} & {path} \\"
        for label, path in mappings
    )
    artifact_rows = "\n".join(
        [
            r"Section 4 provenance and normalization & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/pcag_execution_dataset.json}; \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/dataset_manifest.json}; \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json} \\",
            r"Table 4 integrated benchmark composition & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/releases/integrated_benchmark_release_v2/dataset_manifest.json} and the frozen dataset release \\",
            r"Figure 3 integrated outcome distribution & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json} and \path{manuscript_root/generate_pcag_paper_figures.py} \\",
            r"Table 8 and Figure 4 baseline comparison & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/baselines/baseline_summary_table_latest.csv}; \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/baselines/baseline_asset_breakdown_latest.csv}; \path{manuscript_root/generate_pcag_paper_figures.py} \\",
            r"Section 7.4 independent validation subset & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/independent_validation/independent_validation_subset_latest.json} \\",
            r"Section 7.5 robot direct Isaac evidence & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/independent_validation/robot_execution_evidence_latest.json} \\",
            r"Figure 5 terminal-stage distribution and evidence completeness & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json} \\",
            r"Figure 6 latency by asset family & \path{repository_root/tests/benchmarks/pcag_ijamt_benchmark/results/integrated_pcag_benchmark_latest.json} and \path{manuscript_root/generate_pcag_paper_figures.py} \\",
        ]
    )
    body = [
        r"\section*{Purpose}"
        "\nThis document records an anonymized repository map and regeneration guide for the supplementary package and the manuscript-facing artifacts.",
        r"\section*{Repository-facing artifact map}"
        "\n"
        r"\small"
        "\n"
        r"\begin{tabularx}{\textwidth}{p{0.28\textwidth}Y}"
        "\n\\toprule\nArtifact & Anonymized path \\\\\n\\midrule\n"
        + table_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize",
        r"\section*{Manuscript artifact map}"
        "\n"
        r"\small"
        "\n"
        r"\begin{tabularx}{\textwidth}{p{0.28\textwidth}Y}"
        "\n\\toprule\nManuscript item & Primary repository artifact(s) \\\\\n\\midrule\n"
        + artifact_rows
        + "\n\\bottomrule\n\\end{tabularx}\n\\normalsize",
        r"\section*{Regeneration notes}"
        "\n"
        r"\begin{itemize}[leftmargin=1.5em]"
        "\n\\item Online Resource 1 summarizes the frozen case schema, unified policy format, and integrity-hash construction."
        "\n\\item Online Resource 2 is generated directly from the frozen 368-case release."
        "\n\\item Online Resource 3 is generated from the integrated benchmark execution results and append-only evidence logs."
        "\n\\item Online Resource 4 summarizes label freezing, fault families, and reason-code semantics from the frozen release."
        "\n\\item The manuscript figures are regenerated from the figure script stored under manuscript\\_root."
        "\n\\end{itemize}",
        r"\section*{Anonymization note}"
        "\nRepository paths are intentionally reported in relative form so that the supplementary package can be distributed during review without exposing local workstation structure.",
    ]
    return latex_document(
        "Online Resource 5: Anonymized reproducibility manifest and repository map",
        "\n\n".join(body),
    )


def build_or1_pdf_text(dataset: dict, policy: dict, paths: dict[str, Path]) -> str:
    sample_case = dataset["cases"][0]
    lines = [
        "Purpose",
        "This document records the frozen benchmark case format, the policy layout, and the integrity-hash construction used by the present IJAMT submission.",
        "",
        "Frozen benchmark case layout",
        f"Top-level keys: meta, defaults, libraries, cases. Frozen case count: {len(dataset['cases'])}.",
        "Core fields:",
        "- case_id: stable frozen benchmark identifier",
        "- asset_id: physical asset under the shared gateway contract",
        "- scenario_family: paper-facing family label",
        "- source_benchmark: normalized provenance metadata",
        "- operation_context: station or mission-phase context",
        "- runtime: runtime context, initial state, and preload rule",
        "- proof: structured proof package carried into the gateway",
        "- fault_injection: optional protocol-stress descriptor",
        "- label: frozen gateway-final status, stop stage, and reason code",
        "- expected: HTTP and evidence expectations used in exact-match checking",
        "- module_expectations: expected validator and consensus outputs",
        "- notes: paper role and release metadata",
        "",
        "Proof package contract",
        "Required fields: schema_version, policy_version_id, timestamp_ms, sensor_snapshot_hash, sensor_reliability_index, action_sequence, safety_verification_summary.",
        "Optional fields: sensor_snapshot, agent_id, intent_id, proof_generated_at_ms, proof_origin.",
        f"Source file: {repo_relative(paths['proof_contract'], REPO_ROOT)}",
        "",
        "Gateway and evidence contracts",
        "Gateway response fields: transaction_id, status, reason, reason_code, evidence_ref, alternative_action, alternative_actions.",
        "Evidence event fields: transaction_id, sequence_no, stage, timestamp_ms, created_at, payload, input_hash, prev_hash, event_hash.",
        f"Gateway contract: {repo_relative(paths['gateway_contract'], REPO_ROOT)}",
        f"Evidence contract: {repo_relative(paths['evidence_contract'], REPO_ROOT)}",
        "",
        "Unified benchmark policy format",
        f"Policy version ID: {policy['policy_version_id']}",
        f"Hash algorithm: {policy['global_policy']['hash']['algorithm']}",
        f"Canonicalization version: {policy['global_policy']['hash']['canonicalization_version']}",
        f"Timestamp max age (ms): {policy['global_policy']['defaults']['timestamp_max_age_ms']}",
        "Asset profiles: robot_arm_01, agv_01, reactor_01.",
        f"Policy file: {repo_relative(paths['policy'], REPO_ROOT)}",
        f"Policy notes: {repo_relative(paths['policy_readme'], REPO_ROOT)}",
        "",
        "Integrity hash construction",
        "Sensor hash = SHA256(Canonicalize(sensor_snapshot)).",
        "Event hash = SHA256(prev_hash + Canonicalize(payload)).",
        "Genesis hash = SHA-256 of the empty byte string.",
        "Canonicalization sorts dictionary keys, removes whitespace, preserves list order, and rounds floats to three decimals.",
        "Integrity rejection reasons include policy-version mismatch, sensor-hash mismatch, timestamp expiry or future skew, and sensor divergence.",
        f"Canonicalization utility: {repo_relative(paths['canonicalize'], REPO_ROOT)}",
        f"Hash utility: {repo_relative(paths['hash_utils'], REPO_ROOT)}",
        f"Integrity service: {repo_relative(paths['integrity_service'], REPO_ROOT)}",
        "",
        "Representative frozen case",
        f"case_id: {sample_case['case_id']}",
        f"asset_id: {sample_case['asset_id']}",
        f"scenario_family: {sample_case['scenario_family']}",
        f"runtime_context_ref: {sample_case['runtime']['runtime_context_ref']}",
        f"policy_version_id: {sample_case['proof']['policy_version_id']}",
        f"expected_final_status: {sample_case['label']['expected_final_status']}",
        f"expected_stop_stage: {sample_case['label']['expected_stop_stage']}",
    ]
    return "\n".join(lines)


def build_or3_pdf_text(sample_cases: dict[str, dict], csv_name: str) -> str:
    lines = [
        "Purpose",
        "This document provides representative append-only evidence traces sampled from the frozen integrated benchmark execution results.",
        "The primary samples are aligned with the manuscript walkthroughs: robot nominal, AGV transaction-fault, and process unsafe.",
        f"Companion CSV: {csv_name}",
        "",
        "Sampled transactions",
    ]
    display_order = ["COMMITTED", "ABORTED", "UNSAFE", "REJECTED", "ERROR"]
    sample_no = 1
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        evidence = record["evidence"]
        terminal_stage = evidence["events"][-1]["stage"]
        lines.extend(
            [
                f"- S{sample_no} / {status}: asset_id={record['asset_id']}, terminal_stage={terminal_stage}, events={len(evidence['events'])}, chain_valid={evidence['chain_valid']}",
            ]
        )
        sample_no += 1
    lines.extend(["", "Sample-to-case mapping"])
    sample_no = 1
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        lines.append(f"- S{sample_no}: {record['case_id']}")
        sample_no += 1
    lines.extend(["", "Representative stage sequences"])
    for status in display_order:
        record = sample_cases.get(status)
        if record is None:
            continue
        stages = " -> ".join(event["stage"] for event in record["evidence"]["events"])
        lines.extend([f"{status} / {record['case_id']}", stages, ""])
    lines.extend(
        [
            "Interpretation",
            "Committed cases traverse schema validation, integrity, safety, PREPARE, REVERIFY, and COMMIT_ACK.",
            "Rejected, unsafe, aborted, and error cases terminate earlier while preserving the append-only evidence chain.",
        ]
    )
    return "\n".join(lines)


def build_or4_pdf_text(dataset: dict, paths: dict[str, Path]) -> str:
    statuses = Counter()
    stages = Counter()
    reasons = Counter()
    fault_families = Counter()
    for case in dataset["cases"]:
        label = case.get("label", {})
        fault = case.get("fault_injection") or {}
        statuses[label.get("expected_final_status")] += 1
        stages[label.get("expected_stop_stage")] += 1
        reasons[label.get("expected_reason_code")] += 1
        fault_families[fault.get("fault_family")] += 1
    lines = [
        "Purpose",
        "This document records the gateway-final labeling rule, benchmark fault-injection families, and reason-code taxonomy used by the present IJAMT submission.",
        "",
        "Gateway-final labeling rule",
        "Labels are frozen according to the actual final gateway outcome under the full PCAG path, not according to the originally intended fault family.",
        "Earlier-stage failures pre-empt later-stage targets when the protocol terminates before reaching them.",
        "Protocol order: Integrity -> Rules/Barrier/Simulation -> Consensus -> PREPARE -> REVERIFY -> COMMIT/ABORT/ERROR -> Evidence append.",
        "",
        "Final-status counts",
    ]
    for status in STATUS_ORDER:
        lines.append(f"- {status}: {statuses.get(status, 0)}")
    lines.extend(["", "Terminal-stage counts"])
    for stage, count in stages.items():
        lines.append(f"- {stage}: {count}")
    lines.extend(["", "Reason-code counts"])
    for reason, count in reasons.items():
        reason_text = "None (nominal commit)" if reason is None else str(reason)
        lines.append(f"- {reason_text}: {count}")
    lines.extend(["", "Fault-injection families"])
    for name, status, stage in FAULT_MAPPING:
        lines.append(
            f"- {name}: count={fault_families.get(name, 0)}, target_status={status}, typical_terminal_stage={stage}"
        )
    lines.extend(
        [
            "",
            "Repository references",
            f"dataset: {repo_relative(paths['dataset'], REPO_ROOT)}",
            f"dataset manifest: {repo_relative(paths['dataset_manifest'], REPO_ROOT)}",
            f"integrity service: {repo_relative(paths['integrity_service'], REPO_ROOT)}",
        ]
    )
    return "\n".join(lines)


def build_or5_pdf_text(paths: dict[str, Path]) -> str:
    lines = [
        "Purpose",
        "This document records an anonymized repository map and regeneration guide for the supplementary package and the manuscript-facing artifacts.",
        "",
        "Repository map",
    ]
    mappings = [
        ("Frozen benchmark dataset", f"repository_root/{repo_relative(paths['dataset'], REPO_ROOT)}"),
        ("Dataset manifest", f"repository_root/{repo_relative(paths['dataset_manifest'], REPO_ROOT)}"),
        ("Integrated benchmark results", f"repository_root/{repo_relative(paths['integrated_results'], REPO_ROOT)}"),
        ("Unified benchmark policy", f"repository_root/{repo_relative(paths['policy'], REPO_ROOT)}"),
        ("Baseline summary table", f"repository_root/{repo_relative(paths['baseline_summary'], REPO_ROOT)}"),
        ("Independent validation subset", f"repository_root/{repo_relative(paths['independent_validation'], REPO_ROOT)}"),
        ("Robot direct-execution evidence", f"repository_root/{repo_relative(paths['robot_execution_evidence'], REPO_ROOT)}"),
        ("Figure-generation script", f"manuscript_root/{repo_relative(paths['figure_script'], MANUSCRIPT_DIR)}"),
        ("Manuscript source", f"manuscript_root/{repo_relative(paths['manuscript'], MANUSCRIPT_DIR)}"),
    ]
    for label, path in mappings:
        lines.append(f"- {label}: {path}")
    lines.extend(
        [
            "",
            "Manuscript artifact map",
            "- Section 4 provenance and normalization <- frozen dataset release, dataset manifest, and unified benchmark policy.",
            "- Table 4 integrated benchmark composition <- dataset manifest and frozen release.",
            "- Figure 3 integrated outcome distribution <- integrated benchmark results and figure-generation script.",
            "- Table 8 and Figure 4 baseline comparison <- baseline summary CSV, baseline asset breakdown CSV, and figure-generation script.",
            "- Section 7.4 independent validation subset <- independent_validation_subset_latest.json.",
            "- Section 7.5 robot direct Isaac evidence <- robot_execution_evidence_latest.json.",
            "- Figure 5 terminal-stage distribution and evidence completeness <- integrated benchmark results.",
            "- Figure 6 latency by asset family <- integrated benchmark results and figure-generation script.",
            "",
            "Regeneration notes",
            "- Online Resource 1 summarizes the frozen case schema, unified policy format, and integrity-hash construction.",
            "- Online Resource 2 is generated directly from the frozen 368-case release.",
            "- Online Resource 3 is generated from the integrated benchmark execution results and append-only evidence logs.",
            "- Online Resource 4 summarizes label freezing, fault families, and reason-code semantics from the frozen release.",
            "- Main manuscript figures are regenerated from manuscript_root/generate_pcag_paper_figures.py.",
        ]
    )
    return "\n".join(lines)


def build_readme(dataset_manifest: dict) -> str:
    release_id = dataset_manifest.get("release_id", "unknown_release")
    benchmark_version = dataset_manifest.get("benchmark_version", "unknown_version")
    return "\n".join(
        [
            "# PCAG IJAMT online resources",
            "",
            f"- Release ID: `{release_id}`",
            f"- Benchmark version: `{benchmark_version}`",
            "",
            "Generated artifacts:",
            "",
            "- Online_Resource_1_Benchmark_Schema_and_Integrity_Specification.pdf",
            "- Online_Resource_2_Frozen_368_Case_Manifest.csv",
            "- Online_Resource_2_Frozen_368_Case_Manifest.xlsx",
            "- Online_Resource_3_Sample_Evidence_Logs_and_Terminal_Stage_Traces.pdf",
            "- Online_Resource_3_Sample_Evidence_Logs_and_Terminal_Stage_Traces.csv",
            "- Online_Resource_4_Gateway_Final_Labeling_and_Fault_Specification.pdf",
            "- Online_Resource_5_Anonymized_Reproducibility_Manifest_and_Repository_Map.pdf",
            "- Online_Resource_5_Anonymized_Reproducibility_Manifest_and_Repository_Map.md",
            "",
            "The PDFs are paper-facing summaries. The CSV/XLSX/MD files preserve the machine-readable benchmark structure and repository map used during review.",
        ]
    ) + "\n"


def compile_tex(tex_path: Path) -> bool:
    candidates = [
        "pdflatex",
        r"C:\Users\choiLee\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\texlive\2025\bin\windows\pdflatex.exe",
        r"C:\texlive\2024\bin\windows\pdflatex.exe",
    ]
    latex_cmd = None
    for candidate in candidates:
        if candidate == "pdflatex":
            resolved = shutil.which(candidate)
            if resolved:
                latex_cmd = resolved
                break
        elif Path(candidate).exists():
            latex_cmd = candidate
            break
    if latex_cmd is None:
        return False
    try:
        subprocess.run(
            [latex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tex_path.parent,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return True
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdflatex failed for {tex_path.name}\n{exc.stdout}") from exc


def cleanup_tex_artifacts(tex_path: Path) -> None:
    for suffix in [".aux", ".log", ".out", ".synctex.gz"]:
        artifact = tex_path.with_suffix(suffix)
        if artifact.exists():
            artifact.unlink()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    paths = build_paths()
    dataset = load_json(paths["dataset"])
    dataset_manifest = load_json(paths["dataset_manifest"])
    integrated_results = load_json(paths["integrated_results"])
    policy = load_json(paths["policy"])

    manifest_rows = flatten_manifest_rows(dataset)
    manifest_csv = OUTPUT_DIR / "Online_Resource_2_Frozen_368_Case_Manifest.csv"
    manifest_xlsx = OUTPUT_DIR / "Online_Resource_2_Frozen_368_Case_Manifest.xlsx"
    write_csv(manifest_csv, manifest_rows)
    write_xlsx(manifest_xlsx, manifest_rows, "frozen_manifest")

    sample_cases = select_sample_cases(integrated_results)
    evidence_rows = flatten_evidence_rows(sample_cases)
    evidence_csv = OUTPUT_DIR / "Online_Resource_3_Sample_Evidence_Logs_and_Terminal_Stage_Traces.csv"
    write_csv(evidence_csv, evidence_rows)

    or1_tex = OUTPUT_DIR / "Online_Resource_1_Benchmark_Schema_and_Integrity_Specification.tex"
    or3_tex = OUTPUT_DIR / "Online_Resource_3_Sample_Evidence_Logs_and_Terminal_Stage_Traces.tex"
    or4_tex = OUTPUT_DIR / "Online_Resource_4_Gateway_Final_Labeling_and_Fault_Specification.tex"
    or5_tex = OUTPUT_DIR / "Online_Resource_5_Anonymized_Reproducibility_Manifest_and_Repository_Map.tex"
    or5_md = OUTPUT_DIR / "Online_Resource_5_Anonymized_Reproducibility_Manifest_and_Repository_Map.md"

    write_text(or1_tex, build_or1_tex(dataset, policy, paths))
    write_text(or3_tex, build_or3_tex(sample_cases, evidence_csv.name))
    write_text(or4_tex, build_or4_tex(dataset, paths))
    write_text(or5_tex, build_or5_tex(paths))
    write_text(or5_md, build_or5_md(paths))
    write_text(OUTPUT_DIR / "README.md", build_readme(dataset_manifest))

    compiled = compile_tex(or1_tex)
    if not compiled:
        write_simple_pdf(
            or1_tex.with_suffix(".pdf"),
            "Online Resource 1: Benchmark schema, policy format, and integrity-hash construction",
            build_or1_pdf_text(dataset, policy, paths),
        )
        write_simple_pdf(
            or3_tex.with_suffix(".pdf"),
            "Online Resource 3: Sample evidence logs and terminal-stage traces",
            build_or3_pdf_text(sample_cases, evidence_csv.name),
        )
        write_simple_pdf(
            or4_tex.with_suffix(".pdf"),
            "Online Resource 4: Gateway-final labeling, fault-injection, and reason-code specification",
            build_or4_pdf_text(dataset, paths),
        )
        write_simple_pdf(
            or5_tex.with_suffix(".pdf"),
            "Online Resource 5: Anonymized reproducibility manifest and repository map",
            build_or5_pdf_text(paths),
        )
    else:
        for tex_path in [or3_tex, or4_tex, or5_tex]:
            compile_tex(tex_path)

    for tex_path in [or1_tex, or3_tex, or4_tex, or5_tex]:
        cleanup_tex_artifacts(tex_path)

    generated = [
        manifest_csv.name,
        manifest_xlsx.name,
        evidence_csv.name,
        or1_tex.with_suffix(".pdf").name,
        or3_tex.with_suffix(".pdf").name,
        or4_tex.with_suffix(".pdf").name,
        or5_tex.with_suffix(".pdf").name,
        or5_md.name,
    ]
    print("Generated online resources:")
    for name in generated:
        print(f" - {name}")


if __name__ == "__main__":
    main()
