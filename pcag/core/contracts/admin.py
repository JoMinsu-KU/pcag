"""
Admin API contract.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class CreatePolicyRequest(BaseModel):
    policy_version_id: str
    global_policy: dict
    assets: dict[str, dict]


class CreatePolicyResponse(BaseModel):
    policy_version_id: str
    created_at_ms: int


class ActivatePolicyResponse(BaseModel):
    policy_version_id: str
    activated_at_ms: int
    previous_active_version: Optional[str] = None


class GenerateFromAASRequest(BaseModel):
    aas_server_url: str
    aas_id_short: str
    manual_overrides: Optional[dict] = None


class GenerateFromAASResponse(BaseModel):
    asset_id: str
    generated_profile: dict
    aas_fields_used: list[str]
    manual_fields: list[str]


class UpdateAssetPolicyRequest(BaseModel):
    profile: dict
    new_policy_version_id: Optional[str] = None
    change_reason: Optional[str] = None


class UpdateAssetPolicyResponse(BaseModel):
    policy_version_id: str
    asset_id: str
    updated_at_ms: int
    previous_policy_version_id: Optional[str] = None


class PluginInfo(BaseModel):
    name: str
    module: str
    plugin_class: str
    status: Literal["active", "inactive", "error"] = "active"


class PluginsListResponse(BaseModel):
    simulation: list[PluginInfo]
    sensor: list[PluginInfo]
    executor: list[PluginInfo]


class ServiceHealth(BaseModel):
    name: str
    status: Literal["healthy", "degraded", "unhealthy"] | str
    url: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] | str
    services: list[ServiceHealth]
    uptime_s: float
