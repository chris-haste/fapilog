# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- **BREAKING**: Removed `FunctionProcessor` backward compatibility wrapper
  - Function-based processors are no longer supported
  - All processors must now inherit from the `Processor` base class
  - Removed `FunctionProcessor` class from `src/fapilog/_internal/processor.py`
  - Removed related test cases and mixed processor type tests
  - This change simplifies the processor interface and removes technical debt

## [0.2.0] - 2024-12-19

### Added

- **Documentation Overhaul**: Complete Documentation System Redesign

  - **NEW**: Comprehensive documentation structure with progressive learning path from introduction to advanced topics
  - **NEW**: ReadTheDocs integration with automatic builds and hosted documentation at https://fapilog.readthedocs.io/
  - **NEW**: Complete documentation suite: User Guide, API Reference, Configuration Guide, Examples, Troubleshooting, FAQ
  - **NEW**: Sphinx-based documentation with MyST parser for Markdown support and sphinx-rtd-theme for professional appearance
  - **NEW**: Progressive documentation structure: Introduction → Primer → Quickstart → Core Concepts → User Guide → Configuration → API Reference
  - **NEW**: Comprehensive examples directory with 25+ real-world usage patterns and recipes
  - **NEW**: Troubleshooting guide with common issues, error messages, and solutions
  - **NEW**: FAQ section addressing frequently asked questions and best practices
  - **NEW**: Contributing guide with development setup, code standards, and pull request process
  - **NEW**: Style guide for documentation consistency and quality standards
  - **ENHANCED**: README.md streamlined from 2,161 lines to ~400 lines (80% reduction) focusing on landing page purpose
  - **ENHANCED**: Clear navigation paths for different user types (new users, developers, production teams)
  - **ENHANCED**: Zero-configuration documentation setup with sensible defaults and comprehensive examples
  - **ENHANCED**: Type hints throughout documentation with sphinx-autodoc-typehints integration
  - **ENHANCED**: Cross-referenced documentation with internal links and external references to FastAPI, Pydantic, structlog
  - **MAINTAINED**: All existing functionality documented with backward compatibility preserved
  - **TESTED**: Documentation builds successfully with comprehensive test coverage and validation
  - **PERFORMANCE**: Optimized documentation build process with proper dependency management and caching

  **Documentation Structure:**

  ```
  docs/
  ├── index.md              # Landing page with navigation
  ├── introduction.md        # Sales pitch and key benefits
  ├── primer.md             # What is Fapilog and core concepts
  ├── quickstart.md         # Get up and running in 5 minutes
  ├── core-concepts.md      # Architecture and fundamentals
  ├── user-guide.md         # Step-by-step tutorials
  ├── config.md             # Complete configuration reference
  ├── api-reference.md      # Technical API documentation
  ├── examples/             # Real-world usage patterns
  ├── troubleshooting.md    # Common issues and solutions
  ├── faq.md               # Frequently asked questions
  ├── contributing.md       # Development guidelines
  └── style-guide.md       # Documentation standards
  ```

  **Key Features:**

  - **ReadTheDocs Integration**: Automatic builds from GitHub with version-specific documentation
  - **Markdown Support**: All documentation written in Markdown with MyST parser extensions
  - **Search Functionality**: Full-text search across all documentation pages
  - **Version Control**: Documentation versions match software releases
  - **Mobile Responsive**: Professional theme works on all devices
  - **Developer Experience**: Copy-paste ready examples and comprehensive API reference
  - **Production Ready**: Troubleshooting guides and deployment best practices

  **Configuration Example:**

  ```bash
  # Documentation build dependencies
  pip install sphinx sphinx-rtd-theme myst-parser sphinx-autodoc-typehints

  # Build documentation locally
  cd docs && python -m sphinx -b html . _build/html
  ```

  This comprehensive documentation overhaul provides enterprise-grade documentation suitable for production teams while maintaining the developer-friendly approach that makes fapilog easy to adopt and integrate.

- **Story 14.2**: Version Management Centralization

  - **NEW**: Centralized version management with single source of truth in `pyproject.toml`
  - **NEW**: Dynamic version reading in `src/fapilog/__init__.py` using `importlib.metadata`
  - **NEW**: Robust fallback mechanism to `pyproject.toml` when package metadata unavailable
  - **NEW**: Support for both `tomllib` (Python 3.11+) and `tomli` (older versions) for TOML parsing
  - **NEW**: Comprehensive unit tests (13 tests) covering all version management scenarios
  - **ENHANCED**: Eliminated version duplication between `pyproject.toml` and `__init__.py`
  - **ENHANCED**: Automatic version synchronization - no manual updates needed in `__init__.py`
  - **ENHANCED**: Works correctly in both development (editable install) and production (pip install) environments
  - **ENHANCED**: Graceful error handling for edge cases (missing metadata, import errors, file not found)
  - **TESTED**: All tests passing with comprehensive coverage of fallback scenarios and edge cases
  - **MAINTAINED**: Full backward compatibility - existing code continues to work unchanged
  - **PERFORMANCE**: Zero overhead with efficient metadata reading and minimal fallback logic

  **Technical Implementation:**

  ```python
  # Version is now automatically read from pyproject.toml
  # No manual updates needed in __init__.py
  from fapilog import __version__
  print(__version__)  # Always matches pyproject.toml
  ```

  **Fallback Behavior:**

  - Primary: Reads from package metadata via `importlib.metadata.version("fapilog")`

