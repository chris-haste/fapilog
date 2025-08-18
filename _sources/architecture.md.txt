# Fapilog v3 Architecture Document

This document outlines the overall project architecture for **Fapilog v3**, including backend systems, shared services, and non-UI specific concerns. Its primary goal is to serve as the guiding architectural blueprint for AI-driven development, ensuring consistency and adherence to chosen patterns and technologies.

**Relationship to Frontend Architecture:**  
Since Fapilog v3 is primarily a Python library with CLI components and a future plugin marketplace, any web-based interfaces (plugin marketplace, monitoring dashboards) will require a separate Frontend Architecture Document that MUST be used in conjunction with this document. Core technology stack choices documented herein are definitive for the entire project.

## Introduction

### Starter Template or Existing Project

**Decision:** N/A - Complete greenfield development with no starter templates, building a Python library from scratch.

**Analysis from your project:**

- This is a Python library (not a web application)
- Current structure suggests you're building from scratch
- Focus is on async-first architecture patterns
- CLI components for tooling
- Plugin marketplace infrastructure planned

### Change Log

| Date       | Version | Description                            | Author                            |
| ---------- | ------- | -------------------------------------- | --------------------------------- |
| 2024-01-XX | 1.0     | Initial architecture document creation | Winston (Senior System Architect) |

## High Level Architecture

### Technical Summary

Fapilog v3 employs a revolutionary **async-first pipeline architecture** designed for universal adoption from individual developers to enterprise-scale applications. The system utilizes **zero-copy operations** and **parallel processing** to achieve 500K-2M events/second throughput while maintaining perfect container isolation. Core architectural patterns include an **extensible plugin ecosystem**, **enterprise compliance framework**, and **async-first component factory pattern** that recreates v2 excellence in a pure async context. This architecture directly supports the PRD goals of achieving 9/10+ scores across all architectural categories while enabling both developer productivity and enterprise-grade reliability.

### High Level Overview

**Architectural Style:** **Async-First Monolithic Library** with **Plugin-Based Extensibility**

- **Repository Structure:** Monorepo (as specified in PRD technical assumptions)
- **Service Architecture:** Monolithic core with clear separation through plugin system
- **Primary Data Flow:** Async pipeline with parallel enrichment → processing → sink delivery
- **Key Architectural Decisions:**
  - Pure async-first design (no sync/async mixing)
  - Zero-copy operations throughout the pipeline
  - Container isolation with zero global state
  - Universal plugin ecosystem for extensibility
  - Enterprise compliance built into core architecture

### High Level Project Diagram

```mermaid
graph TB
    subgraph "Application Layer"
        APP["Python Application"]
        CLI["Fapilog CLI"]
    end

    subgraph "Fapilog v3 Core"
        LOGGER["AsyncLogger"]
        CONTAINER["AsyncLoggingContainer"]
        EVENTS["LogEvent Pipeline"]
    end

    subgraph "Plugin Ecosystem"
        ENRICHERS["Enricher Plugins<br/>Context, Metrics, Tracing"]
        PROCESSORS["Processor Plugins<br/>Filtering, Transform, Monitor"]
        SINKS["Sink Plugins<br/>File, DB, Cloud, SIEM"]
    end

    subgraph "Enterprise Features"
        COMPLIANCE["Compliance Engine<br/>PCI-DSS, HIPAA, SOX"]
        METRICS["Metrics Collection<br/>Performance, Health"]
        MARKETPLACE["Plugin Marketplace<br/>Discovery, Install"]
    end

    subgraph "External Systems"
        SIEM["SIEM Systems<br/>Splunk, ELK"]
        CLOUD["Cloud Storage<br/>S3, Azure, GCP"]
        MONITOR["Monitoring<br/>Datadog, Sentry"]
    end

    APP --> LOGGER
    CLI --> CONTAINER
    LOGGER --> CONTAINER
    CONTAINER --> EVENTS

    EVENTS --> ENRICHERS
    ENRICHERS --> PROCESSORS
    PROCESSORS --> SINKS

    CONTAINER --> COMPLIANCE
    CONTAINER --> METRICS
            MARKETPLACE --> CONTAINER

        SINKS --> SIEM
        SINKS --> CLOUD
        SINKS --> MONITOR

        subgraph "Framework Integrations"
            FASTAPI["FastAPI Integration Layer<br/>Middleware, DI, Lifecycle"]
        end

        App --> FASTAPI
        FASTAPI --> LOGGER
        FASTAPI --> CONTAINER

        style CONTAINER fill:#e1f5fe
        style EVENTS fill:#f3e5f5
        style FASTAPI fill:#fff3e0
    style COMPLIANCE fill:#fff3e0
```

### Architectural and Design Patterns

Based on your PRD requirements and v2 excellence patterns, here are the key patterns that will guide the architecture:

- **Async-First Pipeline Pattern:** Pure async/await throughout the logging pipeline with parallel processing - _Rationale:_ Achieves 500K-2M events/second throughput target and 90% latency reduction from PRD requirements

- **Container Isolation Pattern:** Perfect isolation with zero global state using async context managers - _Rationale:_ Recreates v2 excellence while enabling async patterns and preventing race conditions

- **Dependency Injection Pattern:** Constructor-based DI for plugins, containers, and core components - _Rationale:_ Enables testability, container isolation, plugin flexibility, and enterprise customization without tight coupling

- **Zero-Copy Operations Pattern:** Memory views and efficient serialization throughout pipeline - _Rationale:_ Achieves 80% memory reduction target and optimal performance for enterprise-scale deployments

- **Universal Plugin Architecture:** Extensible sinks, processors, and enrichers with async interfaces - _Rationale:_ Enables ecosystem growth (100+ plugins by v3.1) and universal adoption from developers to enterprise

- **Enterprise Compliance Pattern:** Built-in PCI-DSS, HIPAA, SOX compliance with audit trails - _Rationale:_ Addresses critical enterprise requirements identified in market research

- **Async Component Factory Pattern:** Revolutionary async component factory with zero-copy operations - _Rationale:_ Recreates v2 factory excellence while enabling async-first instantiation and configuration

- **Event-Driven Architecture:** Rich metadata events with categories and severity levels - _Rationale:_ Foundation for future alerting capabilities while maintaining structured logging excellence

## Tech Stack

This is the **DEFINITIVE technology selection** for Fapilog v3. These choices will serve as the single source of truth for all development.

Based on your async-first requirements, performance targets, and enterprise compliance needs, here are my recommendations:

### Technology Stack Table

| Category                | Technology         | Version  | Purpose                              | Rationale                                                        |
| ----------------------- | ------------------ | -------- | ------------------------------------ | ---------------------------------------------------------------- |
| **Language**            | Python             | 3.8+     | Core development language            | Async/await native support, typing, wide enterprise adoption     |
| **Framework**           | FastAPI            | 0.100+   | API framework for plugin marketplace | Async-first, Pydantic v2 integration, excellent performance      |
| **Type System**         | Pydantic           | v2       | Data validation and serialization    | Zero-copy serialization, async validation, enterprise compliance |
| **Async Runtime**       | asyncio            | Built-in | Core async operations                | Native Python async, optimal for pipeline architecture           |
| **Plugin Architecture** | importlib.metadata | Built-in | Plugin discovery and loading         | Standard Python approach, no external dependencies               |
| **Configuration**       | Pydantic Settings  | v2       | Environment-based configuration      | Type-safe, async loading, validation for enterprise compliance   |
| **Testing Framework**   | pytest             | 7.4+     | Core testing framework               | Excellent async support via pytest-asyncio                       |
| **Async Testing**       | pytest-asyncio     | 0.21+    | Async test support                   | Essential for async-first testing strategy                       |
| **Performance Testing** | pytest-benchmark   | 4.0+     | Performance regression testing       | Critical for 500K-2M events/second validation                    |
| **Type Checking**       | mypy               | 1.5+     | Static type analysis                 | 100% async type coverage requirement                             |
| **Linting**             | ruff               | 0.0.280+ | Code quality and formatting          | Fastest Python linter, async-aware                               |
| **Documentation**       | MkDocs Material    | 9.2+     | Documentation generation             | Beautiful docs for community adoption                            |
| **CLI Framework**       | Typer              | 0.9+     | Command line interface               | FastAPI ecosystem, excellent async support                       |
| **Metrics Collection**  | Prometheus Client  | 0.17+    | Performance metrics                  | Industry standard, enterprise SIEM integration                   |
| **Structured Logging**  | structlog          | 23.1+    | Internal structured logging          | Async-first, zero-copy operations                                |
| **Plugin Packaging**    | setuptools         | 68.0+    | Plugin distribution                  | Standard Python packaging for marketplace                        |
| **Container Platform**  | Docker             | 24.0+    | Containerization                     | Enterprise deployment requirements                               |
| **CI/CD**               | GitHub Actions     | Latest   | Continuous integration               | Plugin marketplace automation                                    |
| **Code Coverage**       | coverage.py        | 7.3+     | Test coverage measurement            | 90%+ coverage requirement                                        |
| **Security Scanning**   | bandit             | 1.7+     | Security vulnerability detection     | Enterprise compliance validation                                 |

