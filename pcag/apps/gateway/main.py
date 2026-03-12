"""
PCAG Gateway Core Service (Main)
============================================
PCAG 시스템의 중앙 오케스트레이터인 Gateway Core 애플리케이션의 진입점입니다.
에이전트로부터 제어 요청을 수신하고, 전체 파이프라인(무결성 → 안전 검증 → 2PC 실행)을 조율합니다.

PCAG 파이프라인 위치:
  [100] Gateway Core

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §Gateway
"""
from fastapi import FastAPI
from pcag.apps.gateway.routes import router
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware

# Setup logging
setup_logging("gateway-core")

app = FastAPI(
    title="PCAG Gateway Core", 
    version="0.1.0",
    description="Central gateway for handling request and coordinating safety validation."
)

# Add Middleware
app.add_middleware(LoggingMiddleware)

# 라우터 등록
app.include_router(router)
