"""
Executor that delegates PLC writes to the central PLC adapter service.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from pcag.core.ports.executor import IExecutor
from pcag.core.utils.config_loader import get_service_urls

logger = logging.getLogger(__name__)


class PLCAdapterExecutor(IExecutor):
    def __init__(self) -> None:
        self._url = ""
        self._timeout = 10.0
        self.last_error: str | None = None

    def initialize(self, config: dict[str, Any]) -> None:
        service_url = config.get("plc_adapter_url") or get_service_urls().get("plc_adapter")
        if not service_url:
            raise RuntimeError("PLC adapter URL not configured in services.yaml")
        self._url = service_url.rstrip("/")
        self._timeout = float(config.get("timeout_s", 10.0))
        logger.info("PLCAdapterExecutor initialized | url=%s timeout_s=%s", self._url, self._timeout)

    def execute(self, transaction_id: str, asset_id: str, action_sequence: list[dict[str, Any]]) -> bool:
        self.last_error = None
        revision = os.environ.get("PCAG_REVISION_MODE", "").lower() == "true"
        response = httpx.post(
            f"{self._url}/v1/revision/execute" if revision else f"{self._url}/v1/execute",
            json={
                "transaction_id": transaction_id,
                "asset_id": asset_id,
                "action_sequence": action_sequence,
            },
            timeout=self._timeout,
            headers={"X-API-Key": os.environ.get("PCAG_API_KEY_1", "pcag-agent-key-001")},
        )
        if response.status_code != 200:
            if revision:
                # A server error may follow an accepted write or a lost durable
                # receipt. Propagate ambiguity so OT retains UNKNOWN quarantine.
                response.raise_for_status()
            try:
                detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                detail = f"HTTP {response.status_code}"
            self.last_error = detail
            return False
        payload = response.json()
        if revision:
            return payload
        if payload.get("success"):
            return True
        self.last_error = payload.get("reason") or "PLC adapter execution failed"
        return False

    def query_operation(self, *, transaction_id: str, asset_id: str):
        response = httpx.get(f"{self._url}/v1/revision/operation", params={"transaction_id": transaction_id, "asset_id": asset_id}, headers={"X-API-Key": os.environ.get("PCAG_API_KEY_1", "pcag-agent-key-001")}, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def safe_state(self, asset_id: str) -> bool:
        self.last_error = None
        response = httpx.post(
            f"{self._url}/v1/safe-state",
            json={"asset_id": asset_id},
            timeout=self._timeout,
        )
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                detail = f"HTTP {response.status_code}"
            self.last_error = detail
            return False
        payload = response.json()
        if payload.get("success"):
            return True
        self.last_error = payload.get("reason") or "PLC adapter safe state failed"
        return False

    def shutdown(self) -> None:
        return None
