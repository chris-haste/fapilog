"""Unit tests for scripts/check_doc_accuracy.py."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

if TYPE_CHECKING:
    pass


class TestCheckFile:
    """Tests for check_file function."""

    def test_passes_when_must_contain_present(self, tmp_path: Path) -> None:
        """File passes when all must_contain patterns are present."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text(
            "This feature is disabled by default and only works when enabled."
        )

        check = {
            "file": str(doc_file),
            "must_contain": ["disabled by default", "when enabled"],
            "must_not_contain": [],
        }

        result = check_file(check)

        assert result.passed is True
        assert result.errors == []

    def test_fails_when_must_contain_missing(self, tmp_path: Path) -> None:
        """File fails when must_contain pattern is missing."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text("This feature always works automatically.")

        check = {
            "file": str(doc_file),
            "must_contain": ["disabled by default"],
            "must_not_contain": [],
        }

        result = check_file(check)

        assert result.passed is False
        assert len(result.errors) == 1
        assert "disabled by default" in result.errors[0]

    def test_passes_when_must_not_contain_absent(self, tmp_path: Path) -> None:
        """File passes when must_not_contain patterns are absent."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Metadata stays nested in the envelope.")

        check = {
            "file": str(doc_file),
            "must_contain": [],
            "must_not_contain": [r"flattened.*metadata", r"merged at top level"],
        }

        result = check_file(check)

        assert result.passed is True
        assert result.errors == []

    def test_fails_when_must_not_contain_present(self, tmp_path: Path) -> None:
        """File fails when must_not_contain pattern is found."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text(
            "Fields are flattened so metadata keys appear at top level."
        )

        check = {
            "file": str(doc_file),
            "must_contain": [],
            "must_not_contain": [r"flattened.*metadata", r"merged at top level"],
        }

        result = check_file(check)

        assert result.passed is False
        assert len(result.errors) == 1  # Only matches "flattened.*metadata"

    def test_case_insensitive_must_contain(self, tmp_path: Path) -> None:
        """must_contain matching is case-insensitive."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Redaction is DISABLED BY DEFAULT.")

        check = {
            "file": str(doc_file),
            "must_contain": ["disabled by default"],
            "must_not_contain": [],
        }

        result = check_file(check)

        assert result.passed is True

    def test_case_insensitive_must_not_contain(self, tmp_path: Path) -> None:
        """must_not_contain matching is case-insensitive."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Data is ALWAYS SCRUBBED from logs.")

        check = {
            "file": str(doc_file),
            "must_contain": [],
            "must_not_contain": [r"always scrubbed"],
        }

        result = check_file(check)

        assert result.passed is False

    def test_skips_missing_file(self, tmp_path: Path) -> None:
        """Missing file is skipped (returns passed with skip message)."""
        from check_doc_accuracy import check_file

        check = {
            "file": str(tmp_path / "nonexistent.md"),
            "must_contain": ["something"],
            "must_not_contain": [],
        }

        result = check_file(check)

        assert result.passed is True
        assert result.skipped is True


class TestAlwaysWithQualification:
    """Tests for 'always' with qualification detection."""

    def test_always_without_qualification_fails(self, tmp_path: Path) -> None:
        """'always scrubbed' without 'when' qualification should fail."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Credentials are always scrubbed from URLs.")

        check = {
            "file": str(doc_file),
            "must_contain": [],
            "must_not_contain": [r"always scrubbed(?! when)"],
        }

        result = check_file(check)

        assert result.passed is False

    def test_always_with_when_qualification_passes(self, tmp_path: Path) -> None:
        """'always scrubbed when enabled' should pass."""
        from check_doc_accuracy import check_file

        doc_file = tmp_path / "test.md"
        doc_file.write_text(
            "Credentials are always scrubbed when the redactor is enabled."
        )

        check = {
            "file": str(doc_file),
            "must_contain": [],
            "must_not_contain": [r"always scrubbed(?! when)"],
        }

        result = check_file(check)

        assert result.passed is True