## [Unreleased]

- Fallback: Reads directly from `pyproject.toml` if metadata unavailable
- Final fallback: Returns "0.1.2" if all else fails

**Test Coverage:**

- Version attribute existence and format validation
- Package metadata reading in various environments
- Fallback mechanisms for all error scenarios
- Import stability and consistency testing
- Edge cases: missing files, import errors, attribute errors

This improvement eliminates version drift issues and provides a robust, maintainable version management system suitable for production use.

- **Story 13.5a**: Metrics Collection System

  - **NEW**: Comprehensive metrics collection for queue and sink performance monitoring
  - **NEW**: `MetricsCollector` class with thread-safe metrics tracking and configurable sample windows
  - **NEW**: Queue metrics: size, peak size, throughput, latency, dropped events, and memory usage
  - **NEW**: Sink metrics: success/failure rates, write latency, batch sizes, retry counts, and error tracking
  - **NEW**: Performance metrics: total events, events per second, processing time, memory and CPU usage
  - **NEW**: Prometheus metrics export with HTTP endpoint for monitoring integration
  - **NEW**: `PrometheusExporter` class with FastAPI-based HTTP server for metrics scraping
  - **NEW**: Automatic metrics integration with all existing sinks (StdoutSink, FileSink, LokiSink)
  - **NEW**: Container-based metrics initialization with configurable enable/disable options
  - **NEW**: Comprehensive metrics configuration through `LoggingSettings` and environment variables
  - **PERFORMANCE**: Zero overhead when disabled, minimal impact when enabled with bounded memory usage
  - **PRODUCTION**: Enterprise-ready monitoring with proper resource cleanup and error handling
  - **DOCUMENTED**: Complete metrics setup guide, API reference, and working examples
  - **TESTED**: 30 comprehensive tests covering all metrics scenarios with 100% pass rate

  **Configuration Example:**

  ```python
  # Enable metrics collection
  settings = LoggingSettings(
      metrics_enabled=True,
      metrics_prometheus_enabled=True,
      metrics_prometheus_port=8000
  )
  configure_logging(settings=settings)

  # Or via environment variables
  export FAPILOG_METRICS_ENABLED=true
  export FAPILOG_METRICS_PROMETHEUS_ENABLED=true
  ```

  **Available Metrics:**

  - Queue: `fapilog_queue_size`, `fapilog_queue_enqueued_total`, `fapilog_queue_dropped_total`
  - Sinks: `fapilog_sink_writes_total`, `fapilog_sink_success_rate`, `fapilog_sink_latency_ms`
  - Performance: `fapilog_events_total`, `fapilog_events_per_second`, `fapilog_memory_bytes`

### Changed

- **Story 13.4**: Configuration API Simplification

  - **BREAKING**: Removed deprecated keyword arguments from `configure_logging()` function
  - **SIMPLIFIED**: Function signature now only accepts `settings` and `app` parameters
  - **REMOVED**: Deprecated parameters: `level`, `sinks`, `json_console`
  - **STANDARDIZED**: All configuration must now use `LoggingSettings` object
  - **IMPROVED**: Cleaner, more consistent API surface
  - **ENHANCED**: Better type safety and IDE support
  - **MAINTAINED**: All functionality preserved through `LoggingSettings`

  **Migration Example:**

  ```python
  # Before (deprecated)
  configure_logging(level="DEBUG", json_console="json")

  # After (recommended)
  settings = LoggingSettings(level="DEBUG", json_console="json")
  configure_logging(settings=settings)
  ```

- **Story 13.1**: Container-Based Architecture & Dependency Injection

  - **BREAKING INTERNAL**: Eliminated global state variables (`_configured`, `_queue_worker`) in favor of container-based dependency injection
  - **NEW**: `LoggingContainer` class provides advanced dependency injection with multiple configuration support
  - **ENHANCED**: Thread-safe container operations with proper locking and thread-local context management
  - **ENHANCED**: Multiple logging configurations can now coexist safely in the same process
  - **ENHANCED**: Better testability with isolated container instances preventing test interference
  - **ENHANCED**: Automatic memory management with container registry tracking and cleanup mechanisms
  - **ENHANCED**: Improved error handling with comprehensive container lifecycle management
  - **MAINTAINED**: Full backward compatibility - all existing code continues to work unchanged
  - **ADDED**: 42 new comprehensive tests covering container architecture, thread safety, and memory management
  - **IMPROVED**: Test coverage increased from 87% to 91%, exceeding production quality standards
  - **DOCUMENTED**: Complete container architecture documentation with usage examples and migration guide
  - **PERFORMANCE**: Minimal overhead with efficient container creation and resource management

  This major architectural improvement provides a solid foundation for enterprise applications while maintaining the simple, zero-friction API that makes fapilog easy to adopt.

