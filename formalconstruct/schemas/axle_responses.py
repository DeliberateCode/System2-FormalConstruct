from pydantic import BaseModel, Field


class MessageSet(BaseModel):
    """Common structure for lean_messages and tool_messages."""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    infos: list[str] = Field(default_factory=list)


class AxleCheckResult(BaseModel):
    lean_messages: MessageSet
    tool_messages: MessageSet

    @property
    def has_errors(self) -> bool:
        return bool(self.lean_messages.errors or self.tool_messages.errors)


class AxleVerifyResult(BaseModel):
    lean_messages: MessageSet
    tool_messages: MessageSet
    verified: bool  # True if proof is sorry-free and valid
    okay: bool = False  # Raw AXLE success flag (verify_proof reports `okay`)
    failed_declarations: list = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.lean_messages.errors or self.tool_messages.errors)


class RepairStats(BaseModel):
    remove_extraneous_tactics: int = 0
    replace_unsafe_tactics: int = 0
    apply_terminal_tactics: int = 0


class RepairTimings(BaseModel):
    total_ms: int = 0
    repair_ms: int = 0


class AxleRepairResult(BaseModel):
    okay: bool
    repair_stats: RepairStats = Field(default_factory=RepairStats)
    timings: RepairTimings = Field(default_factory=RepairTimings)
    content: str = ""
    lean_messages: MessageSet = Field(default_factory=MessageSet)
    tool_messages: MessageSet = Field(default_factory=MessageSet)


class AxleNormalizeResult(BaseModel):
    content: str
    lean_messages: MessageSet = Field(default_factory=MessageSet)
    tool_messages: MessageSet = Field(default_factory=MessageSet)


class AxleExtractDeclsResult(BaseModel):
    declarations: list[dict]  # Each declaration with name, kind, content, dependencies
    lean_messages: MessageSet = Field(default_factory=MessageSet)
    tool_messages: MessageSet = Field(default_factory=MessageSet)


class AxleTheorem2SorryResult(BaseModel):
    content: str
    lean_messages: MessageSet = Field(default_factory=MessageSet)
    tool_messages: MessageSet = Field(default_factory=MessageSet)


class AxleHave2LemmaResult(BaseModel):
    content: str
    lemmas: list[str] = Field(default_factory=list)
    lean_messages: MessageSet = Field(default_factory=MessageSet)
    tool_messages: MessageSet = Field(default_factory=MessageSet)