class TestRunChecks:
    """Tests for run_checks main function."""

    def test_returns_zero_when_all_pass(self, tmp_path: Path) -> None:
        """Returns 0 exit code when all checks pass."""
        from check_doc_accuracy import run_checks

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Feature is disabled by default.")

        checks = [
            {
                "file": str(doc_file),
                "must_contain": ["disabled by default"],
                "must_not_contain": [],
            }
        ]

        exit_code = run_checks(checks)

        assert exit_code == 0

    def test_returns_one_when_any_fail(self, tmp_path: Path) -> None:
        """Returns 1 exit code when any check fails."""
        from check_doc_accuracy import run_checks

        doc_file = tmp_path / "test.md"
        doc_file.write_text("Feature works automatically.")

        checks = [
            {
                "file": str(doc_file),
                "must_contain": ["disabled by default"],
                "must_not_contain": [],
            }
        ]

        exit_code = run_checks(checks)

        assert exit_code == 1

    def test_skips_missing_files_in_run_checks(self, tmp_path: Path) -> None:
        """Missing files are skipped and don't fail the check."""
        from check_doc_accuracy import run_checks

        checks = [
            {
                "file": str(tmp_path / "nonexistent.md"),
                "must_contain": ["something"],
                "must_not_contain": [],
            }
        ]

        exit_code = run_checks(checks)

        assert exit_code == 0  # Skipped files don't cause failure


class TestAsyncUsageValidation:
    """Tests for async logger usage validation in code blocks."""

    def test_detects_await_with_sync_logger(self, tmp_path: Path) -> None:
        """Detects incorrect await usage with get_logger() (sync logger)."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```python
from fapilog import get_logger

logger = get_logger()

async def my_func():
    await logger.info("test")
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is False
        assert len(result.errors) == 1
        assert "await" in result.errors[0].lower()
        assert "get_logger" in result.errors[0]

    def test_passes_sync_logger_without_await(self, tmp_path: Path) -> None:
        """Passes when sync logger is used without await."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```python
from fapilog import get_logger

logger = get_logger()

async def my_func():
    logger.info("test")  # Correct: no await on sync logger
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is True
        assert result.errors == []

    def test_passes_async_logger_with_await(self, tmp_path: Path) -> None:
        """Passes when async logger is used with await."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```python
from fapilog import get_async_logger

async def my_func():
    logger = await get_async_logger()
    await logger.info("test")  # Correct: await on async logger
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is True
        assert result.errors == []

    def test_passes_runtime_async_with_await(self, tmp_path: Path) -> None:
        """Passes when runtime_async is used with await."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```python
from fapilog import runtime_async

async def process_items(items):
    async with runtime_async() as logger:
        await logger.info("Batch started")
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is True
        assert result.errors == []

    def test_detects_module_level_await(self, tmp_path: Path) -> None:
        """Detects await at module level (outside async function)."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```python
from fapilog import get_async_logger

logger = await get_async_logger()  # Wrong: await at module level
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is False
        assert len(result.errors) == 1
        assert (
            "module level" in result.errors[0].lower()
            or "outside" in result.errors[0].lower()
        )

    def test_skips_non_python_blocks(self, tmp_path: Path) -> None:
        """Skips non-Python code blocks."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# Example

```bash
export FAPILOG_CORE__LOG_LEVEL=DEBUG
```

```json
{"level": "INFO"}
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is True
        assert result.errors == []

    def test_handles_multiple_code_blocks(self, tmp_path: Path) -> None:
        """Checks all Python code blocks in a document."""
        from check_doc_accuracy import check_async_usage

        doc_file = tmp_path / "test.md"
        doc_file.write_text("""
# First Example

```python
from fapilog import get_logger
logger = get_logger()
logger.info("ok")  # Correct
```

# Second Example

```python
from fapilog import get_logger
logger = get_logger()
async def bad():
    await logger.info("wrong")  # Wrong
```
""")

        result = check_async_usage(doc_file)

        assert result.passed is False
        assert len(result.errors) == 1  # Only second block has the error


class TestMain:
    """Tests for main entry point."""

    def test_main_runs_default_checks(self) -> None:
        """main() runs the default CHECKS against actual docs."""
        from check_doc_accuracy import main

        # This tests against real docs, should pass since we fixed them
        exit_code = main()

        assert exit_code == 0
