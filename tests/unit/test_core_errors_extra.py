from __future__ import annotations

import sys

import pytest

from fapilog.core.errors import (
    AsyncErrorContext,
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    FapilogError,
    create_error_context,
    get_error_context,
    serialize_exception,
    set_error_context,
)


def test_set_and_get_error_context_variables() -> None:
    set_error_context(
        request_id="r-1",
        user_id="u-2",
        session_id="s-3",
        container_id="c-4",
    )
    ctx = get_error_context()
    assert ctx["request_id"] == "r-1"
    assert ctx["user_id"] == "u-2"
    assert ctx["session_id"] == "s-3"
    assert ctx["container_id"] == "c-4"


def test_create_error_context_includes_vars_and_metadata() -> None:
    set_error_context(request_id="r-x", user_id="u-y")
    ctx = create_error_context(
        ErrorCategory.SYSTEM,
        ErrorSeverity.HIGH,
        recovery_strategy=ErrorRecoveryStrategy.NONE,
        extra="v",
    )
    assert isinstance(ctx, AsyncErrorContext)
    assert ctx.request_id == "r-x" and ctx.user_id == "u-y"
    assert ctx.metadata.get("extra") == "v"


def test_fapilog_error_to_dict_contains_context_and_cause() -> None:
    try:
        raise ValueError("inner")
    except ValueError as inner:
        err = FapilogError(
            "outer",
            category=ErrorCategory.CONFIG,
            severity=ErrorSeverity.HIGH,
            cause=inner,
        )
    d = err.to_dict()
    assert d["error_type"] == "FapilogError"
    assert d["message"] == "outer"
    assert "context" in d and isinstance(d["context"], dict)
    assert d.get("cause") == "inner"


def test_serialize_exception_includes_cause() -> None:
    try:
        try:
            raise RuntimeError("root")
        except RuntimeError as e:
            raise ValueError("leaf") from e
    except ValueError:
        info = sys.exc_info()
    data = serialize_exception(info, max_frames=10, max_stack_chars=2000)
    assert data.get("error.type") == "ValueError"
    assert data.get("error.cause") == "RuntimeError"
    assert "error.stack" in data


def test_serialize_exception_empty_returns_empty_mapping() -> None:
    data = serialize_exception(None, max_frames=1, max_stack_chars=100)
    assert data == {}


@pytest.mark.skip(reason="Unhandled exception capture covered by integration tests")
def test_unhandled_exception_capture_is_covered_by_integration() -> None:
    assert True
