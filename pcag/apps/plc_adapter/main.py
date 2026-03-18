"""
PCAG PLC adapter service.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from pcag.apps.plc_adapter.routes import router, initialize_plc_adapter, shutdown_plc_adapter
from pcag.core.middleware.logging_middleware import LoggingMiddleware
from pcag.core.utils.logging_config import setup_logging

setup_logging("plc-adapter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_plc_adapter()
    yield
    shutdown_plc_adapter()


app = FastAPI(
    title="PCAG PLC Adapter",
    version="0.1.0",
    description="Central owner of PLC/Modbus I/O connections for sensor reads and OT writes.",
    lifespan=lifespan,
)
app.add_middleware(LoggingMiddleware)
app.include_router(router)
