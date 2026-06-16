"""Unit tests for formalconstruct.core.exceptions hierarchy."""

from formalconstruct.core.exceptions import (
    AxleConnectionError,
    AxleConnectionResetError,
    AxleError,
    AxleInvalidArgumentError,
    AxleNonTransientError,
    AxleRateLimitedError,
    AxleRetriesExhaustedError,
    AxleTimeoutError,
    AxleTransientError,
    AxleUnavailableError,
    AxleValidationError,
    BudgetExhaustedError,
    ExpressionParseError,
    FormalConstructError,
    MissingApiKeyError,
    ScaffoldingError,
    SchemaExtractionError,
    SchemaRollbackRequested,
    UnknownDomainError,
    UnsupportedCompositionError,
    UnsupportedDomainError,
)


def test_all_21_classes_importable():
    classes = [
        FormalConstructError,
        AxleError,
        AxleTransientError,
        AxleRateLimitedError,
        AxleUnavailableError,
        AxleTimeoutError,
        AxleConnectionError,
        AxleConnectionResetError,
        AxleNonTransientError,
        AxleInvalidArgumentError,
        AxleValidationError,
        AxleRetriesExhaustedError,
        MissingApiKeyError,
        SchemaExtractionError,
        UnsupportedDomainError,
        UnsupportedCompositionError,
        ScaffoldingError,
        UnknownDomainError,
        BudgetExhaustedError,
        SchemaRollbackRequested,
        ExpressionParseError,
    ]
    assert len(classes) == 21
    for cls in classes:
        assert issubclass(cls, FormalConstructError)


def test_axle_rate_limited_inherits_from_root():
    e = AxleRateLimitedError("test", retry_after=5.0)
    assert isinstance(e, FormalConstructError)
    assert isinstance(e, AxleError)
    assert isinstance(e, AxleTransientError)
    assert e.retry_after == 5.0


def test_axle_rate_limited_default_retry_after():
    e = AxleRateLimitedError("rate limited")
    assert e.retry_after is None


def test_axle_rate_limited_no_args():
    e = AxleRateLimitedError()
    assert str(e) == ""
    assert e.retry_after is None


def test_axle_retries_exhausted_attributes():
    original = AxleTimeoutError("timed out")
    e = AxleRetriesExhaustedError(original, 3, 12.5)
    assert e.retries_attempted == 3
    assert e.total_elapsed == 12.5
    assert e.original_error is original
    assert "3 attempts" in str(e)
    assert "12.5s" in str(e)


def test_axle_retries_exhausted_inherits_from_axle_error():
    e = AxleRetriesExhaustedError(AxleTimeoutError(), 1, 1.0)
    assert isinstance(e, AxleError)
    assert isinstance(e, FormalConstructError)
    assert not isinstance(e, AxleTransientError)
    assert not isinstance(e, AxleNonTransientError)


def test_transient_subclasses():
    for cls in [
        AxleRateLimitedError,
        AxleUnavailableError,
        AxleTimeoutError,
        AxleConnectionError,
        AxleConnectionResetError,
    ]:
        assert issubclass(cls, AxleTransientError), f"{cls.__name__}"
        assert issubclass(cls, AxleError)
        assert not issubclass(cls, AxleNonTransientError)


def test_non_transient_subclasses():
    for cls in [AxleInvalidArgumentError, AxleValidationError]:
        assert issubclass(cls, AxleNonTransientError), f"{cls.__name__}"
        assert issubclass(cls, AxleError)
        assert not issubclass(cls, AxleTransientError)


def test_pipeline_errors_inherit_from_root():
    for cls in [
        MissingApiKeyError,
        SchemaExtractionError,
        UnsupportedDomainError,
        UnsupportedCompositionError,
        ScaffoldingError,
        UnknownDomainError,
        BudgetExhaustedError,
        SchemaRollbackRequested,
        ExpressionParseError,
    ]:
        assert issubclass(cls, FormalConstructError), f"{cls.__name__}"
        assert not issubclass(cls, AxleError), f"{cls.__name__} should not be AxleError"


def test_schema_rollback_requested_attributes():
    e = SchemaRollbackRequested("missing bound", "add lower bound for x")
    assert e.missing_premise == "missing bound"
    assert e.corrective_prompt == "add lower bound for x"
    assert "missing bound" in str(e)


def test_budget_exhausted_error_attributes():
    sentinel = object()
    e = BudgetExhaustedError("tactic budget", failure=sentinel)
    assert e.failure is sentinel
    assert "tactic budget" in str(e)


def test_budget_exhausted_error_defaults():
    e = BudgetExhaustedError()
    assert e.failure is None
    assert str(e) == ""


def test_expression_parse_error_attributes():
    e = ExpressionParseError("x + * y", 4, "unexpected operator")
    assert e.expression == "x + * y"
    assert e.position == 4
    assert "position 4" in str(e)
    assert "unexpected operator" in str(e)
    assert "x + * y" in str(e)
    assert "    ^" in str(e)


def test_expression_parse_error_position_zero():
    e = ExpressionParseError("@bad", 0, "invalid character")
    assert e.position == 0
    assert "^" in str(e)


def test_exports_from_core_init():
    from formalconstruct.core import (
        ExpressionParseError,
        FormalConstructError,
        SchemaRollbackRequested,
    )
    assert FormalConstructError is not None
    assert SchemaRollbackRequested is not None
    assert ExpressionParseError is not None


def test_exceptions_are_catchable():
    try:
        raise AxleRateLimitedError("429", retry_after=30.0)
    except AxleTransientError as e:
        assert e.retry_after == 30.0
    except Exception:
        raise AssertionError("Should have been caught by AxleTransientError")

    try:
        raise AxleInvalidArgumentError("bad env")
    except AxleNonTransientError:
        pass
    except Exception:
        raise AssertionError("Should have been caught by AxleNonTransientError")
