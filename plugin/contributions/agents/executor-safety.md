## Proof Formalization Safety Rules

All safety constraints apply throughout the proof formalization pipeline.

### No sorry in Final Output

Never produce Lean output containing `sorry` tokens as a final deliverable. `sorry` is only acceptable as an intermediate state during the Proof stage tactic iteration. Any `sorry` remaining when work is reported as complete constitutes a proof failure.

### No Unsafe Native Code

Generated Lean code must not use the `unsafe` keyword or native FFI bindings. All proofs must be kernel-verified. Lean's trusted kernel is the verification authority; circumventing it invalidates the proof.

### Explicit Environment on Every AXLE Call

Every AXLE MCP tool invocation must include `"environment": "lean-4.29.0"`. Never omit the environment parameter. Never substitute a different version unless the user explicitly instructs a version change.

### No Credentials in Source

Never embed API keys, tokens, passwords, or secrets in generated Lean files or ProblemSpec JSON. The `AXLE_API_KEY` is referenced by name in configuration but its value must never appear in source artifacts.
