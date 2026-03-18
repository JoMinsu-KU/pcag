"""
Gateway contract.

This module defines the request/response models exchanged between the
agent and the PCAG gateway.
"""

from typing import Literal, Optional

from pydantic import BaseModel

from pcag.core.contracts.proof_package import ProofPackage


class AlternativeActionProposal(BaseModel):
    """Deterministic fallback action proposed after an unsafe/abort result."""

    proposal_id: Optional[str] = None
    action_type: str
    params: dict
    rationale: str
    source: str


class ControlRequest(BaseModel):
    """Agent-to-gateway control request."""

    transaction_id: str
    asset_id: str
    proof_package: ProofPackage


class ControlResponse(BaseModel):
    """Gateway-to-agent execution result."""

    transaction_id: str
    status: Literal["COMMITTED", "REJECTED", "UNSAFE", "ABORTED", "ERROR"]
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    evidence_ref: Optional[str] = None

    # Backward-compatible single slot retained for older callers.
    alternative_action: Optional[dict] = None

    # Preferred structured list used by the document-conformance path.
    alternative_actions: Optional[list[AlternativeActionProposal]] = None
