"""
Policy Admin API routes.
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from pcag.apps.policy_store.repository import PolicyRepository
from pcag.core.contracts.admin import (
    ActivatePolicyResponse,
    CreatePolicyRequest,
    CreatePolicyResponse,
    GenerateFromAASRequest,
    GenerateFromAASResponse,
    HealthResponse,
    PluginInfo,
    PluginsListResponse,
    ServiceHealth,
    UpdateAssetPolicyRequest,
    UpdateAssetPolicyResponse,
)
from pcag.core.database.engine import get_db
from pcag.core.middleware.auth import verify_admin_key

router = APIRouter(prefix="/v1/admin", tags=["PolicyAdmin"])

_start_time = time.time()


@router.post("/policies")
def create_policy(request: CreatePolicyRequest, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    repo = PolicyRepository(db)

    existing = repo.get_policy(request.policy_version_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy version '{request.policy_version_id}' already exists")

    document = {
        "policy_version_id": request.policy_version_id,
        "global_policy": request.global_policy,
        "assets": request.assets,
    }

    record = repo.create_policy(
        policy_version_id=request.policy_version_id,
        issued_at_ms=int(time.time() * 1000),
        document=document,
    )

    return CreatePolicyResponse(policy_version_id=record.policy_version_id, created_at_ms=record.issued_at_ms)


@router.put("/policies/{version}/activate")
def activate_policy(version: str, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    repo = PolicyRepository(db)
    previous = repo.get_active_version()

    record = repo.activate_policy(version)
    if not record:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")

    return ActivatePolicyResponse(
        policy_version_id=version,
        activated_at_ms=int(time.time() * 1000),
        previous_active_version=previous,
    )


@router.put("/policies/{version}/assets/{asset_id}")
def update_asset_policy(version: str, asset_id: str, request: UpdateAssetPolicyRequest, key: str = Depends(verify_admin_key), db: Session = Depends(get_db)):
    repo = PolicyRepository(db)

    new_record = repo.update_asset_profile(
        version,
        asset_id,
        request.profile,
        new_policy_version_id=request.new_policy_version_id,
        created_by="admin",
        change_reason=request.change_reason,
    )
    if not new_record:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")

    return UpdateAssetPolicyResponse(
        policy_version_id=new_record.policy_version_id,
        asset_id=asset_id,
        updated_at_ms=new_record.issued_at_ms,
        previous_policy_version_id=version,
    )


@router.post("/policies/assets/{asset_id}/generate-from-aas")
def generate_from_aas(asset_id: str, request: GenerateFromAASRequest, key: str = Depends(verify_admin_key)):
    raise HTTPException(status_code=501, detail="AAS integration not yet implemented (Phase 2)")


@router.get("/plugins")
def list_plugins(key: str = Depends(verify_admin_key)):
    return PluginsListResponse(
        simulation=[
            PluginInfo(name="none", module="pcag.plugins.simulation.none_backend", plugin_class="NoneBackend", status="active")
        ],
        sensor=[],
        executor=[],
    )


@router.get("/health")
def health_check():
    policy_store_status: str = "unhealthy"
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            db.execute(text("SELECT 1"))
            policy_store_status = "healthy"
        finally:
            db.close()
    except Exception as exc:
        policy_store_status = f"unhealthy: {exc}"

    overall_status = "healthy" if policy_store_status == "healthy" else "unhealthy"
    return HealthResponse(
        status=overall_status,
        services=[
            ServiceHealth(name="policy_store", status=policy_store_status),
            ServiceHealth(name="policy_admin", status="healthy"),
        ],
        uptime_s=round(time.time() - _start_time, 1),
    )
