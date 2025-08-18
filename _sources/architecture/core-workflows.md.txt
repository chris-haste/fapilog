# Core Workflows

Here are the key system workflows that illustrate the async-first architecture and component interactions:

## High-Performance Async Logging Workflow

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

## Plugin Discovery and Loading Workflow

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

## Enterprise Compliance and Audit Workflow

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

## High-Throughput Batch Processing Workflow

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

## Container Isolation Workflow

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
