## Planning Rules for Proof Formalization Tasks

### Model Proof Obligations as Tasks

Each `sorry` site or theorem in the scaffolded Lean output maps to one implementation task. To enumerate proof obligations:

- Inspect the scaffolded `.lean` output for `sorry` tokens
- Read the `.lean.meta.json` metadata file for structured goal mappings
- Each sorry site or theorem statement becomes a task that the executor will address via AXLE tool calls

### Scope Tactic Work Per Task

Each task should address one sorry site or one theorem:

- Do not batch multiple unrelated proof obligations into a single task
- Closely related obligations may share a task -- for example, a theorem and a lemma it directly depends on
- A task's scope is the tactic work needed to replace one sorry with a verified proof body
- Include the expected tactic iteration budget in the task (default: 8 attempts per goal)

### AXLE Tool Dependencies

Identify which AXLE tools each task requires:

- **Simple proofs**: `check` + `verify_proof` (compile, try tactics, verify)
- **Moderate proofs**: `check` + `repair_proofs` + `verify_proof` (add automated repair)
- **Complex proofs**: `check` + `repair_proofs` + `have2lemma` + `theorem2sorry` + `verify_proof` (add decomposition)
- Every task requires at minimum `check` for compilation feedback and `verify_proof` for final verification

### Task Ordering

Order tasks to respect proof dependencies:

- Tasks for lemmas must precede tasks for theorems that depend on those lemmas
- Independent proof obligations can be listed in any order
- If the design document specifies proof dependencies between sorry sites, reflect those dependencies in task ordering
- The Conjecture stage (running `formalconstruct scaffold`) must complete before any Proof stage tasks begin
