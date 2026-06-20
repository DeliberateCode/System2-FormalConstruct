## Proof Formalization Requirements in EARS Format

When writing requirements for proof formalization work, apply these domain-specific guardrails to ensure each requirement is precise, testable, and traceable to a proof obligation.

## Event-Driven Requirements (EARS "When" Pattern)

Use the "When [event], the system shall [response]" pattern for verification outcomes.

- When `verify_proof` returns failure for a theorem, the system shall report the final goal state (the turnstile expression) and the ordered list of tactics attempted.
- When `check` returns compilation errors after a tactic substitution, the system shall revert the substitution and try the next tactic in the budget.
- When `repair_proofs` returns `okay: false`, the system shall escalate to decomposition via `have2lemma`.

## State-Driven Requirements (EARS "While" Pattern)

Use the "While [state], the system shall [behavior]" pattern for ongoing proof obligations.

- While sorry tokens remain in the Lean source, the executor shall continue the tactic iteration loop for each unresolved sorry site.
- While the tactic budget for a goal has not been exhausted, the executor shall generate and test candidate tactics before escalating to repair.

## Unwanted-Behavior Requirements (EARS "If/Then" Pattern)

Use the "If [condition], then the system shall [mitigation]" pattern for domain restrictions and error conditions.

- If the narrative domain is not in the supported set (continuous_optimization, non_cooperative_game, cooperative_game), then the system shall report an unsupported-domain error with the detected domain.
- If a ProblemSpec file fails schema validation, then the system shall report each validation error with its field path before proceeding to scaffolding.

## Proof Obligation Requirements

Each formalization goal shall have at least one requirement specifying:

- The target theorem name and its mathematical statement.
- Acceptable proof methods (direct tactic application, automation search, or decomposition via sub-lemmas).
- Verification criteria: `verify_proof` returns `verified: true` and the source contains zero sorry tokens.

## Budget Requirements

Express tactic and repair budgets as numeric constraints in requirements:

- The system shall attempt at most 8 distinct tactics per sorry site before escalating to `repair_proofs`.
- The system shall invoke `repair_proofs` at most 2 times per goal before escalating to decomposition.
- Each budget constraint shall appear as a testable numeric bound, not as vague language such as "several attempts."
