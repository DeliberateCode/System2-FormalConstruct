## Review Criteria for Proof Formalization

### Sorry Drift

Check that sorry tokens have not regressed:

- No new `sorry` tokens should be introduced since the last verified state
- All sorry tokens present in scaffolded output must be accounted for: either replaced with verified tactics or explicitly reported as failures with classification (schema gap, Mathlib gap, proof search exhaustion)
- Compare the sorry count before and after the change -- the count must not increase in a proving task
- Also check for `admit` tokens, which have the same semantic as sorry (marking an unproven obligation)

### Unused Lean Imports

Flag `import Mathlib.*` statements where no declaration from that module is referenced:

- Over-importing slows Lean compilation and obscures actual dependencies
- Each Mathlib import should be justified by at least one declaration, tactic, or instance that the proof uses from that module
- Prefer targeted imports (e.g., `import Mathlib.Analysis.Convex.Basic`) over broad imports (e.g., `import Mathlib`) when the required declarations are known

### Proof Completeness

Every `theorem` and `lemma` statement must have a verified proof body:

- No sorry in any proof body
- No `admit` in any proof body
- No `native_decide` unless explicitly justified in the design document (native_decide bypasses kernel verification)
- A theorem with sorry is incomplete work and must not be accepted as a final deliverable

### ProblemSpec-Scaffold Consistency

Verify that the scaffolded Lean code faithfully reflects the ProblemSpec:

- Spaces in ProblemSpec must correspond to set or type definitions in Lean
- Variable declarations must match: names, types, bounds, and classifications
- Function properties in ProblemSpec must appear as type class hypotheses in Lean (e.g., ProblemSpec `StrictConvex` maps to Lean `StrictConvexOn`)
- The theorem statement must match the ProblemSpec objective (direction, expression, target variable)
- Inconsistencies between ProblemSpec and scaffold indicate a scaffolding error or manual corruption of the generated output
