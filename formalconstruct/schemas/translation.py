import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from formalconstruct.schemas.lean_source import SourceMappingEntry as SourceMapping


class NodeState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class PipelinePhase(str, Enum):
    INFORMAL_RIGOR = "informal_rigor"
    SCAFFOLDING = "scaffolding"
    PROVING = "proving"


class TranslationNode(BaseModel):
    """A node in the execution DAG. Represents one pipeline step or sub-step."""
    node_id: str
    phase: PipelinePhase
    state: NodeState = NodeState.PENDING
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))
    completed_at: Optional[datetime.datetime] = None



class TranslationContextSnapshot(BaseModel):
    """Serializable snapshot of the full translation state."""
    narrative: str
    nodes: dict[str, TranslationNode]
    source_mappings: list[SourceMapping]
    current_phase: PipelinePhase
    problem_spec: Optional[dict] = None  # Serialized ProblemSpec
    lean_source: Optional[str] = None
    verified_source: Optional[str] = None
