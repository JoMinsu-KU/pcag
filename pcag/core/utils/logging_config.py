import contextvars
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from pcag.core.utils.config_loader import load_config


request_id_ctx = contextvars.ContextVar("request_id", default="-")
service_name_ctx = contextvars.ContextVar("service_name", default="")
transaction_id_ctx = contextvars.ContextVar("transaction_id", default="-")
asset_id_ctx = contextvars.ContextVar("asset_id", default="-")
default_service_name = "service"


RESET = "\033[0m"
LEVEL_COLORS = {
    "DEBUG": "\033[33m",
    "INFO": "\033[32m",
    "WARNING": "\033[31m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[97;41m",
}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "always"}
    return bool(value)


def _normalize_level_set(levels: list[str] | None, default: set[str]) -> set[str]:
    if not levels:
        return default
    return {str(level).upper() for level in levels}


def _supports_color(mode: str) -> bool:
    normalized = (mode or "auto").strip().lower()
    if normalized == "always":
        return True
    if normalized == "never":
        return False

    stream = getattr(sys.stdout, "isatty", None)
    return bool(stream and stream())


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


class HumanReadableFormatter(logging.Formatter):
    """Readable console formatter with optional color and source metadata."""

    def __init__(self, *, use_color: bool, include_module: bool, source_levels: set[str]):
        super().__init__()
        self.use_color = use_color
        self.include_module = include_module
        self.source_levels = source_levels

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.upper()
        service = service_name_ctx.get() or default_service_name
        request_id = request_id_ctx.get()
        transaction_id = transaction_id_ctx.get()
        asset_id = asset_id_ctx.get()

        parts = [
            timestamp,
            level.ljust(8),
            service.ljust(14),
            f"req={request_id}",
        ]

        if transaction_id != "-":
            parts.append(f"tx={transaction_id}")
        if asset_id != "-":
            parts.append(f"asset={asset_id}")
        if self.include_module:
            parts.append(f"mod={record.name}")
        if level in self.source_levels:
            parts.append(f"src={record.filename}:{record.lineno}")
            parts.append(f"fn={record.funcName}")

        message = " ".join(parts) + f" | {record.getMessage()}"

        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict) and record.extra_fields:
            extra_pairs = [f"{key}={_format_value(value)}" for key, value in record.extra_fields.items()]
            message += " | " + " ".join(extra_pairs)

        if self.use_color:
            color = LEVEL_COLORS.get(level, "")
            if color:
                return f"{color}{message}{RESET}"
        return message


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for log shipping."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname.upper(),
            "service": service_name_ctx.get() or default_service_name,
            "request_id": request_id_ctx.get(),
            "transaction_id": transaction_id_ctx.get(),
            "asset_id": asset_id_ctx.get(),
            "module": record.name,
            "source": f"{record.filename}:{record.lineno}",
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict) and record.extra_fields:
            payload["extra"] = record.extra_fields
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(service_name: str):
    """Configure root logging using the shared logging section in services.yaml."""

    global default_service_name
    default_service_name = service_name
    service_name_ctx.set(service_name)

    config = load_config("services.yaml")
    log_config = config.get("logging", {})
    level_name = str(log_config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter_type = str(log_config.get("format", "human")).lower()
    include_module = _as_bool(log_config.get("include_module", True), True)
    source_levels = _normalize_level_set(
        log_config.get("include_source_levels"),
        default={"DEBUG", "WARNING", "ERROR", "CRITICAL"},
    )
    color_mode = str(log_config.get("console_color", "auto"))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []

    if formatter_type == "json":
        console_formatter: logging.Formatter = JsonFormatter()
        file_formatter: logging.Formatter = JsonFormatter()
    else:
        console_formatter = HumanReadableFormatter(
            use_color=_supports_color(color_mode),
            include_module=include_module,
            source_levels=source_levels,
        )
        file_formatter = HumanReadableFormatter(
            use_color=False,
            include_module=include_module,
            source_levels=source_levels,
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    log_file = log_config.get("log_file")
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
