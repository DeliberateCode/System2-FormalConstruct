# Quick Start Guide

FormalConstruct translates mathematical narratives into verified Lean 4 proofs. You describe your problem in natural language; the `formalize` agent handles the rest.

## 1. Install

```bash
pip install -e ".[dev]"
```

## 2. Configure the AXLE MCP server

Add the following to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "axiom-axle-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "axiom-axle-mcp==0.3.5", "axle-mcp-server"]
    }
  }
}
```

The server process inherits your shell environment, so if `AXLE_API_KEY` is exported there (e.g. in `~/.zshrc`), no further configuration is needed.

## 3. Describe your problem

Write a natural language narrative describing your mathematical problem. For example:

> A firm chooses an output level to minimize total costs. Capital costs are strictly convex. Labor costs are linear. Both are non-negative.

No JSON required — the `formalize` agent extracts all structure from your description.

## 4. Run `/formalize`

In Claude Code, pass your narrative inline:

```
/formalize A firm chooses an output level to minimize total costs. Capital costs are strictly convex. Labor costs are linear. Both are non-negative.
```

Or mention the agent directly:

```
@formalize A firm chooses an output level to minimize total costs...
```

The agent will:

1. **Axioms** — extract a structured ProblemSpec from your narrative and validate it
2. **Conjecture** — generate Lean 4 source with `sorry` at each proof obligation
3. **Proof** — iteratively replace each `sorry` with verified tactics via AXLE

## 5. Review the output

The agent delivers either:
- A verified `.lean` file (`verify_proof` returned `okay: true`), or
- A structured failure report classifying the gap: **schema gap**, **Mathlib gap**, or **proof search exhaustion**

## Supported domains

- Continuous optimization (minimize/maximize)
- Non-cooperative game theory (Nash equilibrium)
- Cooperative game theory (Pareto optimal)
- Composite problems spanning multiple domains

## Advanced: CLI tools

The `formalconstruct` CLI exposes the pipeline stages directly for users who want fine-grained control:

```bash
formalconstruct schema               # Print the full ProblemSpec JSON schema
formalconstruct validate spec.json   # Validate a ProblemSpec file
formalconstruct scaffold spec.json -o proof.lean  # Generate Lean scaffolding
```

See `docs/supported-latex.md` for the LaTeX subset accepted in expression fields.
