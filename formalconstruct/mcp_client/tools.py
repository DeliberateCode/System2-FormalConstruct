"""Async tool wrappers for the 7 AXLE MCP tools.

Each method calls ``self._conn.send_request(tool_name, params)``,
passes the raw response through the matching ``AxleResponseParser.parse_*``
method, and includes ``environment: self._config.lean_environment`` in
every call.

Retry logic lives in ``_call_with_retry`` which retries only on
:class:`AxleTransientError` (HTTP 429, 503, transport timeout/reset)
with exponential backoff + jitter. Non-transient errors propagate
immediately.
"""

from __future__ import annotations

import asyncio
import random
import time

from formalconstruct.core.config import AxleConfig
from formalconstruct.core.exceptions import (
    AxleRateLimitedError,
    AxleRetriesExhaustedError,
    AxleTransientError,
)
from formalconstruct.mcp_client.connection import AxleMcpConnection
from formalconstruct.mcp_client.parsers import AxleResponseParser
from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleExtractDeclsResult,
    AxleHave2LemmaResult,
    AxleNormalizeResult,
    AxleRepairResult,
    AxleTheorem2SorryResult,
    AxleVerifyResult,
)


class AxleToolClient:
    """Async wrappers for all 7 AXLE tools."""

    def __init__(
        self,
        connection: AxleMcpConnection,
        config: AxleConfig | None = None,
    ) -> None:
        self._conn = connection
        self._config = config or AxleConfig()

    async def normalize(self, content: str) -> AxleNormalizeResult:
        """Standardize Lean file formatting.

        Params: content, environment.
        """
        return await self._call_with_retry(
            "normalize",
            {"content": content, "environment": self._config.lean_environment},
            AxleResponseParser.parse_normalize,
        )

    async def check(self, content: str) -> AxleCheckResult:
        """Rapid linter for syntax, identifiers, type-checking.

        Params: content, environment.
        """
        return await self._call_with_retry(
            "check",
            {"content": content, "environment": self._config.lean_environment},
            AxleResponseParser.parse_check,
        )

    async def verify_proof(
        self, content: str, formal_statement: str
    ) -> AxleVerifyResult:
        """Strict verification -- no sorry, no unsafe native code.

        Params: content, formal_statement, environment.
        The formal_statement is the full Lean file with the theorem
        body replaced by ``sorry`` -- AXLE checks that the proof in
        *content* proves exactly this statement.
        """
        return await self._call_with_retry(
            "verify_proof",
            {
                "content": content,
                "formal_statement": formal_statement,
                "environment": self._config.lean_environment,
            },
            AxleResponseParser.parse_verify,
        )

    async def repair_proofs(
        self,
        content: str,
        *,
        theorems_only: bool = False,
        ignore_imports: bool = False,
        repairs: list[str] | None = None,
        terminal_tactics: list[str] | None = None,
    ) -> AxleRepairResult:
        """Automated proof repair.

        Params: content, environment, theorems_only, ignore_imports,
                repairs, terminal_tactics.
        """
        if repairs is None:
            repairs = [
                "remove_extraneous_tactics",
                "replace_unsafe_tactics",
                "apply_terminal_tactics",
            ]
        if terminal_tactics is None:
            terminal_tactics = [
                "grind",
                "aesop",
                "simp",
                "ring",
                "linarith",
                "positivity",
            ]
        return await self._call_with_retry(
            "repair_proofs",
            {
                "content": content,
                "environment": self._config.lean_environment,
                "theorems_only": theorems_only,
                "ignore_imports": ignore_imports,
                "repairs": repairs,
                "terminal_tactics": terminal_tactics,
            },
            AxleResponseParser.parse_repair,
        )

    async def extract_decls(self, content: str) -> AxleExtractDeclsResult:
        """Split verified file into individual declarations.

        Params: content, environment.
        """
        return await self._call_with_retry(
            "extract_decls",
            {"content": content, "environment": self._config.lean_environment},
            AxleResponseParser.parse_extract_decls,
        )

    async def theorem2sorry(self, content: str) -> AxleTheorem2SorryResult:
        """Replace proofs with sorry for macro replan.

        Params: content, environment.
        """
        return await self._call_with_retry(
            "theorem2sorry",
            {"content": content, "environment": self._config.lean_environment},
            AxleResponseParser.parse_theorem2sorry,
        )

    async def have2lemma(self, content: str) -> AxleHave2LemmaResult:
        """Extract have-sub-goals as standalone lemmas.

        Params: content, environment.
        """
        return await self._call_with_retry(
            "have2lemma",
            {"content": content, "environment": self._config.lean_environment},
            AxleResponseParser.parse_have2lemma,
        )

    async def _call_with_retry(
        self,
        tool_name: str,
        params: dict,
        parser,
    ):
        """Retry logic with exponential backoff.

        - Retries on: :class:`AxleTransientError` (HTTP 429, 503,
          transport timeout/reset)
        - Does not retry on: validation errors, schema errors,
          Lean type errors (non-transient)
        - Honors ``Retry-After`` on :class:`AxleRateLimitedError`
        - Max retries: ``config.max_retries`` (default 3)
        - Initial delay: ``config.initial_delay_s`` (default 1.0)
        - Multiplier: ``config.backoff_multiplier`` (default 2.0)
        - Max delay: ``config.max_delay_s`` (default 10.0)
        - Jitter: random uniform ``[0, current_delay * 0.5]``
        - Per-call timeout: handled by the connection layer
        """
        last_error: AxleTransientError | None = None
        start = time.monotonic()
        delay = self._config.initial_delay_s

        for attempt in range(1 + self._config.max_retries):
            try:
                raw = await self._conn.send_request(tool_name, params)
                return parser(raw)
            except AxleTransientError as exc:
                last_error = exc
                if attempt >= self._config.max_retries:
                    break
                # Honor Retry-After header for rate-limited errors
                if isinstance(exc, AxleRateLimitedError) and exc.retry_after is not None:
                    wait = exc.retry_after
                else:
                    jitter = random.uniform(0, delay * 0.5)  # noqa: S311
                    wait = min(delay + jitter, self._config.max_delay_s)
                    delay *= self._config.backoff_multiplier
                await asyncio.sleep(wait)

        elapsed = time.monotonic() - start
        if last_error is None:
            raise AxleRetriesExhaustedError(
                original_error=AxleTransientError("no attempts made"),
                retries=self._config.max_retries,
                elapsed=elapsed,
            )
        raise AxleRetriesExhaustedError(
            original_error=last_error,
            retries=self._config.max_retries,
            elapsed=elapsed,
        )
