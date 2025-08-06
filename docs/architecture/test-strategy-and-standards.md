# Test Strategy and Standards

Comprehensive testing approach focused on **async-first validation**, **plugin ecosystem reliability**, and **500K-2M events/second performance verification**.

## Testing Philosophy

- **Approach:** Test-driven development with async-first patterns throughout
- **Coverage Goals:** 90%+ test coverage with emphasis on async code paths and plugin interactions
- **Test Pyramid:** Balanced distribution favoring fast unit tests with comprehensive integration testing

## Test Types and Organization

### Unit Tests

- **Framework:** pytest 7.4+ with pytest-asyncio 0.21+ for async support
- **File Convention:** `tests/unit/test_{module_name}.py`
- **Location:** `tests/unit/` mirroring `src/fapilog/` structure
- **Mocking Library:** unittest.mock with async mock support
- **Coverage Requirement:** 95% for core library, 85% for plugins

**AI Agent Requirements:**

- Generate tests for all public async methods
- Cover edge cases and error conditions with async patterns
- Follow AAA pattern (Arrange, Act, Assert) with async context
- Mock all external dependencies and I/O operations
- Test container isolation with multiple concurrent containers

```python