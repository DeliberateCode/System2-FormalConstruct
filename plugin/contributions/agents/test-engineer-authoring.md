## Test Authoring Rules for Proof Formalization

### Golden Corpus

Maintain a set of known-good narrative-to-proof pairs that serve as regression anchors:

- Each golden entry includes: narrative text, ProblemSpec JSON, scaffolded Lean (with sorry), and verified Lean (sorry-free)
- When scaffolding logic or domain mappers change, re-verify all golden corpus entries
- Golden entries cover each supported domain: continuous optimization, non-cooperative game theory, cooperative game theory, and discrete domains
- Add a new golden entry whenever a novel proof pattern is successfully verified

### Compilation-Check Tests

For scaffolded output (before sorry replacement), write tests that confirm compilability:

- Call the AXLE `check` tool on each scaffolded `.lean` file
- Scaffolding must always produce compilable Lean -- a compilation failure in scaffolded output indicates a scaffolding bug
- Test that `check` returns no errors (warnings are acceptable for sorry-containing source)
- Include scaffolded output from each supported domain in the compilation test set

### Sorry-Free Assertion Tests

For completed proofs, write tests that assert all three conditions:

- `verify_proof` returns `verified: true` for the Lean source
- The source contains zero `sorry` tokens (text search outside comments)
- The source contains zero `unsafe` keywords

### ProblemSpec Validation Tests

Maintain tests that validate known ProblemSpec JSON files against the schema:

- Run `formalconstruct validate` on each ProblemSpec in the golden corpus
- Validate that schema-conforming ProblemSpec files produce no validation errors
- Include negative tests: ProblemSpec files with intentional errors should produce specific validation error messages
- Cover each supported `problem_domain` value in the validation test set
