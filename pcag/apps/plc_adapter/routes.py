"""
PLC adapter routes.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from pcag.apps.plc_adapter.service import PlcAdapterService
from pcag.core.contracts.plc_adapter import (
    PlcExecuteRequest,
    PlcExecuteResponse,
    PlcHealthResponse,
    PlcRuntimePreloadRequest,
    PlcRuntimePreloadResponse,
    PlcSafeStateRequest,
    PlcSafeStateResponse,
    PlcSnapshotResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["PlcAdapter"])

_service = PlcAdapterService()


def initialize_plc_adapter() -> None:
    _service.initialize()


def shutdown_plc_adapter() -> None:
    _service.shutdown()


@router.get("/health", response_model=PlcHealthResponse)
def health() -> PlcHealthResponse:
    return PlcHealthResponse(**_service.get_health())


@router.get("/assets/{asset_id}/snapshots/latest", response_model=PlcSnapshotResponse)
def get_latest_snapshot(asset_id: str) -> PlcSnapshotResponse:
    try:
        snapshot, connection_key = _service.read_snapshot(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("PLC adapter snapshot failed | asset=%s error=%s", asset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PLC snapshot failed: {exc}") from exc

    return PlcSnapshotResponse(
        asset_id=asset_id,
        timestamp_ms=int(time.time() * 1000),
        sensor_snapshot=snapshot,
        connection_key=connection_key,
    )


@router.post("/runtime/preload", response_model=PlcRuntimePreloadResponse)
def preload_runtime(request: PlcRuntimePreloadRequest) -> PlcRuntimePreloadResponse:
    try:
        preload_result = _service.preload_runtime(
            asset_id=request.asset_id,
            runtime_context=request.runtime_context,
            initial_state=request.initial_state,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("PLC adapter preload failed | asset=%s error=%s", request.asset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PLC runtime preload failed: {exc}") from exc

    return PlcRuntimePreloadResponse(**preload_result)


@router.post("/execute", response_model=PlcExecuteResponse)
def execute(request: PlcExecuteRequest) -> PlcExecuteResponse:
    try:
        success, reason, connection_key = _service.execute_actions(
            transaction_id=request.transaction_id,
            asset_id=request.asset_id,
            action_sequence=request.action_sequence,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("PLC adapter execute failed | tx=%s asset=%s error=%s", request.transaction_id, request.asset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PLC execute failed: {exc}") from exc

    return PlcExecuteResponse(
        transaction_id=request.transaction_id,
        asset_id=request.asset_id,
        success=success,
        executed_at_ms=int(time.time() * 1000) if success else None,
        reason=reason,
        connection_key=connection_key,
    )


@router.post("/safe-state", response_model=PlcSafeStateResponse)
def safe_state(request: PlcSafeStateRequest) -> PlcSafeStateResponse:
    try:
        success, reason, connection_key = _service.safe_state(request.asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("PLC adapter safe state failed | asset=%s error=%s", request.asset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"PLC safe state failed: {exc}") from exc

    return PlcSafeStateResponse(
        asset_id=request.asset_id,
        success=success,
        executed_at_ms=int(time.time() * 1000) if success else None,
        reason=reason,
        connection_key=connection_key,
    )