## [0.1.1] - 2024-12-19

### Added

- **Story 12.4**: Configuration Guide & Examples

  - Created comprehensive `docs/config.md` with complete reference for all configuration options
  - Documented all 22 configuration fields with types, defaults, environment variables, and usage examples
  - Organized settings into logical sections: Core Logging, Redaction, Queue, and Advanced settings
  - Added sink-specific configuration documentation for File and Loki sinks with URI parameters
  - Included practical configuration examples for Development, Production, High-Volume, and Security-focused environments
  - Added validation section explaining error handling and common validation errors
  - All settings support both environment variable and programmatic configuration with clear examples
  - Perfect for developers integrating fapilog to understand available options and customization capabilities

- Enhanced PyPI package discoverability with improved keywords and description
- Competitive feature comparison in README showcasing advantages over alternatives
- Version-agnostic test suite that adapts to current project version
- Additional test coverage for queue worker shutdown scenarios and deprecated API warnings

### Changed

- Package description updated to "Production-ready structured logging for FastAPI with trace IDs, async queues, and observability integration"
- Expanded keywords for better PyPI searchability including "tracing", "monitoring", "microservices", "production", "cloud-native", "opentelemetry"
- Improved README with feature comparison table and competitive positioning
- Enhanced project documentation with clear package naming explanation (repository: fastapi-logger, PyPI: fapilog)
- Source distribution now includes only essential files (library code, README, license) excluding development artifacts
- Test coverage improved to 90.06% (above 90% threshold)

### Fixed

- Release guardrail tests now dynamically detect project version instead of hardcoded expectations
- Deprecated keyword argument tests properly handle warnings and edge cases

### Changed

- **Story 13.3**: Standardize Error Handling Patterns Across Codebase

  - Implemented comprehensive error handling system with 7 custom exception classes for different error types
  - Added `FapilogError` base class with context support and sensitive data filtering
  - Created specialized exceptions: `ConfigurationError`, `SinkError`, `QueueError`, `MiddlewareError`, `RedactionError`, `ContextError`
  - Built error handling utilities in `src/fapilog/_internal/error_handling.py` with context preservation and logging
  - Added advanced error recovery mechanisms: graceful degradation, retry with exponential backoff, safe execution
  - Updated all modules to use standardized error handling: bootstrap, queue, loki sink, middleware, redactors, enrichers
  - Implemented user-friendly error messages with rich context information and automatic sensitive data filtering
  - Added comprehensive error tests (55 test cases) covering all error scenarios with 96% test coverage
  - Enhanced error logging with `log_error_with_context()` for better debugging and troubleshooting
  - All error handling follows FastAPI and Pydantic V2 best practices with full async support
  - Maintains backward compatibility while providing robust error recovery and graceful degradation
  - Perfect for production environments requiring reliable error handling and user-friendly error messages

### Added

- **Story 11.4**: Trusted Publishing with GitHub Actions

  - Implemented automated PyPI publishing using GitHub Actions with Trusted Publishing (OIDC) for secure, token-free releases
  - Created `.github/workflows/publish.yml` workflow that triggers on version tags (`v*`) and automatically publishes to PyPI
  - Added version consistency validation ensuring tag version matches `pyproject.toml` version before publishing
  - Integrated build artifact verification checking both wheel (`.whl`) and source distribution (`.tar.gz`) are created
  - Enhanced security by eliminating need for API tokens through PyPI's Trusted Publishing feature
  - Updated `RELEASING.md` with simplified automated release process documentation removing manual upload steps
  - Workflow includes comprehensive error handling and validation steps with clear logging for troubleshooting
  - Publishing process now requires only: version bump, changelog update, commit, tag creation, and tag push
  - GitHub Actions automatically handles building, verification, and PyPI upload with full audit trail
  - Maintains backward compatibility with manual publishing process for testing purposes

- **Story 11.3**: Install Instructions & Version Pinning

  - Enhanced README.md Installation section with comprehensive version pinning guidance for production deployments
  - Added version pinning examples: `fapilog~=0.1.0` for production (allows patch updates) and `fapilog==0.1.0` for strict reproducibility
  - Added Python compatibility information: requires Python 3.8+ and supports Python 3.8, 3.9, 3.10, 3.11, and 3.12
  - Added "Quick Start" section with minimal usage snippet: `from fapilog import configure_logging, log; configure_logging(); log.info("Hello from fapilog!")`
  - Created `requirements-example.txt` file with common installation patterns for quick-start projects
  - Documented all optional extras: `[loki]`, `[fastapi]`, `[metrics]`, `[dev]` with clear use cases
  - Tested all installation commands locally in clean virtual environment to ensure copy-paste friendly instructions
  - Installation section now includes PyPI version badge, Python compatibility, and clear guidance for different deployment scenarios
  - Ready for new users to easily integrate fapilog into their projects with proper version management

