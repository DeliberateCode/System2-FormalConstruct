"""Batch execution of benchmark problems with concurrency control."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmarking.config import RunConfig
from benchmarking.runner.invoke import RunResult, invoke_single


async def run_batch(
    problems: list[dict],
    config: RunConfig,
    project_root: Path,
    progress_callback: callable | None = None,
    live_save_dir: Path | None = None,
) -> list[RunResult]:
    """Run all problems with bounded concurrency.

    Args:
        problems: List of problem dicts from problems.json.
        config: Run configuration.
        project_root: Path to FormalConstruct repo root.
        progress_callback: Optional fn(completed, total, result) called after each.
        live_save_dir: If provided, save results incrementally as each problem completes.

    Returns:
        List of RunResults in input order.
    """
    semaphore = asyncio.Semaphore(config.concurrency)
    results: list[RunResult | None] = [None] * len(problems)
    completed = 0

    async def run_one(idx: int, problem: dict) -> None:
        nonlocal completed
        async with semaphore:
            try:
                result = await invoke_single(problem, config, project_root)
            except Exception as exc:  # noqa: BLE001 - isolate per-problem failures
                result = RunResult(
                    problem_id=problem.get("id", "unknown"),
                    success=False,
                    exit_code=-3,
                    duration_seconds=0.0,
                    error_message=f"runner error: {exc}",
                )
            results[idx] = result
            completed += 1

            # Save result immediately if live_save_dir provided
            if live_save_dir:
                _save_single_result(result, live_save_dir)

            if progress_callback:
                progress_callback(completed, len(problems), result)

    tasks = [
        asyncio.create_task(run_one(i, p))
        for i, p in enumerate(problems)
    ]
    await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


def _save_single_result(result: RunResult, run_dir: Path) -> None:
    """Save a single problem result immediately."""
    problems_dir = run_dir / "problems"
    problems_dir.mkdir(parents=True, exist_ok=True)

    problem_dir = problems_dir / result.problem_id
    problem_dir.mkdir(exist_ok=True)

    with open(problem_dir / "result.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    if result.lean_source:
        (problem_dir / "output.lean").write_text(result.lean_source)
    if result.problem_spec_json:
        with open(problem_dir / "problem_spec.json", "w") as f:
            json.dump(result.problem_spec_json, f, indent=2)


def save_run(
    results: list[RunResult],
    config: RunConfig,
    problems: list[dict],
    run_dir: Path | None = None,
) -> Path:
    """Save run metadata to directory (individual results saved incrementally).

    Args:
        results: List of completed results.
        config: Run configuration.
        problems: Original problem list.
        run_dir: Existing run directory (if None, creates new one).

    Returns the path to the run directory.
    """
    if run_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = config.results_dir / f"run_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # If no run_dir provided, save individual results now
        for result in results:
            _save_single_result(result, run_dir)

    # Save run metadata
    timestamp = run_dir.name.replace("run_", "")
    meta = {
        "timestamp": timestamp,
        "total_problems": len(problems),
        "completed": len(results),
        "config": {
            "concurrency": config.concurrency,
            "timeout_seconds": config.timeout_seconds,
            "max_turns": config.max_turns,
            "agent_name": config.agent_name,
        },
        "total_duration_seconds": sum(r.duration_seconds for r in results),
    }
    with open(run_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return run_dir
