# Epic 10: Developer Experience & Ergonomics Improvements

**Epic Goal**: Transform fapilog's developer experience to match or exceed loguru's ease-of-use while maintaining its superior async-first architecture and production-grade features.

**Business Value**:

- Reduce onboarding time from 30 minutes to 5 minutes
- Increase developer adoption by lowering initial complexity barrier
- Maintain competitive advantage in async/production features while eliminating DX disadvantage
- Enable progressive disclosure: simple for beginners, powerful for experts

**Current Problem**:
fapilog has superior internals (async, backpressure, plugins) but inferior ergonomics compared to loguru and structlog. Users must write 10+ lines of boilerplate for common tasks that other libraries handle in 1-2 lines.

**Target Outcome**:
fapilog becomes the "best of both worlds" - as easy to start with as loguru, as powerful as the current implementation.

---

## Story 8.0: Epic Summary & Success Metrics

**Epic Overview**: This epic introduces ergonomic improvements to fapilog that dramatically reduce cognitive load and boilerplate while preserving all existing functionality and adding no breaking changes.

**Success Metrics:**

- Lines of code for common tasks reduced by 60-80%
- Zero-config setup works out of box for 90% of use cases
- FastAPI integration reduced from ~40 lines to 2-3 lines
- Human-readable config strings supported (e.g., "10 MB", "7 days")
- New user productivity within 5 minutes vs current 30 minutes

**Key Features:**

1. Configuration presets for common scenarios (dev, production, FastAPI)
2. Human-readable configuration strings
3. One-liner FastAPI integration
4. Pretty console output for development
5. Fluent builder API (optional)
6. Smart environment detection

**Non-Goals:**

- Breaking changes to existing API
- Removing advanced configuration options
- Sacrificing type safety or performance

**Dependencies:**

- None - all improvements are additive

**Timeline Estimate:**

- Phase 1 (Quick Wins): 1-2 weeks
- Phase 2 (API Improvements): 2-3 weeks
- Phase 3 (Advanced DX): 1-2 months

---

## Stories Overview

### Phase 1: Quick Wins

- **Story 8.1**: Configuration Presets (dev/production/fastapi/minimal)
- **Story 8.2**: Pretty Console Output for Development
- **Story 8.3**: One-Liner FastAPI Integration

### Phase 2: API Improvements

- **Story 8.4**: Human-Readable Configuration Strings
- **Story 8.5**: Simplified File Rotation API
- **Story 8.6**: Enhanced Default Behaviors

### Phase 3: Advanced DX

- **Story 8.7**: Fluent Builder API
- **Story 8.8**: Smart Environment Auto-Detection
- **Story 8.9**: DX Documentation & Migration Guide

---

## Story 8.1: Configuration Presets

**As a** developer new to fapilog,
**I want** to use pre-configured profiles for common scenarios,
**So that** I can get started in seconds without understanding all configuration options.

### Acceptance Criteria:

1. **Preset Support**

   - `get_logger(preset="dev")` enables development mode
   - `get_logger(preset="production")` enables production mode
   - `get_logger(preset="fastapi")` enables FastAPI-optimized mode
   - `get_logger(preset="minimal")` maintains current default behavior
   - Invalid preset raises clear error message

2. **Development Preset ("dev")**

   - Log level: DEBUG
   - Output format: Pretty console (colored, human-readable)
   - File logging: Disabled
   - Context enrichment: Enabled
   - Redaction: Disabled (safe for local development)

3. **Production Preset ("production")**

   - Log level: INFO
   - Output format: JSON
   - File logging: Enabled with rotation (50MB, 10 files)
   - Context enrichment: Enabled
   - Redaction: Enabled (field_mask for common sensitive fields)
   - Compression: Enabled for rotated files

4. **FastAPI Preset ("fastapi")**

   - Async mode: Enabled
   - Context variables: Enabled (request_id, user_id, trace_id)
   - Request logging middleware: Auto-configured
   - Output format: JSON
   - Log level: INFO

5. **Minimal Preset ("minimal")**

   - Matches current default: stdout JSON only
   - No file rotation, no extra enrichers

