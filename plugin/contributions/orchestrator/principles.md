- Three-stage formalization pipeline. Proof formalization follows a strict
  three-stage pipeline. Axioms: the LLM reads the mathematical narrative and
  extracts a structured ProblemSpec JSON object capturing the problem domain,
  spaces, variables, functions, and objective. This is direct LLM extraction --
  no external tool call is needed to produce the ProblemSpec, only to validate
  it afterward via the CLI (`formalconstruct validate`). Conjecture: a
  deterministic Python CLI command (`formalconstruct scaffold`) transforms the
  validated ProblemSpec into Lean 4 source code annotated with sorry at each
  proof obligation site, plus a `.lean.meta.json` metadata file. This stage is
  mechanical and reproducible -- the same ProblemSpec always produces the same
  scaffolding. Proof: the executor systematically replaces each sorry
  placeholder with verified Lean tactics by calling AXLE MCP tools in a
  compile-check-repair loop. Each stage is a distinct mode of operation. Stage
  boundaries are not crossed: extraction logic does not leak into scaffolding,
  and scaffolding does not attempt proving.

- Formalize auxiliary agent. The `formalize` agent handles the full pipeline
  end-to-end when invoked directly via `@formalize`. When operating within the
  System2 pipeline, the stages map to System2's workflow: the Axioms stage
  aligns with spec-coordination and requirements, the Conjecture stage aligns
  with design and task planning, and the Proof stage aligns with executor
  implementation. The orchestrator may delegate to the formalize agent for
  self-contained formalization tasks, or decompose the stages across pipeline
  agents for larger projects.

- AXLE as external proof engine. All Lean 4 compilation and verification
  occurs through AXLE MCP tool calls. The available tools are: check (rapid
  compilation check), verify_proof (strict verification that rejects sorry --
  requires both content and formal_statement parameters), repair_proofs
  (automated repair with configurable strategies and terminal tactics),
  normalize (format Lean source), extract_decls (split source into individual
  declarations), theorem2sorry (reset proofs to sorry placeholders), and
  have2lemma (extract sub-goals as standalone lemmas). No local Lean toolchain
  is installed or invoked. The AXLE server requires the AXLE_API_KEY
  environment variable and operates with a pinned lean-4.29.0 environment.
  Every AXLE tool call must include the explicit environment parameter
  `"environment": "lean-4.29.0"`. Responses from AXLE contain two arrays:
  lean_messages (raw compiler output including errors, warnings, and infos) and
  tool_messages (AXLE-specific validation and diagnostics). Both arrays must be
  read to understand the result.

- Tactic discipline and iteration budgets. Proof search is bounded to prevent
  unbounded iteration. For each sorry site, the executor attempts up to 8
  different tactic candidates based on the goal state reported by AXLE check.
  Common tactic patterns include exact applications of Mathlib lemmas, ring,
  linarith, aesop, simp, grind, and exact? (which triggers AXLE-side lemma
  search). If all 8 tactic attempts fail, the executor escalates to
  repair_proofs with strategies (remove_extraneous_tactics,
  replace_unsafe_tactics, apply_terminal_tactics) and terminal tactics (aesop,
  grind, simp, ring, linarith, positivity). At most 2 repair attempts are
  permitted per goal. If repair also fails, the executor decomposes the proof:
  call have2lemma to extract sub-goals as standalone lemmas, call theorem2sorry
  to reset, and attempt a different proof strategy on the smaller obligations.
  These budgets (8 tactics, 2 repairs, then decomposition) are hard limits, not
  guidelines. Exceeding them indicates the proof approach needs
  reconsideration, not more attempts.

- Sorry semantics. In Lean 4, sorry is a built-in tactic that marks an
  unproven proof obligation. It allows the file to compile but flags the proof
  as incomplete -- any theorem proved via sorry is not trustworthy. In the
  formalization pipeline, sorry serves a precise role: the Conjecture stage
  produces Lean source with sorry at every proof site, establishing the theorem
  statements and type-level structure without attempting proofs. The Proof stage
  systematically replaces each sorry with verified tactics, confirming each
  replacement compiles via AXLE check. A proof is complete only when
  verify_proof returns okay: true, which requires zero sorry tokens in the
  source. Any sorry remaining in the final output constitutes a proof failure
  and must be reported as such -- partial proofs with residual sorry are never
  acceptable as final deliverables.

- Structured failure reporting. When proof completion fails after exhausting
  tactic and repair budgets, the executor must produce a structured failure
  report rather than silently abandoning the attempt. The report includes three
  components. First, the final goal state: the turnstile expression from the
  last AXLE check response, showing what remains to be proved. Second, the
  tactics attempted: an ordered list of every tactic tried against that goal,
  including repair strategies. Third, a failure classification drawn from three
  categories: schema gap (the ProblemSpec does not capture enough mathematical
  structure for the proof -- e.g., a missing property or an incorrectly
  classified variable), Mathlib gap (the required lemma or tactic is not
  available in the pinned lean-4.29.0 Mathlib version), or proof search
  exhaustion (the budgets were consumed without finding a valid tactic sequence,
  suggesting the proof may require a fundamentally different approach). This
  classification informs whether the fix is in the ProblemSpec (schema gap),
  requires waiting for upstream Mathlib changes (Mathlib gap), or demands a
  revised proof strategy (exhaustion).
