"""
Safety Cluster contracts.

These models define the request and response payloads exchanged between the
Gateway and the Safety Cluster, plus the generic runtime preload hook used by
benchmark runners.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SafetyValidateRequest(BaseModel):
    transaction_id: str
    asset_id: str
    policy_version_id: str
    action_sequence: list[dict]
    current_sensor_snapshot: dict
    runtime_context: Optional[dict[str, Any]] = None


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
