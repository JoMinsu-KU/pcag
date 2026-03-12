"""
안전 검증 클러스터 FastAPI 앱
==============================
Isaac Sim은 별도 Worker 프로세스에서 실행됩니다.
서버 시작 시 Worker 프로세스를 시작하고,
서버 종료 시 Worker 프로세스를 정리합니다.
"""
import os
import logging
from fastapi import FastAPI
from pcag.apps.safety_cluster.routes import router
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware

# Setup logging
setup_logging("safety-cluster")

logger = logging.getLogger(__name__)

app = FastAPI(title="PCAG Safety Cluster", version="0.1.0")
app.add_middleware(LoggingMiddleware)

app.include_router(router)

# Isaac Sim Proxy — 별도 프로세스와 Queue 통신
_isaac_proxy = None


def get_isaac_backend():
    """Isaac Sim Proxy 반환 (None이면 사용 불가)"""
    return _isaac_proxy


@app.on_event("startup")
def on_startup():
    """서버 시작 시 Isaac Sim Worker 프로세스 시작"""
    global _isaac_proxy
    
    enable_isaac = os.environ.get("PCAG_ENABLE_ISAAC", "false").lower() == "true"
    if not enable_isaac:
        logger.info("Isaac Sim disabled (PCAG_ENABLE_ISAAC != true)")
        return
    
    try:
        from pcag.apps.safety_cluster.isaac_proxy import IsaacSimProxy
        _isaac_proxy = IsaacSimProxy()
        _isaac_proxy.initialize({
            "headless": False,  # GUI 모드 - 시뮬레이션을 직접 볼 수 있음
            "timeout_ms": 30000,
            "simulation_steps_per_action": 30,
        })
        
        if _isaac_proxy.is_initialized():
            logger.info("Isaac Sim Worker process started successfully!")
        else:
            logger.warning("Isaac Sim Worker process failed to start")
            _isaac_proxy = None
    except Exception as e:
        logger.error(f"Isaac Sim Proxy initialization failed: {e}")
        _isaac_proxy = None


@app.on_event("shutdown")
def on_shutdown():
    """서버 종료 시 Isaac Sim Worker 프로세스 종료"""
    global _isaac_proxy
    if _isaac_proxy:
        _isaac_proxy.shutdown()
        _isaac_proxy = None