### Key Architectural Technology Decisions:

**Async-First Stack:** Every component chosen supports native async/await patterns  
**Zero-Copy Focus:** Pydantic v2 and asyncio enable zero-copy operations throughout  
**Enterprise Ready:** All tools support enterprise compliance and audit requirements  
**Plugin Ecosystem:** Standard Python packaging enables community-driven growth  
**Performance Validated:** All choices validated for 500K-2M events/second targets

## Data Models

Based on my analysis of your existing codebase and PRD requirements, here are the core data models that will drive the Fapilog v3 architecture:

### LogEvent

**Purpose:** The central data structure for all log events, designed for future alerting capabilities and enterprise compliance

**Key Attributes:**

- `message: str` - The primary log message content
- `level: str` - Standard logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `timestamp: datetime` - Event timestamp for chronological ordering
- `source: str` - Service/component name for distributed tracing
- `category: EventCategory` - Semantic categorization for alerting rules
- `severity: int` - Numeric severity (1-10) for alert prioritization
- `tags: Dict[str, str]` - Key-value metadata for filtering and enrichment
- `context: Dict[str, Any]` - Request context and trace correlation
- `metrics: Dict[str, float]` - Performance metrics and measurements
- `correlation_id: str` - Distributed tracing and request correlation

**Relationships:**

- **With AsyncLogger:** Created and processed by logger instances
- **With Plugin System:** Enriched by enricher plugins, processed by processor plugins
- **With Compliance Engine:** Validated and redacted based on compliance standards

### UniversalSettings

**Purpose:** Configuration model that drives all aspects of the async-first logging system with enterprise compliance features

**Key Attributes:**

- `level: str` - Global logging level filter
- `sinks: List[str]` - Active sink configurations
- `async_processing: bool` - Enable async pipeline processing
- `batch_size: int` - Event batching for performance optimization
- `queue_max_size: int` - Maximum queue size for backpressure handling
- `max_workers: int` - Parallel processing worker count
- `compliance_standard: ComplianceStandard` - Enterprise compliance mode
- `overflow_strategy: OverflowStrategy` - Queue overflow behavior
- `plugin_config: Dict[str, Any]` - Plugin-specific configurations

**Relationships:**

- **With AsyncLogger:** Configures logger behavior and performance characteristics
- **With Plugin Registry:** Drives plugin loading and configuration
- **With Compliance Engine:** Determines compliance validation rules

### EventCategory

**Purpose:** Semantic categorization enum for future alerting capabilities and enterprise monitoring

**Values:**

- `ERROR` - Error conditions requiring investigation
- `PERFORMANCE` - Performance-related events and metrics
- `SECURITY` - Security events and compliance violations
- `BUSINESS` - Business logic and workflow events
- `SYSTEM` - System-level operational events
- `COMPLIANCE` - Compliance audit and validation events

**Relationships:**

- **With LogEvent:** Defines semantic category for alerting rules
- **With Alerting System:** Future integration point for alert routing

### PluginMetadata

**Purpose:** Metadata model for plugin discovery, loading, and marketplace integration

**Key Attributes:**

- `name: str` - Plugin unique identifier
- `version: str` - Semantic version for compatibility
- `plugin_type: PluginType` - Sink, Processor, or Enricher classification
- `entry_point: str` - Module path for plugin loading
- `dependencies: List[str]` - Required dependencies and versions
- `compliance_certified: bool` - Enterprise compliance validation status
- `performance_profile: Dict[str, float]` - Performance characteristics
- `configuration_schema: Dict[str, Any]` - Plugin configuration validation

**Relationships:**

- **With Plugin Registry:** Enables dynamic plugin discovery and loading
- **With Plugin Marketplace:** Supports community-driven ecosystem growth
- **With Compliance Engine:** Validates enterprise compliance requirements

### AsyncLoggingContainer

**Purpose:** Container isolation model providing perfect isolation with zero global state

**Key Attributes:**

- `container_id: str` - Unique container identifier
- `settings: UniversalSettings` - Container-specific configuration
- `plugin_registry: PluginRegistry` - Isolated plugin instances
- `metrics_collector: MetricsCollector` - Container performance metrics
- `compliance_engine: ComplianceEngine` - Container compliance validation
- `async_pipeline: AsyncPipeline` - Isolated event processing pipeline

**Relationships:**

- **With AsyncLogger:** Provides isolated execution context
- **With Plugin System:** Maintains isolated plugin instances
- **With Metrics System:** Collects container-specific performance data

## Components

Based on the architectural patterns, tech stack, and data models defined above, here are the major logical components that will implement the Fapilog v3 async-first architecture:

### AsyncLogger

**Responsibility:** Primary interface for async-first logging with zero-copy operations and parallel processing

**Key Interfaces:**

- `async def info(message: str, **kwargs) -> None` - Async logging methods
- `async def create(settings: UniversalSettings) -> AsyncLogger` - Factory method
- `async def shutdown() -> None` - Graceful resource cleanup

**Dependencies:** UniversalSettings, AsyncLoggingContainer, LogEvent pipeline  
**Technology Stack:** Python asyncio, Pydantic v2 for validation, zero-copy event creation

### AsyncLoggingContainer

**Responsibility:** Perfect isolation with zero global state, managing isolated plugin instances and pipeline execution

**Key Interfaces:**

- `async def create_logger(settings: UniversalSettings) -> AsyncLogger` - Logger factory
- `async def load_plugins() -> None` - Dynamic plugin loading and validation
- `async def get_metrics() -> ContainerMetrics` - Performance monitoring

**Dependencies:** PluginRegistry, MetricsCollector, ComplianceEngine  
**Technology Stack:** asyncio context management, importlib.metadata for plugin discovery

### AsyncPipeline

**Responsibility:** Core async-first event processing pipeline implementing enrichment → processing → queue → sinks flow

**Key Interfaces:**

- `async def process_event(event: LogEvent) -> None` - Main pipeline entry point
- `async def register_enricher(enricher: EnricherPlugin) -> None` - Plugin registration
- `async def get_pipeline_metrics() -> PipelineMetrics` - Performance monitoring

**Dependencies:** EnricherPlugins, ProcessorPlugins, SinkPlugins, AsyncQueue  
**Technology Stack:** asyncio parallel processing, zero-copy event passing, Prometheus metrics

### PluginRegistry

**Responsibility:** Dynamic plugin discovery, loading, and lifecycle management for the universal plugin ecosystem

**Key Interfaces:**

- `async def discover_plugins() -> List[PluginMetadata]` - Plugin discovery
- `async def load_plugin(metadata: PluginMetadata) -> Plugin` - Safe plugin loading
- `async def validate_plugin_compliance(plugin: Plugin) -> bool` - Enterprise validation

**Dependencies:** PluginMetadata, ComplianceEngine, PluginMarketplace  
**Technology Stack:** importlib.metadata, setuptools entry points, async validation

### ComplianceEngine

**Responsibility:** Enterprise compliance validation and enforcement for PCI-DSS, HIPAA, SOX standards

**Key Interfaces:**

- `async def validate_event(event: LogEvent) -> LogEvent` - Event compliance validation
- `async def redact_sensitive_data(event: LogEvent) -> LogEvent` - PII redaction
- `async def audit_log_access(user: str, action: str) -> None` - Audit trail creation

