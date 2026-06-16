from __future__ import annotations


class FormalConstructError(Exception):
    """Root exception for the package."""


# --- AXLE errors ---


class AxleError(FormalConstructError):
    """Base for all AXLE-related errors."""


class AxleTransientError(AxleError):
    """Transient errors eligible for retry."""


class AxleRateLimitedError(AxleTransientError):
    """HTTP 429."""

    def __init__(self, message: str = "", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AxleUnavailableError(AxleTransientError):
    """HTTP 503."""


class AxleTimeoutError(AxleTransientError):
    """Per-call timeout exceeded."""


class AxleConnectionError(AxleTransientError):
    """Subprocess closed or connection lost."""


class AxleConnectionResetError(AxleTransientError):
    """Transport-level connection reset."""


class AxleNonTransientError(AxleError):
    """Non-transient errors -- do NOT retry."""


class AxleInvalidArgumentError(AxleNonTransientError):
    """e.g., environment mismatch."""


class AxleValidationError(AxleNonTransientError):
    """Lean validation/schema/type errors."""


class AxleRetriesExhaustedError(AxleError):
    """All retries exhausted."""

    def __init__(self, original_error: AxleError, retries: int, elapsed: float):
        super().__init__(f"Retries exhausted after {retries} attempts ({elapsed:.1f}s)")
        self.original_error = original_error
        self.retries_attempted = retries
        self.total_elapsed = elapsed


# --- Pipeline errors ---


class MissingApiKeyError(FormalConstructError):
    """AXLE_API_KEY not set."""


class SchemaExtractionError(FormalConstructError):
    """Informal Rigor Agent failed to extract valid schema."""


class UnsupportedDomainError(FormalConstructError):
    """Narrative domain outside supported set."""


class UnsupportedCompositionError(FormalConstructError):
    """Domain composition not in allowed set."""


class ScaffoldingError(FormalConstructError):
    """Lean Scaffolding Agent mapping failure."""


class UnknownDomainError(FormalConstructError):
    """No mapper registered for domain."""


class BudgetExhaustedError(FormalConstructError):
    """One or more repair loop bounds exhausted."""

    def __init__(self, message: str = "", failure: object = None):
        super().__init__(message)
        self.failure = failure


class SchemaRollbackRequested(FormalConstructError):
    """Proving Executor requests rollback to Informal Rigor phase."""

    def __init__(self, missing_premise: str, corrective_prompt: str):
        super().__init__(f"Schema rollback: {missing_premise}")
        self.missing_premise = missing_premise
        self.corrective_prompt = corrective_prompt


# --- Expression parsing errors ---


class ExpressionParseError(FormalConstructError):
    """Raised when expression_latex cannot be parsed by the expression parser."""

    def __init__(self, expression: str, position: int, message: str):
        self.expression = expression
        self.position = position
        super().__init__(
            f"Cannot parse expression at position {position}: {message}\n"
            f"  {expression}\n"
            f"  {' ' * position}^"
        )
