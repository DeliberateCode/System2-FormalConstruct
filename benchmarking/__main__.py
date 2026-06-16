"""CLI entry point for the benchmarking suite.

Usage:
    python -m benchmarking run [--concurrency N] [--timeout S] [--problem ID]
    python -m benchmarking evaluate <run_dir>
    python -m benchmarking report <run_dir>
    python -m benchmarking curate [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from benchmarking.config import GROUND_TRUTH_FILE, PROBLEMS_FILE, RunConfig


PROJECT_ROOT = Path(__file__).parent.parent


def cmd_run(args: argparse.Namespace) -> None:
    """Run benchmark problems through the formalize agent."""
    config = RunConfig(
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
        max_turns=args.max_turns,
    )

    problems = _load_problems(args.problem)
    if not problems:
        print("No problems to run.", file=sys.stderr)
        sys.exit(1)

    if args.sample:
        problems = problems[:args.sample]

    print(f"Running {len(problems)} problems (concurrency={config.concurrency}, timeout={config.timeout_seconds}s, max_turns={config.max_turns})")

    from benchmarking.runner.batch import run_batch, save_run
    from datetime import datetime, timezone

    # Create run directory early for live saving
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = config.results_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Results directory: {run_dir}\n")

    def on_progress(done: int, total: int, result) -> None:
        status = "OK" if result.success else "FAIL"
        print(f"  [{done}/{total}] {result.problem_id}: {status} ({result.duration_seconds:.0f}s)", flush=True)

    results = asyncio.run(run_batch(problems, config, PROJECT_ROOT, on_progress, live_save_dir=run_dir))
    save_run(results, config, problems, run_dir=run_dir)  # Save final metadata
    print(f"\nResults saved to: {run_dir}")

    # Auto-evaluate using ground truth (has domain_tag etc.)
    gt_problems = _load_ground_truth(None)
    cmd_evaluate_dir(run_dir, gt_problems, results)


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Evaluate a previous run's results."""
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    problems = _load_ground_truth(None)
    results = _load_results(run_dir)
    cmd_evaluate_dir(run_dir, problems, results)


def cmd_evaluate_dir(
    run_dir: Path,
    problems: list[dict],
    results: list,
) -> None:
    """Evaluate and report on results in a directory."""
    from benchmarking.evaluator.classify import Outcome, classify
    from benchmarking.evaluator.score import compute_metrics
    from benchmarking.report.generate import generate_report

    problem_map = {p["id"]: p for p in problems}
    ordered_problems = [problem_map.get(r.problem_id, {}) for r in results]

    outcomes: list[Outcome] = []
    for result in results:
        outcome = classify(result, verification=None)
        outcomes.append(outcome)

    metrics = compute_metrics(results, outcomes, ordered_problems)

    print(f"\n{'='*50}")
    print(f"  Pass Rate: {metrics.pass_rate*100:.1f}% ({metrics.verified}/{metrics.total})")
    print(f"{'='*50}")
    print("  By outcome:")
    for outcome, count in sorted(metrics.by_outcome.items()):
        print(f"    {outcome}: {count}")
    print(f"  Timing: mean={metrics.timing_seconds.get('mean', 0):.0f}s, "
          f"median={metrics.timing_seconds.get('median', 0):.0f}s")

    report_path = generate_report(run_dir, metrics, results, outcomes, ordered_problems)
    print(f"\n  Report: {report_path}")


def cmd_curate(args: argparse.Namespace) -> None:
    """Run the dataset curation script."""
    from benchmarking.data.curate import curate, write_problems
    problems = curate(limit=args.limit, dry_run=args.dry_run)
    if not args.dry_run and problems:
        write_problems(problems, PROBLEMS_FILE)


def _load_problems(problem_id: str | None) -> list[dict]:
    """Load clean problems (id + NL statement only) for the runner."""
    if not PROBLEMS_FILE.exists():
        print(f"Problems file not found: {PROBLEMS_FILE}", file=sys.stderr)
        print("Run 'python -m benchmarking curate' first.", file=sys.stderr)
        return []

    with open(PROBLEMS_FILE) as f:
        problems = json.load(f)

    if problem_id:
        problems = [p for p in problems if p["id"] == problem_id]
        if not problems:
            print(f"Problem '{problem_id}' not found in {PROBLEMS_FILE}", file=sys.stderr)

    return problems


def _load_ground_truth(problem_id: str | None) -> list[dict]:
    """Load full problem data (with domain_tag, formal_statement, etc.) for evaluation."""
    if not GROUND_TRUTH_FILE.exists():
        print(f"Ground truth file not found: {GROUND_TRUTH_FILE}", file=sys.stderr)
        print("Run 'python -m benchmarking curate' first.", file=sys.stderr)
        return []

    with open(GROUND_TRUTH_FILE) as f:
        problems = json.load(f)

    if problem_id:
        problems = [p for p in problems if p["id"] == problem_id]

    return problems


def _load_results(run_dir: Path) -> list:
    """Load RunResults from a saved run directory."""
    from benchmarking.runner.invoke import RunResult

    results = []
    problems_dir = run_dir / "problems"
    if not problems_dir.exists():
        return results

    for problem_dir in sorted(problems_dir.iterdir()):
        result_file = problem_dir / "result.json"
        if not result_file.exists():
            continue
        with open(result_file) as f:
            data = json.load(f)
        results.append(RunResult(
            problem_id=data["problem_id"],
            success=data["success"],
            exit_code=data["exit_code"],
            duration_seconds=data["duration_seconds"],
            lean_source=data.get("lean_source"),
            problem_spec_json=data.get("problem_spec_json"),
            agent_transcript=data.get("agent_transcript", ""),
            error_message=data.get("error_message", ""),
            files_written=data.get("files_written", []),
        ))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="benchmarking",
        description="FormalConstruct benchmark suite",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = subparsers.add_parser("run", help="Run benchmark problems")
    run_parser.add_argument("--concurrency", type=int, default=2)
    run_parser.add_argument("--timeout", type=int, default=600)
    run_parser.add_argument("--max-turns", type=int, default=100, help="Max turns per problem")
    run_parser.add_argument("--problem", type=str, default=None, help="Run single problem by ID")
    run_parser.add_argument("--sample", type=int, default=None, help="Run first N problems only")

    # evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a previous run")
    eval_parser.add_argument("run_dir", type=str)

    # curate
    curate_parser = subparsers.add_parser("curate", help="Curate problems from Lean Workbook")
    curate_parser.add_argument("--dry-run", action="store_true")
    curate_parser.add_argument("--limit", type=int, default=200)

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "curate":
        cmd_curate(args)


if __name__ == "__main__":
    main()
