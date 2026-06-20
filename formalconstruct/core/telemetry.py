"""Structured logging, timing decorators, and repair stats."""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger("formalconstruct")

F = TypeVar("F", bound=Callable[..., Any])


def timed(fn: F) -> F:
    """Async decorator that emits an ``info`` log with *function_name* and *duration_ms*."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return await fn(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "timed_call",
                extra={"function_name": fn.__name__, "duration_ms": elapsed_ms},
            )

    return wrapper  # type: ignore[return-value]


def log_axle_call(
    tool: str, duration_ms: float, has_errors: bool, **extra: Any
) -> None:
    """Emit a structured log for an AXLE tool call."""
    logger.info(
        "axle_tool_call",
        extra={"tool": tool, "duration_ms": duration_ms, "has_errors": has_errors, **extra},
    )


def log_repair_stats(stats: dict[str, Any], strategy: str = "") -> None:
    """Emit a structured log for repair statistics."""
    logger.info(
        "repair_stats",
        extra={"repair_stats": stats, "strategy": strategy},
    )


def log_termination(
    reason: str, tactic_attempts: int = 0, repair_invocations: int = 0
) -> None:
    """Emit a structured log for proving-loop termination."""
    logger.info(
        "termination",
        extra={
            "termination_reason": reason,
            "tactic_attempts": tactic_attempts,
            "repair_invocations": repair_invocations,
        },
    )


def log_phase_duration(phase: str, duration_ms: float) -> None:
    """Emit a structured log for pipeline phase duration."""
    logger.info(
        "phase_duration",
        extra={"phase": phase, "duration_ms": duration_ms},
    )


def sanitize_log_value(value: str, secret: str) -> str:
    """Replace every occurrence of *secret* in *value* with ``[REDACTED]``."""
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")
