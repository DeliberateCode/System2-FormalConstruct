"""FormalConstruct: toolkit for translating mathematical narratives into verified Lean 4 proofs.

This package provides schemas, validation, deterministic Lean scaffolding,
AXLE response parsing, and state management. LLM reasoning is handled by
Claude Code directly — see CLAUDE.md for the orchestration protocol.

Usage from Claude Code:
    python -m formalconstruct schema        # Print ProblemSpec JSON schema
    python -m formalconstruct validate X    # Validate a ProblemSpec JSON
    python -m formalconstruct scaffold X    # Generate Lean 4 from ProblemSpec
    python -m formalconstruct parse-axle T  # Parse AXLE response
"""

from formalconstruct.core.config import AxleConfig, PipelineConfig, RepairBudget
from formalconstruct.core.exceptions import FormalConstructError

__version__ = "0.1.0"

__all__ = [
    "AxleConfig",
    "FormalConstructError",
    "PipelineConfig",
    "RepairBudget",
    "__version__",
]
