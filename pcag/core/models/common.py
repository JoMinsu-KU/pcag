"""
Common domain models used across PCAG.
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RuleType(str, Enum):
    THRESHOLD = "threshold"
    RANGE = "range"
    ENUM = "enum"
    FORBIDDEN_COMBINATION = "forbidden_combination"


class RuleCondition(BaseModel):
    """Single field condition inside a multi-field forbidden combination."""

    field: str
    operator: Literal["lt", "lte", "gt", "gte", "eq", "ne"]
    value: Any


class Rule(BaseModel):
    """Static safety rule stored in policy."""

    rule_id: str
    type: RuleType
    target_field: str

    operator: Optional[Literal["lt", "lte", "gt", "gte", "eq", "ne"]] = None
    value: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    allowed_values: Optional[list[Any]] = None
    forbidden_pairs: Optional[list[list[str]]] = None
    conditions: Optional[list[RuleCondition]] = None

    unit: Optional[str] = None
    aas_source: Optional[str] = None


class ValidatorVerdict(BaseModel):
    verdict: Literal["SAFE", "UNSAFE", "INDETERMINATE"]
    details: dict = Field(default_factory=dict)


class ConsensusMode(str, Enum):
    AUTO = "AUTO"
    AND = "AND"
    WEIGHTED = "WEIGHTED"
    WORST_CASE = "WORST_CASE"


class ConsensusConfig(BaseModel):
    mode: ConsensusMode = ConsensusMode.AUTO
    weights: Optional[dict[str, float]] = None
    threshold: Optional[float] = None
    on_sim_indeterminate: Literal["FAIL_CLOSED", "RENORMALIZE", "TREAT_AS_UNSAFE", "IGNORE"] = "FAIL_CLOSED"


class ConsensusResult(BaseModel):
    final_verdict: Literal["SAFE", "UNSAFE"]
    mode_used: str
    weights_used: Optional[dict[str, float]] = None
    score: Optional[float] = None
    threshold: Optional[float] = None
    explanation: str


class DivergenceThreshold(BaseModel):
    sensor_type: str
    method: Literal["absolute", "percentage"]
    max_divergence: float


class IntegrityConfig(BaseModel):
    timestamp_max_age_ms: int = 500
    sensor_divergence_thresholds: list[DivergenceThreshold] = Field(default_factory=list)
