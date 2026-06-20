## Required Design Document Sections for Proof Formalization

The design document must include these additional sections when the project involves Lean 4 proof formalization.

### Lean Architecture

This section must specify:

- **File organization**: How many `.lean` files, what each file contains, and why this decomposition was chosen
- **Import hierarchy**: Which files import which, depicted as a dependency graph or ordered list
- **Namespace conventions**: Lean namespace structure following Mathlib style (e.g., `FC.Domain.Theorem`)
- **Mathlib import strategy**: Import granularity (broad `import Mathlib` vs. targeted module imports) with rationale
- **Shared definitions placement**: Where common types, sets, variables, and type class instances live

### Sorry Decomposition Strategy

This section must specify:

- **Proof obligation granularity**: How many sorry sites, one per theorem vs. finer decomposition, with rationale
- **Tactic scope boundaries**: Which sorry sites are expected to yield to simple tactics (ring, linarith, simp) and which require multi-step proofs or automation (aesop, grind, repair_proofs)
- **Proof dependencies**: Known dependencies between sorry sites (e.g., lemma A must be proved before theorem B can close)
- **Scaffolding-to-proof mapping**: How the scaffolded Lean output (from `formalconstruct scaffold`) maps to the final proof structure
