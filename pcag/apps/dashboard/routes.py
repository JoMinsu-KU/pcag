"""Routes for the PCAG real-time monitoring dashboard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from pcag.apps.dashboard.service import DashboardMonitor

router = APIRouter(tags=["Dashboard"])
_monitor = DashboardMonitor()
_STATIC_DIR = Path(__file__).resolve().parent / "static"


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@router.get("/v1/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "refresh_ms": _monitor.refresh_ms,
            "window_minutes": _monitor.window_minutes,
        }
    )


@router.get("/v1/snapshot")
async def snapshot() -> JSONResponse:
    return JSONResponse(await _monitor.build_snapshot())


@router.get("/v1/stream")
async def stream() -> StreamingResponse:
    async def event_generator():
        try:
            while True:
                snapshot = await _monitor.build_snapshot()
                yield f"event: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
                await asyncio.sleep(max(_monitor.refresh_ms / 1000, 0.5))
        except asyncio.CancelledError:
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")
