"""Generate benchmark reports from run results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from benchmarking.evaluator.classify import Outcome
from benchmarking.evaluator.score import BenchmarkMetrics
from benchmarking.runner.invoke import RunResult


TEMPLATE_DIR = Path(__file__).parent


def generate_report(
    run_dir: Path,
    metrics: BenchmarkMetrics,
    results: list[RunResult],
    outcomes: list[Outcome],
    problems: list[dict],
) -> Path:
    """Generate markdown and JSON reports in the run directory."""
    run_id = run_dir.name
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # JSON metrics
    metrics_path = run_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)

    # Markdown report
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("template.md.j2")

    problem_details = list(zip(
        [SimpleNamespace(**p) for p in problems],
        outcomes,
        results,
    ))

    report_content = template.render(
        run_id=run_id,
        timestamp=timestamp,
        metrics=metrics,
        problem_details=problem_details,
    )

    report_path = run_dir / "report.md"
    report_path.write_text(report_content)

    return report_path
