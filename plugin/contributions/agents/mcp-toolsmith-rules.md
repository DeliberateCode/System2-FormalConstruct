## AXLE Tool Surface Design Principles

When designing or reviewing MCP tool interfaces for the AXLE Lean engine, apply these principles to maintain a consistent, predictable tool surface.

## Explicit Environment Parameter

Every AXLE tool call requires an `environment` string parameter (e.g., `"lean-4.29.0"`). The server does not assume a default environment. Omitting the environment parameter is an error. Tool schemas must mark `environment` as required, not optional.

## Separate Response Arrays

AXLE tool responses include two distinct message arrays:

- `lean_messages`: raw Lean compiler output (errors, warnings, infos including goal states after the turnstile).
- `tool_messages`: AXLE-specific validation and diagnostics (repair outcomes, declaration extraction results, normalization changes).

Consumers must read both arrays. A response with empty `lean_messages` and non-empty `tool_messages` (or vice versa) is valid and meaningful.

## One Tool Per Lean Operation

Tool granularity follows the principle of one tool per distinct Lean operation. The AXLE tool surface consists of:

- `check` -- compile Lean source, report errors and goal states.
- `verify_proof` -- strict verification that rejects any source containing sorry.
- `repair_proofs` -- automated repair with configurable strategies and terminal tactics.
- `normalize` -- format Lean source to canonical style.
- `extract_decls` -- split source into individual declarations.
- `theorem2sorry` -- reset theorem proofs to sorry placeholders.
- `have2lemma` -- extract have-block sub-goals as standalone lemmas.

Do not merge these into a single multi-mode tool. Each tool has a single responsibility and a distinct parameter schema.

## Idempotent vs. Transformative Operations

- **Idempotent read operations**: `check`, `verify_proof`, `normalize`, and `extract_decls` do not modify persisted state. Calling them multiple times with the same input produces the same output. They are safe to retry on transient failures.
- **Transformative operations**: `repair_proofs`, `theorem2sorry`, and `have2lemma` return transformed content in the response body but do not persist the transformation. The caller is responsible for applying the returned content to subsequent tool calls.
