# CI Configuration for fapilog Tests

## Environment Variables for Test Tuning

The test suite includes several environment variables that can be tuned for CI environments:

### Integration Test Configuration

- **`FAPILOG_TEST_LOAD_SIZE`** (default: 8000)

  - Controls the number of events in load tests
  - Tuned to ensure backpressure testing while maintaining CI stability
  - Reduce for slower CI environments: `export FAPILOG_TEST_LOAD_SIZE=5000`
  - Note: Values below 5000 may not exercise backpressure behavior

- **`FAPILOG_TEST_MAX_LOOP_STALL_SECONDS`** (default: 0.20, minimum: 0.10)

  - Maximum allowed event loop stall time
  - Increase for slower CI: `export FAPILOG_TEST_MAX_LOOP_STALL_SECONDS=0.50`

- **`FAPILOG_TEST_MAX_AVG_FLUSH_SECONDS`** (default: 0.30, minimum: 1.00)
  - Maximum allowed average drain latency
  - Increase for slower CI: `export FAPILOG_TEST_MAX_AVG_FLUSH_SECONDS=1.00`

### Timeout Protection

Integration tests now include automatic timeout protection:

- Producer operations: 30s timeout
- Logger drain operations: 10s timeout
- Monitor task cleanup: 5s timeout

If any timeout is exceeded, the test will fail with a clear error message indicating a potential hang bug.

### Example CI Configuration

```bash
# For resource-constrained CI environments
export FAPILOG_TEST_LOAD_SIZE=5000  # Minimum to ensure backpressure testing
export FAPILOG_TEST_MAX_LOOP_STALL_SECONDS=0.50
export FAPILOG_TEST_MAX_AVG_FLUSH_SECONDS=1.00

# Run tests
python -m pytest tests/
```

### Debugging Hangs

If tests still hang in CI, the timeout protections will provide clear error messages:

- "Producer timed out after 30s" - Issue with event submission
- "Logger drain timed out" - Issue with worker shutdown
- Check system resources and concurrent test execution
