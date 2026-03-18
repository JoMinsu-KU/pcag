"""
Proof Package contract.

This module defines the OT-oriented proof package carried by control
requests. The gateway validates this structure before any physical
execution path is entered.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProofPackage(BaseModel):
    """Structured proof payload sent from the agent to the gateway."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(min_length=1)
    policy_version_id: str = Field(min_length=1)
    timestamp_ms: int
    sensor_snapshot_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    sensor_reliability_index: float = Field(ge=0.0, le=1.0)
    action_sequence: list[dict[str, Any]] = Field(default_factory=list)
    safety_verification_summary: dict[str, Any] = Field(default_factory=dict)

    # Optional fields used by stronger integrity and traceability paths.
    sensor_snapshot: Optional[dict[str, Any]] = None
    agent_id: Optional[str] = None
    intent_id: Optional[str] = None
    proof_generated_at_ms: Optional[int] = None
    proof_origin: Optional[str] = None