6. **Documentation**

   - README updated with preset examples
   - Comparison table showing what each preset configures
   - Migration guide for users with existing Settings objects

7. **Tests**
   - Unit tests for each preset configuration
   - Integration tests verifying preset behavior
   - Backward compatibility tests (no preset = minimal)

### Technical Notes:

- Presets are implemented as Settings dictionaries
- Users can override preset values: `get_logger(preset="production", level="DEBUG")`
- Presets don't break existing `settings=Settings(...)` usage

---

## Story 8.2: Pretty Console Output for Development

**As a** developer working locally,
**I want** human-readable, colored console output instead of raw JSON,
**So that** I can easily read logs during development and debugging.

### Acceptance Criteria:

1. **Pretty Formatter Implementation**

   - Human-readable timestamp format
   - Colored log levels (ERROR=red, WARNING=yellow, INFO=blue, DEBUG=gray)
   - Key-value pairs displayed inline: `message key1=value1 key2=value2`
   - Exception tracebacks formatted for readability
   - TTY detection: auto-enable colors in terminal, disable in pipes/files

2. **Configuration Options**

   - `format="pretty"` - force pretty mode
   - `format="json"` - force JSON mode
   - `format="auto"` - auto-detect based on TTY (default)
   - Colors can be disabled: `pretty_colors=False`

3. **Output Examples**

   ```
   # Pretty format
   2025-01-09 14:30:22 | INFO     | Application started env=production version=1.0.0
   2025-01-09 14:30:23 | WARNING  | High memory usage percent=85 threshold=80
   2025-01-09 14:30:24 | ERROR    | Database connection failed host=localhost error=timeout

   # JSON format (current behavior)
   {"timestamp":"2025-01-09T14:30:22Z","level":"INFO","message":"Application started","env":"production","version":"1.0.0"}
   ```

4. **Integration with Presets**

   - `preset="dev"` uses `format="pretty"` by default
   - `preset="production"` uses `format="json"` by default
   - Explicit `format=` overrides preset default

5. **Performance**

   - Pretty formatting only applied to stdout sink
   - No performance impact on JSON sinks
   - Lazy formatting (only format if being written)

6. **Tests**
   - Unit tests for pretty formatter
   - TTY detection tests
   - Color output tests
   - Performance benchmarks vs JSON formatting

### Technical Notes:

- Implement as new `PrettyConsoleSink` plugin
- Use ANSI color codes for terminal colors
- Fallback gracefully when colors not supported

---

## Story 8.3: One-Liner FastAPI Integration

**As a** FastAPI developer,
**I want** to enable logging with a single function call,
**So that** I don't have to write 40+ lines of boilerplate for middleware and lifecycle management.

### Acceptance Criteria:

1. **Setup Function**

   ```python
   from fapilog.fastapi import setup_logging

   app = FastAPI()
   setup_logging(app)  # That's it!
   ```

2. **What It Configures**

   - Adds `RequestContextMiddleware` for correlation IDs
   - Adds `LoggingMiddleware` for request/response logging
   - Configures lifespan manager for logger cleanup
   - Registers logger dependency for `Depends(get_logger)`

3. **Configuration Options**

   ```python
   setup_logging(
       app,
       preset="production",           # Use preset
       sample_rate=1.0,               # Log all requests
       skip_paths=["/health"],        # Skip health checks
       redact_headers=["authorization"], # Redact sensitive headers
       include_request_body=False,    # Don't log request bodies
       include_response_body=False,   # Don't log response bodies
   )
   ```

4. **Logger Dependency**

   ```python
   from fapilog.fastapi import get_logger
   from fastapi import Depends

   @app.get("/")
   async def home(logger = Depends(get_logger)):
       await logger.info("Request handled")
       return {"status": "ok"}
   ```

5. **Backward Compatibility**

   - Existing manual middleware setup still works
   - No breaking changes to current FastAPI integration
   - Users can gradually migrate to new setup function

6. **Documentation**

   - FastAPI quickstart guide updated
   - Examples showing before/after code reduction
   - Advanced configuration guide for custom setups