- **Story 11.2**: Manual PyPI Publishing

  - Enhanced `RELEASING.md` with comprehensive manual PyPI publishing instructions including PyPI account setup, secure credential storage, and step-by-step upload process
  - Added detailed sections for TestPyPI testing, production PyPI upload, and troubleshooting common issues
  - Created `scripts/publish_to_pypi.py` helper script that validates build artifacts, checks credentials, and provides guided publishing workflow
  - Updated README.md with proper PyPI badge using dynamic version detection and comprehensive installation instructions including optional dependencies
  - Added installation examples for different use cases: `pip install fapilog[loki]`, `pip install fapilog[fastapi]`, `pip install fapilog[metrics]`, `pip install fapilog[dev]`
  - Verified build process works correctly: `python -m build` produces valid wheel and sdist artifacts in `dist/`
  - Confirmed `twine check dist/*` passes validation for both wheel and source distribution
  - Tested local installation: `pip install dist/fapilog-0.1.0-py3-none-any.whl` succeeds and `import fapilog` works
  - Added `__version__` attribute to `fapilog/__init__.py` for proper version detection
  - Ready for manual PyPI publishing with secure credential storage via `~/.pypirc` or environment variables
  - Complete documentation for repeatable manual publishing process with proper Git tagging workflow

- **Story 11.1**: Public Package Metadata

  - Enhanced `pyproject.toml` with comprehensive package metadata for PyPI discovery and distribution
  - Updated project description to "Production-ready structured logging for FastAPI with trace IDs, async queues, and observability integration" for better clarity
  - Added keywords array: `["fastapi", "logging", "structured", "asyncio", "middleware", "observability", "json", "loki", "tracing", "monitoring", "microservices", "production", "context", "correlation", "distributed", "cloud-native", "opentelemetry"]` for improved PyPI searchability
  - Added metadata badges to README.md: License (MIT), Python version support (3.8+), and PyPI version (0.1.0)
  - Verified build artifacts pass `python -m build` and `twine check dist/*` validation
  - All required metadata fields present: name, version, description, readme, license, authors, dependencies, classifiers
  - Project URLs configured for homepage, repository, documentation, and bug tracker
  - Optional dependencies documented: `dev`, `loki`, `fastapi`, `metrics` extras for different use cases
  - Ready for PyPI distribution with complete and accurate package information

- **Story 10.4**: CONTRIBUTING Guide

  - Created comprehensive `CONTRIBUTING.md` file with detailed setup instructions, development workflow, and contribution guidelines
  - Added project setup section with step-by-step instructions for cloning, virtual environment setup, and dependency installation
  - Included development workflow guidelines covering feature branch usage, code quality checks, and pre-commit hooks
  - Documented commit message conventions using Conventional Commits format with examples for different change types
  - Added pull request guidelines with proper title formatting and review process
  - Included release process documentation referencing `RELEASING.md` and semantic versioning guidelines
  - Added comprehensive "How to Get Help" section covering bug reporting, feature suggestions, and community guidelines
  - Included testing guidelines with best practices for writing tests and running test suites
  - Added code style guidelines covering PEP 8 compliance, type hints, and import organization
  - Created development commands reference section for quick access to common development tasks
  - Updated `README.md` to include link to contributing guide under new "🤝 Contributing" section
  - Ensured all sections align with project's existing tools (hatch, ruff, mypy, pytest, pre-commit)
  - Perfect for onboarding new contributors and maintaining consistent development practices across the project

- **Story 10.1**: CHANGELOG tracking and conventions

  - Added changelog link to README.md for easy access to version history
  - Added comprehensive changelog conventions to CONTRIBUTING.md with Keep a Changelog format guidelines
  - Established story reference format for traceability between changes and user stories
  - Ensured all future contributions will follow consistent changelog entry patterns

- **Story 9.4**: Build Artifacts with `python -m build`

  - Added `build>=1.0.0` to dev dependencies in `pyproject.toml` for package building
  - Running `python -m build` successfully creates both wheel (`.whl`) and source distribution (`.tar.gz`) artifacts
  - Build artifacts are saved to `dist/` folder and are valid for installation via `pip install dist/*.whl`
  - Generated packages install correctly and `import fapilog` succeeds after installation
  - Build process completes without warnings or errors using Hatchling backend
  - `dist/` directory is already properly ignored in `.gitignore` to prevent build artifacts from version control
  - Supports downstream release automation and PyPI distribution workflows
  - All required metadata properly configured in `pyproject.toml` including name, version, description, authors, license, dependencies, and classifiers

- **Story 9.2**: Pre-commit Hooks for Linting and Type-checking

  - Added `.pre-commit-config.yaml` with Ruff for linting and formatting, MyPy for type checking, and Vulture for dead code detection
  - Pre-commit hooks run automatically on staged files to catch issues before commit
  - Added `pre-commit>=3.0.0` and `vulture>=2.10.0` to dev dependencies in `pyproject.toml`
  - Updated README with pre-commit setup instructions and usage examples
  - Hooks configured to use project's existing Ruff and MyPy settings from `pyproject.toml`
  - Added comprehensive Vulture configuration with whitelist for legitimate unused code
  - Fixed example file `examples/16_security_logging.py` to use correct API imports
  - All hooks pass successfully on clean repository with no linting, type, or dead code errors
  - Developers can run `pre-commit install` to set up local git hooks
  - Manual execution available via `pre-commit run --all-files` for full codebase validation