**Dependencies:** UniversalSettings, ComplianceStandard enums, audit storage  
**Technology Stack:** Pydantic v2 validation, structured audit logging, async compliance checks

### MetricsCollector

**Responsibility:** Comprehensive metrics collection with async-first patterns and zero-copy operations for 500K-2M events/second monitoring

**Key Interfaces:**

- `async def record_event_processed(duration: float) -> None` - Event processing metrics
- `async def record_pipeline_throughput(events_per_second: float) -> None` - Throughput tracking
- `async def export_metrics() -> Dict[str, float]` - Metrics export for monitoring systems

**Dependencies:** Prometheus client, AsyncPipeline performance data  
**Technology Stack:** Prometheus client async support, zero-copy metric aggregation

### PluginMarketplace

**Responsibility:** Community-driven plugin ecosystem with discovery, installation, and validation capabilities

**Key Interfaces:**

- `async def search_plugins(query: str) -> List[PluginMetadata]` - Plugin discovery
- `async def install_plugin(name: str, version: str) -> bool` - Plugin installation
- `async def validate_plugin_security(plugin: PluginMetadata) -> bool` - Security scanning

**Dependencies:** PluginRegistry, HTTP client for marketplace API, security scanner  
**Technology Stack:** FastAPI for marketplace API, async HTTP client, security validation

### AsyncQueue

**Responsibility:** High-performance async buffering and batching with overflow handling for zero-copy operations

**Key Interfaces:**

- `async def enqueue(event: LogEvent) -> None` - Event queuing with backpressure
- `async def dequeue_batch(size: int) -> List[LogEvent]` - Batch dequeuing
- `async def handle_overflow(strategy: OverflowStrategy) -> None` - Overflow management

**Dependencies:** asyncio.Queue, OverflowStrategy, batch management  
**Technology Stack:** asyncio native queuing, zero-copy event references, batch optimization

### FastAPIIntegrationLayer

**Responsibility:** Framework integration for FastAPI applications providing middleware, dependency injection, lifecycle management, and testing utilities

**Key Interfaces:**

- `class FapilogMiddleware` - ASGI middleware for request-scoped logging with correlation ID propagation
- `async def get_logger() -> AsyncLogger` - FastAPI dependency for logger injection
- `def register_fapilog_lifecycle(app: FastAPI, settings: UniversalSettings) -> None` - Lifecycle hook registration
- `class FapilogExceptionHandler` - Optional exception logging integration
- `def fapilog_test_fixture() -> AsyncLogger` - Test fixture for FastAPI applications

**Dependencies:** AsyncLogger, AsyncLoggingContainer, FastAPI application instance  
**Technology Stack:** FastAPI middleware, dependency injection, async context variables, pytest fixtures

**Key Features:**

- **Zero Global State**: Each request gets independent logger instance with container isolation
- **Correlation ID Propagation**: Automatic correlation ID generation and async context propagation
- **Request-Aware Logging**: Optional request/response logging plugin with PII redaction
- **Performance Optimized**: <1ms initialization overhead per request
- **Testing Support**: Comprehensive test fixtures for FastAPI application testing

### Component Diagrams

```mermaid
graph TB
    subgraph "Container Isolation"
        CONTAINER["AsyncLoggingContainer"]
        LOGGER["AsyncLogger"]
        PIPELINE["AsyncPipeline"]
    end

    subgraph "Plugin Ecosystem"
        REGISTRY["PluginRegistry"]
        MARKETPLACE["PluginMarketplace"]
        ENRICHER["EnricherPlugins"]
        PROCESSOR["ProcessorPlugins"]
        SINK["SinkPlugins"]
    end

    subgraph "Enterprise Features"
        COMPLIANCE["ComplianceEngine"]
        METRICS["MetricsCollector"]
        QUEUE["AsyncQueue"]
    end

    subgraph "Data Models"
        EVENT["LogEvent"]
        SETTINGS["UniversalSettings"]
        METADATA["PluginMetadata"]
    end

    CONTAINER --> LOGGER
    CONTAINER --> REGISTRY
    LOGGER --> PIPELINE
    PIPELINE --> QUEUE
    PIPELINE --> ENRICHER
    PIPELINE --> PROCESSOR
    PIPELINE --> SINK

    REGISTRY --> MARKETPLACE
    REGISTRY --> METADATA

    PIPELINE --> COMPLIANCE
    PIPELINE --> METRICS

    LOGGER --> EVENT
    CONTAINER --> SETTINGS

    COMPLIANCE --> EVENT
    METRICS --> EVENT
    QUEUE --> EVENT

    style CONTAINER fill:#e1f5fe
    style PIPELINE fill:#f3e5f5
    style COMPLIANCE fill:#fff3e0
    style EVENT fill:#e8f5e8
```

## External APIs

### Core Library: Zero External Dependencies

The core fapilog library has **NO external API dependencies**. It works completely offline and out-of-the-box.

### Plugin Ecosystem: Community-Driven via PyPI

**Plugin Discovery via GitHub**

- **GitHub Topics**: Search repositories with `fapilog-plugin` topic
- **Awesome Fapilog**: Curated list in community repository
- **Plugin Template**: Standard template for creating new plugins

**Plugin Installation via PyPI**

```bash
# Standard Python package installation
pip install fapilog-splunk-sink
pip install fapilog-audit-trail
pip install fapilog-prometheus-metrics
```

**Plugin Configuration via Entry Points**

```toml
# pyproject.toml for plugin packages
[project.entry-points."fapilog.sinks"]
splunk = "fapilog_splunk:SplunkSink"

[project.entry-points."fapilog.processors"]
pii_redaction = "fapilog_compliance:PIIRedactionProcessor"
```

### Enterprise Plugins: Optional External APIs

**Only when enterprise plugins are installed:**

- **Splunk HEC API** - `fapilog-splunk-sink` plugin
- **Prometheus Metrics** - `fapilog-prometheus` plugin
- **Elasticsearch API** - `fapilog-elastic-sink` plugin
- **Datadog Logs API** - `fapilog-datadog-sink` plugin

## Built-in Core Features

Fapilog v3 includes essential features **out of the box** to ensure immediate productivity without requiring any plugins. These built-in components provide a complete logging solution while serving as reference implementations for the plugin ecosystem.

### Core Sinks (Built-in)

**Essential output destinations included in core library:**

```python
# Built-in sinks - no plugins required
BUILTIN_SINKS = {
    "stdout": StdoutSink,      # Console output with color support
    "stderr": StderrSink,      # Error output with color support
    "file": FileSink,          # File output with rotation
    "null": NullSink,          # Discard (for testing/disabled)
}

class StdoutSink(BaseSink):
    """Built-in stdout sink with async support."""

    async def send(self, event: LogEvent) -> bool:
        """Send to stdout with optional color formatting."""
        formatted = await self.format_event(event)
        if self.config.get("colors", True):
            formatted = self.colorize_by_level(formatted, event.level)

        # Non-blocking stdout write
        await asyncio.get_event_loop().run_in_executor(
            None, print, formatted
        )
        return True

class FileSink(BaseSink):
    """Built-in file sink with async I/O and rotation."""

    async def send(self, event: LogEvent) -> bool:
        """Write to file with async I/O."""
        formatted = await self.format_event(event)

        async with aiofiles.open(self.file_path, 'a') as f:
            await f.write(f"{formatted}\n")

        # Check if rotation needed
        if await self.should_rotate():
            await self.rotate_file()

        return True
```

### Core Processors (Built-in)

**Essential processing capabilities included in core library:**

