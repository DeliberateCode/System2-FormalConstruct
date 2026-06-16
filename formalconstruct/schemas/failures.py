from enum import Enum
from pydantic import BaseModel, Field


class FailureClassification(str, Enum):
    """Failure classification categories."""
    SCHEMA_INSUFFICIENCY = "schema_insufficiency"
    MATHLIB_GAP = "mathlib_gap"
    PROOF_SEARCH_EXHAUSTION = "proof_search_exhaustion"


class StructuredFailure(BaseModel):
    """Structured failure report when repair loop exhausted."""
    classification: FailureClassification
    final_lean_goal: str
    compiler_errors: list[str] = Field(default_factory=list)
    tool_errors: list[str] = Field(default_factory=list)
    originating_schema_fields: list[str] = Field(default_factory=list)
    originating_narrative_indices: list[tuple[int, int]] = Field(default_factory=list)
    attempted_tactics: list[str] = Field(default_factory=list)
    attempted_repairs: list[str] = Field(default_factory=list)
    tactic_attempts_used: int = 0
    repair_attempts_used: int = 0
    replans_used: int = 0
    schema_rollbacks_used: int = 0
    axle_calls_used: int = 0
    wall_clock_seconds: float = 0.0
    exhausted_bound: str = ""  # Which bound triggered termination
    phase: str = ""  # Pipeline phase where failure occurred
    traceback_path: list[str] = Field(default_factory=list)