- **Story 9.1**: CI Setup with GitHub Actions

  - Added comprehensive GitHub Actions workflow (`.github/workflows/ci.yml`) for automated testing and quality checks
  - Separate jobs for linting (`hatch run lint:lint`), type checking (`hatch run typecheck:typecheck`), and testing (`hatch run test:test`)
  - Optional tox job for compatibility validation across Python versions
  - Workflow triggers on pushes to `main` branch, pull requests to `main`, and all `feature/**` branches
  - Uses Python 3.11 and ubuntu-latest runners for consistent build environment
  - Added CI status badge to README.md showing build status
  - Failures block merging to main branch ensuring code quality standards
  - Supports both hatch-based and tox-based testing workflows

- **Story 7.2**: Automatic PII Redaction

  - New regex-based PII scanner as a post-processor in the logging pipeline
  - Automatically detects and redacts common sensitive values, including:
    - Email addresses
    - Credit card numbers (basic pattern, not Luhn)
    - Phone numbers
    - IPv4 addresses
  - Patterns are configurable via settings (`custom_pii_patterns`, `enable_auto_redact_pii`)
  - Redaction happens recursively across all string values in the event_dict
  - Uses the same `REDACT_REPLACEMENT` setting as field redaction
  - Unit tests confirm detection, replacement, and opt-out behavior
  - README includes explanation, limitations, and opt-out instructions

- **Story 7.1**: Field Redaction Support

  - New field-based redaction system in `fapilog/redactors.py` for precise control over sensitive data removal
  - Support for nested field redaction using dot notation (e.g., `user.password`, `auth.token`)
  - Automatic redaction of fields within lists of dictionaries (e.g., `users.password`)
  - Configurable replacement value via `FAPILOG_REDACT_REPLACEMENT` (default: `"REDACTED"`)
  - Environment variable support: `FAPILOG_REDACT_FIELDS` for comma-separated field list
  - Non-destructive redaction: original data is never modified, only log output is redacted
  - Integration with existing processor pipeline positioned after pattern-based redaction
  - Comprehensive unit tests (17 tests) covering flat fields, nested fields, lists, custom replacement values, and edge cases
  - Tests verify redaction works correctly with complex nested structures and list handling
  - Updated README with "Data Redaction" section documenting both pattern-based and field-based approaches
  - Examples showing before/after redaction output and combining both redaction methods
  - Perfect for GDPR compliance, security auditing, and protecting sensitive user data in logs
  - Zero performance impact with efficient recursive field processing

- **Story 7.3**: Context-Aware Redaction by Log Level

  - Added `FAPILOG_REDACT_LEVEL` setting to control minimum log level for redaction (default: `"INFO"`)
  - All redaction processors (pattern-based, field-based, and PII auto-detection) now respect log level thresholds
  - DEBUG logs bypass redaction to preserve full context for development and troubleshooting
  - INFO and higher logs apply redaction to protect sensitive data in production environments
  - Log level hierarchy: DEBUG < INFO < WARNING < ERROR < CRITICAL
  - Added helper functions `_get_log_level_numeric()` and `_should_redact_at_level()` for level comparison
  - Updated all redaction processors to accept and use `redact_level` parameter
  - Comprehensive unit tests (19 tests) covering all redaction types with different log levels
  - Tests verify level-aware behavior: DEBUG not redacted, INFO+ redacted, custom levels, missing levels
  - Integration tests confirm all redaction processors respect the same level setting
  - Updated README with "Level-Aware Redaction" section including examples and environment variable documentation
  - Perfect for development workflows where DEBUG provides full context while production logs remain secure
  - Zero performance impact with efficient level checking before redaction processing

- **Story 6.3**: Context Enricher: User and Auth Context

  - New `user_context_enricher` processor that automatically adds authenticated user information to log events
  - Added user context variables: `user_id_ctx`, `user_roles_ctx`, `auth_scheme_ctx` in `src/fapilog/_internal/context.py`
  - All log events during authenticated requests automatically include: `user_id`, `user_roles`, `auth_scheme`
  - New `create_user_dependency` factory function in `src/fapilog/enrichers.py` for FastAPI integration
  - Compatible with any FastAPI authentication mechanism (OAuth2, JWT, Bearer tokens, custom auth)
  - Supports both dict-based and class-based user objects with automatic field extraction
  - Graceful handling of unauthenticated requests (user fields omitted, no errors)
  - New `USER_CONTEXT_ENABLED` setting in `LoggingSettings` (default: True) for configuration control
  - Environment variable support: `FAPILOG_USER_CONTEXT_ENABLED` for easy deployment configuration
  - Manual user context binding via `bind_user_context()` helper function for non-HTTP contexts
  - Helper functions: `get_user_id()`, `get_user_roles()`, `get_auth_scheme()` for context access
  - Enricher positioned after request context enrichers, before custom enrichers in processor chain
  - Comprehensive unit tests (14 tests) in `tests/test_user_context.py` covering authentication scenarios, type conversions, edge cases, and FastAPI integration
  - Updated README with "User Context Enrichment" section documenting FastAPI integration, configuration, and usage examples
  - New example `examples/18_user_context_enrichment.py` demonstrating real-world authentication scenarios

