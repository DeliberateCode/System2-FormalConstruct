# Changelog

## [0.1.0] - 2026-06-14

### Added
- `formalconstruct` Python package: ProblemSpec schemas, domain mappers (continuous optimization, game theory, composite), Lean 4 scaffolding agent, MCP client for AXLE, Jinja2 prompt templates, telemetry, and CLI entry point
- System2 overlay (`plugin/`): 17 contribution files injecting proof-formalization guidance into executor, code-reviewer, design-architect, spec-coordinator, requirements-engineer, task-planner, test-engineer, docs-release, and mcp-toolsmith agents
- `formalize` auxiliary agent and `/formalize` slash command for end-to-end proof formalization from natural language
- AXLE MCP server configuration (`axiom-axle-mcp`) with `AXLE_API_KEY` environment variable support; bundled in the Claude plugin manifest (`plugin/.claude-plugin/plugin.json`) and registered at user scope by `install.sh`
- `lean-toolchain` pinned to `leanprover/lean4:lean-4.29.0`
- Benchmarking suite with problem corpus, evaluator, and report generation
- GitHub Actions CI workflow (Python 3.11, 3.12, 3.13)
- Complex-optimization schema constructs: `inequality` and `existential_bound` objective directions; `IndexedVariable`, `ParametricConstraint`, `SequenceRelation`, `Summation` (with concrete `summand` templates), and `ExistentialBound` models; `SequenceRelation` `recurrence`/`initial` types for recursive sequences (e.g. `a 0 = 1`, `∀ n, a (n+1) = Real.sqrt (3 * a n + 1)`); `Function.applied_to` for convex-on-sequence functions; built-in transcendental functions (`sin`, `cos`, `log`, `sqrt`, ...) that emit as `Real.*` without explicit declaration
- Scaffolder support for the above: sequence-variable binders (`x : ℕ → ℝ`), parametric-constraint and sequence-relation hypotheses, summation goals, and a Lean `include` directive so hypotheses bind into inequality theorems
- `mcp__axle__*` tools added to the `formalize` agent's allowlist so it can call AXLE verification directly

### Fixed
- `AxleResponseParser.parse_verify` now reads AXLE's actual success contract (`okay` + empty `failed_declarations`); it previously only read a non-existent `verified` key and reported failure on every real success
- Lean 4.29 summation notation: emit `∑ k ∈ Finset.range n` (not the removed `in` form) with `open scoped BigOperators`
- Game-theory mapper no longer emits type-invalid property hypotheses (`ContinuousOn u S`) on utility functions, whose type is never the scalar `S → ℝ` shape those predicates require
- `ContinuousOptMapper._resolve_type` maps non-real base-type codomains (`Int`/`Nat`/`Bool`) to `ℤ`/`ℕ`/`Bool` instead of collapsing them to `ℝ`
- Benchmark robustness: a per-problem runner exception no longer aborts the whole batch; the AXLE MCP initialize handshake fails loudly on a closed/invalid response; `extract_verify_result` checks explicit failure phrasing before the looser "verified" keyword; and `evaluator/verify.py` uses the real `AxleToolClient` instead of a non-existent module-level `verify_proof`
- `indexed_variables` bounds are now numeric-validated (matching scalar `variables`); endogenous variables are declared explicitly under the `inequality`/`existential_bound` directions (which emit no binding lambda), avoiding an "unknown identifier" error when referenced in a constraint
- Constraint and sequence-relation hypotheses now render after the function block, so a constraint/recurrence expression referencing a declared function (e.g. `f(x)`) no longer uses it before its declaration; and the scalar `inequality` `objective.bound` is validated as a numeric literal or declared variable