```python
# Built-in processors - no plugins required
BUILTIN_PROCESSORS = {
    "filter": FilterProcessor,        # Level-based filtering
    "throttle": ThrottleProcessor,    # Rate limiting
    "format": FormatProcessor,        # Message formatting
    "dedupe": DedupeProcessor,        # Duplicate detection
}

class FilterProcessor(BaseProcessor):
    """Built-in level-based filtering."""

    async def process(self, event: LogEvent) -> Optional[LogEvent]:
        """Filter events by level."""
        min_level = self.config.get("min_level", "INFO")

        if self.should_filter(event.level, min_level):
            return None  # Filter out

        return event

class ThrottleProcessor(BaseProcessor):
    """Built-in rate limiting processor."""

    async def process(self, event: LogEvent) -> Optional[LogEvent]:
        """Rate limit events to prevent spam."""
        key = f"{event.source}:{event.level}"

        if await self.rate_limiter.is_allowed(key):
            return event

        # Return throttled indicator on first drop
        if await self.rate_limiter.is_first_drop(key):
            return LogEvent(
                message=f"Rate limit exceeded for {key} - throttling messages",
                level="WARNING",
                source="fapilog.throttle"
            )

        return None  # Drop silently after first warning
```

### Core Enrichers (Built-in)

**Essential context enrichment included in core library:**

```python
# Built-in enrichers - no plugins required
BUILTIN_ENRICHERS = {
    "timestamp": TimestampEnricher,    # High-precision timestamps
    "correlation": CorrelationEnricher, # Request correlation IDs
    "context": ContextEnricher,        # Thread/async context
    "hostname": HostnameEnricher,      # System identification
}

class CorrelationEnricher(BaseEnricher):
    """Built-in correlation ID management."""

    async def enrich(self, event: LogEvent) -> LogEvent:
        """Add or preserve correlation IDs."""
        if not event.correlation_id:
            # Get from async context or generate new
            event.correlation_id = (
                self.get_context_correlation_id() or
                str(uuid4())
            )

        return event

class ContextEnricher(BaseEnricher):
    """Built-in async context enrichment."""

    async def enrich(self, event: LogEvent) -> LogEvent:
        """Add async task and thread context."""
        context_data = {
            "task_name": asyncio.current_task().get_name(),
            "thread_id": threading.get_ident(),
            "process_id": os.getpid(),
        }

        # Merge with existing context
        event.context = {**event.context, **context_data}
        return event
```

### Core Formatters (Built-in)

**Essential output formatting included in core library:**

```python
# Built-in formatters - no plugins required
BUILTIN_FORMATTERS = {
    "simple": SimpleFormatter,      # Human-readable format
    "json": JSONFormatter,          # Structured JSON output
    "logfmt": LogfmtFormatter,      # Key=value format
    "minimal": MinimalFormatter,    # Compact format
}

class JSONFormatter(BaseFormatter):
    """Built-in JSON formatter for structured logging."""

    async def format(self, event: LogEvent) -> str:
        """Format as JSON with proper async serialization."""
        data = {
            "timestamp": event.timestamp.isoformat(),
            "level": event.level,
            "message": event.message,
            "source": event.source,
            "correlation_id": event.correlation_id,
            **event.context
        }

        return json.dumps(data, default=self.json_serializer)

class SimpleFormatter(BaseFormatter):
    """Built-in human-readable formatter."""

    async def format(self, event: LogEvent) -> str:
        """Format for human consumption."""
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"{timestamp} [{event.level}] {event.source}: {event.message}"
```

### Default Configuration

**Zero-configuration experience for developers:**

```python
# Default settings - works immediately after pip install
DEFAULT_SETTINGS = UniversalSettings(
    # Built-in sinks
    sinks=["stdout"],

    # Built-in processors
    processors=["filter", "throttle"],

    # Built-in enrichers
    enrichers=["timestamp", "correlation", "context"],

    # Built-in formatter
    formatter="simple",

    # Performance defaults
    async_processing=True,
    batch_size=100,
    queue_max_size=10000,

    # Developer-friendly defaults
    level="INFO",
    colors=True,
    enable_internal_logging=False,  # Silent by default
)

# Immediate usage - no configuration required
logger = await AsyncLogger.create()  # Uses defaults
await logger.info("Hello World!")   # Works immediately
```

### Built-in vs Plugin Feature Matrix

| Category         | Built-in Features                         | Plugin Features (Examples)                                   |
| ---------------- | ----------------------------------------- | ------------------------------------------------------------ |
| **Sinks**        | stdout, stderr, file, null                | splunk, elasticsearch, datadog, loki, syslog, kafka, webhook |
| **Processors**   | filter, throttle, format, dedupe          | pii-redaction, encryption, compression, sampling, alerting   |
| **Enrichers**    | timestamp, correlation, context, hostname | user-context, geo-location, performance-metrics, tracing     |
| **Formatters**   | simple, json, logfmt, minimal             | custom-json, xml, protobuf, csv, syslog-rfc5424              |
| **Compliance**   | Input validation, basic security          | pci-dss, hipaa, sox, gdpr, audit-trails                      |
| **Performance**  | Async pipeline, batching                  | advanced-compression, sharding, caching, metrics             |
| **Integrations** | FastAPI middleware, lifecycle, DI         | request-logger, otel-formatter, tracing, custom frameworks   |

### Progressive Enhancement Philosophy

```python
# Level 1: Zero configuration (built-in features)
logger = await AsyncLogger.create()
await logger.info("Works immediately")

# Level 2: Basic customization (built-in features)
settings = UniversalSettings(
    sinks=["file"],
    processors=["filter", "throttle"],
    formatter="json",
    level="DEBUG"
)
logger = await AsyncLogger.create(settings)

# Level 3: Enterprise features (plugins)
settings = UniversalSettings(
    sinks=["file", "splunk-sink", "datadog-sink"],
    processors=["pii-redaction", "encryption", "filter"],
    enrichers=["user-context", "geo-location", "correlation"],
    compliance_standards=["pci-dss", "hipaa"]
)
logger = await AsyncLogger.create(settings)
```

### Core Library Guarantees

**What developers can rely on without any plugins:**

1. **Immediate Functionality** - `pip install fapilog` → works immediately
2. **Production Ready** - File output with rotation, rate limiting, filtering
3. **Development Friendly** - Colored console output, readable formats
4. **Performance** - Async pipeline, batching, non-blocking I/O
5. **Reliability** - Error handling, graceful degradation, container isolation
6. **Observability** - Correlation IDs, context enrichment, structured output

**The built-in features provide a complete logging solution that competes with existing libraries, while the plugin ecosystem enables unlimited extensibility for enterprise use cases.**

---

## Core Workflows

Here are the key system workflows that illustrate the async-first architecture and component interactions:

### High-Performance Async Logging Workflow

```mermaid
sequenceDiagram
    participant App as Application
    participant Logger as AsyncLogger
    participant Container as AsyncLoggingContainer
    participant Pipeline as AsyncPipeline
    participant Enricher as EnricherPlugins
    participant Processor as ProcessorPlugins
    participant Queue as AsyncQueue
    participant Sink as SinkPlugins
    participant Compliance as ComplianceEngine
    participant Metrics as MetricsCollector

    Note over App, Metrics: High-Performance Async Logging Workflow

    App->>Logger: await logger.info("message", **metadata)
    Logger->>Container: get_pipeline()
    Container->>Pipeline: process_event(LogEvent)

    par Parallel Enrichment
        Pipeline->>Enricher: enrich_event(event)
        Enricher-->>Pipeline: enriched_event
    and Metrics Collection
        Pipeline->>Metrics: record_event_start()
    end

    Pipeline->>Processor: process_event(enriched_event)

    alt Compliance Validation Required
        Processor->>Compliance: validate_event(event)
        Compliance-->>Processor: validated_event
    end

    Processor->>Queue: enqueue(processed_event)

    par Async Background Processing
        Queue->>Sink: dequeue_batch(events)
        Sink->>Sink: async write to destinations
    and Performance Monitoring
        Pipeline->>Metrics: record_event_processed()
    end

    Pipeline-->>Logger: processing_started
    Logger-->>App: None (async complete)
```

### Plugin Discovery and Loading Workflow

