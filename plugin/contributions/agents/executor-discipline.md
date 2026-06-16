## Proof Stage Implementation Discipline

The executor handles the Proof stage of the formalization pipeline: replacing `sorry` placeholders with verified Lean 4 tactics. The upstream stages (Axioms and Conjecture) produce a validated ProblemSpec and compiled Lean scaffolding before the executor receives a proof task.

## Iterative Sorry Replacement via AXLE

Process each `sorry` sequentially using AXLE MCP tools.

### Step 1: Check and Read Goal State

Call `check` with the current Lean source and `environment: "lean-4.29.0"`. Read `tool_messages.infos` for the goal state after the turnstile. The goal state tells you what needs to be proved.

### Step 2: Generate a Candidate Tactic

Based on the goal state, select a candidate tactic. Common patterns:

- Sum of strictly convex and convex functions: `exact StrictConvexOn.add_convexOn h_strict h_convex`
- Simple arithmetic identities: `ring`
- Linear arithmetic: `linarith`
- Automation: `aesop`, `simp`, `grind`
- Lemma search: `exact?` (AXLE will search Mathlib)
- Positivity: `positivity`

### Step 3: Replace and Verify

Replace the first `sorry` with the candidate tactic in the Lean source. Call `check` again with the updated source and `environment: "lean-4.29.0"`.

- If the source compiles cleanly, the tactic is correct. Move to the next `sorry`.
- If there are errors, try a different tactic.

### Step 4: Repeat

Continue steps 1-3 for each remaining `sorry` token until none remain.

### Tactic Iteration Budget

Attempt up to 8 different tactics per goal before escalating to repair. Track which tactics have been tried to avoid repetition.

## AXLE Tool Calling Patterns

All AXLE tools require `environment: "lean-4.29.0"`.

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `check` | Rapid compilation check | `content`, `environment` |
| `verify_proof` | Strict verification (rejects sorry) | `content`, `formal_statement`, `environment` |
| `repair_proofs` | Automated proof repair | `content`, `environment`, `repairs`, `terminal_tactics` |
| `normalize` | Format Lean source | `content`, `environment` |
| `extract_decls` | Split into individual declarations | `content`, `environment` |
| `theorem2sorry` | Reset proofs to sorry | `content`, `environment` |
| `have2lemma` | Extract sub-goals as standalone lemmas | `content`, `environment` |

Responses include two arrays:
- `lean_messages`: raw compiler output (errors, warnings, infos)
- `tool_messages`: AXLE-specific validation and diagnostics

Read both arrays when processing responses.

## Repair Escalation

When 8 tactic attempts fail for a single goal, escalate to automated repair.

### Step 1: Call repair_proofs

```
Tool: repair_proofs
Arguments: {
  "content": "<lean source>",
  "environment": "lean-4.29.0",
  "repairs": [
    "remove_extraneous_tactics",
    "replace_unsafe_tactics",
    "apply_terminal_tactics"
  ],
  "terminal_tactics": ["aesop", "grind", "simp", "ring", "linarith", "positivity"]
}
```

If the response returns `okay: true`, use the repaired content and continue.

### Step 2: Retry or Decompose

At most 2 repair attempts per goal are permitted. If repair does not resolve the goal:

1. Call `have2lemma` to extract sub-goals as standalone lemmas.
2. Call `theorem2sorry` to reset proof attempts on the decomposed structure.
3. Attempt a different proof strategy on the resulting sub-goals.

Each sub-goal inherits its own tactic budget (8 attempts) and repair budget (2 attempts).
