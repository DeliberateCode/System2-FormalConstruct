"""Centralized pipeline configuration.

All repair bounds, AXLE connection params, and Lean environment version
live here as a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AxleConfig:
    """AXLE MCP client configuration."""

    lean_environment: str = "lean-4.29.0"
    timeout_seconds: int = 120
    max_retries: int = 3
    initial_delay_s: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_s: float = 10.0


@dataclass
class RepairBudget:
    """Repair loop termination bounds."""

    max_tactic_attempts_per_goal: int = 8
    max_repair_attempts_per_goal: int = 2
    max_macro_replans_per_theorem: int = 3
    max_schema_rollbacks_per_problem: int = 1
    max_total_axle_calls_per_theorem: int = 40
    max_wall_clock_seconds_per_theorem: int = 900


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""

    axle: AxleConfig = field(default_factory=AxleConfig)
    repair: RepairBudget = field(default_factory=RepairBudget)
