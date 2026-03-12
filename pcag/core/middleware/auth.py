"""
PCAG API Key 인증 미들웨어
===========================
X-API-Key 헤더로 API Key 인증을 수행합니다.

Phase 2a: API Key 기반 인증
Phase 2b (향후): JWT + mTLS

config/services.yaml의 auth 섹션에서 유효한 키 목록을 로드합니다.
"""
import logging
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from pcag.core.utils.config_loader import load_config

logger = logging.getLogger(__name__)

# API Key 헤더 정의
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
ADMIN_KEY_HEADER = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def _get_auth_config() -> dict:
    """인증 설정 로드"""
    config = load_config("services.yaml")
    return config.get("auth", {})


def _is_auth_enabled() -> bool:
    """인증이 활성화되어 있는지"""
    return _get_auth_config().get("enabled", True)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """
    에이전트 API Key 검증
    
    FastAPI Dependency로 사용:
      @router.post("/control-requests")
      async def submit(request, api_key = Depends(verify_api_key)):
    """
    if not _is_auth_enabled():
        return "auth-disabled"
    
    if not api_key:
        logger.warning("API Key missing in request")
        raise HTTPException(status_code=401, detail="API Key required. Set X-API-Key header.")
    
    valid_keys = _get_auth_config().get("api_keys", [])
    if api_key not in valid_keys:
        logger.warning(f"Invalid API Key: {api_key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    return api_key


async def verify_admin_key(admin_key: str = Security(ADMIN_KEY_HEADER)):
    """
    관리자 API Key 검증
    
    Admin API 전용:
      @router.post("/admin/policies")
      async def create(request, key = Depends(verify_admin_key)):
    """
    if not _is_auth_enabled():
        return "auth-disabled"
    
    if not admin_key:
        logger.warning("Admin Key missing in request")
        raise HTTPException(status_code=401, detail="Admin Key required. Set X-Admin-Key header.")
    
    valid_keys = _get_auth_config().get("admin_keys", [])
    if admin_key not in valid_keys:
        logger.warning(f"Invalid Admin Key: {admin_key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid Admin Key")
    
    return admin_key
