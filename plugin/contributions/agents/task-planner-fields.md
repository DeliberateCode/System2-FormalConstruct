## Per-Task Fields for Proof Formalization

Each proof task should include these domain-specific fields in addition to standard task fields.

### `target_sorry_site`

Identifies the sorry location to be resolved:

- **File**: The `.lean` file containing the sorry
- **Line**: The line number of the sorry token
- **Theorem name**: The enclosing theorem or lemma declaration
- **Sorry index**: If a theorem contains multiple sorry sites, the index within that theorem (0-based)

### `required_axle_tools`

Array of AXLE tool names the task is expected to use:

- Simple proofs: `["check", "verify_proof"]`
- Proofs needing automated repair: `["check", "repair_proofs", "verify_proof"]`
- Proofs needing decomposition: `["check", "repair_proofs", "have2lemma", "theorem2sorry", "verify_proof"]`

### `tactic_budget`

Number of tactic attempts allocated for this sorry site:

- Default: 8 attempts per goal
- Reduce to 4 for obligations expected to yield to simple tactics (ring, linarith, simp)
- Increase to 12 for known-hard proofs where exploration is warranted
- This budget applies before escalation to `repair_proofs`

### `expected_strategy`

The anticipated proof approach for this sorry site:

- **`direct_tactic`**: Simple closure expected via ring, linarith, simp, or a single exact application
- **`automation`**: Closure expected via aesop, grind, exact?, or similar search tactics
- **`decomposition`**: Proof likely requires splitting via have2lemma before individual sub-goals can be closed
