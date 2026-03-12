import time
import uuid
import json
import logging
import contextvars
from typing import Callable, Awaitable, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from starlette.concurrency import iterate_in_threadpool

from pcag.core.utils.logging_config import request_id_ctx, load_config

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.time()
        
        # 1. Generate Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_ctx.set(request_id)
        
        # 2. Load Config for logging rules
        config = load_config("services.yaml")
        log_config = config.get("logging", {})
        max_body_size = log_config.get("max_body_log_size", 500)
        mask_fields = log_config.get("mask_fields", ["api_key", "X-API-Key"])
        
        # 3. Capture Request Body
        request_body_str = ""
        try:
            # We need to read the body, but it consumes the stream.
            # So we read it, then replace the receive method.
            body_bytes = await request.body()
            
            # Re-inject body for the next handler
            async def receive() -> Message:
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
            
            if body_bytes:
                try:
                    # Attempt to parse JSON for structured logging
                    body_json = json.loads(body_bytes)
                    # Mask fields
                    self._mask_sensitive_data(body_json, mask_fields)
                    request_body_str = json.dumps(body_json)
                except json.JSONDecodeError:
                    request_body_str = body_bytes.decode("utf-8", errors="replace")
                
                # Truncate
                if len(request_body_str) > max_body_size:
                    request_body_str = request_body_str[:max_body_size] + "...[TRUNCATED]"
        except Exception:
            request_body_str = "[Error reading body]"

        # 4. Log Request
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"--> {request.method} {request.url.path}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "client": client_host,
                    "body": request_body_str
                }
            }
        )
        
        # 5. Process Request
        response = await call_next(request)
        
        # 6. Capture Response Body
        response_body_str = ""
        response_body = b""
        
        # Only capture text/json responses to avoid binary data issues
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or "text/" in content_type:
            try:
                # Read response body
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                # Re-construct response body iterator
                response.body_iterator = iterate_in_threadpool(iter([response_body]))
                
                try:
                    body_json = json.loads(response_body)
                    self._mask_sensitive_data(body_json, mask_fields)
                    response_body_str = json.dumps(body_json)
                except:
                    response_body_str = response_body.decode("utf-8", errors="replace")
                
                if len(response_body_str) > max_body_size:
                    response_body_str = response_body_str[:max_body_size] + "...[TRUNCATED]"
            except Exception:
                response_body_str = "[Error reading response]"

        # 7. Log Response
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"<-- {response.status_code} {response.headers.get('content-type', 'unknown')}",
            extra={
                "extra_fields": {
                    "status": response.status_code,
                    "duration_ms": f"{duration_ms:.2f}ms",
                    "response": response_body_str
                }
            }
        )
        
        # Reset context
        request_id_ctx.reset(token)
        
        return response

    def _mask_sensitive_data(self, data: Any, mask_fields: list):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in mask_fields:
                    data[key] = "***MASKED***"
                else:
                    self._mask_sensitive_data(value, mask_fields)
        elif isinstance(data, list):
            for item in data:
                self._mask_sensitive_data(item, mask_fields)
