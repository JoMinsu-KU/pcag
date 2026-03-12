"""
PCAG Policy Admin (Main)
============================================
시스템 관리자를 위한 정책 관리 및 모니터링 애플리케이션의 진입점입니다.
AAS 기반 정책 자동 생성, 버전 관리, 시스템 상태 점검 기능을 제공합니다.

PCAG 파이프라인 위치:
  [Policy Admin] Service

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §PolicyAdmin
"""

from fastapi import FastAPI
from pcag.apps.policy_admin.routes import router
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware

# Setup logging
setup_logging("policy-admin")

app = FastAPI(
    title="PCAG Policy Admin", 
    version="0.1.0",
    description="Administration interface for policy management and system monitoring."
)

# Add Middleware
app.add_middleware(LoggingMiddleware)

# 라우터 등록
app.include_router(router)
