# Epic 9: FastAPI Integration Layer

**Epic Goal**: Provide native FastAPI integration tools that enhance developer productivity, request-level observability, and testability, while preserving Fapilog's async-first, plugin-driven architecture.

**Integration Requirements**: All FastAPI integrations must follow existing Fapilog architecture (plugin-based, zero global state, container isolation) and must be optional and non-intrusive to core library behavior.

## Story 9.1: FastAPI Middleware for Request Context Logging

As a FastAPI developer,
I want middleware that injects a Fapilog logger and correlation ID per request,
so that I can trace logs easily without boilerplate.

**Acceptance Criteria:**

1. Middleware automatically creates isolated logger instance per request
2. Correlation ID generation and propagation across all async operations
3. Logger injection into request context for endpoint access
4. Zero global state - each request gets independent logger instance
5. Optional configuration for correlation ID header names
6. Async context preservation across middleware chain
7. Performance impact <1ms per request initialization
8. Compatible with FastAPI dependency injection system
9. The FastAPI integration MUST be installed via a first‑party extra: `pip install fapilog[fastapi]`. All integration code paths MUST be import‑guarded so the core functions without the extra.
10. When FastAPI integration is referenced but not installed, the system MUST emit a clear, structured diagnostic instructing the developer to install the extra (e.g., `Install with: pip install fapilog[fastapi]`).

## Story 9.2: Request/Response Logging Plugin

As a FastAPI developer,
I want a plugin that logs HTTP requests/responses with optional body redaction,
so that I can observe access patterns and debug issues in production.

**Acceptance Criteria:**

1. Automatic request/response logging with configurable detail levels
2. Optional request/response body logging with size limits
3. PII redaction capabilities for sensitive request data
4. Configurable exclusion patterns for health checks and static files
5. Structured logging format compatible with Fapilog pipeline
6. Performance optimization for high-throughput APIs
7. Integration with existing Fapilog processors and sinks
8. Support for custom request/response enrichment

## Story 9.3: FastAPI Lifecycle Hook Registration

As a FastAPI developer,
I want a helper to auto-register logger lifecycle with startup and shutdown,
so that I can cleanly manage the logger within my app lifecycle.

**Acceptance Criteria:**

1. Automatic logger initialization during FastAPI startup
2. Graceful logger shutdown during FastAPI shutdown
3. Container isolation - multiple FastAPI apps can coexist
4. Configuration loading from environment variables or files
5. Plugin discovery and loading during startup
6. Health check endpoints for logger status
7. Zero global state - logger bound to FastAPI app instance
8. Support for multiple logger configurations per app

## Story 9.4: FastAPI-Aware Exception Handling

As a FastAPI developer,
I want to log unhandled exceptions and validation errors using Fapilog,
so that I can catch production issues with full context.

**Acceptance Criteria:**

1. Automatic exception logging with full context preservation
2. FastAPI validation error logging with request details
3. Correlation ID preservation in exception logs
4. Structured exception data compatible with Fapilog processors
5. Optional exception response formatting
6. Integration with FastAPI exception handlers
7. Support for custom exception enrichment
8. Performance isolation - exceptions don't impact healthy requests

## Story 9.5: FastAPI Logger DI via Depends

As a FastAPI developer,
I want to inject a logger into endpoints using Depends,
so that I can maintain clean and testable route functions.

**Acceptance Criteria:**

1. Depends-based logger injection for FastAPI endpoints
2. Request-scoped logger with automatic correlation ID
3. Type-safe dependency injection with proper annotations
4. Compatible with FastAPI testing framework
5. Support for custom logger configuration per endpoint
6. Thread-safe and async-safe dependency resolution
7. Optional caching for performance optimization
8. Integration with existing FastAPI security dependencies

## Story 9.6: FastAPI Test Fixtures for Logger Verification

As a developer,
I want to use a test fixture that captures Fapilog events in FastAPI tests,
so that I can assert logging behavior reliably.

**Acceptance Criteria:**

1. pytest fixtures for capturing Fapilog events in tests
2. Integration with FastAPI TestClient for end-to-end testing
3. Mock sinks for verifying log output without side effects
4. Assertion helpers for common logging verification patterns
5. Support for async test functions
6. Correlation ID verification in test scenarios
7. Performance testing utilities for logging overhead
8. Documentation and examples for testing best practices
