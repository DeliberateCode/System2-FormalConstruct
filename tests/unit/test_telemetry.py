"""Unit tests for formalconstruct.core.telemetry."""

from __future__ import annotations

import logging

import pytest

from formalconstruct.core.telemetry import (
    log_axle_call,
    log_phase_duration,
    log_repair_stats,
    log_termination,
    sanitize_log_value,
    timed,
)


# ---------------------------------------------------------------------------
# sanitize_log_value
# ---------------------------------------------------------------------------


class TestSanitizeLogValue:
    def test_replaces_secret(self) -> None:
        assert sanitize_log_value("key=abc123xyz", "abc123xyz") == "key=[REDACTED]"

    def test_replaces_multiple_occurrences(self) -> None:
        result = sanitize_log_value("a]secret[b]secret[c", "secret")
        assert result == "a][REDACTED][b][REDACTED][c"

    def test_no_match_returns_original(self) -> None:
        assert sanitize_log_value("nothing here", "absent") == "nothing here"

    def test_empty_secret_returns_original(self) -> None:
        assert sanitize_log_value("value", "") == "value"

    def test_empty_value(self) -> None:
        assert sanitize_log_value("", "secret") == ""


# ---------------------------------------------------------------------------
# @timed decorator
# ---------------------------------------------------------------------------


class TestTimedDecorator:
    async def test_preserves_return_value(self) -> None:
        @timed
        async def add(a: int, b: int) -> int:
            return a + b

        result = await add(3, 4)
        assert result == 7

    async def test_emits_log_with_extra(self, caplog: pytest.LogCaptureFixture) -> None:
        @timed
        async def example() -> str:
            return "done"

        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            await example()

        # Find the timing log record
        timing_records = [
            r for r in caplog.records if hasattr(r, "function_name")
        ]
        assert len(timing_records) == 1
        record = timing_records[0]
        assert record.function_name == "example"
        assert isinstance(record.duration_ms, float)
        assert record.duration_ms >= 0

    async def test_propagates_exception(self) -> None:
        @timed
        async def failing() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await failing()


# ---------------------------------------------------------------------------
# log_axle_call
# ---------------------------------------------------------------------------


class TestLogAxleCall:
    def test_emits_info_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_axle_call(tool="check", duration_ms=123.4, has_errors=False)

        records = [r for r in caplog.records if hasattr(r, "tool")]
        assert len(records) == 1
        record = records[0]
        assert record.tool == "check"
        assert record.duration_ms == 123.4
        assert record.has_errors is False

    def test_accepts_extra_kwargs(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_axle_call(
                tool="verify_proof",
                duration_ms=500.0,
                has_errors=True,
                axle_calls_used=5,
            )

        records = [r for r in caplog.records if hasattr(r, "tool")]
        assert len(records) == 1
        assert records[0].axle_calls_used == 5


# ---------------------------------------------------------------------------
# log_repair_stats
# ---------------------------------------------------------------------------


class TestLogRepairStats:
    def test_emits_log_with_stats(self, caplog: pytest.LogCaptureFixture) -> None:
        stats = {"remove_extraneous_tactics": 2, "replace_unsafe_tactics": 1}
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_repair_stats(stats, strategy="apply_terminal_tactics")

        records = [r for r in caplog.records if hasattr(r, "repair_stats")]
        assert len(records) == 1
        assert records[0].repair_stats == stats
        assert records[0].strategy == "apply_terminal_tactics"

    def test_default_strategy_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_repair_stats({"a": 1})

        records = [r for r in caplog.records if hasattr(r, "repair_stats")]
        assert len(records) == 1
        assert records[0].strategy == ""


# ---------------------------------------------------------------------------
# log_termination
# ---------------------------------------------------------------------------


class TestLogTermination:
    def test_emits_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_termination(
                reason="success",
                tactic_attempts=12,
                repair_invocations=2,
            )

        records = [r for r in caplog.records if hasattr(r, "termination_reason")]
        assert len(records) == 1
        assert records[0].termination_reason == "success"
        assert records[0].tactic_attempts == 12
        assert records[0].repair_invocations == 2


# ---------------------------------------------------------------------------
# log_phase_duration
# ---------------------------------------------------------------------------


class TestLogPhaseDuration:
    def test_emits_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="formalconstruct"):
            log_phase_duration(phase="informal_rigor", duration_ms=1500.0)

        records = [r for r in caplog.records if hasattr(r, "phase")]
        assert len(records) == 1
        assert records[0].phase == "informal_rigor"
        assert records[0].duration_ms == 1500.0


# ---------------------------------------------------------------------------
# Imports from core __init__
# ---------------------------------------------------------------------------


class TestCoreExports:
    def test_exports_from_core(self) -> None:
        from formalconstruct.core import (
            log_axle_call,
            sanitize_log_value,
            timed,
        )

        assert callable(timed)
        assert callable(log_axle_call)
        assert callable(sanitize_log_value)
