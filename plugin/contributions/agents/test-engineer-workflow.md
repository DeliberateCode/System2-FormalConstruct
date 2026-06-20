## Verification Workflow for Proof Formalization

### Primary Verification Gate

Use the AXLE `verify_proof` tool as the primary verification for Lean output:

- Call `verify_proof` with the complete Lean source and `environment: "lean-4.29.0"`
- `verify_proof` rejects any source containing `sorry` -- this is the strictest available check
- A result of `okay: true` confirms the proof is complete and kernel-verified
- A result of `okay: false` means the proof has unresolved obligations or verification errors

### Compilation Before Verification

Before calling `verify_proof`, call the AXLE `check` tool to confirm the Lean source compiles:

- Compilation failures must be fixed before attempting verification
- This two-step approach (check then verify_proof) provides better error localization
- `check` returns `lean_messages` with compiler errors and `tool_messages` with goal states
- Fix all compilation errors reported by `check` before proceeding to `verify_proof`

### Sorry-Free Validation

As a defense-in-depth check, grep the final Lean source for the literal string `sorry` outside of comments:

- The `verify_proof` tool catches sorry tokens, but an explicit text check provides an independent validation layer
- Also check for `admit` and `native_decide` (unless explicitly justified in the design)
- Any sorry token in the final deliverable is a verification failure

### Regression Detection

If a previously verified proof breaks after changes (e.g., upstream definition modifications, Mathlib import changes):

- Classify as a non-local regression
- Record the previously passing verification and the current failure
- Escalate to the regression loop rather than attempting local fixes
- Re-verification of all proofs in the project may be necessary after shared definition changes
