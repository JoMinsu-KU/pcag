"""
Admin API Contract (Policy Admin)
============================================
이 모듈은 관리자(Admin)가 정책을 관리하고 시스템 상태를 모니터링하기 위한 API 계약을 정의합니다.

PCAG 파이프라인 위치:
  [Policy Admin] Service

관련 문서:
  - plans/PCAG_Schema_Definitions.md §3.7
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal

class CreatePolicyRequest(BaseModel):
    """
    새로운 정책 버전 생성 요청.
    
    관리자가 새로운 안전 정책(전역 규칙 및 자산별 프로필)을 생성합니다.
    생성된 정책은 즉시 활성화되지 않으며, 별도의 활성화 요청이 필요합니다.
    """
    policy_version_id: str  # 생성할 정책 버전 ID (Unique)
    global_policy: dict     # 전역 정책 설정 (모든 자산에 공통 적용)
    assets: dict[str, dict]  # 자산별 정책 프로필 맵 (Key: asset_id, Value: AssetPolicyProfile)

class CreatePolicyResponse(BaseModel):
    """
    정책 생성 완료 응답.
    """
    policy_version_id: str
    created_at_ms: int  # 생성 완료 시각

class ActivatePolicyResponse(BaseModel):
    """
    정책 활성화 요청에 대한 응답.
    
    특정 버전의 정책을 시스템 활성 정책으로 지정합니다.
    이전 활성 정책은 비활성화됩니다.
    """
    policy_version_id: str  # 활성화된 정책 버전 ID
    activated_at_ms: int    # 활성화 시각
    previous_active_version: Optional[str] = None  # 직전까지 활성화되어 있던 정책 버전 ID

class GenerateFromAASRequest(BaseModel):
    """
    AAS(Asset Administration Shell) 기반 정책 자동 생성 요청.
    
    외부 AAS 서버로부터 자산 정보를 가져와 초기 정책 프로필을 생성합니다.
    """
    aas_server_url: str  # AAS 서버 URL
    aas_id_short: str    # AAS 자산 식별자 (idShort)
    manual_overrides: Optional[dict] = None  # 자동 생성된 값 중 수동으로 덮어쓸 필드

class GenerateFromAASResponse(BaseModel):
    """
    AAS 기반 정책 생성 결과.
    """
    asset_id: str
    generated_profile: dict  # 생성된 자산 정책 프로필
    aas_fields_used: list[str]  # AAS에서 매핑된 필드 목록 (추적성 확보)
    manual_fields: list[str]    # 수동으로 설정된 필드 목록

class UpdateAssetPolicyRequest(BaseModel):
    """
    특정 자산의 정책 프로필 업데이트 요청.
    
    전체 정책을 새로 생성하지 않고, 특정 자산의 설정만 수정할 때 사용합니다.
    내부적으로는 새로운 정책 버전을 생성합니다.
    """
    profile: dict  # 업데이트할 자산 정책 프로필 전체 내용

class UpdateAssetPolicyResponse(BaseModel):
    """
    자산 정책 업데이트 결과.
    """
    policy_version_id: str  # 업데이트로 인해 새로 생성된 정책 버전 ID
    asset_id: str
    updated_at_ms: int

class PluginInfo(BaseModel):
    """
    플러그인 정보 구조.
    """
    name: str          # 플러그인 이름
    module: str        # 모듈 경로
    plugin_class: str  # 클래스명
    status: Literal["active", "inactive", "error"] = "active"  # 플러그인 상태

class PluginsListResponse(BaseModel):
    """
    로드된 모든 플러그인 목록 응답.
    """
    simulation: list[PluginInfo]  # 시뮬레이션 백엔드 플러그인 목록
    sensor: list[PluginInfo]      # 센서 어댑터 플러그인 목록
    executor: list[PluginInfo]    # 실행기(Executor) 플러그인 목록

class ServiceHealth(BaseModel):
    """
    개별 서비스 상태 정보.
    """
    name: str    # 서비스 이름 (예: "gateway", "safety_cluster")
    status: Literal["healthy", "degraded", "unhealthy"]  # 상태
    url: Optional[str] = None  # 서비스 URL

class HealthResponse(BaseModel):
    """
    시스템 전체 상태 모니터링 응답.
    """
    status: Literal["healthy", "degraded", "unhealthy"]  # 전체 시스템 상태 (가장 낮은 서비스 상태 기준)
    services: list[ServiceHealth]  # 개별 서비스 상태 목록
    uptime_s: float  # 시스템 가동 시간 (초)
