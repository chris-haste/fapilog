# Coding Standards

These standards are **MANDATORY for AI agents** and critical for maintaining code quality. Focused on project-specific conventions and preventing common async/plugin mistakes.

## Core Standards

- **Languages & Runtimes:** Python 3.8+ with asyncio for all async operations
- **Style & Linting:** ruff (replaces black, isort, flake8) with async-aware rules
- **Test Organization:** `tests/{unit,integration,performance}/test_*.py` with pytest-asyncio

## Naming Conventions

| Element         | Convention                          | Example                                    |
| --------------- | ----------------------------------- | ------------------------------------------ |
| Async Functions | `async def snake_case()`            | `async def process_event()`                |
| Plugin Classes  | `PascalCase` ending in type         | `SplunkSink`, `PIIProcessor`               |
| Event Fields    | `snake_case`                        | `correlation_id`, `event_category`         |
| Settings        | `snake_case` with descriptive names | `async_processing`, `queue_max_size`       |
| Constants       | `UPPER_SNAKE_CASE`                  | `DEFAULT_BATCH_SIZE`, `MAX_RETRY_ATTEMPTS` |

## Critical Rules

- **Async Everywhere:** All I/O operations must use async/await - never blocking calls in async context
- **Plugin Error Isolation:** All plugin operations must be wrapped in try/catch with graceful degradation
- **Container Isolation:** Never use global state - all state must be container-scoped
- **Zero-Copy Operations:** Pass LogEvent by reference, never copy event data unnecessarily
- **Correlation ID Propagation:** All async operations must propagate correlation_id for tracing
  - The default pipeline reads `request_id` from the async context and assigns it to `LogEvent.correlation_id`, defaulting to a UUID if none exists
  - Sinks should include `correlation_id` in emitted records when present
- **Enrichment Order:** Default enrichers run before serialization/sinks
  - `runtime_info` provides service/env/version/host/pid/python
  - `context_vars` provides request_id/user_id and optional trace/span IDs
  - Enrichers must be best-effort and non-fatal; failures must not block pipelines
- **Plugin Entry Points:** All plugins must use standard Python entry points, never dynamic imports
- **Configuration Validation:** All settings must use Pydantic v2 validation with clear error messages
- **Emergency Fallbacks:** All critical paths must have fallback mechanisms that never crash user apps
- **FastAPI Integration Isolation:** FastAPI integrations must not break context isolation or introduce global state

## Dependency Injection Patterns

```python

```
