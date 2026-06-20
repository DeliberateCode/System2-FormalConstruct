## Required Context Sections for Proof Formalization

When writing `spec/context.md` for a proof formalization project, include the following sections.

### Mathematical Domain Identification

Identify which supported mathematical domains apply to the problem:

- Continuous optimization (convex/strictly convex cost functions, real-valued domains)
- Non-cooperative game theory (Nash equilibria, per-player strategy spaces)
- Cooperative game theory (Pareto optimality, domination predicates)

If the problem spans multiple domains, note the composite nature and identify the primary domain for ProblemSpec extraction.

### Proof Scope

State the theorems to be formalized. For each target theorem, identify:

- The main result and its mathematical statement
- Required supporting lemmas
- Expected proof structure (direct, by contradiction, by induction, or automation)
- Known difficulty areas that may resist automated tactic search

### Mathlib Dependency Expectations

List the Mathlib theories expected to be needed (e.g., `Mathlib.Analysis.Convex`, `Mathlib.Topology`, `Mathlib.GameTheory`). Flag any results that may not be available in Mathlib, as these represent potential Mathlib gaps that will affect proof strategy.

### Lean Environment

State the target environment configuration:

- Lean version: `lean-4.29.0`
- Mathlib version constraints (if any beyond the Lean version pin)
- AXLE MCP server requirement: `axiom-axle-mcp` with `AXLE_API_KEY`
