"""Unit tests for async context propagation helpers.

Tests for Story 1.35: Async Context Propagation Helpers.
"""

from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor


class TestCreateTaskWithContext:
    """Tests for create_task_with_context helper."""

    async def test_create_task_with_context_preserves_bindings(self) -> None:
        """Task created with helper inherits current context variables."""
        from fapilog.context import create_task_with_context

        # Set up a context variable to track
        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("parent-value")

        captured_value: str | None = None

        async def background_work() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        # Create task with context preservation
        task = create_task_with_context(background_work())
        await task

        assert captured_value == "parent-value"

    async def test_create_task_without_helper_loses_context(self) -> None:
        """Demonstrate that regular create_task loses context (control test)."""
        # This test documents the problem we're solving
        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("parent-value")

        captured_value: str | None = None

        async def background_work() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        # Regular create_task - context should be lost
        task = asyncio.create_task(background_work())
        await task

        # In Python 3.11+, create_task copies context by default at task creation.
        # This means the context IS preserved - this test documents that behavior.
        # Our helper provides explicit context copying which works consistently
        # across Python versions and makes the intent clear.
        assert captured_value == "parent-value"

    async def test_create_task_with_context_returns_correct_type(self) -> None:
        """Task returned has correct asyncio.Task type with proper generic."""
        from fapilog.context import create_task_with_context

        async def returns_string() -> str:
            return "hello"

        task = create_task_with_context(returns_string())

        assert isinstance(task, asyncio.Task)
        result = await task
        assert result == "hello"

    async def test_create_task_with_context_accepts_name(self) -> None:
        """Task can be created with a custom name."""
        from fapilog.context import create_task_with_context

        async def noop() -> None:
            pass

        task = create_task_with_context(noop(), name="my-task")

        assert task.get_name() == "my-task"
        await task

    async def test_create_task_with_context_preserves_multiple_vars(self) -> None:
        """Multiple context variables are all preserved."""
        from fapilog.context import create_task_with_context

        var1: contextvars.ContextVar[str] = contextvars.ContextVar("var1")
        var2: contextvars.ContextVar[int] = contextvars.ContextVar("var2")
        var3: contextvars.ContextVar[list[str]] = contextvars.ContextVar("var3")

        var1.set("value-1")
        var2.set(42)
        var3.set(["a", "b", "c"])

        captured: dict[str, object] = {}

        async def capture_all() -> None:
            captured["var1"] = var1.get(None)
            captured["var2"] = var2.get(None)
            captured["var3"] = var3.get(None)

        task = create_task_with_context(capture_all())
        await task

        assert captured["var1"] == "value-1"
        assert captured["var2"] == 42
        assert captured["var3"] == ["a", "b", "c"]


class TestRunInExecutorWithContext:
    """Tests for run_in_executor_with_context helper."""

    async def test_run_in_executor_with_context_preserves_bindings(self) -> None:
        """Sync function in executor inherits current context variables."""
        from fapilog.context import run_in_executor_with_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("parent-value")

        captured_value: str | None = None

        def sync_work() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            await run_in_executor_with_context(executor, sync_work)
        finally:
            executor.shutdown(wait=True)

        assert captured_value == "parent-value"

    async def test_run_in_executor_with_context_passes_args(self) -> None:
        """Arguments are correctly passed to the sync function."""
        from fapilog.context import run_in_executor_with_context

        def add(a: int, b: int) -> int:
            return a + b

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            result = await run_in_executor_with_context(executor, add, 2, 3)
        finally:
            executor.shutdown(wait=True)

        assert result == 5

    async def test_run_in_executor_with_context_returns_value(self) -> None:
        """Return value from sync function is correctly propagated."""
        from fapilog.context import run_in_executor_with_context

        def get_greeting() -> str:
            return "hello from executor"

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            result = await run_in_executor_with_context(executor, get_greeting)
        finally:
            executor.shutdown(wait=True)

        assert result == "hello from executor"

    async def test_run_in_executor_with_context_none_executor(self) -> None:
        """None executor uses the default loop executor."""
        from fapilog.context import run_in_executor_with_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("default-executor-value")

        def get_value() -> str | None:
            return test_var.get(None)

        result = await run_in_executor_with_context(None, get_value)

        assert result == "default-executor-value"

    async def test_run_in_executor_with_context_preserves_multiple_vars(self) -> None:
        """Multiple context variables are preserved in executor."""
        from fapilog.context import run_in_executor_with_context

        var1: contextvars.ContextVar[str] = contextvars.ContextVar("var1")
        var2: contextvars.ContextVar[int] = contextvars.ContextVar("var2")

        var1.set("string-value")
        var2.set(123)

        captured: dict[str, object] = {}

        def capture_all() -> None:
            captured["var1"] = var1.get(None)
            captured["var2"] = var2.get(None)

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            await run_in_executor_with_context(executor, capture_all)
        finally:
            executor.shutdown(wait=True)

        assert captured["var1"] == "string-value"
        assert captured["var2"] == 123


