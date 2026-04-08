"""Evidence Ledger API contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceAppendRequest(BaseModel):
    """Append-only evidence event written by Gateway Core."""

    transaction_id: str
    sequence_no: int = Field(ge=0)
    stage: Literal[
        "RECEIVED",
        "SCHEMA_VALIDATED",
        "INTEGRITY_PASSED",
        "INTEGRITY_REJECTED",
        "SAFETY_PASSED",
        "SAFETY_UNSAFE",
        "PREPARE_LOCK_GRANTED",
        "PREPARE_LOCK_DENIED",
        "REVERIFY_PASSED",
        "REVERIFY_FAILED",
        "COMMIT_ACK",
        "COMMIT_TIMEOUT",
        "COMMIT_FAILED",
        "COMMIT_ERROR",
        "ABORTED",
        "ESTOP_TRIGGERED",
    ]
    timestamp_ms: int
    payload: dict[str, Any]
    input_hash: str
    prev_hash: str
    event_hash: str


class EvidenceAppendResponse(BaseModel):
    """Append response returned after the DB write succeeds."""

    transaction_id: str
    sequence_no: int
    event_hash: str
    created_at: datetime


class EvidenceEventResponse(BaseModel):
    """A single stored evidence event."""

    transaction_id: str
    sequence_no: int
    stage: str
    timestamp_ms: int
    created_at: datetime
    payload: dict[str, Any]
    input_hash: str
    prev_hash: str
    event_hash: str


class TransactionEvidenceResponse(BaseModel):
    """Full evidence chain for a transaction."""

    transaction_id: str
    events: list[EvidenceEventResponse]
    chain_valid: bool