```mermaid
sequenceDiagram
    participant Container as AsyncLoggingContainer
    participant Registry as PluginRegistry
    participant Marketplace as PluginMarketplace
    participant Compliance as ComplianceEngine
    participant Plugin as PluginInstance
    participant Pipeline as AsyncPipeline

    Note over Container, Pipeline: Plugin Discovery and Loading Workflow

    Container->>Registry: discover_plugins()
    Registry->>Marketplace: search_plugins(criteria)
    Marketplace-->>Registry: available_plugins[]

    loop For Each Plugin
        Registry->>Marketplace: get_plugin_metadata(name)
        Marketplace-->>Registry: plugin_metadata

        alt Enterprise Deployment
            Registry->>Compliance: validate_plugin_compliance(metadata)
            Compliance-->>Registry: compliance_result
        end

        alt Compliance Passed or Not Required
            Registry->>Registry: load_plugin(metadata)
            Registry->>Plugin: initialize(config)
            Plugin-->>Registry: plugin_instance
        end
    end

    Registry->>Pipeline: register_plugins(loaded_plugins)
    Pipeline-->>Container: plugins_ready
```

### Enterprise Compliance and Audit Workflow

```mermaid
sequenceDiagram
    participant Event as LogEvent
    participant Compliance as ComplianceEngine
    participant Audit as AuditLogger
    participant Redaction as RedactionEngine
    participant Validation as ValidationEngine
    participant SIEM as External SIEM

    Note over Event, SIEM: Enterprise Compliance and Audit Workflow

    Event->>Compliance: validate_event(event)

    alt PII Detection Required
        Compliance->>Redaction: scan_for_pii(event)
        Redaction-->>Compliance: redacted_event
    end

    Compliance->>Validation: validate_schema(event, standard)

    alt Schema Validation Failed
        Validation-->>Compliance: validation_error
        Compliance->>Audit: log_compliance_violation(event, error)
        Audit->>SIEM: send_compliance_alert(violation)
    else Schema Valid
        Validation-->>Compliance: validation_passed
    end

    alt Audit Trail Required
        Compliance->>Audit: log_audit_event(event)
        Audit->>Audit: create_immutable_record(event)
    end

    Compliance-->>Event: compliant_event
```

### High-Throughput Batch Processing Workflow

```mermaid
sequenceDiagram
    participant Queue as AsyncQueue
    participant Batch as BatchManager
    participant Sink1 as FileSink
    participant Sink2 as SplunkSink
    participant Sink3 as LokiSink
    participant Monitor as HealthMonitor
    participant Metrics as MetricsCollector

    Note over Queue, Metrics: High-Throughput Batch Processing Workflow

    Queue->>Batch: dequeue_batch(batch_size)
    Batch->>Batch: optimize_batch_for_sinks()

    par Parallel Sink Processing
        Batch->>Sink1: async write_batch(file_events)
        Sink1->>Sink1: async file operations
        Sink1-->>Batch: write_complete
    and
        Batch->>Sink2: async send_to_splunk(splunk_events)
        Sink2->>Sink2: async HTTP batch request
        Sink2-->>Batch: send_complete
    and
        Batch->>Sink3: async push_to_loki(loki_events)
        Sink3->>Sink3: async stream processing
        Sink3-->>Batch: push_complete
    end

    alt Sink Failure Detected
        Batch->>Monitor: handle_sink_failure(sink, error)
        Monitor->>Queue: retry_events(failed_events)
    end

    Batch->>Metrics: record_batch_metrics(throughput, latency)
    Metrics->>Metrics: update_performance_counters()

    Batch-->>Queue: batch_processed
```

### Container Isolation Workflow

```mermaid
sequenceDiagram
    participant App as Application
    participant Container1 as Container-A
    participant Container2 as Container-B
    participant Logger1 as Logger-A
    participant Logger2 as Logger-B
    participant Pipeline1 as Pipeline-A
    participant Pipeline2 as Pipeline-B

    Note over App, Pipeline2: Container Isolation Workflow (Zero Global State)

    App->>Container1: create_logger(settings_dev)
    Container1->>Logger1: AsyncLogger.create()
    Logger1->>Pipeline1: initialize_pipeline()

    par Isolated Container Creation
        App->>Container2: create_logger(settings_prod)
        Container2->>Logger2: AsyncLogger.create()
        Logger2->>Pipeline2: initialize_pipeline()
    end

    Note over Container1, Pipeline1: Dev Environment Processing
    App->>Logger1: log_event(dev_data)
    Logger1->>Pipeline1: process(dev_event)
    Pipeline1->>Pipeline1: dev_plugins_processing

    Note over Container2, Pipeline2: Prod Environment Processing (Isolated)
    App->>Logger2: log_event(prod_data)
    Logger2->>Pipeline2: process(prod_event)
    Pipeline2->>Pipeline2: prod_plugins_processing

    Note over Container1, Pipeline2: Perfect Isolation - No Cross-Contamination
    Pipeline1-->>Logger1: dev_complete
    Pipeline2-->>Logger2: prod_complete
```

## REST API Spec

### Core Library: No REST API

The core fapilog library is a **Python library only** - no web server, no REST API, no complexity.

### Optional Plugin Marketplace API

If the community grows large enough, a **simple GitHub Pages site** could provide:

- Plugin discovery and search
- Installation instructions
- Plugin ratings and reviews
- **No database required** - all data sourced from GitHub API and PyPI API

## Database Schema

### Core Library: No Database

The core fapilog library requires **zero database setup**. It works immediately after `pip install fapilog`.

### Enterprise Plugin Databases

Individual plugins may include their own database requirements:

- **`fapilog-audit-trail`** - May include SQLite/PostgreSQL schemas
- **`fapilog-metrics-storage`** - May include time-series database schemas
- **`fapilog-compliance-tracker`** - May include compliance violation tracking

**Each plugin manages its own storage needs** - not the core library's responsibility.

## Source Tree

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
│       │   ├── registry.py             # Plugin discovery via entry points
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
│       │   ├── __init__.py
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

## Infrastructure and Deployment

Since Fapilog v3 is a **Python library** (not a service), the infrastructure and deployment approach is fundamentally different from traditional applications:

### Infrastructure as Code

- **Tool:** GitHub Actions (workflow automation)
- **Location:** `.github/workflows/`
- **Approach:** Library-focused CI/CD with plugin ecosystem validation

### Deployment Strategy

- **Strategy:** Package Distribution via PyPI
- **CI/CD Platform:** GitHub Actions
- **Pipeline Configuration:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`

### Environments

- **Development:** Local development with `pip install -e .`
- **Testing:** GitHub Actions runners with matrix testing (Python 3.8-3.12)
- **Staging:** TestPyPI for release candidates
- **Production:** PyPI for stable releases

### Environment Promotion Flow

```text
Local Development
       ↓
GitHub Actions CI (PR validation)
       ↓
TestPyPI (Release Candidates)
       ↓
PyPI (Stable Releases)
       ↓
User Environments (pip install fapilog)
```

### Rollback Strategy

- **Primary Method:** PyPI version pinning and yanking
- **Trigger Conditions:** Critical bugs, security vulnerabilities, performance regressions
- **Recovery Time Objective:** < 1 hour (immediate PyPI package yank)

### Framework Lifecycle Integration

**FastAPI Application Deployment:**

```python
# Recommended FastAPI integration pattern
from fastapi import FastAPI
from fapilog.fastapi import register_fapilog_lifecycle, FapilogMiddleware
from fapilog import UniversalSettings

app = FastAPI()

# Register lifecycle hooks for clean startup/shutdown
settings = UniversalSettings(
    sinks=["file", "stdout"],
    processors=["filter", "throttle"],
    level="INFO"
)
register_fapilog_lifecycle(app, settings)

# Add middleware for request-scoped logging
app.add_middleware(FapilogMiddleware, correlation_header="X-Request-ID")

# Container deployment (Docker/Kubernetes)
# No special Fapilog configuration needed - standard Python app deployment
```

**Container Deployment Notes:**

- **Zero Special Setup**: Fapilog is a library, not a service - no special container configuration
- **Configuration via Environment**: Standard environment variable configuration
- **Graceful Shutdown**: FastAPI lifecycle hooks ensure proper logger cleanup

## Error Handling Strategy

The error handling strategy balances **developer simplicity** (errors don't crash apps) with **enterprise observability** (full error tracking via plugins).

### General Approach

- **Error Model:** Async-first exception hierarchy with graceful degradation
- **Exception Hierarchy:** Custom exceptions inheriting from `FapilogError` base class
- **Error Propagation:** Non-blocking - logging errors never crash user applications

### Logging Standards

- **Library:** Python's built-in `logging` module for internal fapilog logging
- **Format:** Structured JSON for enterprise compatibility
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL aligned with user log levels
- **Required Context:**
  - Correlation ID: UUID4 format for tracing async operations
  - Service Context: `fapilog.core`, `fapilog.plugins.{plugin_name}`
  - User Context: Never log user data in internal fapilog errors

### Error Handling Patterns

#### External API Errors

```python
# Plugin-specific retry policies for external integrations
class ExternalAPIError(FapilogError):
    """External API integration errors."""
    pass

