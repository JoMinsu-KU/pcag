"""
PCAG OT Interface (Main)
============================================
OT(운영 기술) 장비와 직접 통신하며 물리적 제어를 수행하는 애플리케이션의 진입점입니다.
2PC(2단계 커밋) 프로토콜의 참가자(Participant)로서 자원 잠금과 명령 실행을 담당합니다.

PCAG 파이프라인 위치:
  [130] OT Interface

관련 문서:
  - plans/PCAG_Modular_Architecture_Analysis.md §OTInterface
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pcag.apps.ot_interface.routes import router
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware
from pcag.core.database.engine import init_db
from pcag.apps.ot_interface.executor_manager import ExecutorManager

# Setup logging
setup_logging("ot-interface")

# Initialize Database Tables
# 실제 운영 환경에서는 Alembic 등을 사용해야 하지만, 현재는 간편한 초기화를 위해 여기서 호출
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic (if any)
    yield
    # Shutdown logic
    ExecutorManager.reset()

app = FastAPI(
    title="PCAG OT Interface", 
    version="0.1.0",
    description="OT device controller implementing 2PC participant logic.",
    lifespan=lifespan
)

# Add Middleware
app.add_middleware(LoggingMiddleware)

# 라우터 등록
app.include_router(router)
