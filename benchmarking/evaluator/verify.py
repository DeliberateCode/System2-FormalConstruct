"""Verification of agent outputs using AXLE MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of verifying an agent's Lean output."""

    problem_id: str
    verified: bool
    sorry_free: bool
    compiles: bool
    error_details: str = ""

    def to_dict(self) -> dict:
        return {
            "problem_id": self.problem_id,
            "verified": self.verified,
            "sorry_free": self.sorry_free,
            "compiles": self.compiles,
            "error_details": self.error_details,
        }


def check_sorry_free(lean_source: str) -> bool:
    """Check that no sorry tokens remain in the source."""
    import re
    return not bool(re.search(r"\bsorry\b", lean_source))


async def verify_with_axle(
    problem_id: str,
    lean_source: str,
    formal_statement: str,
) -> VerificationResult:
    """Verify agent output via AXLE MCP server.

    Calls verify_proof with the agent's completed source and the original
    formal_statement (with sorry) to confirm the proof is valid.

    This requires the AXLE MCP server to be accessible. If not available,
    falls back to static analysis (sorry-freedom + syntax check).
    """
    sorry_free = check_sorry_free(lean_source)

    if not sorry_free:
        return VerificationResult(
            problem_id=problem_id,
            verified=False,
            sorry_free=False,
            compiles=False,
            error_details="Source contains sorry tokens",
        )

    axle_key = os.environ.get("AXLE_API_KEY")
    if not axle_key:
        return VerificationResult(
            problem_id=problem_id,
            verified=False,
            sorry_free=True,
            compiles=False,
            error_details="AXLE_API_KEY not set; cannot verify. Marking as sorry-free only.",
        )

    try:
        result = await _call_axle_verify(lean_source, formal_statement)
        return VerificationResult(
            problem_id=problem_id,
            verified=result.get("okay", False),
            sorry_free=True,
            compiles=result.get("compiles", False),
            error_details=result.get("error", ""),
        )
    except Exception as e:
        return VerificationResult(
            problem_id=problem_id,
            verified=False,
            sorry_free=True,
            compiles=False,
            error_details=f"AXLE verification error: {e}",
        )


async def _call_axle_verify(content: str, formal_statement: str) -> dict:
    """Call AXLE verify_proof via the MCP server.

    Routes through the formalconstruct MCP client, which reads ``AXLE_API_KEY``
    from the environment and passes it to the subprocess via its env (never on a
    command line, and never to an unvalidated host). There is no HTTP fallback:
    if the client is unavailable, that is a hard configuration error rather than
    a reason to leak the key onto a ``curl`` argv.
    """
    from formalconstruct.mcp_client.connection import AxleMcpConnection
    from formalconstruct.mcp_client.tools import AxleToolClient

    async with AxleMcpConnection() as conn:
        result = await AxleToolClient(conn).verify_proof(content, formal_statement)
    return {
        "okay": result.verified,
        "compiles": not result.has_errors,
        "error": "; ".join(result.lean_messages.errors + result.tool_messages.errors),
    }