7. **Tests**
   - Integration tests with FastAPI TestClient
   - Middleware registration tests
   - Lifespan management tests
   - Request context propagation tests

### Technical Notes:

- Lifespan wrapper handles async logger cleanup
- Dependency injection uses request-scoped logger instances
- Context variables automatically propagate to background tasks

---

## Story 8.4: Human-Readable Configuration Strings

**As a** developer,
**I want** to use intuitive strings like "10 MB" and "7 days" for configuration,
**So that** I don't have to calculate bytes or convert time units manually.

### Acceptance Criteria:

1. **Size Parsing**

   - Supports: "10 KB", "50 MB", "1 GB", "2 TB"
   - Case insensitive: "10mb", "10 MB", "10 Mb" all work
   - Integer bytes still supported: `max_bytes=10485760`
   - Clear error on invalid format: "Invalid size format: '10 XB'. Use format like '10 MB'"

2. **Duration Parsing**

   - Supports: "5s", "10m", "1h", "7d", "2w"
   - Multiple units: "1h 30m" = 5400 seconds
   - Integer seconds still supported: `timeout=5.0`
   - Clear error on invalid format

3. **Retention Parsing**

   - File count: `retention=7` keeps 7 files
   - Time-based: `retention="7 days"` deletes files older than 7 days
   - Size-based: `retention="100 MB"` keeps total size under 100MB
   - Combined: `retention={"count": 7, "age": "30 days", "size": "100 MB"}`

4. **Integration Points**

   ```python
   # File rotation with human-readable config
   logger.add_file(
       "app.log",
       rotation="10 MB",      # Instead of max_bytes=10485760
       retention="7 days",     # Instead of manual cleanup
       compression=True,
   )

   # Settings object
   settings = Settings(
       file=RotatingFileSettings(
           max_bytes="50 MB",
           retention="14 days",
       )
   )
   ```

5. **Validation**

   - Pydantic validators convert strings to appropriate types
   - Type hints updated to accept `str | int` where applicable
   - Validation errors show both original string and expected format

6. **Documentation**

   - Configuration reference updated with string format examples
   - Migration guide for converting existing integer configs
   - Type hints in IDE show accepted string formats

7. **Tests**
   - Parser unit tests for all formats
   - Edge case tests (negative, zero, overflow)
   - Pydantic validation tests
   - Backward compatibility tests

### Technical Notes:

- Implement `parse_size()`, `parse_duration()`, `parse_retention()` utilities
- Add Pydantic field validators using `@field_validator`
- Maintain type safety with Union types

---

## Story 8.5: Simplified File Rotation API

**As a** developer,
**I want** a simple method to add file rotation,
**So that** I don't need to create Settings objects for basic file logging.

### Acceptance Criteria:

1. **New Method: `logger.add_file()`**

   ```python
   logger = get_logger()
   logger.add_file(
       "app.log",
       rotation="10 MB",       # Size-based rotation
       retention="7 days",      # Keep 7 days of logs
       compression=True,        # Compress rotated files
       level="INFO",           # Minimum level for this file
       format="json",          # json or text
   )
   ```

2. **Multiple File Sinks**

   ```python
   # Separate files for different levels
   logger.add_file("info.log", level="INFO", rotation="10 MB")
   logger.add_file("errors.log", level="ERROR", rotation="50 MB")
   logger.add_file("debug.log", level="DEBUG", retention="1 day")
   ```

3. **Time-Based Rotation**

   ```python
   logger.add_file(
       "app.log",
       rotation="daily",      # Rotate at midnight
       retention="30 days",
   )

   # Also support: "hourly", "weekly", "monthly"
   # Or specific time: rotation="00:00"
   ```

4. **Return Sink ID**

   ```python
   sink_id = logger.add_file("app.log", rotation="10 MB")

   # Later: remove the sink
   logger.remove_sink(sink_id)
   ```

5. **Integration with Settings**

   - `add_file()` dynamically adds sink without recreating logger
   - Works alongside Settings-based configuration
   - Changes don't affect existing sinks