## [0.1.2] - 2024-12-19

### Fixed

- Corrected license metadata from MIT to Apache-2.0 to match actual LICENSE file
- Updated PyPI classifiers to show correct Apache Software License
- Fixed README license badge to display Apache 2.0

## [Unreleased]

- Updated security logging example `examples/16_security_logging.py` to use user context enrichment
- Zero-configuration setup: wrap existing auth dependencies with `create_user_dependency()` for automatic user context
- Perfect for security auditing, user behavior analysis, and troubleshooting user-specific issues

- **Story 6.1**: Context Enricher: Request Metadata

  - Enhanced `TraceIDMiddleware` to automatically capture HTTP request metadata in context variables
  - New context variables: `client_ip` (client IP address), `method` (HTTP method), `path` (request path)
  - Configurable trace ID header extraction via `LoggingSettings.trace_id_header` (default: "X-Request-ID")
  - Updated `src/fapilog/_internal/context.py` with new context variable support and type safety
  - All log events during HTTP requests automatically include: `trace_id`, `span_id`, `method`, `path`, `client_ip`, `status_code`, `latency_ms`, `user_agent`, `req_bytes`, `res_bytes`
  - Context variables properly isolated per request using `contextvars` for async safety
  - Context automatically set up at request start and cleaned up after response completion
  - Enhanced `configure_logging()` to pass trace header settings to middleware
  - Comprehensive unit tests (11 tests) in `tests/test_request_enricher.py` covering context injection, cleanup, custom headers, and settings integration
  - Updated existing tests to use new default "X-Request-ID" header instead of "X-Trace-Id"
  - Updated README with "Request Context Enrichment" section documenting automatic fields, configuration, and usage examples
  - Zero-configuration setup: simply call `configure_logging(app=app)` for rich request metadata in all logs
  - Perfect request traceability across microservices with automatic trace ID propagation

- **Story 5.4**: Multi-Sink Fan-out Support

  - Logging now supports multiple sinks in parallel (fan-out) via the `FAPILOG_SINKS` environment variable or programmatic configuration.
  - All sinks receive the same log event; failures in one sink do not block others (full error isolation).
  - Internal runner uses `asyncio.gather(..., return_exceptions=True)` for concurrent, robust delivery.
  - Misconfigured sinks raise errors at startup, not at runtime.
  - Comprehensive unit tests in `tests/test_multi_sink.py` verify fan-out, error isolation, and startup validation.
  - README updated with a dedicated "Multiple Sink Support" section and usage examples.

- **Story 5.3**: Loki Sink via HTTP Push

  - New `LokiSink` class in `fapilog/sinks/loki.py` for pushing logs to Grafana Loki over HTTP
  - Supports `loki://` and `https://` URI-style config with `labels`, `batch_size`, and `batch_interval` parameters
  - Buffers logs and pushes them in batches to `/loki/api/v1/push` using `httpx.AsyncClient`
  - Each log is formatted as a Loki-compatible line: nanosecond timestamp and JSON-serialized event
  - Failures are logged and retried with exponential backoff; clear ImportError if `httpx` is missing
  - Unit tests verify batch formatting, buffering, label parsing, and retry logic
  - README documents Loki support, configuration, and install instructions

- **Story 5.2**: File Sink with Rotation Support

  - New `FileSink` class in `fapilog/sinks/file.py` with automatic log rotation using `logging.handlers.RotatingFileHandler`
  - URI-based configuration format: `file:///path/to/log.log?maxBytes=10485760&backupCount=5`
  - Configurable rotation parameters: `maxBytes` (default: 10 MB) and `backupCount` (default: 5)
  - Thread-safe async writing with immediate flush to prevent data loss in crash scenarios
  - Automatic directory creation for log file paths
  - Integration with sink loader in `configure_logging()` for environment-based configuration
  - Comprehensive unit tests (5 tests) covering file creation, rotation behavior, URI parsing, and error handling
  - Tests verify log file creation and writing, rotation occurs when file exceeds threshold, parsed query parameters override defaults, and invalid URIs raise helpful errors
  - Updated README with "File Sink" section documenting configuration, URI format, features, and production usage examples
  - Perfect for production environments requiring persistent logs with automatic size management
  - Support for multiple sinks simultaneously (e.g., `stdout,file:///var/log/app.log`)

