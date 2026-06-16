## Design Constraints for Proof Formalization

### Lean File Decomposition

Plan how Lean proof files are organized:

- **One file per theorem** for independent results, or **one file per domain component** for closely related results that share definitions
- Place shared definitions (spaces, variables, type class instances) in a common import file (e.g., `FC/Common.lean`)
- Follow Mathlib namespace conventions: `FC.Domain.Theorem` (e.g., `FC.Optimization.CostMinimization`)
- Specify the import hierarchy explicitly: which files import which, and which Mathlib modules each file requires
- Keep import granularity as narrow as practical -- prefer `import Mathlib.Analysis.Convex.Basic` over `import Mathlib` when the required declarations are known

### Sorry Boundary Strategy

Define where `sorry` placeholders appear in scaffolded output:

- Each `sorry` corresponds to exactly one proof obligation
- Granularity should match natural proof structure: one `sorry` per theorem statement, with additional sorry sites for required lemmas that the theorem depends on
- Avoid over-decomposition: do not split a proof into many tiny sorry sites when a single tactic or short tactic sequence can close the goal
- Avoid under-decomposition: do not use one sorry for a multi-step proof that requires separate strategies for each step
- Document expected difficulty per sorry site: which sites should yield to simple tactics (ring, linarith, simp) and which will likely require multi-step proofs or automation (aesop, grind, repair_proofs)

### ProblemSpec-to-Lean Mapping

Specify how ProblemSpec fields map to Lean constructs:

- **`spaces`** map to Lean `Set` or `Type` definitions (e.g., `def OutputSpace : Set R := Set.Ici 0`)
- **`variables`** map to bound variable declarations with type class hypotheses (e.g., `(x : R)` with `(hx : x \in OutputSpace)`)
- **`functions`** map to variable declarations with property hypotheses (e.g., `(f : R -> R)` with `(hf : StrictConvexOn R s f)`)
- **`objective`** maps to the theorem statement: the direction and expression become the goal to prove
- Document any ProblemSpec fields that do not have a direct Lean mapping, and explain how they are represented
