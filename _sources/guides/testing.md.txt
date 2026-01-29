# Testing with Fapilog

This guide covers patterns for testing applications that use fapilog.

## Capturing Stdout Output

The `StdoutJsonSink` uses `os.writev()` for high-performance output, which bypasses Python's `sys.stdout` redirection. This makes it difficult to capture output in tests using `contextlib.redirect_stdout()`.

### Solution: Use `capture_mode=True`

Enable `capture_mode` when creating your logger to use buffered writes that can be captured:

```python
import io
import sys
import asyncio
from fapilog import AsyncLoggerBuilder

async def test_logging_output():
    # Create a buffer to capture output
    buf = io.BytesIO()
    orig_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")

    try:
        # Enable capture_mode for testing
        logger = await (
            AsyncLoggerBuilder()
            .add_stdout(capture_mode=True)
            .build_async()
        )

        await logger.info("test message", data={"key": "value"})
        await logger.drain()

        # Flush and read captured output
        sys.stdout.flush()
        output = buf.getvalue().decode("utf-8")

        assert "test message" in output
        assert '"key": "value"' in output or '"key":"value"' in output
    finally:
        sys.stdout = orig_stdout
```

### Sync Logger Example

```python
from fapilog import LoggerBuilder

def test_sync_logging():
    buf = io.BytesIO()
    orig_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")

    try:
        logger = LoggerBuilder().add_stdout(capture_mode=True).build()
        logger.info("sync test")
        logger.drain()

        sys.stdout.flush()
        output = buf.getvalue().decode("utf-8")
        assert "sync test" in output
    finally:
        sys.stdout = orig_stdout
```

### pytest Fixture

Create a reusable fixture for capturing fapilog output:

```python
import io
import sys
import pytest
from fapilog import AsyncLoggerBuilder

@pytest.fixture
def captured_stdout():
    """Fixture that captures stdout for testing."""
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")

    yield buf

    sys.stdout = orig

@pytest.fixture
async def test_logger(captured_stdout):
    """Fixture that provides a capture-enabled logger."""
    logger = await (
        AsyncLoggerBuilder()
        .add_stdout(capture_mode=True)
        .build_async()
    )
    yield logger
    await logger.drain()

@pytest.mark.asyncio
async def test_with_fixture(test_logger, captured_stdout):
    await test_logger.info("using fixtures")
    await test_logger.drain()

    sys.stdout.flush()
    output = captured_stdout.getvalue().decode("utf-8")
    assert "using fixtures" in output
```

## When to Use capture_mode

| Scenario | Use capture_mode? |
|----------|-------------------|
| Unit tests that verify log content | Yes |
| Integration tests checking log format | Yes |
| Production applications | No (default) |
| Benchmarks measuring logging performance | No |

**Note:** `capture_mode=True` disables the `os.writev()` optimization, so it should only be used in tests, not production.

## Testing with Pretty Output

The `StdoutPrettySink` (used with `format="pretty"`) already uses `sys.stdout.write()` and doesn't need `capture_mode`. You can capture its output directly:

```python
logger = LoggerBuilder().add_stdout(format="pretty").build()
# Output can be captured without capture_mode
```

## Alternative: File Sink for Testing

For tests that don't need real-time output capture, consider using a temporary file sink:

```python
import tempfile
from pathlib import Path
from fapilog import AsyncLoggerBuilder

async def test_with_file_sink():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = await (
            AsyncLoggerBuilder()
            .add_file(Path(tmpdir) / "test.log")
            .build_async()
        )

        await logger.info("file test")
        await logger.drain()

        log_content = (Path(tmpdir) / "test.log").read_text()
        assert "file test" in log_content
```
