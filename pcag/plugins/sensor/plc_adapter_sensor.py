"""
Sensor source that delegates PLC reads to the central PLC adapter service.
"""

from __future__ import annotations

import logging

import httpx

from pcag.core.ports.sensor_source import ISensorSource
from pcag.core.utils.config_loader import get_service_urls

logger = logging.getLogger(__name__)


class PLCAdapterSensorSource(ISensorSource):
    def __init__(self) -> None:
        self._url = ""
        self._timeout = 10.0

    def initialize(self, config: dict) -> None:
        service_url = config.get("plc_adapter_url") or get_service_urls().get("plc_adapter")
        if not service_url:
            raise RuntimeError("PLC adapter URL not configured in services.yaml")
        self._url = service_url.rstrip("/")
        self._timeout = float(config.get("timeout_s", 10.0))
        logger.info("PLCAdapterSensorSource initialized | url=%s timeout_s=%s", self._url, self._timeout)

    def read_snapshot(self, asset_id: str) -> dict:
        response = httpx.get(f"{self._url}/v1/assets/{asset_id}/snapshots/latest", timeout=self._timeout)
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                detail = f"HTTP {response.status_code}"
            raise RuntimeError(detail)
        return response.json()["sensor_snapshot"]

    def shutdown(self) -> None:
        return None
