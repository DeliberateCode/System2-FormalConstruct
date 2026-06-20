# FormalConstruct Development

This repo is a System2 overlay and standalone Claude Code toolkit for Lean 4 proof
formalization. It provides overlay contributions that System2's compose engine injects
into pipeline agents, plus a `formalize` auxiliary agent for direct use in Claude Code.

## Project Structure

```
plugin/                              # Installable overlay unit
├── .claude-plugin/plugin.json       # Plugin identity
├── system2.overlay.json             # Overlay manifest (contribution declarations)
├── contributions/                   # Content files referenced by the manifest
│   ├── orchestrator/
│   │   └── principles.md            # Proof-pipeline operating principles
│   └── agents/                      # Prompt sections for pipeline agents (17 files)
├── agents/
│   └── formalize.md                 # Auxiliary agent: end-to-end proof formalization
formalconstruct/                     # Python package (schemas, mappers, CLI, MCP client)
tests/                               # Package tests + overlay smoke tests
.claude/
├── commands/
│   └── formalize.md                 # Slash command (delegates to formalize agent)
```

## Testing

Package tests:

```bash
pytest tests/ -m "not live"
```

Overlay smoke tests (require `../System2`):

```bash
pytest tests/test_compose_smoke.py
```

## Conventions

- Contribution content files are plain Markdown — no frontmatter, no YAML.
- Each file is self-contained guidance for a specific anchor point in a specific agent.
- Content is prescriptive: tell the agent what to do in the proof-formalization domain.
- Summaries in `system2.overlay.json` must accurately reflect the content file — the
  orchestrator reads the summary to decide whether to include the full content in a delegation.
- Contribution IDs use the `fc-` prefix.
- All IDs must be unique across the manifest.

## Overlay Manifest Schema

The manifest (`plugin/system2.overlay.json`) is validated against System2's
`plugin/schemas/overlay.schema.json`. Valid contribution types: orchestrator principles,
agent prompt sections (keyed by anchor name), spec required sections,
delegation advisory sources, auxiliary agents, and MCP servers.

Valid anchor names per agent are defined in `plugin/schemas/anchor-map.json` in System2.

## Adding Contributions

1. Write the content file in `plugin/contributions/`.
2. Add the contribution declaration to `plugin/system2.overlay.json` with a unique `fc-` prefixed ID.
3. Add the ID to `EXPECTED_CONTRIBUTION_IDS` in `tests/test_compose_smoke.py`.
4. Run smoke tests to validate.
