import logging
import sys
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional
import contextvars

from pcag.core.utils.config_loader import load_config

# Context variable for request ID to be used across the request lifecycle
request_id_ctx = contextvars.ContextVar("request_id", default="-")
service_name_ctx = contextvars.ContextVar("service_name", default="Service")

class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs logs in the specified structured format:
    YYYY-MM-DD HH:MM:SS [LEVEL] [Service] [req-ID] Message | extra_fields
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        
        # Get context values
        req_id = request_id_ctx.get()
        service = service_name_ctx.get()
        
        # Format the base message
        log_msg = f"{timestamp} [{level}] [{service}] [{req_id}] {record.getMessage()}"
        
        # Add extra fields if present (passed via extra={'extra_fields': {...}})
        if hasattr(record, 'extra_fields') and isinstance(record.extra_fields, dict):
            extra_str = " | ".join([f"{k}={v}" for k, v in record.extra_fields.items()])
            if extra_str:
                log_msg += f" | {extra_str}"
                
        return log_msg

def setup_logging(service_name: str):
    """
    Sets up the logging configuration for the service.
    Reads configuration from config/services.yaml.
    """
    # Set service name in context
    service_name_ctx.set(service_name)
    
    # Load config
    config = load_config("services.yaml")
    log_config = config.get("logging", {})
    
    level_str = log_config.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)
    
    # File Handler (optional)
    log_file = log_config.get("log_file")
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
