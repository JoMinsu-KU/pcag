"""
센서 게이트웨이 FastAPI 앱
===========================
서버 시작 시 센서 소스를 초기화합니다.
ModRSsim2가 실행 중이면 Modbus, 아니면 Mock 사용.

conda pcag 환경에서 실행.
"""
from fastapi import FastAPI
from pcag.apps.sensor_gateway.routes import router, initialize_sensor_source
from pcag.core.utils.logging_config import setup_logging
from pcag.core.middleware.logging_middleware import LoggingMiddleware

# Setup logging
setup_logging("sensor-gateway")

app = FastAPI(title="PCAG Sensor Gateway", version="0.1.0")
app.add_middleware(LoggingMiddleware)

app.include_router(router)

@app.on_event("startup")
def startup():
    """서버 시작 시 센서 소스 초기화"""
    initialize_sensor_source()
