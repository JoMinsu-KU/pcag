"""
정책 관리 API (Policy Admin) — 실제 구현
==========================================
정책 CRUD + 활성화 관리.

API:
  POST /v1/admin/policies                                    — 새 정책 생성
  PUT  /v1/admin/policies/{version}/activate                 — 정책 활성화
  PUT  /v1/admin/policies/{version}/assets/{asset_id}        — 자산 정책 수정
  POST /v1/admin/policies/assets/{asset_id}/generate-from-aas — AAS 기반 생성 (Phase 2)
  GET  /v1/admin/plugins                                     — 플러그인 목록
  GET  /v1/admin/health                                      — 헬스 체크

conda pcag 환경에서 실행.
"""
import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pcag.core.contracts.admin import (
    CreatePolicyRequest, CreatePolicyResponse,
    ActivatePolicyResponse,
    GenerateFromAASRequest, GenerateFromAASResponse,
    UpdateAssetPolicyRequest, UpdateAssetPolicyResponse,
    PluginsListResponse, PluginInfo,
    HealthResponse, ServiceHealth
)
from pcag.core.database.engine import get_db
from pcag.apps.policy_store.repository import PolicyRepository
from pcag.core.middleware.auth import verify_admin_key

router = APIRouter(prefix="/v1/admin", tags=["PolicyAdmin"])

# 서버 시작 시각 (uptime 계산용)
_start_time = time.time()


@router.post("/policies")
def create_policy(request: CreatePolicyRequest, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    """새 PolicyDocument 생성"""
    repo = PolicyRepository(db)
    
    # 이미 존재하는 버전인지 확인
    existing = repo.get_policy(request.policy_version_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy version '{request.policy_version_id}' already exists")
    
    document = {
        "policy_version_id": request.policy_version_id,
        "global_policy": request.global_policy,
        "assets": request.assets
    }
    
    record = repo.create_policy(
        policy_version_id=request.policy_version_id,
        issued_at_ms=int(time.time() * 1000),
        document=document
    )
    
    return CreatePolicyResponse(
        policy_version_id=record.policy_version_id,
        created_at_ms=record.issued_at_ms
    )


@router.put("/policies/{version}/activate")
def activate_policy(version: str, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    """특정 버전의 정책을 활성화"""
    repo = PolicyRepository(db)
    
    # 현재 활성 버전 기록
    previous = repo.get_active_version()
    
    record = repo.activate_policy(version)
    if not record:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")
    
    return ActivatePolicyResponse(
        policy_version_id=version,
        activated_at_ms=int(time.time() * 1000),
        previous_active_version=previous
    )


@router.put("/policies/{version}/assets/{asset_id}")
def update_asset_policy(version: str, asset_id: str, request: UpdateAssetPolicyRequest, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    """개별 자산의 정책 프로필 수정"""
    repo = PolicyRepository(db)
    
    success = repo.update_asset_profile(version, asset_id, request.profile)
    if not success:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")
    
    return UpdateAssetPolicyResponse(
        policy_version_id=version,
        asset_id=asset_id,
        updated_at_ms=int(time.time() * 1000)
    )


@router.post("/policies/assets/{asset_id}/generate-from-aas")
def generate_from_aas(asset_id: str, request: GenerateFromAASRequest, key: str = Depends(verify_admin_key)):
    """AAS/BaSyx에서 자산 정책 자동 생성 (Phase 2 — 아직 미구현)"""
    raise HTTPException(status_code=501, detail="AAS integration not yet implemented (Phase 2)")


@router.get("/plugins")
def list_plugins(key: str = Depends(verify_admin_key)):
    """등록된 플러그인 목록 반환"""
    return PluginsListResponse(
        simulation=[
            PluginInfo(name="none", module="pcag.plugins.simulation.none_backend", plugin_class="NoneBackend", status="active")
        ],
        sensor=[],
        executor=[]
    )


from sqlalchemy import text

@router.get("/health")
def health_check():
    """시스템 헬스 체크"""
    
    # Check DB connection
    policy_store_status = "unhealthy"
    try:
        # Create a new session for health check
        db_gen = get_db()
        db = next(db_gen)
        try:
            db.execute(text("SELECT 1"))
            policy_store_status = "healthy"
        finally:
            db.close()
    except Exception as e:
        policy_store_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if policy_store_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=overall_status,
        services=[
            ServiceHealth(name="policy_store", status=policy_store_status),
            ServiceHealth(name="policy_admin", status="healthy"),
        ],
        uptime_s=round(time.time() - _start_time, 1)
    )
