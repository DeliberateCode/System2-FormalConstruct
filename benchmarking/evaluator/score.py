"""Compute aggregate metrics from classified results."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from benchmarking.evaluator.classify import Outcome
from benchmarking.runner.invoke import RunResult


@dataclass
class BenchmarkMetrics:
    """Aggregate metrics for a benchmark run."""

    total: int = 0
    verified: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    by_domain: dict[str, dict[str, int]] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)
    timing_seconds: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "verified": self.verified,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "by_domain": self.by_domain,
            "by_outcome": self.by_outcome,
            "timing_seconds": self.timing_seconds,
        }


def compute_metrics(
    results: list[RunResult],
    outcomes: list[Outcome],
    problems: list[dict],
) -> BenchmarkMetrics:
    """Compute aggregate metrics from classified results."""
    if not results:
        return BenchmarkMetrics()

    total = len(results)
    verified = sum(1 for o in outcomes if o == Outcome.VERIFIED)
    failed = total - verified

    # By domain
    domain_stats: dict[str, dict[str, int]] = {}
    for problem, outcome in zip(problems, outcomes):
        domain = problem.get("domain_tag", "unknown")
        if domain not in domain_stats:
            domain_stats[domain] = {"total": 0, "verified": 0, "failed": 0}
        domain_stats[domain]["total"] += 1
        if outcome == Outcome.VERIFIED:
            domain_stats[domain]["verified"] += 1
        else:
            domain_stats[domain]["failed"] += 1

    # By outcome
    outcome_counts = Counter(o.value for o in outcomes)

    # Timing
    durations = [r.duration_seconds for r in results]
    durations_sorted = sorted(durations)
    timing = {
        "total": round(sum(durations), 1),
        "mean": round(sum(durations) / len(durations), 1),
        "median": round(durations_sorted[len(durations_sorted) // 2], 1),
        "min": round(min(durations), 1),
        "max": round(max(durations), 1),
        "p95": round(durations_sorted[int(len(durations_sorted) * 0.95)], 1),
    }

    return BenchmarkMetrics(
        total=total,
        verified=verified,
        failed=failed,
        pass_rate=verified / total if total > 0 else 0.0,
        by_domain=domain_stats,
        by_outcome=dict(outcome_counts),
        timing_seconds=timing,
    )
