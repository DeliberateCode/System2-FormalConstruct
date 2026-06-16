## Documenting Proof Formalization Work

When writing user-facing documentation for proof formalization projects, cover these four areas to give readers a complete picture of outcomes, scope, tooling, and workflow.

## Proof Completion Status

Document the outcome using one of three classifications:

- **Verified**: all theorems proved, zero sorry tokens remain, `verify_proof` returned `verified: true` for the complete source.
- **Partially proved**: some theorems verified, others still contain sorry or received a failure classification. List which theorems are verified and which are not.
- **Failed**: proof completion was not achieved. Include the failure classification for each unresolved theorem: schema gap (ProblemSpec does not capture enough structure), Mathlib gap (required lemma unavailable in the pinned Lean/Mathlib version), or proof search exhaustion (tactic and repair budgets consumed without success).

## Supported Domains

Document which mathematical domains are supported and how they map to ProblemSpec fields:

- **Continuous optimization**: real-valued domains with bounds, convex/strictly convex cost functions. ProblemSpec `problem_domain: "continuous_optimization"`.
- **Non-cooperative game theory**: Nash equilibria via `Function.update` (homogeneous strategy spaces) or explicit tuple reconstruction with right-associated projections (heterogeneous per-player strategy spaces). ProblemSpec `problem_domain: "non_cooperative_game"`.
- **Cooperative game theory**: Pareto optimality with negated domination predicates. ProblemSpec `problem_domain: "cooperative_game"`.
- **Discrete domains**: Int, Nat, Bool base types with generic theorem scaffolding.

## AXLE MCP Integration

Document the integration requirements for the AXLE Lean engine:

- Server name: `axiom-axle-mcp`.
- API key environment variable: `AXLE_API_KEY` (must be set before server startup).
- Lean environment pin: `lean-4.29.0` (passed as the `environment` parameter on every tool call).
- Configuration: add the AXLE server entry to `.mcp.json` with type `stdio`, command `uvx`, and args `["--from", "axiom-axle-mcp", "axle-mcp-server"]`.

## Pipeline Workflow

Document the user-facing workflow so readers understand what happens at each stage:

1. **Axioms**: the user supplies a mathematical problem description in natural language. The system extracts a structured ProblemSpec (JSON) capturing domain, spaces, variables, functions, and objective.
2. **Conjecture**: the system generates Lean 4 source from the ProblemSpec via `formalconstruct scaffold`. Output includes a `.lean` file with sorry placeholders and a `.lean.meta.json` metadata file.
3. **Proof**: the system iteratively replaces each sorry with verified tactics using AXLE MCP tools (`check`, `verify_proof`, `repair_proofs`). The final output is a fully verified Lean proof or a structured failure report.
