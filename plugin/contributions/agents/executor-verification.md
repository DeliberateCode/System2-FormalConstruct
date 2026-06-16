## Proof Verification Rules

### Final Verification Gate

Once all `sorry` tokens have been replaced with tactics, call `verify_proof` with `content` (the proved file), `formal_statement` (the scaffolded file with `sorry` placeholders), and `environment: "lean-4.29.0"`. The `verify_proof` tool is the strictest check: it rejects any source containing `sorry`.

If the response returns `okay: true`, the proof is complete. Deliver the verified Lean source.

### Structured Failure Reporting

If `verify_proof` returns failure, or if sorry replacement could not be completed within the tactic and repair budgets, report a structured failure containing:

- **Final goal state**: The turnstile expression from the last `check` response for each unresolved goal.
- **Tactics attempted**: The ordered list of tactics tried for each goal, including repair strategies applied.
- **Failure classification**: One of:
  - **Schema gap**: The ProblemSpec does not capture enough mathematical structure for this proof (e.g., missing properties, insufficient type information).
  - **Mathlib gap**: A required lemma or definition is not available in the pinned Lean/Mathlib version (`lean-4.29.0`).
  - **Proof search exhaustion**: Tactic and repair budgets were consumed without finding a valid proof.

### No Partial Delivery

Either the proof is complete (`verify_proof` returns `okay: true` with zero `sorry` tokens) or it is a reported failure with classification. Never deliver Lean source that fails `verify_proof` as a completed proof. Incomplete work is reported as failure, not as partial success.
