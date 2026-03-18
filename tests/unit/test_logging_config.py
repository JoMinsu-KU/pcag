import logging

from pcag.core.middleware.logging_middleware import LoggingMiddleware
from pcag.core.utils.logging_config import (
    HumanReadableFormatter,
    asset_id_ctx,
    request_id_ctx,
    service_name_ctx,
    transaction_id_ctx,
)


def test_human_formatter_includes_context_module_and_source():
    req_token = request_id_ctx.set("req-123")
    svc_token = service_name_ctx.set("gateway-core")
    tx_token = transaction_id_ctx.set("tx-001")
    asset_token = asset_id_ctx.set("reactor_01")

    try:
        formatter = HumanReadableFormatter(use_color=False, include_module=True, source_levels={"ERROR"})
        record = logging.LogRecord(
            name="pcag.apps.gateway.routes",
            level=logging.ERROR,
            pathname=__file__,
            lineno=42,
            msg="Commit failed",
            args=(),
            exc_info=None,
            func="test_func",
        )
        record.extra_fields = {"phase": "commit", "reason_code": "COMMIT_FAILED"}
        line = formatter.format(record)
    finally:
        request_id_ctx.reset(req_token)
        service_name_ctx.reset(svc_token)
        transaction_id_ctx.reset(tx_token)
        asset_id_ctx.reset(asset_token)

    assert "gateway-core" in line
    assert "req=req-123" in line
    assert "tx=tx-001" in line
    assert "asset=reactor_01" in line
    assert "mod=pcag.apps.gateway.routes" in line
    assert "src=test_logging_config.py:42" in line
    assert "fn=test_func" in line
    assert "phase=commit" in line
    assert "reason_code=COMMIT_FAILED" in line


def test_human_formatter_applies_info_color_when_enabled():
    formatter = HumanReadableFormatter(use_color=True, include_module=False, source_levels=set())
    record = logging.LogRecord(
        name="pcag.apps.gateway.routes",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Gateway started",
        args=(),
        exc_info=None,
        func="test_func",
    )

    line = formatter.format(record)
    assert line.startswith("\033[32m")
    assert line.endswith("\033[0m")


def test_logging_middleware_summarizes_request_without_full_body():
    middleware = LoggingMiddleware(app=lambda scope, receive, send: None)
    summary = middleware._summarize_request(
        {
            "transaction_id": "tx-001",
            "asset_id": "reactor_01",
            "proof_package": {
                "policy_version_id": "v2025-03-06",
                "sensor_snapshot_hash": "a" * 64,
                "action_sequence": [{"action_type": "set_heater_output", "params": {"value": 60}}],
            },
        },
        include_body=False,
    )

    assert summary["request_tx"] == "tx-001"
    assert summary["request_asset"] == "reactor_01"
    assert summary["policy_version"] == "v2025-03-06"
    assert summary["action_count"] == 1
    assert "request_body" not in summary
