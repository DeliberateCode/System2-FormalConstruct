"""Unit tests for AxleToolClient async tool wrappers.

Uses a mock AxleMcpConnection to validate:
- Each tool method calls send_request with the correct tool name and params
- Every call includes environment from AxleConfig
- Responses are parsed through the correct AxleResponseParser method
- Retry logic retries on transient errors only
- Retry-After header is honored
- Non-transient errors propagate immediately
- AxleRetriesExhaustedError raised when retries exhausted
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from formalconstruct.core.config import AxleConfig
from formalconstruct.core.exceptions import (
    AxleInvalidArgumentError,
    AxleRateLimitedError,
    AxleRetriesExhaustedError,
    AxleTimeoutError,
    AxleUnavailableError,
    AxleValidationError,
)
from formalconstruct.mcp_client.tools import AxleToolClient
from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleExtractDeclsResult,
    AxleHave2LemmaResult,
    AxleNormalizeResult,
    AxleRepairResult,
    AxleTheorem2SorryResult,
    AxleVerifyResult,
)


# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------


def _make_mock_connection(
    responses: list[dict | Exception] | None = None,
) -> AsyncMock:
    """Create a mock AxleMcpConnection with queued send_request responses.

    Each entry in *responses* is either a dict (returned) or an Exception
    (raised). Calls pop from the front of the list.
    """
    conn = AsyncMock()
    if responses is None:
        responses = [{}]
    side_effects: list[Any] = []
    for r in responses:
        if isinstance(r, Exception):
            side_effects.append(r)
        else:
            side_effects.append(r)
    conn.send_request = AsyncMock(side_effect=side_effects)
    return conn


def _empty_message_set() -> dict:
    return {"errors": [], "warnings": [], "infos": []}


def _ok_check_response() -> dict:
    return {
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


def _ok_verify_response(verified: bool = True) -> dict:
    return {
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
        "verified": verified,
    }


def _ok_repair_response(okay: bool = True) -> dict:
    return {
        "okay": okay,
        "content": "-- repaired",
        "repair_stats": {},
        "timings": {},
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


def _ok_normalize_response() -> dict:
    return {
        "content": "-- normalized",
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


def _ok_extract_decls_response() -> dict:
    return {
        "declarations": [{"name": "myThm", "kind": "theorem", "content": "..."}],
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


def _ok_theorem2sorry_response() -> dict:
    return {
        "content": "-- sorry'd",
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


def _ok_have2lemma_response() -> dict:
    return {
        "content": "-- with lemmas",
        "lemmas": ["lemma1"],
        "lean_messages": _empty_message_set(),
        "tool_messages": _empty_message_set(),
    }


@pytest.fixture
def config() -> AxleConfig:
    """Configuration with fast retry for tests."""
    return AxleConfig(
        lean_environment="lean-4.29.0",
        max_retries=3,
        initial_delay_s=0.001,
        backoff_multiplier=2.0,
        max_delay_s=0.01,
    )


# ===========================================================================
# Tool method tests: correct tool name and params sent
# ===========================================================================


class TestToolMethodParams:
    """Each tool method sends the correct tool name and includes environment."""

    @pytest.mark.asyncio
    async def test_normalize_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_normalize_response()])
        client = AxleToolClient(conn, config)
        result = await client.normalize("import Mathlib")
        assert isinstance(result, AxleNormalizeResult)
        conn.send_request.assert_called_once_with(
            "normalize",
            {"content": "import Mathlib", "environment": "lean-4.29.0"},
        )

    @pytest.mark.asyncio
    async def test_check_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_check_response()])
        client = AxleToolClient(conn, config)
        result = await client.check("theorem myThm : True := by trivial")
        assert isinstance(result, AxleCheckResult)
        conn.send_request.assert_called_once_with(
            "check",
            {
                "content": "theorem myThm : True := by trivial",
                "environment": "lean-4.29.0",
            },
        )

    @pytest.mark.asyncio
    async def test_verify_proof_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_verify_response()])
        client = AxleToolClient(conn, config)
        result = await client.verify_proof(
            "theorem myThm : True := by trivial",
            "theorem myThm : True := by sorry",
        )
        assert isinstance(result, AxleVerifyResult)
        assert result.verified is True
        conn.send_request.assert_called_once_with(
            "verify_proof",
            {
                "content": "theorem myThm : True := by trivial",
                "formal_statement": "theorem myThm : True := by sorry",
                "environment": "lean-4.29.0",
            },
        )

    @pytest.mark.asyncio
    async def test_repair_proofs_default_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_repair_response()])
        client = AxleToolClient(conn, config)
        result = await client.repair_proofs("import Mathlib\ntheorem t := by sorry")
        assert isinstance(result, AxleRepairResult)
        assert result.okay is True
        call_args = conn.send_request.call_args
        assert call_args[0][0] == "repair_proofs"
        params = call_args[0][1]
        assert params["environment"] == "lean-4.29.0"
        assert params["repairs"] == [
            "remove_extraneous_tactics",
            "replace_unsafe_tactics",
            "apply_terminal_tactics",
        ]
        assert params["terminal_tactics"] == [
            "grind",
            "aesop",
            "simp",
            "ring",
            "linarith",
            "positivity",
        ]
        assert params["theorems_only"] is False
        assert params["ignore_imports"] is False

    @pytest.mark.asyncio
    async def test_repair_proofs_custom_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_repair_response()])
        client = AxleToolClient(conn, config)
        await client.repair_proofs(
            "content",
            theorems_only=True,
            ignore_imports=True,
            repairs=["apply_terminal_tactics"],
            terminal_tactics=["simp"],
        )
        params = conn.send_request.call_args[0][1]
        assert params["theorems_only"] is True
        assert params["ignore_imports"] is True
        assert params["repairs"] == ["apply_terminal_tactics"]
        assert params["terminal_tactics"] == ["simp"]

    @pytest.mark.asyncio
    async def test_extract_decls_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_extract_decls_response()])
        client = AxleToolClient(conn, config)
        result = await client.extract_decls("import Mathlib")
        assert isinstance(result, AxleExtractDeclsResult)
        assert len(result.declarations) == 1
        conn.send_request.assert_called_once_with(
            "extract_decls",
            {"content": "import Mathlib", "environment": "lean-4.29.0"},
        )

    @pytest.mark.asyncio
    async def test_theorem2sorry_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_theorem2sorry_response()])
        client = AxleToolClient(conn, config)
        result = await client.theorem2sorry("theorem t := by ring")
        assert isinstance(result, AxleTheorem2SorryResult)
        assert result.content == "-- sorry'd"
        conn.send_request.assert_called_once_with(
            "theorem2sorry",
            {"content": "theorem t := by ring", "environment": "lean-4.29.0"},
        )

    @pytest.mark.asyncio
    async def test_have2lemma_params(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_have2lemma_response()])
        client = AxleToolClient(conn, config)
        result = await client.have2lemma("theorem t := by have h := sorry; exact h")
        assert isinstance(result, AxleHave2LemmaResult)
        assert result.lemmas == ["lemma1"]
        conn.send_request.assert_called_once_with(
            "have2lemma",
            {
                "content": "theorem t := by have h := sorry; exact h",
                "environment": "lean-4.29.0",
            },
        )


# ===========================================================================
# Environment parameter tests
# ===========================================================================


class TestEnvironmentParam:
    """Every AXLE call includes the configured lean_environment."""

    @pytest.mark.asyncio
    async def test_custom_environment_propagated(self) -> None:
        """A non-default lean_environment is passed to every call."""
        custom_config = AxleConfig(
            lean_environment="lean-4.30.0",
            max_retries=0,
            initial_delay_s=0.001,
        )
        conn = _make_mock_connection([_ok_check_response()])
        client = AxleToolClient(conn, custom_config)
        await client.check("content")
        params = conn.send_request.call_args[0][1]
        assert params["environment"] == "lean-4.30.0"


# ===========================================================================
# Response parsing tests
# ===========================================================================


class TestResponseParsing:
    """Responses are parsed through the correct AxleResponseParser method."""

    @pytest.mark.asyncio
    async def test_check_response_has_errors(self, config: AxleConfig) -> None:
        error_response = {
            "lean_messages": {"errors": ["type mismatch"], "warnings": [], "infos": []},
            "tool_messages": _empty_message_set(),
        }
        conn = _make_mock_connection([error_response])
        client = AxleToolClient(conn, config)
        result = await client.check("bad code")
        assert isinstance(result, AxleCheckResult)
        assert result.has_errors
        assert "type mismatch" in result.lean_messages.errors

    @pytest.mark.asyncio
    async def test_verify_false(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_verify_response(verified=False)])
        client = AxleToolClient(conn, config)
        result = await client.verify_proof("sorry code", "sorry stmt")
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_repair_content_returned(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_repair_response()])
        client = AxleToolClient(conn, config)
        result = await client.repair_proofs("content")
        assert result.content == "-- repaired"

    @pytest.mark.asyncio
    async def test_normalize_content_returned(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_normalize_response()])
        client = AxleToolClient(conn, config)
        result = await client.normalize("content")
        assert result.content == "-- normalized"


# ===========================================================================
# Retry logic tests
# ===========================================================================


class TestRetryLogic:
    """Retry behavior: transient errors retried, non-transient propagated."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limited(self, config: AxleConfig) -> None:
        """HTTP 429 triggers retry; success on 2nd attempt."""
        conn = _make_mock_connection([
            AxleRateLimitedError("rate limited"),
            _ok_check_response(),
        ])
        client = AxleToolClient(conn, config)
        result = await client.check("content")
        assert isinstance(result, AxleCheckResult)
        assert conn.send_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_unavailable(self, config: AxleConfig) -> None:
        """HTTP 503 triggers retry; success on 2nd attempt."""
        conn = _make_mock_connection([
            AxleUnavailableError("unavailable"),
            _ok_check_response(),
        ])
        client = AxleToolClient(conn, config)
        result = await client.check("content")
        assert isinstance(result, AxleCheckResult)
        assert conn.send_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, config: AxleConfig) -> None:
        """Transport timeout triggers retry."""
        conn = _make_mock_connection([
            AxleTimeoutError("timed out"),
            _ok_check_response(),
        ])
        client = AxleToolClient(conn, config)
        result = await client.check("content")
        assert isinstance(result, AxleCheckResult)
        assert conn.send_request.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_validation_error(self, config: AxleConfig) -> None:
        """Validation errors are not retried."""
        conn = _make_mock_connection([
            AxleValidationError("bad argument"),
        ])
        client = AxleToolClient(conn, config)
        with pytest.raises(AxleValidationError, match="bad argument"):
            await client.check("content")
        assert conn.send_request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_invalid_argument(self, config: AxleConfig) -> None:
        """AxleInvalidArgument is not retried."""
        conn = _make_mock_connection([
            AxleInvalidArgumentError("env mismatch"),
        ])
        client = AxleToolClient(conn, config)
        with pytest.raises(AxleInvalidArgumentError, match="env mismatch"):
            await client.check("content")
        assert conn.send_request.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_exhausted(self, config: AxleConfig) -> None:
        """AxleRetriesExhaustedError raised after max retries."""
        conn = _make_mock_connection([
            AxleRateLimitedError("limited"),
            AxleRateLimitedError("limited"),
            AxleRateLimitedError("limited"),
            AxleRateLimitedError("limited"),
        ])
        client = AxleToolClient(conn, config)
        with pytest.raises(AxleRetriesExhaustedError) as exc_info:
            await client.check("content")
        err = exc_info.value
        assert err.retries_attempted == 3
        assert isinstance(err.original_error, AxleRateLimitedError)
        assert err.total_elapsed >= 0
        # 1 initial + 3 retries = 4 calls
        assert conn.send_request.call_count == 4

    @pytest.mark.asyncio
    async def test_retry_after_honored(self, config: AxleConfig) -> None:
        """Retry-After header overrides computed backoff delay."""
        rate_err = AxleRateLimitedError("limited", retry_after=0.001)
        conn = _make_mock_connection([rate_err, _ok_check_response()])
        client = AxleToolClient(conn, config)
        with patch("formalconstruct.mcp_client.tools.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.check("content")
        assert isinstance(result, AxleCheckResult)
        # The sleep should have used the Retry-After value (0.001), not computed backoff
        mock_sleep.assert_called_once()
        actual_delay = mock_sleep.call_args[0][0]
        assert actual_delay == pytest.approx(0.001)

    @pytest.mark.asyncio
    async def test_retry_zero_retries_config(self) -> None:
        """With max_retries=0, transient error propagates immediately."""
        no_retry_config = AxleConfig(max_retries=0, initial_delay_s=0.001)
        conn = _make_mock_connection([AxleRateLimitedError("limited")])
        client = AxleToolClient(conn, no_retry_config)
        with pytest.raises(AxleRetriesExhaustedError) as exc_info:
            await client.check("content")
        assert exc_info.value.retries_attempted == 0
        assert conn.send_request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_multiple_failures(self, config: AxleConfig) -> None:
        """Success on the 3rd attempt (after 2 transient failures)."""
        conn = _make_mock_connection([
            AxleUnavailableError("503"),
            AxleTimeoutError("timeout"),
            _ok_normalize_response(),
        ])
        client = AxleToolClient(conn, config)
        result = await client.normalize("content")
        assert isinstance(result, AxleNormalizeResult)
        assert conn.send_request.call_count == 3


# ===========================================================================
# Default config tests
# ===========================================================================


class TestDefaultConfig:
    """AxleToolClient uses AxleConfig defaults when none provided."""

    @pytest.mark.asyncio
    async def test_default_config_used(self) -> None:
        conn = _make_mock_connection([_ok_check_response()])
        client = AxleToolClient(conn)
        await client.check("content")
        params = conn.send_request.call_args[0][1]
        # Default lean_environment from AxleConfig
        assert params["environment"] == "lean-4.29.0"


# ===========================================================================
# All 7 tools produce correct result types
# ===========================================================================


class TestAllToolResultTypes:
    """Each of the 7 tools returns the correct typed result model."""

    @pytest.mark.asyncio
    async def test_normalize_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_normalize_response()])
        client = AxleToolClient(conn, config)
        result = await client.normalize("c")
        assert isinstance(result, AxleNormalizeResult)

    @pytest.mark.asyncio
    async def test_check_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_check_response()])
        client = AxleToolClient(conn, config)
        result = await client.check("c")
        assert isinstance(result, AxleCheckResult)

    @pytest.mark.asyncio
    async def test_verify_proof_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_verify_response()])
        client = AxleToolClient(conn, config)
        result = await client.verify_proof("c", "s")
        assert isinstance(result, AxleVerifyResult)

    @pytest.mark.asyncio
    async def test_repair_proofs_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_repair_response()])
        client = AxleToolClient(conn, config)
        result = await client.repair_proofs("c")
        assert isinstance(result, AxleRepairResult)

    @pytest.mark.asyncio
    async def test_extract_decls_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_extract_decls_response()])
        client = AxleToolClient(conn, config)
        result = await client.extract_decls("c")
        assert isinstance(result, AxleExtractDeclsResult)

    @pytest.mark.asyncio
    async def test_theorem2sorry_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_theorem2sorry_response()])
        client = AxleToolClient(conn, config)
        result = await client.theorem2sorry("c")
        assert isinstance(result, AxleTheorem2SorryResult)

    @pytest.mark.asyncio
    async def test_have2lemma_result_type(self, config: AxleConfig) -> None:
        conn = _make_mock_connection([_ok_have2lemma_response()])
        client = AxleToolClient(conn, config)
        result = await client.have2lemma("c")
        assert isinstance(result, AxleHave2LemmaResult)
