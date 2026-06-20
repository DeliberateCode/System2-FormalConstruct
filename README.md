# FormalConstruct

FormalConstruct translates mathematical narratives into verified Lean 4 proofs. It ships two ways:

1. **Standalone** -- a Python package and a Claude Code agent that orchestrates the full pipeline directly.
2. **System2 overlay** -- injects proof-formalization guidance into [System2](https://github.com/DeliberateCode/System2) pipeline agents during composition.

Both paths use the same Python toolkit and the same [AXLE MCP server](https://github.com/AxiomMath/axle-mcp-server) for Lean compilation and verification.

## Installation

### Step 1: Install the package

```bash
git clone https://github.com/DeliberateCode/System2-FormalConstruct.git
cd System2-FormalConstruct
./install.sh
```

This installs:
- The `formalconstruct` CLI (via pipx, uv, or a local venv)
- The `formalize` agent to `.claude/agents/`
- The `/formalize` command to `.claude/commands/`

This is sufficient for standalone use. You can invoke `@formalize` or `/formalize` immediately.

### Step 2 (optional): Compose the System2 overlay

If you use [System2](https://github.com/DeliberateCode/System2), compose the overlay into your project. From within the target project in Claude Code:

```
/system2:compose <path-to-FormalConstruct/plugin>
```

This injects proof-formalization guidance into System2's pipeline agents and installs the `formalize` auxiliary agent. Step 1 must be completed first so the `formalconstruct` CLI is available on PATH.

## Usage

From [Claude Code](https://claude.ai/claude-code), invoke the formalization agent:

```
@formalize A firm chooses an output level to minimize total costs,
balancing a strictly convex capital cost against a linear labor cost.
```

Or use the slash command:

```
/formalize A firm chooses an output level to minimize total costs,
balancing a strictly convex capital cost against a linear labor cost.
```

The agent produces a verified Lean 4 file or a structured failure report. You can interact with it mid-run if it needs clarification about the problem structure.

## How the Agent Works

The `formalize` agent is defined at `plugin/agents/formalize.md` and installed to `.claude/agents/formalize.md` by the install script (or by System2's composer during overlay composition). When invoked, Claude Code spawns a subagent with that file's persona and instructions. The agent has access to the same tools as the main session (Bash, Read, Edit, MCP) but operates under the formalization protocol.

The agent runs in the current conversation -- it takes over the turn, executes the pipeline, and returns the result.

### Axioms: Narrative to ProblemSpec

The agent reads the mathematical narrative and extracts a structured ProblemSpec JSON. This is LLM reasoning -- the agent identifies the problem domain, decision variables, function properties (convexity, linearity), domain constraints, and objective direction from the prose. It maps natural-language patterns to schema fields:

- "strictly convex" becomes `StrictConvex`
- "non-negative" or "x >= 0" becomes `bounds.lower_bound = "0"`, `strict_inequality = false`
- "Nash equilibrium" becomes `direction: "equilibrium"`

The agent writes the JSON to a file, then validates it by calling the CLI:

```bash
formalconstruct validate spec.json
```

Validation enforces cross-field reference integrity: every variable must reference a declared space, every function domain must reference a declared space, and expression identifiers must match declared symbols. If validation fails, the agent fixes the spec and re-validates.

### Conjecture: ProblemSpec to Lean Scaffolding

The agent calls the deterministic scaffolder:

```bash
formalconstruct scaffold spec.json -o proof.lean
```

This produces Lean 4 source with Mathlib imports, domain set definitions, function hypotheses, and theorem statements. Each proof obligation is marked with `sorry`. The scaffolder also emits a `.meta.json` file with source mappings linking every Lean line back to the ProblemSpec field that generated it.

The agent verifies the scaffold compiles by calling AXLE `check` before proceeding.

### Proof: Iterative Sorry Replacement

The agent replaces each `sorry` sequentially using AXLE MCP tools:

1. **Check** -- call `check` to read the goal state (what needs to be proved).
2. **Generate tactic** -- based on the goal, select a candidate (`exact`, `ring`, `linarith`, `aesop`, `simp`, `grind`, `exact?`).
3. **Replace and verify** -- substitute the `sorry`, call `check` again. If it compiles, move to the next goal. If not, try a different tactic.
4. **Budget enforcement** -- at most 8 tactic attempts per goal. If all fail, escalate to `repair_proofs` (automated repair with terminal tactics like `aesop`, `grind`, `positivity`). At most 2 repair attempts per goal.
5. **Decomposition** -- if repair also fails, call `have2lemma` to extract sub-goals as standalone lemmas and retry with fresh budgets.
6. **Final gate** -- once all `sorry` tokens are removed, call `verify_proof` for strict verification. This rejects any proof containing `sorry` or unsafe native code.

The output is either a verified Lean 4 file (`verify_proof` returns `okay: true`) or a structured failure report containing the final goal state, tactics attempted, and a classification: **schema gap** (ProblemSpec needs more structure), **Mathlib gap** (required lemma unavailable in lean-4.29.0), or **proof search exhaustion** (budgets consumed).

## Requirements

- [Claude Code](https://claude.ai/claude-code)
- Python >= 3.11
- `AXLE_API_KEY` environment variable (for proof verification)
- Generated proofs target **lean-4.29.0** with Mathlib

## Supported Domains

- **Continuous Optimization** -- convex/strictly convex cost functions, real-valued domains with bounds, minimization and maximization theorems
- **Non-cooperative Game Theory** -- Nash equilibrium with per-player deviation clauses, right-associated tuple projections for 3+ players
- **Cooperative Game Theory** -- Pareto optimality scaffolding
- **Composite** -- game theory + continuous optimization (e.g., Cournot duopoly with convex costs)

## CLI

The CLI is used internally by the formalization agent but can also be invoked directly:

| Command | Description |
|---------|-------------|
| `formalconstruct schema` | Print the ProblemSpec JSON schema |
| `formalconstruct validate <spec.json>` | Validate a ProblemSpec JSON file |
| `formalconstruct scaffold <spec.json> [-o out.lean]` | Generate Lean 4 scaffolding |
| `formalconstruct parse-axle <tool> [response.json]` | Parse an AXLE JSON response |
| `formalconstruct list-domains` | List available domain mappers |

## System2 Overlay

FormalConstruct is also a System2 overlay plugin. The overlay provides the same proof-formalization guidance as the standalone agent, but decomposed into per-agent contributions that System2's compose engine injects at anchor points across 9 pipeline agents. The `formalize` auxiliary agent is declared in the overlay manifest and installed during composition.

See [Installation Step 2](#step-2-optional-compose-the-system2-overlay) for setup. The overlay manifest, contribution content files, and auxiliary agent definition all live under `plugin/`.

## Development

```bash
make setup    # Create venv and install dev dependencies
make test     # Run the test suite
make lint     # Run linter
make format   # Format code
```

Package tests: `pytest tests/ -m "not live"`

Overlay smoke tests: `pytest tests/test_compose_smoke.py` (requires `../System2`)

## Documentation

- [Supported LaTeX](docs/supported-latex.md)
- [Quick Start Guide](docs/quickstart.md)
