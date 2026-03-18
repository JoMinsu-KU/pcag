"""
PCAG 데이터베이스 엔진 설정
===========================
PostgreSQL을 사용하여 정책, 증거 등을 영구 저장합니다.

Docker Compose로 PostgreSQL 실행:
  docker compose -f docker/docker-compose.db.yml up -d

pgAdmin 접속:
  http://localhost:5050
  Email: admin@pcag.local
  Password: (see dev docs)

conda pcag 환경에서 실행.
"""
import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)


def _load_project_env() -> None:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_project_env()

# PostgreSQL 연결 설정 (Docker Compose 기본값)
DATABASE_URL = os.environ.get("PCAG_DATABASE_URL")

if not DATABASE_URL:
    logger.warning("PCAG_DATABASE_URL not set. Using default development credentials (unsafe for production).")
    DATABASE_URL = "postgresql://pcag_user:pcag_pass@localhost:5432/pcag"

# SQLAlchemy 엔진
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """모든 ORM 모델의 기본 클래스"""
    pass


def get_db():
    """FastAPI Dependency: DB 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """DB 테이블 생성 (없으면 생성)"""
    Base.metadata.create_all(bind=engine)
