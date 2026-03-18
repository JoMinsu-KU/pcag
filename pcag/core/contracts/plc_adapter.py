"""
PLC adapter contracts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlcSnapshotResponse(BaseModel):
    asset_id: str
    timestamp_ms: int
    sensor_snapshot: dict[str, Any]
    source: str = "modbus"
    connection_key: str


class PlcExecuteRequest(BaseModel):
    transaction_id: str
    asset_id: str
    action_sequence: list[dict[str, Any]]


class PlcExecuteResponse(BaseModel):
    transaction_id: str
    asset_id: str
    success: bool
    executed_at_ms: int | None = None
    reason: str | None = None
    connection_key: str | None = None


class PlcSafeStateRequest(BaseModel):
    asset_id: str


class PlcSafeStateResponse(BaseModel):
    asset_id: str
    success: bool
    executed_at_ms: int | None = None
    reason: str | None = None
    connection_key: str | None = None


class PlcHealthResponse(BaseModel):
    status: str = Field(pattern="^(OK|DEGRADED|ERROR)$")
    connections: list[dict[str, Any]]
