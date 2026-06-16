## Simplification Criteria for Proof Formalization

In simplification mode, flag the following as candidates for removal or consolidation.

### Removable Lean Imports

Imports where no declaration, tactic, or instance from that Mathlib module is used anywhere in the file. Each removable import adds unnecessary compilation cost.

### Over-Decomposed Proofs

Proofs that were split via `have2lemma` into multiple standalone lemmas where the original proof could have been completed directly. Indicators of over-decomposition:

- A lemma is used exactly once and could be inlined as a `have` statement
- A lemma's proof body is a single tactic application (e.g., `by ring` or `by simp`)
- The decomposition adds naming overhead without aiding readability or reuse

### Redundant Type Class Hypotheses

Type class hypotheses that are already implied by other hypotheses in scope. Common redundancies in formalization work:

- `[TopologicalSpace X]` when `[MetricSpace X]` is present (MetricSpace implies TopologicalSpace)
- `[AddCommMonoid X]` when `[Field X]` is present (Field implies AddCommMonoid through the algebra hierarchy)
- Duplicate property hypotheses that are strict specializations of each other
