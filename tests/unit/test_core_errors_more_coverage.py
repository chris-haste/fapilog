from __future__ import annotations

import traceback

import pytest

from fapilog.core.errors import (
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    FapilogError,
    create_error_context,
    serialize_exception,
    set_error_context,
)


def test_serialize_exception_none_returns_empty() -> None:
    out = serialize_exception(None, max_frames=5, max_stack_chars=1000)
    assert out == {}


def test_serialize_exception_basic_fields_and_frame_limit() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = traceback.sys.exc_info()
    out = serialize_exception(exc_info, max_frames=1, max_stack_chars=10_000)
    assert out.get("error.type") in {"ValueError", str(ValueError)}
    assert "error.message" in out
    frames = out.get("error.frames", [])
    assert isinstance(frames, list)
    assert len(frames) <= 1


def test_serialize_exception_truncates_stack_string() -> None:
    try:
        # Create a deeper stack by nested calls
        def _a():
            def _b():
                raise RuntimeError("deep")

            _b()

        _a()
    except RuntimeError:
        exc_info = traceback.sys.exc_info()
    out = serialize_exception(exc_info, max_frames=10, max_stack_chars=16)
    stack = out.get("error.stack", "")
    assert isinstance(stack, str)
    assert len(stack) <= 16
    assert stack.endswith("...")


@pytest.mark.asyncio
async def test_fapilog_error_captures_async_and_contextvars() -> None:
    set_error_context(request_id="r1", user_id="u1", session_id="s1", container_id="c1")
    err = FapilogError(
        "msg",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.LOW,
        recovery_strategy=ErrorRecoveryStrategy.NONE,
        extra_key=True,
    )
    # Async context fields
    assert err.context.category == ErrorCategory.VALIDATION
    assert err.context.severity == ErrorSeverity.LOW
    assert err.context.recovery_strategy == ErrorRecoveryStrategy.NONE
    # Contextvars propagated
    assert err.context.request_id == "r1"
    assert err.context.user_id == "u1"
    # Metadata carries kwargs
    assert err.context.metadata.get("extra_key") is True
    # to_dict serializes expected fields
    as_dict = err.to_dict()
    assert as_dict["error_type"] == "FapilogError"
    assert as_dict["message"] == "msg"
    assert isinstance(as_dict["context"], dict)


def test_create_error_context_populates_fields() -> None:
    ctx = create_error_context(
        ErrorCategory.DATABASE,
        ErrorSeverity.HIGH,
        ErrorRecoveryStrategy.RETRY,
        note="x",
    )
    assert ctx.category == ErrorCategory.DATABASE
    assert ctx.severity == ErrorSeverity.HIGH
    assert ctx.recovery_strategy == ErrorRecoveryStrategy.RETRY
    assert ctx.metadata.get("note") == "x"


def test_with_context_updates_metadata() -> None:
    err = FapilogError("m")
    err.with_context(alpha=1, beta=2)
    assert err.context.metadata.get("alpha") == 1
    assert err.context.metadata.get("beta") == 2
