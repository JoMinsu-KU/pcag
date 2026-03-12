"""
정책 저장소 (Policy Store) — 실제 구현
======================================
SQLite DB를 사용하여 정책을 저장하고 조회합니다.

PCAG 파이프라인 위치:
  Gateway Core (100) → 여기서 정책 조회 (110 무결성 검사에 사용)
  Safety Cluster (120) → 여기서 정책 조회 (검증기 설정에 사용)

API:
  GET  /v1/policies/active                     — 활성 정책 버전 조회
  GET  /v1/policies/{version}                  — 전체 정책 문서 조회
  GET  /v1/policies/{version}/assets/{asset_id} — 자산별 정책 프로필 조회

conda pcag 환경에서 실행.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pcag.core.contracts.policy import (
    ActivePolicyResponse, PolicyDocumentResponse, AssetPolicyProfileResponse
)
from pcag.core.database.engine import get_db
from pcag.apps.policy_store.repository import PolicyRepository

router = APIRouter(prefix="/v1", tags=["PolicyStore"])


@router.get("/policies/active")
def get_active_policy(db: Session = Depends(get_db)):
    """
    현재 활성 정책 버전 조회
    
    다른 서비스(Gateway, Safety Cluster)가 정책 조회 시 
    먼저 이 엔드포인트로 활성 버전을 확인합니다.
    """
    repo = PolicyRepository(db)
    active_version = repo.get_active_version()
    if not active_version:
        raise HTTPException(status_code=404, detail="No active policy found")
    return ActivePolicyResponse(policy_version_id=active_version)


@router.get("/policies/{version}")
def get_policy(version: str, db: Session = Depends(get_db)):
    """
    전체 PolicyDocument 조회
    
    정책 버전 ID로 전체 정책 문서(GlobalPolicy + 모든 AssetPolicyProfile)를 반환합니다.
    """
    repo = PolicyRepository(db)
    record = repo.get_policy(version)
    if not record:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")
    
    doc = record.get_document()
    return PolicyDocumentResponse(
        policy_version_id=record.policy_version_id,
        issued_at_ms=record.issued_at_ms,
        global_policy=doc.get("global_policy", {}),
        assets=doc.get("assets", {})
    )


@router.get("/policies/{version}/assets/{asset_id}")
def get_asset_policy(version: str, asset_id: str, db: Session = Depends(get_db)):
    """
    개별 AssetPolicyProfile 조회
    
    Safety Cluster가 검증기 설정(consensus, ruleset, simulation 등)을
    가져올 때 이 엔드포인트를 사용합니다.
    """
    repo = PolicyRepository(db)
    record = repo.get_policy(version)
    if not record:
        raise HTTPException(status_code=404, detail=f"Policy version '{version}' not found")
    
    profile = record.get_asset_profile(asset_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found in policy '{version}'")
    
    return AssetPolicyProfileResponse(
        policy_version_id=version,
        asset_id=asset_id,
        profile=profile
    )
