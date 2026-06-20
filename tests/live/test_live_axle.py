"""Live AXLE tests are run via Claude Code's native MCP tool access.

FormalConstruct does not manage the AXLE subprocess directly — Claude Code
calls AXLE MCP tools (check, verify_proof, repair_proofs, etc.) as part of
the Proof stage protocol described in CLAUDE.md.

To test AXLE connectivity, ask Claude Code to run:
    check tool with: {"content": "theorem foo : True := by trivial", "environment": "lean-4.29.0"}
"""