# Retry configuration for enterprise plugins
@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_factor: float = 2.0
    max_delay: float = 60.0

async def retry_with_backoff(operation, config: RetryConfig):
    """Async retry with exponential backoff."""
    for attempt in range(config.max_attempts):
        try:
            return await operation()
        except ExternalAPIError as e:
            if attempt == config.max_attempts - 1:
                # Final attempt failed - log but don't crash
                await internal_logger.error(
                    "External API permanently failed",
                    error=str(e),
                    attempts=config.max_attempts
                )
                return None  # Graceful degradation

            delay = min(config.backoff_factor ** attempt, config.max_delay)
            await asyncio.sleep(delay)
```

**Circuit Breaker:** Plugin-level circuit breakers for external services
**Timeout Configuration:** Configurable timeouts per plugin (default 30s)
**Error Translation:** Plugin errors mapped to user-friendly messages

#### Business Logic Errors

```python
# Core library exceptions that users might handle
class FapilogError(Exception):
    """Base exception for all fapilog errors."""
    pass

class ConfigurationError(FapilogError):
    """Invalid configuration provided by user."""
    pass

class PluginError(FapilogError):
    """Plugin loading or execution error."""
    pass

class PipelineError(FapilogError):
    """Async pipeline processing error."""
    pass

# User-facing error handling
async def safe_log_processing(event: LogEvent) -> bool:
    """Process log event with comprehensive error handling."""
    try:
        await pipeline.process_event(event)
        return True
    except PluginError as e:
        # Plugin failed - log internally but continue
        await internal_logger.warning(
            "Plugin processing failed",
            plugin=e.plugin_name,
            error=str(e),
            correlation_id=event.correlation_id
        )
        # Try fallback processing without failed plugin
        await pipeline.process_event_safe_mode(event)
        return True
    except PipelineError as e:
        # Pipeline failed - log internally, use emergency fallback
        await internal_logger.error(
            "Pipeline processing failed",
            error=str(e),
            correlation_id=event.correlation_id
        )
        # Emergency fallback: direct to stdout
        print(f"FAPILOG EMERGENCY: {event.message}")
        return False
    except Exception as e:
        # Unexpected error - never crash user application
        await internal_logger.critical(
            "Unexpected fapilog error",
            error=str(e),
            correlation_id=event.correlation_id
        )
        # Emergency fallback
        print(f"FAPILOG CRITICAL: {event.message}")
        return False
```

**Custom Exceptions:** Specific exception types for different failure modes
**User-Facing Errors:** Clear error messages for configuration issues
**Error Codes:** Structured error codes for enterprise monitoring

#### Data Consistency

```python
# Container isolation ensures no cross-contamination on errors
class ContainerIsolationError(FapilogError):
    """Container isolation violation."""
    pass

# Transaction-like behavior for batch processing
async def process_event_batch(events: List[LogEvent]) -> BatchResult:
    """Process events with partial failure handling."""
    successful = []
    failed = []

    for event in events:
        try:
            await process_single_event(event)
            successful.append(event)
        except Exception as e:
            failed.append((event, e))
            # Continue processing other events
            await internal_logger.warning(
                "Event processing failed in batch",
                event_id=event.correlation_id,
                error=str(e)
            )

    return BatchResult(
        successful_count=len(successful),
        failed_count=len(failed),
        failed_events=failed
    )

# Idempotency for retry scenarios
async def idempotent_event_processing(event: LogEvent) -> bool:
    """Ensure event processing is idempotent."""
    # Check if event already processed (via correlation_id)
    if await was_event_processed(event.correlation_id):
        return True

    # Mark event as being processed
    await mark_event_processing(event.correlation_id)

    try:
        result = await process_event(event)
        await mark_event_completed(event.correlation_id)
        return result
    except Exception as e:
        await mark_event_failed(event.correlation_id, str(e))
        raise
```

**Transaction Strategy:** Batch-level transactions with partial failure handling
**Compensation Logic:** Automatic retry and fallback mechanisms
**Idempotency:** Correlation ID-based deduplication for retry scenarios

---

## Developer-Friendly Error Experience

### Default Behavior: Silent Resilience

```python
# This should never crash user applications
logger = await AsyncLogger.create()
await logger.info("This works even if plugins fail")  # Always succeeds
```

### Optional Error Observability

```python
# Developers can opt into error monitoring
settings = UniversalSettings(
    enable_internal_logging=True,  # See fapilog's own errors
    internal_log_level="WARNING",  # Only serious issues
    error_callback=my_error_handler  # Custom error handling
)

async def my_error_handler(error: FapilogError):
    """Custom error handling for application monitoring."""
    if isinstance(error, PluginError):
        # Handle plugin failures in application
        await send_to_monitoring(f"Fapilog plugin failed: {error}")
```

### Enterprise Error Integration

```python
# Enterprise plugins can provide rich error monitoring
settings = UniversalSettings(
    sinks=["stdout", "error-tracking-sink"],  # Plugin for error monitoring
    processors=["error-enrichment"],  # Add context to errors
    error_handling_mode="enterprise"  # Enhanced error tracking
)
```

## Plugin Error Isolation

### Plugin Failure Containment

```python
# Plugin failures don't affect other plugins or core library
class PluginExecutor:
    async def execute_plugin_safe(self, plugin: Plugin, event: LogEvent):
        """Execute plugin with complete error isolation."""
        try:
            return await asyncio.wait_for(
                plugin.process(event),
                timeout=plugin.timeout or 30.0
            )
        except asyncio.TimeoutError:
            await self.handle_plugin_timeout(plugin.name)
            return None
        except Exception as e:
            await self.handle_plugin_error(plugin.name, e)
            return None

    async def handle_plugin_error(self, plugin_name: str, error: Exception):
        """Handle plugin errors without affecting other plugins."""
        # Log plugin error internally
        await internal_logger.error(
            "Plugin execution failed",
            plugin=plugin_name,
            error=str(error),
            error_type=type(error).__name__
        )

        # Optionally disable failing plugin temporarily
        if self.should_disable_plugin(plugin_name, error):
            await self.temporarily_disable_plugin(plugin_name)
```

### Graceful Degradation

```python
# Core functionality continues even with plugin failures
async def process_with_fallbacks(event: LogEvent):
    """Process event with multiple fallback levels."""

    # Try full plugin pipeline
    if await try_full_pipeline(event):
        return

    # Try essential plugins only
    if await try_essential_plugins(event):
        return

    # Try built-in sinks only
    if await try_builtin_sinks(event):
        return

    # Emergency fallback: direct output
    print(f"EMERGENCY LOG: {event.message}")
```

### Framework Hook Error Handling

**FastAPI Exception Integration:**

```python
# Optional FastAPI exception handler integration
from fastapi import Request, HTTPException
from fapilog.fastapi import get_logger

async def fapilog_exception_handler(request: Request, exc: Exception):
    """Optional exception logging for FastAPI applications."""
    logger = await get_logger()  # Get request-scoped logger

    # Log exception with full context
    await logger.error(
        "Unhandled FastAPI exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        request_method=request.method,
        request_url=str(request.url),
        request_headers=dict(request.headers),
        # Correlation ID automatically included via request context
    )

    # Let FastAPI handle the actual HTTP response
    if isinstance(exc, HTTPException):
        raise exc
    else:
        raise HTTPException(status_code=500, detail="Internal server error")

