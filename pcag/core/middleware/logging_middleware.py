import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from starlette.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from pcag.core.utils.config_loader import load_config
from pcag.core.utils.logging_config import asset_id_ctx, request_id_ctx, transaction_id_ctx

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        config = load_config("services.yaml")
        log_config = config.get("logging", {})
        mask_fields = log_config.get("mask_fields", ["api_key", "X-API-Key"])
        body_logging_enabled = bool(log_config.get("log_request_body", False))
        response_logging_enabled = bool(log_config.get("log_response_body", False))

        request_token = request_id_ctx.set(request_id)
        tx_token = transaction_id_ctx.set("-")
        asset_token = asset_id_ctx.set("-")

        request_body_json = None
        request_summary = {"content_type": request.headers.get("content-type", "-")}

        try:
            body_bytes = b""
            if self._should_capture_request_body(request):
                body_bytes = await request.body()

            request_body_json = self._parse_json_body(body_bytes)
            if request_body_json is not None:
                self._mask_sensitive_data(request_body_json, mask_fields)
                extracted_tx = self._extract_first(request_body_json, "transaction_id")
                extracted_asset = self._extract_first(request_body_json, "asset_id")
                if extracted_tx:
                    transaction_id_ctx.set(str(extracted_tx))
                if extracted_asset:
                    asset_id_ctx.set(str(extracted_asset))
                request_summary.update(self._summarize_request(request_body_json, include_body=body_logging_enabled))
            else:
                request_summary.update(self._summarize_text_body(body_bytes, include_body=body_logging_enabled))

            logger.info(
                f"HTTP {request.method} {request.url.path} started",
                extra={
                    "extra_fields": {
                        "client": request.client.host if request.client else "unknown",
                        "query": str(request.query_params) or "-",
                        **request_summary,
                    }
                },
            )

            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.exception(
                f"HTTP {request.method} {request.url.path} raised exception",
                extra={"extra_fields": {"duration_ms": duration_ms, "error": str(exc)}},
            )
            raise

        try:
            response_summary = {}
            content_type = response.headers.get("content-type", "")
            if self._should_capture_response_body(response, content_type):
                response_body = b""
                try:
                    async for chunk in response.body_iterator:
                        response_body += chunk
                    response.body_iterator = iterate_in_threadpool(iter([response_body]))

                    parsed_response = self._parse_json_body(response_body)
                    if parsed_response is not None:
                        self._mask_sensitive_data(parsed_response, mask_fields)
                        response_summary = self._summarize_response(parsed_response, include_body=response_logging_enabled)
                    else:
                        response_summary = self._summarize_text_body(response_body, include_body=response_logging_enabled)
                except Exception as exc:
                    response_summary = {"response_summary": f"[response_read_error:{exc}]"}

            duration_ms = round((time.time() - start_time) * 1000, 2)
            response_level = self._response_log_level(response.status_code)
            response_logger = getattr(logger, response_level)
            response_logger(
                f"HTTP {request.method} {request.url.path} completed",
                extra={
                    "extra_fields": {
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                        **response_summary,
                    }
                },
            )
            return response
        finally:
            request_id_ctx.reset(request_token)
            transaction_id_ctx.reset(tx_token)
            asset_id_ctx.reset(asset_token)

    def _should_capture_request_body(self, request: Request) -> bool:
        # SSE나 일반 GET/HEAD 요청은 body를 재주입하지 않아야 disconnect 채널을 오염시키지 않습니다.
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return False

        accept = (request.headers.get("accept") or "").lower()
        if "text/event-stream" in accept:
            return False

        return True

    def _should_capture_response_body(self, response: Response, content_type: str) -> bool:
        if isinstance(response, StreamingResponse):
            return False
        lowered = (content_type or "").lower()
        if "text/event-stream" in lowered:
            return False
        return "application/json" in lowered or "text/" in lowered

    def _parse_json_body(self, body_bytes: bytes) -> dict | list | None:
        if not body_bytes:
            return None
        try:
            return json.loads(body_bytes)
        except Exception:
            return None

    def _extract_first(self, payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            if key in payload:
                return payload[key]
            for value in payload.values():
                extracted = self._extract_first(value, key)
                if extracted is not None:
                    return extracted
        elif isinstance(payload, list):
            for item in payload:
                extracted = self._extract_first(item, key)
                if extracted is not None:
                    return extracted
        return None

    def _summarize_request(self, payload: Any, *, include_body: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"request_keys": self._describe_keys(payload)}

        summary: dict[str, Any] = {"request_keys": self._describe_keys(payload)}
        if "transaction_id" in payload:
            summary["request_tx"] = payload["transaction_id"]
        if "asset_id" in payload:
            summary["request_asset"] = payload["asset_id"]

        proof = payload.get("proof_package")
        if isinstance(proof, dict):
            summary["policy_version"] = proof.get("policy_version_id", "-")
            action_sequence = proof.get("action_sequence") or []
            summary["action_count"] = len(action_sequence) if isinstance(action_sequence, list) else "-"
            if proof.get("sensor_snapshot_hash"):
                summary["sensor_hash"] = f"{str(proof['sensor_snapshot_hash'])[:10]}..."

        if include_body:
            summary["request_body"] = self._compact(payload)
        return summary

    def _summarize_response(self, payload: Any, *, include_body: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"response_keys": self._describe_keys(payload)}

        summary: dict[str, Any] = {"response_keys": self._describe_keys(payload)}
        for field in ("status", "reason_code", "final_verdict", "evidence_ref"):
            if field in payload:
                summary[field] = payload[field]

        detail = payload.get("detail")
        if isinstance(detail, list):
            summary["detail"] = f"list[{len(detail)}]"
        elif detail is not None:
            summary["detail"] = detail

        if include_body:
            summary["response_body"] = self._compact(payload)
        return summary

    def _summarize_text_body(self, body_bytes: bytes, *, include_body: bool) -> dict[str, Any]:
        if not body_bytes:
            return {"body_size": 0}
        body_text = body_bytes.decode("utf-8", errors="replace")
        summary = {"body_size": len(body_bytes)}
        if include_body:
            summary["body_preview"] = body_text[:160]
        return summary

    def _describe_keys(self, payload: Any) -> str:
        if isinstance(payload, dict):
            return ",".join(list(payload.keys())[:8]) or "-"
        if isinstance(payload, list):
            return f"list[{len(payload)}]"
        return type(payload).__name__

    def _compact(self, payload: Any) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:240]
        except Exception:
            return str(payload)[:240]

    def _response_log_level(self, status_code: int) -> str:
        if status_code >= 500:
            return "error"
        if status_code >= 400:
            return "warning"
        return "info"

    def _mask_sensitive_data(self, data: Any, mask_fields: list[str]):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in mask_fields:
                    data[key] = "***MASKED***"
                else:
                    self._mask_sensitive_data(value, mask_fields)
        elif isinstance(data, list):
            for item in data:
                self._mask_sensitive_data(item, mask_fields)