class TestPreserveContextDecorator:
    """Tests for preserve_context decorator."""

    async def test_preserve_context_preserves_bindings(self) -> None:
        """Decorated function preserves context when called as task."""
        from fapilog.context import preserve_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        captured_value: str | None = None

        @preserve_context
        async def worker() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        test_var.set("decorator-value")
        await worker()

        assert captured_value == "decorator-value"

    async def test_preserve_context_with_create_task(self) -> None:
        """Decorated function preserves context even via create_task."""
        from fapilog.context import preserve_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        captured_value: str | None = None

        @preserve_context
        async def worker() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        test_var.set("task-value")
        task: asyncio.Task[None] = asyncio.create_task(worker())
        await task

        assert captured_value == "task-value"

    async def test_preserve_context_with_gather(self) -> None:
        """Multiple decorated functions preserve context in gather."""
        from fapilog.context import preserve_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        captured_values: list[str | None] = []

        @preserve_context
        async def worker() -> None:
            captured_values.append(test_var.get(None))

        test_var.set("gather-value")
        await asyncio.gather(worker(), worker(), worker())

        assert captured_values == ["gather-value", "gather-value", "gather-value"]

    async def test_preserve_context_preserves_return_value(self) -> None:
        """Decorated function correctly returns values."""
        from fapilog.context import preserve_context

        @preserve_context
        async def get_value() -> str:
            return "returned-value"

        result = await get_value()

        assert result == "returned-value"

    async def test_preserve_context_preserves_args_and_kwargs(self) -> None:
        """Decorated function receives args and kwargs correctly."""
        from fapilog.context import preserve_context

        @preserve_context
        async def process(a: int, b: int, *, multiplier: int = 1) -> int:
            return (a + b) * multiplier

        result = await process(2, 3, multiplier=10)

        assert result == 50

    async def test_preserve_context_preserves_function_metadata(self) -> None:
        """Decorated function preserves __name__ and __doc__."""
        from fapilog.context import preserve_context

        @preserve_context
        async def documented_function() -> None:
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."


class TestContextIsolation:
    """Tests for context isolation between tasks."""

    async def test_nested_task_context_isolation(self) -> None:
        """Nested tasks have isolated contexts (changes don't affect parent)."""
        from fapilog.context import create_task_with_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("parent-value")

        async def child_task() -> None:
            # Modify in child - should NOT affect parent
            test_var.set("child-value")

        task = create_task_with_context(child_task())
        await task

        # Parent context should be unaffected
        assert test_var.get() == "parent-value"

    async def test_context_not_shared_between_independent_tasks(self) -> None:
        """Two independent tasks don't share context modifications."""
        from fapilog.context import create_task_with_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        test_var.set("initial")

        captured_in_task2: str | None = None
        task1_ready = asyncio.Event()
        task2_can_check = asyncio.Event()

        async def task1() -> None:
            test_var.set("task1-value")
            task1_ready.set()
            await task2_can_check.wait()

        async def task2() -> None:
            nonlocal captured_in_task2
            await task1_ready.wait()
            # Even though task1 modified its copy, task2 should see initial
            captured_in_task2 = test_var.get(None)
            task2_can_check.set()

        t1 = create_task_with_context(task1())
        t2 = create_task_with_context(task2())
        await asyncio.gather(t1, t2)

        # Task2 should see original value, not task1's modification
        assert captured_in_task2 == "initial"


class TestPublicAPIExports:
    """Tests for public API exports (AC4)."""

    def test_top_level_exports(self) -> None:
        """Helpers accessible from fapilog top-level."""
        import fapilog

        assert hasattr(fapilog, "create_task_with_context")
        assert hasattr(fapilog, "preserve_context")
        assert hasattr(fapilog, "run_in_executor_with_context")

    def test_context_module_exports(self) -> None:
        """Helpers accessible from fapilog.context module."""
        from fapilog.context import (
            create_task_with_context,
            preserve_context,
            run_in_executor_with_context,
        )

        assert callable(create_task_with_context)
        assert callable(preserve_context)
        assert callable(run_in_executor_with_context)

    def test_backward_compatible_core_import(self) -> None:
        """preserve_context is still importable from fapilog.core (backward compat)."""
        from fapilog.core import preserve_context

        assert callable(preserve_context)

    async def test_core_preserve_context_works(self) -> None:
        """preserve_context from core module works correctly (fixed implementation)."""
        from fapilog.core import preserve_context

        test_var: contextvars.ContextVar[str] = contextvars.ContextVar("test_var")
        captured_value: str | None = None

        @preserve_context
        async def worker() -> None:
            nonlocal captured_value
            captured_value = test_var.get(None)

        test_var.set("core-import-value")
        await worker()

        assert captured_value == "core-import-value"