# Register with FastAPI
app.add_exception_handler(Exception, fapilog_exception_handler)
```

**Framework Hook Isolation:**

- **No Global State**: Exception hooks operate on request-scoped loggers
- **Error Isolation**: Framework hook failures never affect core logging
- **Optional Integration**: Framework hooks are completely optional and non-intrusive

## Coding Standards

These standards are **MANDATORY for AI agents** and critical for maintaining code quality. Focused on project-specific conventions and preventing common async/plugin mistakes.

### Core Standards

- **Languages & Runtimes:** Python 3.8+ with asyncio for all async operations
- **Style & Linting:** ruff (replaces black, isort, flake8) with async-aware rules
- **Test Organization:** `tests/{unit,integration,performance}/test_*.py` with pytest-asyncio

### Naming Conventions

| Element         | Convention                          | Example                                    |
| --------------- | ----------------------------------- | ------------------------------------------ |
| Async Functions | `async def snake_case()`            | `async def process_event()`                |
| Plugin Classes  | `PascalCase` ending in type         | `SplunkSink`, `PIIProcessor`               |
| Event Fields    | `snake_case`                        | `correlation_id`, `event_category`         |
| Settings        | `snake_case` with descriptive names | `async_processing`, `queue_max_size`       |
| Constants       | `UPPER_SNAKE_CASE`                  | `DEFAULT_BATCH_SIZE`, `MAX_RETRY_ATTEMPTS` |

### Critical Rules

- **Async Everywhere:** All I/O operations must use async/await - never blocking calls in async context
- **Plugin Error Isolation:** All plugin operations must be wrapped in try/catch with graceful degradation
- **Container Isolation:** Never use global state - all state must be container-scoped
- **Zero-Copy Operations:** Pass LogEvent by reference, never copy event data unnecessarily
- **Correlation ID Propagation:** All async operations must propagate correlation_id for tracing
- **Plugin Entry Points:** All plugins must use standard Python entry points, never dynamic imports
- **Configuration Validation:** All settings must use Pydantic v2 validation with clear error messages
- **Emergency Fallbacks:** All critical paths must have fallback mechanisms that never crash user apps
- **FastAPI Integration Isolation:** FastAPI integrations must not break context isolation or introduce global state

### Dependency Injection Patterns

```python
# ✅ CORRECT: Constructor-based dependency injection for plugins
class AsyncLoggingContainer:
    def __init__(self,
                 settings: UniversalSettings,
                 plugin_registry: PluginRegistry,
                 metrics_collector: MetricsCollector):
        self.settings = settings
        self.plugin_registry = plugin_registry
        self.metrics_collector = metrics_collector

    async def create_logger(self) -> AsyncLogger:
        """Inject dependencies into logger."""
        return AsyncLogger(
            container=self,
            pipeline=await self._create_pipeline()
        )

# ✅ CORRECT: Plugin dependency injection
class SplunkSink(BaseSink):
    def __init__(self,
                 config: Dict[str, Any],
                 http_client: Optional[aiohttp.ClientSession] = None):
        super().__init__(config)
        # Allow injection for testing, create default for production
        self.http_client = http_client or aiohttp.ClientSession()

# ❌ WRONG: Hard-coded dependencies
class BadContainer:
    def __init__(self, settings: UniversalSettings):
        self.settings = settings
        self.plugin_registry = PluginRegistry()  # Hard-coded, not testable
        self.metrics = MetricsCollector()        # Can't inject mocks
```

## Test Strategy and Standards

Comprehensive testing approach focused on **async-first validation**, **plugin ecosystem reliability**, and **500K-2M events/second performance verification**.

### Testing Philosophy

- **Approach:** Test-driven development with async-first patterns throughout
- **Coverage Goals:** 90%+ test coverage with emphasis on async code paths and plugin interactions
- **Test Pyramid:** Balanced distribution favoring fast unit tests with comprehensive integration testing

### Test Types and Organization

#### Unit Tests

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
# Unit test example for async logger
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_logger_info():
    """Test async logger info method."""
    # Arrange
    settings = UniversalSettings(async_processing=True)
    container = await AsyncLoggingContainer.create(settings)
    logger = await container.get_logger()

    # Act
    result = await logger.info("test message", source="test")

    # Assert
    assert result is True
    assert logger._last_event.message == "test message"
    assert logger._last_event.source == "test"

    # Cleanup
    await container.shutdown()

@pytest.mark.asyncio
async def test_plugin_error_isolation():
    """Test that plugin errors don't crash logger."""
    # Arrange
    failing_plugin = AsyncMock(side_effect=Exception("Plugin failed"))
    settings = UniversalSettings(sinks=["failing-sink"])

    with patch('fapilog.plugins.registry.load_plugin', return_value=failing_plugin):
        container = await AsyncLoggingContainer.create(settings)
        logger = await container.get_logger()

    # Act - should not raise despite plugin failure
    result = await logger.info("test with failing plugin")

    # Assert
    assert result is True  # Graceful degradation

    await container.shutdown()
```

#### Integration Tests

- **Scope:** Cross-component interactions, plugin loading, async pipeline flows
- **Location:** `tests/integration/`
- **Test Infrastructure:**
  - **Async Queue Testing:** Real asyncio.Queue instances with controlled scenarios
  - **Plugin Loading:** Actual entry point discovery and loading
  - **Container Isolation:** Multiple containers with different configurations

```python
# Integration test example
@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """Test complete async pipeline from logger to sink."""
    # Arrange
    events_received = []

    class TestSink(BaseSink):
        async def send(self, event: LogEvent) -> bool:
            events_received.append(event)
            return True

    # Register test sink
    with patch('fapilog.plugins.registry.discover_sinks',
               return_value={'test-sink': TestSink}):
        settings = UniversalSettings(
            sinks=["test-sink"],
            async_processing=True,
            batch_size=10
        )
        container = await AsyncLoggingContainer.create(settings)
        logger = await container.get_logger()

        # Act
        for i in range(25):  # Test batching
            await logger.info(f"Message {i}")

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Assert
        assert len(events_received) == 25
        assert all(isinstance(event, LogEvent) for event in events_received)

        await container.shutdown()
```

#### Performance Tests

- **Framework:** pytest-benchmark 4.0+ for performance regression testing
- **Scope:** 500K-2M events/second validation, latency measurement, memory usage
- **Environment:** Dedicated performance test environment
- **Test Data:** Realistic log event payloads with varying sizes

### Test Data Management

- **Strategy:** Factory pattern for creating realistic test data
- **Fixtures:** Shared async fixtures for containers, loggers, and plugins
- **Factories:** Event factories with varying complexity and size
- **Cleanup:** Automatic async resource cleanup in teardown

### Continuous Testing

- **CI Integration:** All tests run on every PR with matrix testing
- **Performance Monitoring:** Benchmark results tracked over time
- **Plugin Validation:** Community plugins tested against new releases
- **Coverage Reporting:** Automatic coverage reports with trend analysis

### FastAPI Test Utilities

**Test Fixtures for FastAPI Integration:**

```python
# FastAPI test fixtures in fapilog.fastapi.testing
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fapilog.fastapi import register_fapilog_lifecycle, FapilogMiddleware
from fapilog import UniversalSettings

@pytest.fixture
async def fapilog_test_app():
    """Create FastAPI app with Fapilog for testing."""
    app = FastAPI()
    settings = UniversalSettings(
        sinks=["memory"],  # Memory sink for test assertions
        processors=["filter", "throttle"],
        level="DEBUG"
    )
    register_fapilog_lifecycle(app, settings)
    app.add_middleware(FapilogMiddleware)
    return app

@pytest.fixture
def fapilog_memory_sink():
    """Capture log events for assertions."""
    events = []

    class MemorySink:
        async def send(self, event):
            events.append(event)
            return True

    return MemorySink(), events

# Test example for FastAPI integration
@pytest.mark.asyncio
async def test_fastapi_request_logging(fapilog_test_app, fapilog_memory_sink):
    """Test that FastAPI requests are logged correctly."""
    sink, events = fapilog_memory_sink

    # Register test endpoint
    @fapilog_test_app.get("/test")
    async def test_endpoint(logger = Depends(get_logger)):
        await logger.info("Test endpoint called")
        return {"message": "success"}

    # Make request
    with TestClient(fapilog_test_app) as client:
        response = client.get("/test")

    # Assert logging behavior
    assert response.status_code == 200
    assert len(events) >= 1
    assert any("Test endpoint called" in event.message for event in events)
    # Verify correlation ID propagation
    correlation_ids = [event.correlation_id for event in events if event.correlation_id]
    assert len(set(correlation_ids)) == 1  # All events share same correlation ID
```