6. **Error Handling**

   - Clear error if directory doesn't exist (with suggestion to create)
   - Clear error on permission issues
   - Validates rotation/retention formats before adding sink

7. **Tests**
   - Unit tests for add_file() method
   - Integration tests with rotation triggers
   - Multiple sink tests
   - Remove sink tests
   - Error handling tests

### Technical Notes:

- Implement as method on logger facades
- Internally creates RotatingFileSinkConfig and registers with worker
- Sink IDs are UUIDs for safe removal

---

## Story 8.6: Enhanced Default Behaviors

**As a** developer,
**I want** sensible defaults that work for most use cases,
**So that** I rarely need to configure anything explicitly.

### Acceptance Criteria:

1. **Smart Log Level Defaults**

   - Development (interactive terminal): DEBUG
   - Production (deployed environment): INFO
   - CI/CD environment: INFO
   - Respects `LOG_LEVEL` or `FAPILOG_LOG_LEVEL` env var

2. **Automatic Sink Selection**

   - TTY detected → Pretty console output
   - No TTY (piped/file) → JSON output
   - Docker/Kubernetes → JSON with container metadata
   - AWS Lambda → CloudWatch-optimized format

3. **Context Enrichment**

   - Always include: timestamp, level, message, logger name
   - Production: Add host, pid, env, version
   - FastAPI: Add request_id, user_id if available
   - Kubernetes: Add pod, namespace, node if detected

4. **Graceful Degradation**

   - CloudWatch sink fails → fallback to file
   - File write fails → fallback to stderr
   - Never lose logs due to sink failure
   - Emit warning on degradation

