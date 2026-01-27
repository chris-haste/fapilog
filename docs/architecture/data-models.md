# Data Models

Based on my analysis of your existing codebase and PRD requirements, here are the core data models that will drive the Fapilog v3 architecture:

## LogEvent

**Purpose:** The central data structure for all log events, designed for future alerting capabilities and enterprise compliance

**Key Attributes:**

- `message: str` - The primary log message content
- `level: str` - Standard logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `timestamp: datetime` - Event timestamp for chronological ordering
- `source: str` - Service/component name for distributed tracing
- `severity: int` - Numeric severity (1-10) for alert prioritization
- `tags: Dict[str, str]` - Key-value metadata for filtering and enrichment
- `context: Dict[str, Any]` - Request context and trace correlation
- `metrics: Dict[str, float]` - Performance metrics and measurements
- `correlation_id: str` - Distributed tracing and request correlation

**Relationships:**

- **With AsyncLogger:** Created and processed by logger instances
- **With Plugin System:** Enriched by enricher plugins, processed by processor plugins
- **With Redactors:** Redacted based on configured patterns

## Settings

**Purpose:** Configuration model that drives all aspects of the async-first logging system

**Key Attributes:**

- `level: str` - Global logging level filter
- `sinks: List[str]` - Active sink configurations
- `batch_size: int` - Event batching for performance optimization
- `queue_max_size: int` - Maximum queue size for backpressure handling
- `max_workers: int` - Parallel processing worker count
- `overflow_strategy: OverflowStrategy` - Queue overflow behavior
- `plugin_config: Dict[str, Any]` - Plugin-specific configurations

**Relationships:**

- **With AsyncLogger:** Configures logger behavior and performance characteristics
- **With Plugin Registry:** Drives plugin loading and configuration

## PluginMetadata

**Purpose:** Metadata model for plugin discovery, loading, and ecosystem integration

**Key Attributes:**

- `name: str` - Plugin unique identifier
- `version: str` - Semantic version for compatibility
- `plugin_type: PluginType` - Sink, Processor, or Enricher classification
- `entry_point: str` - Module path for plugin loading
- `dependencies: List[str]` - Required dependencies and versions
- `performance_profile: Dict[str, float]` - Performance characteristics
- `configuration_schema: Dict[str, Any]` - Plugin configuration validation

**Relationships:**

- **With Plugin Registry:** Enables dynamic plugin discovery and loading
- **With Plugin Ecosystem:** Supports community-driven ecosystem growth via PyPI

## AsyncLoggingContainer

**Purpose:** Container isolation model providing perfect isolation with zero global state

**Key Attributes:**

- `container_id: str` - Unique container identifier
- `settings: Settings` - Container-specific configuration
- `plugin_registry: PluginRegistry` - Isolated plugin instances
- `metrics_collector: MetricsCollector` - Container performance metrics
- `async_pipeline: AsyncPipeline` - Isolated event processing pipeline

**Relationships:**

- **With AsyncLogger:** Provides isolated execution context
- **With Plugin System:** Maintains isolated plugin instances
- **With Metrics System:** Collects container-specific performance data
