"""
정책 저장소 FastAPI 앱 — DB 초기화 포함
"""
from fastapi import FastAPI
from pcag.apps.policy_store.routes import router
from pcag.core.database.engine import init_db
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware

# Setup logging
setup_logging("policy-store")

app = FastAPI(title="PCAG Policy Store", version="0.1.0")
app.add_middleware(LoggingMiddleware)

app.include_router(router)

@app.on_event("startup")
def startup():
    """서버 시작 시 DB 테이블 생성"""
    init_db()
