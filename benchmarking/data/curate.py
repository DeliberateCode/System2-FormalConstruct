"""Download and filter Lean Workbook problems to FormalConstruct domains.

Usage:
    python -m benchmarking.data.curate [--dry-run] [--limit N] [--output PATH]

Requires: pip install datasets
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from benchmarking.config import DATA_DIR, PROBLEMS_FILE


def load_keywords() -> dict[str, list[str]]:
    keywords_path = DATA_DIR / "keywords.json"
    with open(keywords_path) as f:
        return json.load(f)


def match_domain(text: str, keywords: dict[str, list[str]]) -> str | None:
    """Return the best-matching domain for a natural language statement.

    Returns None if no domain keywords match.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for domain, terms in keywords.items():
        score = sum(1 for term in terms if term.lower() in text_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return None

    return max(scores, key=scores.__getitem__)


def has_optimization_structure(formal: str) -> bool:
    """Check if formal statement has actual optimization structure.

    True optimization problems have:
    - Real variables (ℝ)
    - Inequalities (suggesting bounds or constraints)
    - Preferably explicit optimization keywords

    We accept problems that look like "prove f(x) ≤ bound for all x satisfying constraints"
    since those can be reformulated as optimization problems.
    """
    has_real = "ℝ" in formal
    has_inequality = any(op in formal for op in ["≤", "≥", "<", ">"])

    # Explicit optimization or extremal value keywords
    has_opt_keyword = any(kw in formal.lower() for kw in [
        "minimize", "maximize", "argmin", "argmax", "infimum", "supremum",
        "minimum", "maximum", "optimal", "least", "greatest"
    ])

    # Also accept "sqrt" and trigonometric functions (often optimization)
    has_opt_function = any(fn in formal for fn in ["Real.sqrt", "sin", "cos", "exp", "log"])

    # Must have real numbers and either:
    # - Explicit optimization keyword, OR
    # - Inequalities + optimization-related functions
    return has_real and (has_opt_keyword or (has_inequality and has_opt_function))


def has_game_theory_structure(formal: str) -> bool:
    """Check if formal statement has game theory structure.

    Game theory problems have:
    - Multiple players/agents (indexed variables)
    - Strategy spaces or payoff functions
    - Nash equilibrium, dominant strategy, or payoff keywords
    """
    has_real = "ℝ" in formal

    # Game theory keywords in formal statement
    has_game_keyword = any(kw in formal.lower() for kw in [
        "nash", "equilibrium", "strategy", "payoff", "player",
        "dominant", "pareto", "coalition"
    ])

    # Indexed variables suggesting multiple agents (but this is heuristic)
    has_indexed = any(pattern in formal for pattern in ["_1", "_2", "ₙ", "ᵢ"])

    return has_real and (has_game_keyword or has_indexed)


def is_suitable(entry: dict, keywords: dict[str, list[str]]) -> tuple[bool, str | None]:
    """Check if a Lean Workbook entry is suitable for benchmarking.

    Returns (suitable, domain) tuple.
    """
    if entry.get("status") != "proved":
        return False, None

    nl_statement = entry.get("natural_language_statement", "")
    if not nl_statement or len(nl_statement) < 30:
        return False, None

    formal = entry.get("formal_statement", "")
    if not formal or "sorry" not in formal:
        return False, None

    # First check NL keywords for initial domain guess
    domain = match_domain(nl_statement, keywords)
    if domain is None:
        return False, None

    # Validate formal statement actually has the domain structure
    if domain == "continuous_optimization":
        if not has_optimization_structure(formal):
            return False, None
    elif domain in ("non_cooperative_game", "cooperative_game"):
        if not has_game_theory_structure(formal):
            return False, None
    else:
        return False, None

    # Reject overly complex problems (many hypotheses suggest multi-sorry)
    sorry_count = formal.count("sorry")
    if sorry_count > 3:
        return False, None

    return True, domain


def estimate_difficulty(entry: dict) -> str:
    """Estimate problem difficulty based on tactic complexity."""
    tactic = entry.get("tactic", "")
    if not tactic:
        return "unknown"

    simple_tactics = {"ring", "linarith", "simp", "norm_num", "positivity", "omega"}
    tactic_stripped = tactic.strip()

    if tactic_stripped in simple_tactics:
        return "easy"
    if len(tactic) < 100 and not re.search(r"\b(calc|have|obtain|suffices)\b", tactic):
        return "medium"
    return "hard"


def curate(limit: int | None = None, dry_run: bool = False) -> list[dict]:
    """Download Lean Workbook and filter to FormalConstruct-relevant problems."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Error: 'datasets' package required. Install with: pip install datasets", file=sys.stderr)
        sys.exit(1)

    print("Loading Lean Workbook dataset from HuggingFace...")
    dataset = load_dataset("internlm/Lean-Workbook", split="train")

    keywords = load_keywords()
    candidates: list[dict] = []
    seen_ids: set[str] = set()

    print(f"Scanning {len(dataset)} entries...")
    for i, entry in enumerate(dataset):
        suitable, domain = is_suitable(entry, keywords)
        if not suitable:
            continue

        pid = entry.get("id", f"lw_{i:05d}")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)

        problem = {
            "id": pid,
            "source": "internlm/Lean-Workbook",
            "natural_language_statement": entry["natural_language_statement"],
            "formal_statement": entry["formal_statement"],
            "ground_truth_tactic": entry.get("tactic", ""),
            "ground_truth_answer": entry.get("answer", ""),
            "domain_tag": domain,
            "difficulty_estimate": estimate_difficulty(entry),
            "sorry_count": entry["formal_statement"].count("sorry"),
        }
        candidates.append(problem)

        if limit and len(candidates) >= limit:
            break

    print(f"Found {len(candidates)} candidate problems:")
    domain_counts = {}
    for c in candidates:
        domain_counts[c["domain_tag"]] = domain_counts.get(c["domain_tag"], 0) + 1
    for domain, count in sorted(domain_counts.items()):
        print(f"  {domain}: {count}")

    if dry_run:
        print("\n[Dry run] Would write to:", PROBLEMS_FILE)
        for c in candidates[:5]:
            print(f"  - [{c['domain_tag']}] {c['natural_language_statement'][:80]}...")
        return candidates

    return candidates


def write_problems(problems: list[dict], output: Path) -> None:
    """Write curated problems as two files: clean inputs and ground truth.

    problems.json contains only id + natural_language_statement (safe for
    the formalize agent to see).  ground_truth.json contains all fields
    (used only by the evaluator, never accessible to the agent).
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    clean = [
        {"id": p["id"], "natural_language_statement": p["natural_language_statement"]}
        for p in problems
    ]
    with open(output, "w") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(clean)} problems to {output}")

    gt_path = output.parent / "ground_truth.json"
    with open(gt_path, "w") as f:
        json.dump(problems, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(problems)} ground truth records to {gt_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate Lean Workbook problems for benchmarking")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=200, help="Max candidates to collect")
    parser.add_argument("--output", type=Path, default=PROBLEMS_FILE, help="Output path")
    args = parser.parse_args()

    problems = curate(limit=args.limit, dry_run=args.dry_run)

    if not args.dry_run and problems:
        write_problems(problems, args.output)


if __name__ == "__main__":
    main()
