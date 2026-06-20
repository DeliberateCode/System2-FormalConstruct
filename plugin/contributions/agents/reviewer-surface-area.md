## Surface Area Delta Tracking for Proof Formalization

Track these as surface-area deltas in proof formalization changes.

### ProblemSpec Schema Fields

Report new fields added to the ProblemSpec schema, changed field types, or removed fields. Schema changes affect all downstream consumers: validation, scaffolding, and domain mappers.

### Lean Import Sets

Report Mathlib modules added to or removed from import statements. Import changes may affect compilation time and indicate shifting proof strategies.

### Theorem Signatures

Report changes to theorem or lemma statement names, hypotheses, or conclusions. Signature changes may break downstream proofs that depend on the modified theorem.

### Sorry-Site Count

Report the net change in sorry count: sites added (new proof obligations) vs. sites resolved (sorry replaced with verified tactics). The sorry-site count is the primary progress metric for proof formalization work.