- **Story 5.1**: Stdout Sink Implementation

  - Enhanced `StdoutSink` class with new mode parameter supporting `"json"`, `"pretty"`, and `"auto"` options
  - Integration with `structlog.dev.ConsoleRenderer` for proper pretty console output with ANSI color codes
  - Automatic TTY detection in `auto` mode: pretty output in interactive terminals, JSON in non-interactive environments
  - Updated sink integration in `bootstrap.py` to use new mode parameter instead of deprecated `pretty` boolean
  - Comprehensive unit tests (12 tests) covering all output formats, TTY detection, mode selection, and edge cases
  - Tests verify JSON output is compact and valid, pretty output contains ANSI codes, and auto mode correctly detects TTY
  - Updated existing tests in `test_log_queue.py` to use new interface
  - Updated README with "Sink Configuration" section documenting stdout sink usage and mode selection behavior
  - Perfect for development (pretty logs in terminal) and production (JSON logs in Docker/Kubernetes)
  - Default sink behavior with proper integration into async queue system

- **Story 4.4**: Custom Enricher Registry and Hook Support

  - Global registry for custom enrichers in `fapilog/enrichers.py` with `register_enricher(fn)` and `clear_enrichers()` functions
  - Custom enrichers are automatically included at the end of the processor chain in registration order
  - Enricher functions follow structlog processor signature: `(logger, method_name, event_dict) → event_dict`
  - Duplicate registration prevention (same function reference or name)
  - Exception handling ensures enricher failures don't break the logging pipeline
  - Comprehensive unit tests (13 tests) covering registration, execution order, duplicate handling, and error scenarios
  - Integration tests (5 tests) verifying custom enrichers work correctly in the full pipeline
  - Updated README with "Custom Enrichers" section including usage examples and best practices
  - Enables application-specific metadata injection without modifying core library
  - Test isolation support via `clear_enrichers()` for clean test state

- **Story 4.3**: Request Size & Response Size Enricher

  - New `body_size_enricher` processor that specifically adds `req_bytes` and `res_bytes` fields to log events
  - Request body size capture via `Content-Length` header or body size calculation
  - Response body size capture via `len(response.body)` when available
  - Works for standard JSON, form, and plain requests with graceful fallback to `Content-Length` header
  - Enricher positioned after context and before final rendering in processor chain
  - Logs emitted outside HTTP context do not raise errors—fields are omitted gracefully
  - Comprehensive unit tests verifying accurate request/response size measurement for various methods
  - Tests verify enricher skips gracefully when context is missing and field values are numeric
  - Integration with existing `TraceIDMiddleware` infrastructure for context variable management
  - Fields are only added if not already present, allowing manual override of values
  - Updated README "Log Fields" section already documents `req_bytes` and `res_bytes` fields

- **Story 4.2**: Memory & CPU Snapshot Enricher

  - New `resource_snapshot_enricher` processor that adds `memory_mb` and `cpu_percent` fields to all log events
  - Memory usage capture via `psutil.Process().memory_info().rss` converted to megabytes (rounded float)
  - CPU usage capture via `psutil.Process().cpu_percent(interval=None)` as percentage (0.0-100.0)
  - Cached `psutil.Process()` object for performance optimization using `@lru_cache`
  - Optional dependency on `psutil>=5.9` via `fapilog[metrics]` package
  - Conditional inclusion based on `LoggingSettings.enable_resource_metrics` (default: False)
  - Environment variable support: `FAPILOG_ENABLE_RESOURCE_METRICS` for easy configuration
  - Graceful error handling for cases where process info cannot be retrieved (OSError, AttributeError)
  - Fields are only added if not already present, allowing manual override of values
  - Enricher positioned after request/response enricher, before sampling processor
  - Comprehensive unit tests covering field presence, value validation, opt-out logic, and error handling
  - Integration tests verifying pipeline inclusion/exclusion based on settings
  - Updated README with "Resource Metrics" section including configuration, dependencies, and performance considerations
  - Updated "Log Fields" documentation to include `memory_mb` and `cpu_percent` fields

- **Story 4.1**: Hostname & Process Info Enricher

  - New `host_process_enricher` processor that adds `hostname` and `pid` fields to all log events
  - Automatic hostname detection via `socket.gethostname()` with performance caching using `@lru_cache`
  - Process ID capture via `os.getpid()` with caching for optimal performance
  - Fields are only added if not already present, allowing manual override of values
  - Enricher positioned early in processor chain (before redaction and rendering)
  - Zero external dependencies beyond standard library (`socket`, `os`)
  - Comprehensive unit tests covering field presence, manual override, caching, and edge cases
  - Updated README "Log Fields" section to document `hostname` and `pid` fields
  - Integration with existing processor pipeline ensuring consistent log format

