"""
Safety Cluster FastAPI entrypoint.

Isaac Sim runs in a dedicated worker process, while AGV/process benchmark
viewers can be bootstrapped as persistent watcher windows from server startup.
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI

from pcag.apps.safety_cluster.routes import router
from pcag.core.middleware.logging_middleware import LoggingMiddleware
from pcag.core.utils.config_loader import get_benchmark_runtime_config
from pcag.core.utils.logging_config import setup_logging
from pcag.plugins.simulation.viewer_bootstrap import ensure_benchmark_viewers_started, shutdown_benchmark_viewers

setup_logging("safety-cluster")

logger = logging.getLogger(__name__)

app = FastAPI(title="PCAG Safety Cluster", version="0.1.0")
app.add_middleware(LoggingMiddleware)
app.include_router(router)

_isaac_proxy = None


def get_isaac_backend():
    return _isaac_proxy


def _apply_benchmark_runtime_defaults() -> None:
    runtime_config = get_benchmark_runtime_config()
    env_mapping = {
        "PCAG_ENABLE_ISAAC": runtime_config.get("enable_isaac"),
        "PCAG_ENABLE_BENCHMARK_TWIN_GUIS": runtime_config.get("enable_benchmark_twin_guis"),
        "PCAG_ENABLE_AGV_GUI": runtime_config.get("enable_agv_gui"),
        "PCAG_ENABLE_PROCESS_GUI": runtime_config.get("enable_process_gui"),
    }
    for env_name, value in env_mapping.items():
        if value is None:
            continue
        if env_name not in os.environ:
            os.environ[env_name] = str(value).lower()

    # Keep legacy runtime flags aligned with the newer enable_* config names so
    # centralized GUI boot and the validator backends observe the same intent.
    alias_mapping = {
        "PCAG_AGV_GUI": os.environ.get("PCAG_ENABLE_AGV_GUI"),
        "PCAG_PROCESS_GUI": os.environ.get("PCAG_ENABLE_PROCESS_GUI"),
    }
    for env_name, value in alias_mapping.items():
        if value is None:
            continue
        if env_name not in os.environ:
            os.environ[env_name] = str(value).lower()


@app.on_event("startup")
def on_startup():
    global _isaac_proxy

    _apply_benchmark_runtime_defaults()

    enable_isaac = os.environ.get("PCAG_ENABLE_ISAAC", "false").lower() == "true"
    if not enable_isaac:
        logger.info("Isaac Sim disabled (PCAG_ENABLE_ISAAC != true)")
        try:
            viewer_info = ensure_benchmark_viewers_started()
            if any(viewer_info.values()):
                logger.info("Benchmark viewers started: %s", viewer_info)
        except Exception as exc:
            logger.warning("Benchmark viewer bootstrap failed: %s", exc, exc_info=True)
        return

    try:
        from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy

        _isaac_proxy = IsaacSimProxy()
        _isaac_proxy.initialize(
            {
                "headless": False,
                "timeout_ms": 30000,
                "simulation_steps_per_action": 30,
            }
        )

        if _isaac_proxy.is_initialized():
            logger.info("Isaac Sim Worker process started successfully")
        else:
            logger.warning("Isaac Sim Worker process failed to start")
            _isaac_proxy = None
    except Exception as exc:
        logger.error("Isaac Sim Proxy initialization failed: %s", exc, exc_info=True)
        _isaac_proxy = None

    # On Windows, starting the lightweight AGV/process viewers at the exact same
    # moment as the Isaac viewport can destabilize GUI startup. Boot Isaac first,
    # then bring up the auxiliary viewers.
    time.sleep(1.0)
    try:
        viewer_info = ensure_benchmark_viewers_started()
        if any(viewer_info.values()):
            logger.info("Benchmark viewers started: %s", viewer_info)
    except Exception as exc:
        logger.warning("Benchmark viewer bootstrap failed: %s", exc, exc_info=True)


@app.on_event("shutdown")
def on_shutdown():
    global _isaac_proxy

    try:
        shutdown_benchmark_viewers()
    except Exception as exc:
        logger.warning("Benchmark viewer shutdown failed: %s", exc, exc_info=True)

    if _isaac_proxy:
        _isaac_proxy.shutdown()
        _isaac_proxy = None
