"""Real-time monitoring data service for the PCAG dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from pcag.core.database.engine import SessionLocal
from pcag.core.utils.config_loader import get_sensor_mappings, get_service_urls, load_config

logger = logging.getLogger(__name__)


FINAL_STAGE_TO_STATUS = {
    "COMMIT_ACK": "COMMITTED",
    "SAFETY_UNSAFE": "UNSAFE",
    "INTEGRITY_REJECTED": "REJECTED",
    "PREPARE_LOCK_DENIED": "ABORTED",
    "REVERIFY_FAILED": "ABORTED",
    "COMMIT_TIMEOUT": "ABORTED",
    "COMMIT_FAILED": "ERROR",
    "ABORTED": "ABORTED",
    "ESTOP_TRIGGERED": "ABORTED",
}

DEFAULT_PROBE_PATHS = {
    "gateway": "/openapi.json",
    "policy_store": "/openapi.json",
    "sensor_gateway": "/openapi.json",
    "safety_cluster": "/openapi.json",
    "ot_interface": "/openapi.json",
    "evidence_ledger": "/openapi.json",
    "policy_admin": "/v1/admin/health",
    "plc_adapter": "/v1/health",
    "dashboard": "/v1/health",
}


def _safe_json_load(raw: str | dict | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _iso_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%H:%M:%S")
        except Exception:
            return value
    return str(value)


def _coerce_latency_ms(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _summarize_snapshot_fields(snapshot: dict[str, Any], *, limit: int = 6) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for key, value in list(snapshot.items())[:limit]:
        if isinstance(value, float):
            rendered = f"{value:.3f}"
        elif isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            rendered = str(value)
        fields.append({"name": key, "value": rendered})
    return fields


class DashboardMonitor:
    """Collects live service state, DB metrics, and log summaries for the dashboard."""

    def __init__(self) -> None:
        config = load_config("services.yaml", required=True)
        dashboard_config = config.get("dashboard", {})
        self._service_urls = get_service_urls()
        self._sensor_config = get_sensor_mappings()
        self._dashboard_config = dashboard_config
        self.refresh_ms = int(dashboard_config.get("refresh_ms", 2000))
        self.window_minutes = int(dashboard_config.get("window_minutes", 30))
        self.max_transactions = int(dashboard_config.get("max_transactions", 18))
        self.max_assets = int(dashboard_config.get("max_assets", 8))
        self.log_tail_lines = int(dashboard_config.get("log_tail_lines", 120))
        self._probe_paths = {**DEFAULT_PROBE_PATHS, **dashboard_config.get("probe_paths", {})}
        log_file = dashboard_config.get("log_file") or config.get("logging", {}).get("log_file") or "logs/pcag.log"
        self._log_file = Path(log_file)
        self._service_history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=180))
        self._collection_lock = asyncio.Lock()
        self._last_collection_duration_ms = 0.0
        self._started_at_ms = int(time.time() * 1000)

    async def build_snapshot(self) -> dict[str, Any]:
        async with self._collection_lock:
            started = time.perf_counter()

            db_metrics = self._query_db_metrics()
            services = await self._probe_services()
            policy_summary = db_metrics["policy"]
            plc_health = await self._fetch_plc_health()
            assets = await self._fetch_asset_snapshots(policy_summary)
            logs = self._tail_logs()
            evaluation = self._load_evaluation_summary()

            generated_at_ms = int(time.time() * 1000)
            self._last_collection_duration_ms = (time.perf_counter() - started) * 1000
            self._record_service_sample("dashboard", "healthy", self._last_collection_duration_ms, generated_at_ms)
            db_metrics["overview"]["collection_latency_ms"] = _coerce_latency_ms(self._last_collection_duration_ms)

            services = [
                *services,
                {
                    "name": "dashboard",
                    "url": self._service_urls.get("dashboard", ""),
                    "probe_path": "/v1/health",
                    "status": "healthy",
                    "status_code": 200,
                    "latency_ms": _coerce_latency_ms(self._last_collection_duration_ms),
                    "last_error": None,
                    "updated_at_ms": generated_at_ms,
                },
            ]

            return {
                "generated_at_ms": generated_at_ms,
                "generated_at": datetime.fromtimestamp(generated_at_ms / 1000).isoformat(timespec="seconds"),
                "refresh_ms": self.refresh_ms,
                "window_minutes": self.window_minutes,
                "overview": db_metrics["overview"],
                "services": services,
                "service_history": self._serialize_service_history(),
                "policy": policy_summary,
                "pipeline": db_metrics["pipeline"],
                "transactions": db_metrics["transactions"],
                "safety": db_metrics["safety"],
                "locks": db_metrics["locks"],
                "plc": plc_health,
                "assets": assets,
                "logs": logs,
                "evaluation": evaluation,
            }

    async def _probe_services(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            tasks = [
                self._probe_service(client, name, url)
                for name, url in self._service_urls.items()
                if name != "dashboard"
            ]
            results = await asyncio.gather(*tasks)
        return sorted(results, key=lambda item: item["name"])

    async def _probe_service(self, client: httpx.AsyncClient, name: str, base_url: str) -> dict[str, Any]:
        probe_path = self._probe_paths.get(name, "/openapi.json")
        started = time.perf_counter()
        now_ms = int(time.time() * 1000)
        try:
            response = await client.get(f"{base_url}{probe_path}")
            latency_ms = (time.perf_counter() - started) * 1000
            status_code = response.status_code
            if status_code >= 500:
                status = "unhealthy"
                last_error = f"HTTP {status_code}"
            elif status_code >= 400:
                status = "degraded"
                last_error = f"HTTP {status_code}"
            else:
                status = "healthy"
                last_error = None
        except Exception as exc:
            latency_ms = None
            status_code = None
            status = "unreachable"
            last_error = str(exc)

        self._record_service_sample(name, status, latency_ms, now_ms)
        return {
            "name": name,
            "url": base_url,
            "probe_path": probe_path,
            "status": status,
            "status_code": status_code,
            "latency_ms": _coerce_latency_ms(latency_ms),
            "last_error": last_error,
            "updated_at_ms": now_ms,
        }

    def _record_service_sample(self, name: str, status: str, latency_ms: float | None, timestamp_ms: int) -> None:
        self._service_history[name].append(
            {
                "timestamp_ms": timestamp_ms,
                "label": datetime.fromtimestamp(timestamp_ms / 1000).strftime("%H:%M:%S"),
                "latency_ms": _coerce_latency_ms(latency_ms),
                "status": status,
            }
        )

    def _serialize_service_history(self) -> dict[str, list[dict[str, Any]]]:
        return {name: list(history) for name, history in self._service_history.items()}

    def _query_db_metrics(self) -> dict[str, Any]:
        current_time_ms = int(time.time() * 1000)
        with SessionLocal() as session:
            overview = session.execute(
                text(
                    """
                    SELECT
                        (SELECT policy_version_id FROM policies WHERE is_active = TRUE LIMIT 1) AS active_policy_version,
                        (SELECT document FROM policies WHERE is_active = TRUE LIMIT 1) AS active_policy_document,
                        (SELECT COUNT(*) FROM policies) AS policy_version_count,
                        (SELECT COUNT(*) FROM evidence_events) AS evidence_event_count,
                        (SELECT COUNT(*) FROM transactions) AS transaction_count,
                        (
                            SELECT COUNT(*)
                            FROM transactions
                            WHERE status = 'LOCKED'
                              AND COALESCE(lock_expires_at_ms, 0) > :current_time_ms
                        ) AS locked_count,
                        (SELECT COUNT(*) FROM transactions WHERE status = 'COMMITTED') AS committed_count,
                        (SELECT COUNT(*) FROM transactions WHERE status = 'ABORTED') AS aborted_count
                    """
                ),
                {"current_time_ms": current_time_ms},
            ).mappings().one()

            policy_document = _safe_json_load(overview["active_policy_document"])
            asset_profiles = policy_document.get("assets", {})

            transactions = session.execute(
                text(
                    f"""
                    WITH latest AS (
                        SELECT DISTINCT ON (transaction_id)
                            transaction_id,
                            stage,
                            created_at,
                            payload
                        FROM evidence_events
                        ORDER BY transaction_id, sequence_no DESC
                    ),
                    spans AS (
                        SELECT
                            transaction_id,
                            MIN(created_at) AS started_at,
                            MAX(created_at) AS ended_at,
                            COUNT(*) AS event_count
                        FROM evidence_events
                        GROUP BY transaction_id
                    )
                    SELECT
                        latest.transaction_id,
                        latest.stage AS latest_stage,
                        latest.created_at AS latest_created_at,
                        latest.payload AS latest_payload,
                        spans.started_at,
                        spans.ended_at,
                        spans.event_count,
                        transactions.asset_id,
                        transactions.status AS tx_status
                    FROM latest
                    JOIN spans ON spans.transaction_id = latest.transaction_id
                    LEFT JOIN transactions ON transactions.transaction_id = latest.transaction_id
                    ORDER BY latest.created_at DESC
                    LIMIT {self.max_transactions}
                    """
                )
            ).mappings().all()

            lock_rows = session.execute(
                text(
                    """
                    SELECT transaction_id, asset_id, status, lock_expires_at_ms, updated_at
                    FROM transactions
                    WHERE status = 'LOCKED'
                      AND COALESCE(lock_expires_at_ms, 0) > :current_time_ms
                    ORDER BY updated_at DESC
                    """
                ),
                {"current_time_ms": current_time_ms},
            ).mappings().all()

            outcome_rows = session.execute(
                text(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (transaction_id)
                            transaction_id,
                            stage,
                            created_at
                        FROM evidence_events
                        WHERE created_at >= now() - (:window_minutes * interval '1 minute')
                        ORDER BY transaction_id, sequence_no DESC
                    )
                    SELECT date_trunc('minute', created_at) AS bucket, stage, COUNT(*) AS count
                    FROM latest
                    GROUP BY bucket, stage
                    ORDER BY bucket ASC
                    """
                ),
                {"window_minutes": self.window_minutes},
            ).mappings().all()

            stage_rows = session.execute(
                text(
                    """
                    SELECT stage, COUNT(*) AS count
                    FROM evidence_events
                    WHERE created_at >= now() - (:window_minutes * interval '1 minute')
                    GROUP BY stage
                    ORDER BY count DESC
                    """
                ),
                {"window_minutes": self.window_minutes},
            ).mappings().all()

            safety_rows = session.execute(
                text(
                    """
                    SELECT stage, created_at, payload
                    FROM evidence_events
                    WHERE stage IN ('SAFETY_PASSED', 'SAFETY_UNSAFE')
                      AND created_at >= now() - (:window_minutes * interval '1 minute')
                    ORDER BY created_at DESC
                    LIMIT 120
                    """
                ),
                {"window_minutes": self.window_minutes},
            ).mappings().all()

        transaction_items = [self._normalize_transaction_row(row) for row in transactions]
        latest_outcome_counts = self._build_latest_outcome_counts(transaction_items)
        outcome_timeseries = self._build_outcome_timeseries(outcome_rows)
        safety_summary = self._build_safety_summary(safety_rows)

        policy_summary = {
            "active_policy_version": overview["active_policy_version"],
            "policy_version_count": int(overview["policy_version_count"] or 0),
            "asset_count": len(asset_profiles),
            "assets": [
                {
                    "asset_id": asset_id,
                    "sil_level": profile.get("sil_level"),
                    "consensus_mode": profile.get("consensus", {}).get("mode"),
                    "simulation_engine": profile.get("simulation", {}).get("engine"),
                    "sensor_source": profile.get("sensor_source"),
                    "ot_executor": profile.get("ot_executor"),
                }
                for asset_id, profile in asset_profiles.items()
            ],
            "document": policy_document,
        }

        overview_payload = {
            "active_policy_version": overview["active_policy_version"],
            "policy_version_count": int(overview["policy_version_count"] or 0),
            "evidence_event_count": int(overview["evidence_event_count"] or 0),
            "transaction_count": int(overview["transaction_count"] or 0),
            "locked_count": int(overview["locked_count"] or 0),
            "committed_count": int(overview["committed_count"] or 0),
            "aborted_count": int(overview["aborted_count"] or 0),
            "dashboard_uptime_s": round((int(time.time() * 1000) - self._started_at_ms) / 1000, 1),
            "collection_latency_ms": _coerce_latency_ms(self._last_collection_duration_ms),
        }

        return {
            "overview": overview_payload,
            "policy": policy_summary,
            "transactions": transaction_items,
            "locks": [self._normalize_lock_row(row) for row in lock_rows],
            "pipeline": {
                "outcome_timeseries": outcome_timeseries,
                "latest_outcome_counts": latest_outcome_counts,
                "stage_totals": [{"stage": row["stage"], "count": int(row["count"])} for row in stage_rows],
            },
            "safety": safety_summary,
        }

    def _normalize_transaction_row(self, row: dict[str, Any]) -> dict[str, Any]:
        latest_stage = row["latest_stage"]
        tx_status = row["tx_status"]
        final_status = self._map_transaction_status(latest_stage, tx_status)
        started_at = row["started_at"]
        ended_at = row["ended_at"]
        latest_payload = _safe_json_load(row["latest_payload"])
        duration_ms = None
        if isinstance(started_at, datetime) and isinstance(ended_at, datetime):
            duration_ms = round((ended_at - started_at).total_seconds() * 1000, 2)
        return {
            "transaction_id": row["transaction_id"],
            "asset_id": row["asset_id"] or self._infer_asset_from_transaction_id(row["transaction_id"]),
            "latest_stage": latest_stage,
            "final_status": final_status,
            "tx_status": tx_status,
            "started_at": started_at.isoformat(timespec="seconds") if isinstance(started_at, datetime) else str(started_at),
            "ended_at": ended_at.isoformat(timespec="seconds") if isinstance(ended_at, datetime) else str(ended_at),
            "latest_created_at": row["latest_created_at"].isoformat(timespec="seconds")
            if isinstance(row["latest_created_at"], datetime)
            else str(row["latest_created_at"]),
            "event_count": int(row["event_count"] or 0),
            "duration_ms": duration_ms,
            "reason_excerpt": self._extract_reason_excerpt(latest_stage, latest_payload),
            "evidence_ref": f"/v1/transactions/{row['transaction_id']}",
            "evidence_url": f"{self._service_urls.get('evidence_ledger', '')}/v1/transactions/{row['transaction_id']}",
        }

    def _normalize_lock_row(self, row: dict[str, Any]) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        lock_expires = row["lock_expires_at_ms"] or 0
        remaining_ms = max(lock_expires - now_ms, 0)
        return {
            "transaction_id": row["transaction_id"],
            "asset_id": row["asset_id"],
            "status": row["status"],
            "lock_expires_at_ms": lock_expires,
            "remaining_ms": remaining_ms,
            "updated_at": row["updated_at"].isoformat(timespec="seconds") if isinstance(row["updated_at"], datetime) else str(row["updated_at"]),
        }

    def _build_latest_outcome_counts(self, transactions: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"COMMITTED": 0, "UNSAFE": 0, "REJECTED": 0, "ABORTED": 0, "ERROR": 0, "IN_PROGRESS": 0}
        for item in transactions:
            counts[item["final_status"]] = counts.get(item["final_status"], 0) + 1
        return counts

    def _build_outcome_timeseries(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            label = _iso_label(row["bucket"])
            entry = buckets.setdefault(
                label,
                {"label": label, "COMMITTED": 0, "UNSAFE": 0, "REJECTED": 0, "ABORTED": 0, "ERROR": 0, "IN_PROGRESS": 0},
            )
            status = self._map_transaction_status(row["stage"], None)
            entry[status] += int(row["count"] or 0)
        return list(buckets.values())

    def _build_safety_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        consensus_series: list[dict[str, Any]] = []
        unsafe_reason_counts: dict[str, int] = defaultdict(int)
        unsafe_validator_counts: dict[str, int] = defaultdict(int)

        for row in reversed(rows):
            payload = _safe_json_load(row["payload"])
            label = _iso_label(row["created_at"])
            if row["stage"] == "SAFETY_PASSED":
                score = payload.get("consensus", {}).get("score")
                if score is not None:
                    consensus_series.append({"label": label, "score": round(float(score), 3)})
            else:
                details = payload.get("details", {})
                validators = details.get("validators", {})
                for validator_name, verdict in validators.items():
                    if verdict.get("verdict") == "UNSAFE":
                        unsafe_validator_counts[validator_name] += 1

                rules_violations = validators.get("rules", {}).get("details", {}).get("violated_rules", [])
                if rules_violations:
                    for violation in rules_violations[:3]:
                        unsafe_reason_counts[violation.get("rule_id", "rule")] += 1
                elif validators.get("cbf", {}).get("verdict") == "UNSAFE":
                    unsafe_reason_counts["CBF_BARRIER"] += 1
                elif validators.get("simulation", {}).get("verdict") == "UNSAFE":
                    unsafe_reason_counts["SIMULATION_VIOLATION"] += 1
                else:
                    unsafe_reason_counts["CONSENSUS_THRESHOLD"] += 1

        return {
            "consensus_score_series": consensus_series[-50:],
            "unsafe_reason_counts": [
                {"label": label, "count": count}
                for label, count in sorted(unsafe_reason_counts.items(), key=lambda item: item[1], reverse=True)[:8]
            ],
            "unsafe_validator_counts": [
                {"label": label, "count": count}
                for label, count in sorted(unsafe_validator_counts.items(), key=lambda item: item[1], reverse=True)
            ],
        }

    async def _fetch_plc_health(self) -> dict[str, Any]:
        plc_url = self._service_urls.get("plc_adapter")
        if not plc_url:
            return {"status": "missing", "connections": [], "error": "plc_adapter URL missing"}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(f"{plc_url}/v1/health")
            payload = response.json() if response.status_code == 200 else {}
            payload["latency_ms"] = _coerce_latency_ms((time.perf_counter() - started) * 1000)
            payload["status_code"] = response.status_code
            return payload
        except Exception as exc:
            return {
                "status": "unreachable",
                "connections": [],
                "error": str(exc),
                "latency_ms": None,
                "status_code": None,
            }

    async def _fetch_asset_snapshots(self, policy_summary: dict[str, Any]) -> list[dict[str, Any]]:
        sensor_url = self._service_urls.get("sensor_gateway")
        if not sensor_url:
            return []

        active_assets = [item["asset_id"] for item in policy_summary.get("assets", [])]
        watched = self._dashboard_config.get("watched_assets") or active_assets
        asset_ids = watched[: self.max_assets]
        if not asset_ids:
            return []

        async with httpx.AsyncClient(timeout=4.0) as client:
            tasks = [self._fetch_asset_snapshot(client, sensor_url, asset_id) for asset_id in asset_ids]
            return await asyncio.gather(*tasks)

    async def _fetch_asset_snapshot(self, client: httpx.AsyncClient, sensor_url: str, asset_id: str) -> dict[str, Any]:
        source_hint = self._sensor_config.get("assets", {}).get(asset_id, {}).get("source", "unknown")
        started = time.perf_counter()
        try:
            response = await client.get(f"{sensor_url}/v1/assets/{asset_id}/snapshots/latest")
            latency_ms = (time.perf_counter() - started) * 1000
            if response.status_code != 200:
                return {
                    "asset_id": asset_id,
                    "status": "error",
                    "source_hint": source_hint,
                    "latency_ms": _coerce_latency_ms(latency_ms),
                    "error": f"HTTP {response.status_code}",
                }
            payload = response.json()
            snapshot = payload.get("sensor_snapshot", {})
            return {
                "asset_id": asset_id,
                "status": "healthy",
                "source_hint": source_hint,
                "latency_ms": _coerce_latency_ms(latency_ms),
                "timestamp_ms": payload.get("timestamp_ms"),
                "sensor_snapshot_hash": payload.get("sensor_snapshot_hash"),
                "sensor_reliability_index": payload.get("sensor_reliability_index"),
                "summary_fields": _summarize_snapshot_fields(snapshot),
                "field_count": len(snapshot),
            }
        except Exception as exc:
            return {
                "asset_id": asset_id,
                "status": "error",
                "source_hint": source_hint,
                "latency_ms": None,
                "error": str(exc),
            }

    def _tail_logs(self) -> list[dict[str, Any]]:
        if not self._log_file.exists():
            return []

        try:
            lines = deque(self._log_file.read_text(encoding="utf-8", errors="replace").splitlines(), maxlen=self.log_tail_lines)
        except Exception as exc:
            return [{"level": "ERROR", "service": "dashboard", "message": f"로그 파일을 읽지 못했습니다: {exc}"}]

        parsed: list[dict[str, Any]] = []
        for line in reversed(lines):
            parsed.append(self._parse_log_line(line))
        return parsed[:40]

    def _parse_log_line(self, line: str) -> dict[str, Any]:
        if " | " not in line:
            return {"level": "INFO", "service": "unknown", "message": line}

        prefix, message = line.split(" | ", 1)
        tokens = prefix.split()
        if len(tokens) < 4:
            return {"level": "INFO", "service": "unknown", "message": line}

        item: dict[str, Any] = {
            "timestamp": f"{tokens[0]} {tokens[1]}",
            "level": tokens[2],
            "service": tokens[3],
            "message": message,
        }
        for token in tokens[4:]:
            if "=" in token:
                key, value = token.split("=", 1)
                item[key] = value
        return item

    def _load_evaluation_summary(self) -> dict[str, Any]:
        results_dir = Path("tests/e2e/results")
        single_path = results_dir / "live_gateway_eval_latest.json"
        repeat_path = results_dir / "live_gateway_eval_repeat_latest.json"

        summary: dict[str, Any] = {"single": None, "repeat": None}

        if single_path.exists():
            try:
                single = json.loads(single_path.read_text(encoding="utf-8"))
                total = int(single.get("total", 0))
                passed = int(single.get("passed", 0))
                failed = int(single.get("failed", 0))
                summary["single"] = {
                    "generated_at_ms": single.get("generated_at_ms"),
                    "passed": passed,
                    "failed": failed,
                    "total": total,
                    "accuracy_pct": round((passed / total) * 100, 2) if total else None,
                }
            except Exception as exc:
                summary["single"] = {"error": str(exc)}

        if repeat_path.exists():
            try:
                repeat = json.loads(repeat_path.read_text(encoding="utf-8"))
                summary["repeat"] = {
                    "generated_at_ms": repeat.get("generated_at_ms"),
                    "runs": repeat.get("runs"),
                    "overall_accuracy_pct": repeat.get("overall_accuracy_pct"),
                    "loss_rate_pct": repeat.get("loss_rate_pct"),
                    "run_success_rate_pct": repeat.get("run_success_rate_pct"),
                    "flaky_cases": [
                        {
                            "case_id": item.get("case_id"),
                            "pass_rate_pct": item.get("pass_rate_pct"),
                            "loss_rate_pct": item.get("loss_rate_pct"),
                        }
                        for item in repeat.get("per_case", [])
                        if item.get("failed_runs", 0) > 0
                    ][:8],
                }
            except Exception as exc:
                summary["repeat"] = {"error": str(exc)}

        return summary

    def _map_transaction_status(self, latest_stage: str | None, tx_status: str | None) -> str:
        if tx_status == "COMMITTED":
            return "COMMITTED"
        if tx_status == "ABORTED":
            return "ABORTED"
        if tx_status == "LOCKED":
            return "IN_PROGRESS"
        if latest_stage in FINAL_STAGE_TO_STATUS:
            return FINAL_STAGE_TO_STATUS[latest_stage]
        return "IN_PROGRESS"

    def _extract_reason_excerpt(self, stage: str, payload: dict[str, Any]) -> str | None:
        if not payload:
            return None
        if "reason" in payload:
            return str(payload.get("reason"))
        if "error" in payload:
            return str(payload.get("error"))
        if stage == "SAFETY_UNSAFE":
            details = payload.get("details", {})
            validators = details.get("validators", {})
            rules = validators.get("rules", {}).get("details", {}).get("violated_rules", [])
            if rules:
                first = rules[0]
                return f"{first.get('rule_id')}: {first.get('reason')}"
            if validators.get("cbf", {}).get("verdict") == "UNSAFE":
                return "CBF barrier violation"
            if validators.get("simulation", {}).get("verdict") == "UNSAFE":
                return "Simulation violation"
        return None

    def _infer_asset_from_transaction_id(self, transaction_id: str) -> str | None:
        for asset_id in self._sensor_config.get("assets", {}).keys():
            prefix = asset_id.replace("_01", "")
            if prefix and prefix in transaction_id:
                return asset_id
        return None
