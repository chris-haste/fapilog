# Source Tree

```plaintext
fapilog/
├── src/
│   └── fapilog/
│       ├── __init__.py                 # Public API: AsyncLogger, UniversalSettings
│       ├── py.typed                    # Type information marker
│       │
│       ├── core/                       # Core async-first logging
│       │   ├── __init__.py
│       │   ├── logger.py               # AsyncLogger - main interface
│       │   ├── events.py               # LogEvent, EventCategory, EventSeverity
│       │   ├── settings.py             # UniversalSettings configuration
│       │   └── pipeline.py             # AsyncPipeline for event processing
│       │
│       ├── containers/                 # Perfect isolation (v2 excellence)
│       │   ├── __init__.py
│       │   └── container.py            # AsyncLoggingContainer
│       │
│       ├── plugins/                    # Universal plugin system
│       │   ├── __init__.py
│       │   ├── registry.py             # Plugin discovery via entry points (multi-group)
│       │   ├── base.py                 # Base plugin classes
│       │   ├── sinks/                  # Built-in sinks (stdout, file)
│       │   │   ├── __init__.py
│       │   │   ├── stdout.py           # Console output sink
│       │   │   ├── file.py             # File output sink
│       │   │   └── http.py             # Basic HTTP sink
│       │   ├── processors/             # Built-in processors
│       │   │   ├── __init__.py
│       │   │   └── formatter.py        # Basic log formatting
│       │   └── enrichers/              # Built-in enrichers
│       │       ├── __init__.py
│       │       └── timestamp.py        # Timestamp enrichment
│       │
│       ├── caching/                    # AsyncSmartCache (v2 excellence)
│       │   ├── __init__.py
│       │   └── smart_cache.py          # Race-condition-free caching
│       │
│       ├── metrics/                    # Optional built-in metrics
│       │   ├── __init__.py
│       │   └── collector.py            # Basic performance tracking
│       │
│       ├── fastapi/                    # FastAPI integration layer
│       │   ├── __init__.py             # Import guard (AVAILABLE flag) for optional extra
│       │   ├── middleware.py           # FapilogMiddleware for request context
│       │   ├── lifecycle.py            # App startup/shutdown hooks
│       │   ├── exceptions.py           # Exception logging integration
│       │   ├── di.py                   # Dependency injection via Depends
│       │   └── testing.py              # Test fixtures and utilities
│       │
│       └── cli/                        # Command line interface
│           ├── __init__.py
│           └── main.py                 # Basic CLI commands
│
├── plugins/                            # Example community plugins
│   ├── fapilog-splunk/                 # Enterprise Splunk integration
│   │   ├── src/fapilog_splunk/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── fapilog-audit-trail/            # Enterprise audit trail
│   │   ├── src/fapilog_audit_trail/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── fapilog-prometheus/             # Metrics collection
│   │   ├── src/fapilog_prometheus/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── fapilog-request-logger/         # FastAPI request/response logging
│   │   ├── src/fapilog_request_logger/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── fapilog-otel-formatter/         # OpenTelemetry formatting
│   │   ├── src/fapilog_otel_formatter/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── fapilog-compliance-pci/         # PCI-DSS compliance
│       ├── src/fapilog_compliance_pci/
│       ├── pyproject.toml
│       └── README.md
│
├── tests/                              # Comprehensive test suite
│   ├── unit/                           # Core library unit tests
│   │   ├── test_logger.py
│   │   ├── test_events.py
│   │   ├── test_container.py
│   │   └── test_plugins.py
│   ├── integration/                    # Plugin integration tests
│   │   ├── test_sink_plugins.py
│   │   └── test_processor_plugins.py
│   ├── performance/                    # 500K-2M events/second validation
│   │   ├── test_throughput.py
│   │   └── test_latency.py
│   └── plugin_examples/                # Plugin development examples
│       ├── example_sink.py
│       ├── example_processor.py
│       └── example_enricher.py
│
├── docs/                               # Documentation
│   ├── quickstart.md                   # Zero-config getting started
│   ├── plugin-development.md          # Plugin creation guide
│   ├── enterprise-guide.md            # Enterprise deployment
│   ├── performance-tuning.md          # 500K-2M optimization
│   ├── compliance-guide.md            # Compliance plugin usage
│   └── api-reference.md               # Complete API documentation
│
├── examples/                           # Usage examples
│   ├── basic_usage.py                  # Simple logger usage
│   ├── plugin_usage.py                # Using community plugins
│   ├── enterprise_setup.py            # Enterprise configuration
│   └── performance_demo.py            # High-throughput example
│
├── scripts/                            # Development and maintenance
│   ├── benchmark.py                    # Performance benchmarking
│   ├── plugin_validator.py            # Plugin validation utility
│   └── generate_docs.py               # Documentation generation
│
├── pyproject.toml                      # Core library packaging
├── README.md                           # Developer-first documentation
├── LICENSE                             # Apache 2.0 license
├── CONTRIBUTING.md                     # Community contribution guide
├── CHANGELOG.md                        # Version history
└── .github/                            # CI/CD and community
    ├── workflows/
    │   ├── ci.yml                      # Core library CI
    │   ├── plugin-ci.yml               # Plugin validation CI
    │   └── performance.yml             # Throughput validation
    └── ISSUE_TEMPLATE/
        ├── bug_report.md
        ├── feature_request.md
        └── plugin_request.md
```

## Plugin entry points (v3)

- Registration uses multiple entry point groups to classify plugins by type:
  - `fapilog.sinks`
  - `fapilog.processors`
  - `fapilog.enrichers`
  - `fapilog.alerting`
- Legacy `fapilog.plugins` is heuristically supported for back-compat.

## Optional FastAPI integration

- Declared as an extra in `pyproject.toml`: `[project.optional-dependencies].fastapi`.
- `fapilog.fastapi` uses an import guard and exposes `AVAILABLE` and `get_router`.
- If FastAPI is not installed, `AVAILABLE` is `False` and integration remains inactive.
