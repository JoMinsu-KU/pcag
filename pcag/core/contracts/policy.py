"""
Policy Contract (Gateway / Safety Cluster ↔ Policy Store)
============================================
이 모듈은 Gateway Core 및 Safety Cluster와 Policy Store 간의 통신 계약을 정의합니다.

PCAG 파이프라인 위치:
  [Policy Store] → [100] Gateway / [120] Safety Cluster

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.3
  - plans/PCAG_Modular_Architecture_Analysis.md §PolicyStore
"""

from pydantic import BaseModel, Field
from typing import Optional, Any

class ActivePolicyResponse(BaseModel):
    """
    현재 활성화된 정책 버전을 조회하기 위한 응답.
    
    사용 경로: Gateway/Safety → Policy Store (GET /v1/policies/active)
    """
    policy_version_id: str  # 현재 시스템에 적용 중인 활성 정책 버전 ID

class PolicyDocumentResponse(BaseModel):
    """
    특정 버전의 전체 정책 문서를 반환하는 응답.
    
    사용 경로: Gateway/Safety → Policy Store (GET /v1/policies/{version})
    
    전역 설정과 모든 자산별 정책 프로필을 포함합니다.
    """
    policy_version_id: str  # 정책 버전 ID
    issued_at_ms: int       # 정책 발행 시각 (Unix Timestamp ms)
    global_policy: dict     # 시스템 전반에 적용되는 전역 규칙 및 설정
    assets: dict[str, dict]  # 자산별 정책 프로필 (Key: asset_id, Value: AssetPolicyProfile)

class AssetPolicyProfileResponse(BaseModel):
    """
    특정 자산에 대한 정책 프로필을 반환하는 응답.
    
    사용 경로: Gateway/Safety → Policy Store (GET /v1/policies/{version}/assets/{asset_id})
    
    특정 장비(Asset)에 대한 제어 권한, 안전 규칙, 검증 파라미터 등을 포함합니다.
    """
    policy_version_id: str  # 정책 버전 ID
    asset_id: str           # 대상 자산 ID
    profile: dict           # 해당 자산의 전체 정책 프로필 (AssetPolicyProfile 모델 참조)