- **Story 3.4**: Load Testing the Logging Queue

  - Comprehensive load testing script (`scripts/load_test_log_queue.py`) for simulating high-throughput logging scenarios
  - Configurable test parameters via CLI arguments or environment variables: concurrency, rate, duration, queue settings
  - Performance metrics tracking: total logs attempted, successfully enqueued, dropped logs, average enqueue latency
  - Support for all overflow strategies (drop, block, sample) with detailed performance reporting
  - Integration with hatch scripts: `hatch run test-queue-load` for easy execution
  - Updated README with "Benchmarking Logging Queue" section including usage examples and performance targets
  - Performance assessment with latency thresholds: <100 µs (excellent), <500 µs (good), >500 µs (poor)
  - Environment variable support for all test parameters: `LOAD_TEST_CONCURRENCY`, `LOAD_TEST_RATE`, `LOAD_TEST_DURATION`, etc.
  - Detailed test output with min/max latency, throughput analysis, and queue configuration summary
  - No external dependencies beyond `fapilog` and standard library modules

- **Story 3.3**: Queue Overflow Strategy: Drop, Block, or Sample

  - Configurable queue overflow handling via `LoggingSettings.queue_overflow` with three strategies:
    - `drop`: Silently discard logs when queue is full (default)
    - `block`: Wait for queue space before continuing (guaranteed delivery)
    - `sample`: Use probabilistic sampling when queue is full (adaptive logging)
  - Enhanced `QueueWorker.enqueue()` method to respect overflow strategy settings
  - Updated `queue_sink()` processor to handle different overflow strategies in sync contexts
  - Comprehensive unit tests for all overflow strategies with proper async/sync behavior
  - Updated README with "Controlling Queue Overflow Behavior" section and configuration examples
  - Environment variable support: `FAPILOG_QUEUE_OVERFLOW` for strategy selection
  - Integration with existing `sampling_rate` setting for sample strategy

- **Story 3.2**: Background Queue Worker & Graceful Shutdown

  - Enhanced `QueueWorker` shutdown with proper event loop management and timeout handling
  - Added `shutdown_sync()` method for safe shutdown from sync contexts (atexit, CLI)
  - Fixed event loop conflicts during shutdown using `run_coroutine_threadsafe`
  - Improved shutdown reliability with 5-second timeout to prevent hanging
  - Queue worker now tracks its event loop and ensures shutdown runs on the correct loop
  - Graceful degradation: if worker loop is unavailable, falls back to `asyncio.run()`
  - All tests now pass with robust async/sync shutdown handling
  - Updated test suite to use `@pytest.mark.asyncio` decorators for async tests
  - Fixed pytest-asyncio compatibility issues by pinning to version 0.23.6

- **Story 3.1**: Non-Blocking In-Process Log Queue

  - Async log queue implementation using `asyncio.Queue` for non-blocking logging
  - Background `QueueWorker` coroutine that processes log events in batches
  - Graceful degradation: when queue is full, events are dropped silently to prevent blocking
  - Retry logic with exponential backoff for failed sink writes
  - Graceful shutdown via `atexit` or FastAPI `on_shutdown` handlers
  - Comprehensive unit tests verifying queue behavior, capacity limits, and non-blocking performance
  - Queue configuration via environment variables: `FAPILOG_QUEUE_ENABLED`, `FAPILOG_QUEUE_SIZE`, `FAPILOG_QUEUE_BATCH_SIZE`, etc.
  - Updated README with "Async Logging Queue" section documenting performance benefits and configuration

- **Story 2.4**: Test Coverage for Middleware & Context Propagation

  - Achieved ≥90% enforced test coverage for `middleware.py` and `context.py` (trace propagation, request/response enrichment, context utilities)
  - Added/expanded tests for TraceIDMiddleware: header passthrough, trace generation, context cleanup, error handling, and idempotent registration
  - Verified request/response metadata enrichment (status code, latency, byte sizes, user-agent)
  - Ensured context utility helpers (`get_context`, `bind_context`, `clear_context`, `context_copy`) are fully covered
  - Added tests for context propagation in background tasks and isolation between concurrent requests (no context leakage)
  - CI and local coverage gate now enforce 90%+ threshold; PRs below threshold will fail
  - Updated README with contributor instructions for running middleware/context tests and viewing coverage delta

- **Story 2.3**: ContextVar Utilities & Leak Prevention

  - ContextVar utilities for safe context management with `get_context()`, `bind_context()`, `clear_context()`, and `context_copy()` functions
  - Automatic context propagation to background tasks using `asyncio.create_task(context_copy().run(func))`
  - Context leak prevention ensuring separate requests receive different trace_ids
  - Comprehensive unit tests for context utilities with 100% coverage
  - Background task context propagation example in README
  - Request & Response Metadata Enricher with automatic capture of HTTP status codes, request/response body sizes, latency, and user-agent information
  - Automatic enrichment of all log events with `status_code`, `latency_ms`, `req_bytes`, `res_bytes`, and `user_agent` fields
  - Comprehensive unit tests for request/response metadata enrichment covering POST requests with bodies, GET requests without bodies, and out-of-context logging
  - Baseline unit tests with comprehensive coverage for core functionality
  - Coverage gate enforcing minimum 85% test coverage threshold
  - GitHub Actions CI workflow with automated test execution
  - Expanded test suite covering import/bootstrap path, settings validation, and processor pipeline
  - Test coverage reporting with HTML and terminal output