**Test Utilities Features:**

- **Memory Sink**: Capture log events for assertions without side effects
- **Mock Fixtures**: Pre-configured FastAPI apps with Fapilog integration
- **Assertion Helpers**: Utilities for verifying logging behavior in FastAPI tests
- **Correlation Verification**: Test correlation ID propagation across async operations
- **Performance Testing**: Utilities for measuring logging overhead in FastAPI applications

## Security

Security implementation focused on **core library safety**, **plugin ecosystem security**, and **enterprise compliance** while maintaining developer simplicity.

### Input Validation

- **Validation Library:** Pydantic v2 for all configuration and event validation
- **Validation Location:** At API boundaries before any processing begins
- **Required Rules:**
  - All external inputs MUST be validated before entering the async pipeline
  - Validation at configuration loading and event creation points
  - Whitelist approach for allowed values and patterns
  - Async validation patterns for performance-critical paths

```python
# Core input validation patterns
class LogEvent(BaseModel):
    """LogEvent with comprehensive validation."""

    message: str = Field(..., min_length=1, max_length=10000)
    level: str = Field(..., regex=r'^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="", max_length=255)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))

    # Security: Prevent code injection in log messages
    @field_validator('message')
    @classmethod
    def validate_message_security(cls, v: str) -> str:
        """Validate message for security concerns."""
        # Remove potential script injections
        dangerous_patterns = ['<script', 'javascript:', 'data:text/html']
        message_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in message_lower:
                raise ValueError(f"Potentially dangerous content detected: {pattern}")
        return v

class UniversalSettings(BaseModel):
    """Settings with security validation."""

    sinks: List[str] = Field(default=["stdout"], min_items=1)
    async_processing: bool = True
    batch_size: int = Field(default=100, ge=1, le=10000)  # Prevent memory attacks
    queue_max_size: int = Field(default=10000, ge=100, le=1000000)  # DoS protection

    @field_validator('sinks')
    @classmethod
    def validate_sink_names(cls, v: List[str]) -> List[str]:
        """Validate sink names against injection attacks."""
        safe_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        for sink in v:
            if not safe_pattern.match(sink):
                raise ValueError(f"Invalid sink name: {sink}. Use alphanumeric, underscore, hyphen only.")
        return v
```

### Authentication & Authorization

- **Auth Method:** Plugin-based authentication for enterprise features
- **Session Management:** Stateless design - no session management in core library
- **Required Patterns:**
  - Core library has no authentication (it's a library, not a service)
  - Enterprise plugins implement their own auth as needed
  - Plugin marketplace uses PyPI's existing authentication
  - No user management in core library

### Secrets Management

- **Development:** Environment variables with `.env` files (not committed)
- **Production:** Plugin-specific secret management (enterprise choice)
- **Code Requirements:**
  - NEVER hardcode secrets in core library or plugins
  - Access secrets via configuration validation only
  - No secrets in logs or error messages
  - Plugin developers responsible for their own secret management

### Plugin Security

- **Plugin Isolation:** Each plugin runs in isolated async context
- **Code Execution:** Plugins use standard Python entry points (no eval/exec)
- **Resource Limits:** Timeouts and memory limits per plugin
- **Security Scanning:** Plugin validation framework for community plugins

### Data Protection

- **Encryption at Rest:** Plugin responsibility - core library doesn't store data
- **Encryption in Transit:** HTTPS enforcement for network plugins
- **PII Handling:** Optional PII detection and redaction via plugins
- **Logging Restrictions:** No sensitive data in internal fapilog logs

### Dependency Security

- **Scanning Tool:** bandit for security vulnerability detection
- **Update Policy:** Monthly security dependency reviews
- **Approval Process:** All new dependencies require security review

### Security Testing

- **SAST Tool:** bandit for static analysis security testing
- **DAST Tool:** Plugin-specific dynamic testing for network operations
- **Penetration Testing:** Annual third-party security assessment for enterprise features

## Checklist Results Report

**Architecture Document Status:** ✅ **Complete and Ready for Validation**

**Document Summary:**

- **Total Sections:** 16 comprehensive sections
- **Architecture Focus:** Developer-first simplicity with enterprise extensibility
- **Core Approach:** Async-first Python library with plugin ecosystem
- **Key Revisions:** Simplified from complex enterprise infrastructure to library-focused design
- **Performance Target:** 500K-2M events/second with zero-copy operations
- **Plugin Strategy:** PyPI + GitHub based community ecosystem

## Next Steps

After completing the Fapilog v3 architecture:

### Immediate Development Priorities

1. **Core Library Foundation**

   - Implement AsyncLogger with async-first patterns
   - Build AsyncLoggingContainer with perfect isolation
   - Create universal plugin system with entry points
   - Establish async pipeline with parallel processing

2. **Plugin Ecosystem Bootstrap**

   - Develop core sink plugins (stdout, file, http)
   - Create plugin development documentation and templates
   - Establish community contribution guidelines
   - Build plugin validation and testing framework

3. **Performance Validation**
   - Implement performance benchmarking suite
   - Validate 500K-2M events/second targets
   - Optimize zero-copy operations and async patterns
   - Create continuous performance monitoring

### Development Team Handoff

**For AI Development Agents:**

```
You are now implementing Fapilog v3 based on this comprehensive architecture document.

Key Implementation Priorities:
1. Follow the async-first patterns exactly as specified
2. Implement plugin isolation with graceful error handling
3. Maintain zero-copy operations throughout the pipeline
4. Ensure container isolation prevents cross-contamination
5. Build developer-first simplicity with enterprise plugin extensibility

Architecture Document: docs/architecture.md
Coding Standards: Section 13 contains mandatory patterns for AI agents
Performance Targets: 500K-2M events/second with <1ms latency
Plugin Strategy: Standard Python entry points with PyPI distribution

Start with AsyncLogger and AsyncLoggingContainer as the foundation, then build the plugin system.
```

**For Human Developers:**

```
Fapilog v3 Architecture Implementation Guide

This architecture balances developer simplicity ("works out of box") with enterprise extensibility (plugin ecosystem).

Core Principles:
- Async-first throughout - never mix sync/async patterns
- Plugin-based everything - enterprise features are optional plugins
- Container isolation - perfect isolation with zero global state
- Developer experience - zero configuration required for basic usage
- Enterprise ready - full compliance and observability via plugins

Implementation Sequence:
1. Core library (AsyncLogger, Container, Pipeline)
2. Plugin system (Registry, Base classes, Built-ins)
3. Community plugins (Splunk, Prometheus, Audit trail)
4. Performance optimization (500K-2M events/second)
5. Enterprise features (Compliance, Security, Monitoring)

Reference: docs/architecture.md for complete implementation guidance
```

### Community Ecosystem Development

1. **Plugin Marketplace Strategy**

   - Create awesome-fapilog repository for plugin discovery
   - Establish plugin development standards and templates
   - Build community recognition and contribution programs
   - Develop plugin security validation framework

2. **Documentation and Education**

   - Create developer-focused quick start guides
   - Build comprehensive plugin development tutorials
   - Establish enterprise deployment and compliance guides
   - Create performance optimization documentation

3. **Community Growth**
   - Engage Python logging community with async-first benefits
   - Target enterprise users with compliance and performance features
   - Build contributor community around plugin development
   - Establish feedback loops for continuous improvement

### Enterprise Adoption Strategy

1. **Compliance and Security**

   - Develop enterprise compliance plugin suite (PCI-DSS, HIPAA, SOX)
   - Create security validation and scanning frameworks
   - Build enterprise monitoring and observability plugins
   - Establish enterprise support and consulting services

2. **Integration and Deployment**
   - Create SIEM integration plugins (Splunk, ELK, etc.)
   - Build cloud platform integration guides
   - Develop container and Kubernetes deployment examples
   - Create enterprise configuration and tuning guides

---

**The architecture is now complete and ready for implementation. This document serves as the definitive guide for building Fapilog v3 as a revolutionary async-first logging library that achieves both developer simplicity and enterprise power.**
