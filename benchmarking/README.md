# FormalConstruct Benchmark Suite

Evaluates the `formalize` agent's ability to translate plain-text math problems into verified Lean 4 proofs. Problems are sourced from [Lean Workbook](https://huggingface.co/datasets/internlm/Lean-Workbook) and filtered to FormalConstruct's supported domains (continuous optimization, game theory).

**Current results:** [RESULTS.md](RESULTS.md) — 15/16 verified (93.8%).

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- `AXLE_API_KEY` environment variable set
- FormalConstruct installed: `pip install -e ".[dev,benchmark]"` from repo root

## Quick Start

```bash
# 1. Curate problems from Lean Workbook (first time only)
python -m benchmarking curate --limit 200

# 2. Run the benchmark
python -m benchmarking run --concurrency 2 --timeout 600

# 3. Re-evaluate a previous run
python -m benchmarking evaluate benchmarking/results/run_YYYYMMDD_HHMMSS
```

## How It Works

1. **Curation** (`python -m benchmarking curate`): Downloads Lean Workbook, filters to optimization/game-theory problems using keyword matching, outputs `data/problems.json`.

2. **Running** (`python -m benchmarking run`): For each problem, invokes `claude -p --agent formalize` with only the natural language statement. The agent must independently translate the problem into a ProblemSpec, scaffold Lean 4 code, and prove theorems via AXLE.

3. **Evaluation**: Classifies each result into the outcome taxonomy:
   - `verified` — proof complete, AXLE confirms
   - `domain_mismatch` — problem outside supported domains
   - `schema_gap` — ProblemSpec couldn't represent the math
   - `scaffolding_failure` — scaffold didn't compile
   - `proof_search_exhaustion` — tactic budget consumed
   - `mathlib_gap` — required lemma unavailable in Lean 4.29.0
   - `timeout` / `agent_error` — infrastructure failures

4. **Reporting**: Generates `report.md` and `metrics.json` in the run directory.

## Configuration

Key parameters in `config.py`:
- `concurrency`: Max parallel agent invocations (default: 2)
- `timeout_seconds`: Wall-clock limit per problem (default: 600s)
- `max_turns`: Agent turn limit (default: 50)

## Problem Set

`data/problems.json` contains the curated benchmark set. Each entry:

```json
{
  "id": "lean_workbook_plus_42",
  "source": "internlm/Lean-Workbook",
  "natural_language_statement": "Minimize the strictly convex function...",
  "formal_statement": "theorem ... := by sorry",
  "ground_truth_tactic": "exact ...",
  "domain_tag": "continuous_optimization",
  "difficulty_estimate": "medium",
  "sorry_count": 1
}
```

The agent only sees `natural_language_statement`. All other fields are for evaluation.

## Running Tests

```bash
pytest benchmarking/tests/ -v
```