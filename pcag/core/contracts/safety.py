"""
Safety Cluster contracts.

These models define the request and response payloads exchanged between the
Gateway and the Safety Cluster, plus the generic runtime preload hook used by
benchmark runners.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SafetyValidateRequest(BaseModel):
    transaction_id: str
    asset_id: str
    policy_version_id: str
    action_sequence: list[dict]
    current_sensor_snapshot: dict
    runtime_context: Optional[dict[str, Any]] = None
    revision_enabled_validators: Optional[list[Literal["rules", "cbf", "simulation"]]] = Field(
        default=None, min_length=1, max_length=3,
        description="Revision-only ablation subset; rejected unless PCAG_REVISION_MODE is enabled.",
    )

    @field_validator("revision_enabled_validators")
    @classmethod
    def unique_revision_validators(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("revision_enabled_validators must not contain duplicates")
        return value


class ValidatorVerdictResponse(BaseModel):
    verdict: Literal["SAFE", "UNSAFE", "INDETERMINATE"]
    details: dict[str, Any] = Field(default_factory=dict)


class ConsensusDetailsResponse(BaseModel):
    mode: str
    weights_used: Optional[dict[str, float]] = None
    score: Optional[float] = None
    threshold: Optional[float] = None
    explanation: str = ""


class SafetyValidateResponse(BaseModel):
    transaction_id: str
    final_verdict: Literal["SAFE", "UNSAFE"]
    validators: dict[str, ValidatorVerdictResponse]
    consensus_details: ConsensusDetailsResponse
    enabled_validators: list[str] = Field(default_factory=lambda: ["rules", "cbf", "simulation"])
    validator_runtime_ms: dict[str, float] = Field(default_factory=dict)
    validation_wall_ms: Optional[float] = None


class RuntimePreloadRequest(BaseModel):
    asset_id: str
    runtime_context: dict[str, Any]
    initial_state: Optional[dict[str, Any]] = None


class RuntimePreloadResponse(BaseModel):
    asset_id: str
    runtime_id: str
    status: Literal["READY"]
    scene_path: Optional[str] = None
    shell_config_path: Optional[str] = None
    robot_spawn_position: Optional[list[float]] = None
    applied_initial_joint_positions: Optional[list[float]] = None
    current_state: dict[str, Any] = Field(default_factory=dict)
