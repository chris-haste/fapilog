# Error Handling Strategy

The error handling strategy balances **developer simplicity** (errors don't crash apps) with **enterprise observability** (full error tracking via plugins).

## General Approach

- **Error Model:** Async-first exception hierarchy with graceful degradation
- **Exception Hierarchy:** Custom exceptions inheriting from `FapilogError` base class
- **Error Propagation:** Non-blocking - logging errors never crash user applications

## Logging Standards

- **Library:** Python's built-in `logging` module for internal fapilog logging
- **Format:** Structured JSON for enterprise compatibility
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL aligned with user log levels
- **Required Context:**
  - Correlation ID: UUID4 format for tracing async operations
  - Service Context: `fapilog.core`, `fapilog.plugins.{plugin_name}`
  - User Context: Never log user data in internal fapilog errors

## Error Handling Patterns

### External API Errors

```python