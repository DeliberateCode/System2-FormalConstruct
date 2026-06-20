"""Benchmark configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


BENCHMARKING_ROOT = Path(__file__).parent
DATA_DIR = BENCHMARKING_ROOT / "data"
RESULTS_DIR = BENCHMARKING_ROOT / "results"
PROBLEMS_FILE = DATA_DIR / "problems.json"
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.json"


@dataclass(frozen=True)
class RunConfig:
    """Configuration for a benchmark run."""

    concurrency: int = 2
    timeout_seconds: int = 600
    max_turns: int = 100
    output_format: str = "json"
    agent_name: str = "formalize"
    results_dir: Path = field(default_factory=lambda: RESULTS_DIR)

    @property
    def claude_args(self) -> list[str]:
        return [
            "claude",
            "-p",
            "--agent", self.agent_name,
            "--output-format", self.output_format,
            "--max-turns", str(self.max_turns),
            "--dangerously-skip-permissions",
        ]