5. **Performance Defaults**

   - Queue size: 10,000 events
   - Batch size: 100 events
   - Flush interval: 1 second
   - Drop policy: Wait (don't lose logs by default)

6. **Security Defaults**

   - Common sensitive fields auto-redacted in production preset
   - Fields: password, api_key, token, secret, authorization
   - URL credentials always masked
   - Exception locals limited to 10 frames by default

7. **Tests**
   - Environment detection tests
   - Default value tests
   - Fallback behavior tests
   - Integration tests for each environment type

### Technical Notes:

- Use environment variable detection for smart defaults
- Check for `/var/run/secrets/kubernetes.io` for k8s detection
- Check for `AWS_LAMBDA_FUNCTION_NAME` for Lambda detection

---

## Story 8.7: Fluent Builder API

**As a** developer who prefers builder patterns,
**I want** a chainable API for configuring the logger,
**So that** I can discover options through IDE autocomplete and build configurations fluently.

### Acceptance Criteria:

1. **Builder Implementation**

   ```python
   from fapilog import LoggerBuilder

   logger = (
       LoggerBuilder()
       .with_name("api")
       .with_level("INFO")
       .add_file("app.log", rotation="10 MB", retention=7)
       .add_cloudwatch("/my-app/logs", region="us-east-1")
       .with_redaction(fields=["password", "ssn"])
       .with_context(service="api", env="production")
       .with_preset("production")  # Apply preset then override
       .build()
   )
   ```

2. **Method Chaining**

   - All methods return `self` for chaining
   - `build()` creates and returns the logger
   - Type hints ensure IDE autocomplete works perfectly

3. **Sink Methods**

   ```python
   builder.add_file(path, rotation=None, retention=None, level=None)
   builder.add_cloudwatch(log_group, region=None, stream=None)
   builder.add_postgres(connection_string, table="logs")
   builder.add_loki(url, labels=None)
   builder.add_stdout(format="json")
   builder.add_webhook(url, secret=None)
   ```

4. **Configuration Methods**

   ```python
   builder.with_level(level)           # Set log level
   builder.with_preset(preset)         # Apply preset
   builder.with_context(**kwargs)      # Set context variables
   builder.with_redaction(fields=[], patterns=[])
   builder.with_enrichers(*enrichers)
   builder.with_filters(*filters)
   builder.with_queue_size(size)
   builder.with_batch_size(size)
   ```

5. **Async Builder**

   ```python
   from fapilog import AsyncLoggerBuilder

   logger = await (
       AsyncLoggerBuilder()
       .with_level("INFO")
       .add_file("app.log")
       .build_async()
   )
   ```

6. **Validation**

   - Builder validates configuration on `build()`
   - Clear error messages for invalid combinations
   - Type hints prevent invalid method calls

7. **Documentation**

   - Builder API reference
   - Examples comparing Settings vs Builder approach
   - When to use each approach guide

8. **Tests**
   - Builder method tests
   - Chain validation tests
   - Build output tests
   - Type hint tests

### Technical Notes:

- Builder internally creates Settings object
- `build()` calls `get_logger(settings=...)`
- Builder is syntactic sugar, not a new implementation

---

## Story 8.8: Smart Environment Auto-Detection

**As a** developer,
**I want** the logger to auto-configure based on my deployment environment,
**So that** I get optimal settings without manual configuration.

### Acceptance Criteria:

1. **Environment Detection**

   - Local development: Interactive terminal session
   - Docker: `/proc/1/cgroup` contains `docker`
   - Kubernetes: `/var/run/secrets/kubernetes.io/serviceaccount` exists
   - AWS Lambda: `AWS_LAMBDA_FUNCTION_NAME` env var set
   - CI/CD: `CI=true` or common CI env vars (GITHUB_ACTIONS, JENKINS_URL, etc.)

2. **Development Environment**

   - Log level: DEBUG
   - Output: Pretty console with colors
   - File logging: Disabled
   - Enrichers: Minimal (timestamp, level, message)

3. **Docker Environment**

   - Log level: INFO (or from env var)
   - Output: JSON to stdout
   - Add: container_id, container_name
   - File logging: Disabled (let Docker handle persistence)

4. **Kubernetes Environment**

   - Log level: INFO
   - Output: JSON to stdout
   - Add: pod_name, pod_namespace, node_name, container_name
   - Labels from pod annotations if available
   - File logging: Disabled (let k8s handle persistence)

5. **AWS Lambda Environment**

   - Log level: INFO
   - Output: CloudWatch-optimized JSON
   - Add: function_name, function_version, request_id
   - Batch settings optimized for Lambda timeouts
   - Auto-drain on shutdown

6. **CI/CD Environment**

   - Log level: INFO
   - Output: JSON to stdout (parseable)
   - No colors (even if TTY)
   - Timestamps in ISO format
   - Add: ci_provider, build_id, commit_sha

7. **Override Mechanism**

   ```python
   # Auto-detect
   logger = get_logger()

   # Disable auto-detection
   logger = get_logger(auto_detect=False)

   # Override specific detection
   logger = get_logger(environment="production")
   ```

8. **Metadata Enrichment**

   - Kubernetes: Read from `/etc/hostname`, downward API
   - Docker: Read from `/proc/self/cgroup`
   - AWS: Read from Lambda environment variables
   - CI: Read from standard CI env vars

9. **Tests**
   - Mock environment detection for each platform
   - Configuration tests for each environment
   - Override tests
   - Metadata enrichment tests

### Technical Notes:

- Implement as `detect_environment()` function
- Environment detection runs once at logger creation
- Detected config merged with explicit config (explicit wins)

---

## Story 8.9: DX Documentation & Migration Guide

**As a** developer evaluating or adopting fapilog,
**I want** comprehensive documentation showing DX improvements and migration paths,
**So that** I can quickly understand the value and adopt the new features.

### Acceptance Criteria:

1. **DX Comparison Page**

   - Side-by-side: fapilog vs loguru vs structlog
   - Code examples for common tasks
   - Lines of code comparison
   - Feature matrix
   - When to use each library

2. **Quick Start Guide**

   - Zero to logging in 60 seconds
   - Shows preset usage first
   - Progressive examples (simple → advanced)
   - FastAPI integration example
   - Common patterns cookbook

3. **Migration Guides**

   - **From stdlib logging**: Direct translation examples
   - **From loguru**: Feature mapping and code conversion
   - **From structlog**: Processor → enricher mapping
   - **From old fapilog**: Settings → presets conversion

4. **API Reference Updates**

   - All new methods documented
   - Preset descriptions and use cases
   - Builder API reference
   - Human-readable config formats

5. **Examples Repository**

   ```
   examples/
   ├── quickstart/
   │   ├── 01_hello_world.py
   │   ├── 02_presets.py
   │   ├── 03_file_rotation.py
   │   └── 04_custom_config.py
   ├── fastapi/
   │   ├── 01_setup.py
   │   ├── 02_request_logging.py
   │   └── 03_custom_middleware.py
   ├── advanced/
   │   ├── builder_api.py
   │   ├── multi_sink.py
   │   └── custom_enrichers.py
   └── migration/
       ├── from_loguru.py
       ├── from_structlog.py
       └── from_stdlib.py
   ```

6. **Before/After Showcases**

   - Real-world examples showing code reduction
   - Performance comparisons
   - DX improvement metrics

7. **Video Tutorials** (Optional)

   - 5-minute quickstart screencast
   - FastAPI integration walkthrough
   - Advanced configuration deep dive

8. **FAQ Updates**
   - When to use presets vs custom config?
   - How do I migrate from X?
   - What's the difference between fapilog and Y?
   - Performance FAQ

### Technical Notes:

- Documentation uses MkDocs or Sphinx
- Code examples are tested in CI
- Keep examples up to date with library changes

---

## Implementation Phases

### Phase 1: Quick Wins (Week 1-2)

- Story 8.1: Configuration Presets
- Story 8.2: Pretty Console Output
- Story 8.3: One-Liner FastAPI Integration
- **Outcome**: Immediate DX improvement for new users

### Phase 2: API Improvements (Week 3-5)

- Story 8.4: Human-Readable Configuration Strings
- Story 8.5: Simplified File Rotation API
- Story 8.6: Enhanced Default Behaviors
- **Outcome**: Competitive parity with loguru ergonomics

### Phase 3: Advanced DX (Month 2-3)

- Story 8.7: Fluent Builder API
- Story 8.8: Smart Environment Auto-Detection
- Story 8.9: DX Documentation & Migration Guide
- **Outcome**: Best-in-class developer experience

---

## Success Criteria

### Quantitative Metrics:

- [ ] Lines of code for basic setup: 10+ → 1-3
- [ ] Lines for FastAPI integration: 40+ → 2-3
- [ ] Time to first log: 30 min → 5 min
- [ ] GitHub stars increase by 20% within 3 months
- [ ] Documentation visits increase by 50%

### Qualitative Metrics:

- [ ] Developer feedback: "As easy as loguru, better for production"
- [ ] Zero breaking changes
- [ ] 90%+ of use cases covered by presets
- [ ] IDE autocomplete shows intuitive options

### Technical Criteria:

- [ ] All new features have 90%+ test coverage
- [ ] Type safety maintained (mypy strict)
- [ ] Performance unchanged or improved
- [ ] Backward compatibility 100%

---

## Open Questions

1. Should presets be extensible (users define custom presets)?
2. Should builder API be the recommended approach or alternative?
3. Do we need a migration CLI tool for automated conversion?
4. Should we support loguru-compatible imports for easy migration?

---

## Dependencies & Risks

### Dependencies:

- None - all changes are additive to existing codebase

### Risks:

1. **Complexity creep**: Adding too many ways to configure

   - Mitigation: Clear documentation on when to use each approach

2. **Preset bikeshedding**: Endless debate on preset defaults

   - Mitigation: Data-driven decisions based on user research

3. **Maintenance burden**: More APIs to maintain

   - Mitigation: Builder/presets are thin wrappers over Settings

4. **User confusion**: Too many options
   - Mitigation: Progressive disclosure in docs (simple first)

---

## Related Epics

- **Epic 5**: Developer Experience & Documentation (provides foundation)
- **Epic 9**: FastAPI Integration Layer (Story 8.3 enhances this)
- **Epic 7**: Community & Ecosystem Growth (DX improvements drive adoption)
