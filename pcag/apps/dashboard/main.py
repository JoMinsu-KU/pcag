"""Main entrypoint for the PCAG monitoring dashboard."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pcag.apps.dashboard.routes import router
from pcag.core.middleware.logging_middleware import LoggingMiddleware
from pcag.core.utils.logging_config import setup_logging

setup_logging("dashboard")

app = FastAPI(
    title="PCAG Monitoring Dashboard",
    version="0.1.0",
    description="Real-time operational dashboard for the PCAG microservice suite.",
)

app.add_middleware(LoggingMiddleware)
app.include_router(router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="dashboard-static")
