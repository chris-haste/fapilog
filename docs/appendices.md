# Appendices

Reference materials and additional information.

```{toctree}
:maxdepth: 2
:caption: Appendices

env-vars
settings-guide
schema-guide
plugin-guide
redaction-guarantees
security-operator-workflows
quality-signals
```

## Overview

The appendices contain reference materials and additional information:

- **Glossary** - Definitions of key terms and concepts
- **Architecture Diagrams** - Visual representations of fapilog's design
- **License & Credits** - Legal information and acknowledgments

## Quick Reference

### Common Terms

- **Envelope** - The standardized log message format
- **Context** - Request-scoped information and correlation
- **Sink** - Output destination for log messages
- **Redactor** - Data masking and security component
- **Processor** - Message transformation and optimization
- **Dedup Window** - Time window for deduplication

### Architecture Components

- **Pipeline** - Message processing flow
- **Queue** - Message buffering and backpressure
- **Workers** - Async message processing
- **Plugins** - Extensible functionality

---

## Glossary

### A

**Async-First Design**
A design approach where all operations are asynchronous by default, ensuring non-blocking behavior and high performance.

**Audit Logging**
Comprehensive logging for compliance and security purposes, including immutable records and integrity verification.

### B

**Backpressure**
A mechanism to handle situations where the system receives more messages than it can process, preventing resource exhaustion.

**Batching**
Grouping multiple log messages together for efficient processing and transmission.

### C

**Context Binding**
The process of attaching request-scoped information to log messages for correlation and debugging.

**Circuit Breaker**
A pattern that prevents cascading failures by temporarily stopping operations when error thresholds are exceeded.

### D

**Deduplication**
Removing duplicate log messages within a configurable time window to reduce noise and storage.

**Dedup Window**
The time period during which duplicate messages are identified and removed.

### E

**Envelope**
The standardized structure that contains all log message data, including metadata, context, and the actual log content.

**Enrichers**
Components that add additional metadata to log messages, such as runtime information or business context.

### F

**Facade**
The main logging interface that developers interact with, hiding the complexity of the underlying pipeline.

**Fallback**
A mechanism that provides alternative behavior when primary operations fail.

### G

**Guarantees**
Promises about system behavior, such as async operations, bounded memory usage, and graceful degradation.

### H

**Hot Reload**
The ability to update configuration and plugins without restarting the application.

### I

**Intersphinx**
A Sphinx extension that enables cross-references between different documentation projects.

### J

**JSON Lines**
A format where each line is a valid JSON object, commonly used for log aggregation and processing.

### L

**Lock-Free Design**
A concurrent programming approach that avoids locks and blocking, improving performance and scalability.

### M

**Metrics**
Quantitative measurements of system behavior, such as throughput, latency, and error rates.

**Middleware**
Software that runs between the application and the logging system, providing additional functionality.

### N

**Non-Blocking**
Operations that don't prevent other operations from proceeding, essential for high-performance systems.

### O

**Observability**
The ability to understand system behavior through logs, metrics, and traces.

**Overflow**
A condition where the message queue reaches its capacity limit, requiring backpressure handling.

### P

**Pipeline**
The sequence of processing stages that log messages go through, from creation to output.

**Plugin**
Extensible components that add custom functionality to fapilog, such as custom sinks or processors.

**Processor**
Components that transform and optimize log messages, such as batching or compression.

### Q

**Queue**
A buffer that stores messages between processing stages, handling backpressure and ensuring smooth operation.

### R

**Redactor**
Components that remove or mask sensitive information from log messages for security and compliance.

**Ring Buffer**
A circular data structure used for efficient message queuing with bounded memory usage.

**Runtime**
The execution environment where fapilog operates, including lifecycle management and resource allocation.

### S

**Sink**
The final destination for log messages, such as files, HTTP endpoints, or stdout.

**Structured Logging**
Logging that uses structured data formats (like JSON) instead of plain text, enabling better analysis and processing.

**Serialization**
The process of converting log messages to a format suitable for transmission or storage.

### T

**Throughput**
The rate at which the system can process log messages, typically measured in messages per second.

**Trace ID**
A unique identifier that links related log messages across different parts of a distributed system.

### U

**Use Case**
A specific scenario or requirement that demonstrates how fapilog can be used to solve real problems.

### V

**Validation**
The process of ensuring that log messages conform to expected formats and constraints.

**Versioning**
A system for managing compatibility between different versions of fapilog and its plugins.

### W

**Worker**
Background processes that handle log message processing, ensuring non-blocking operation.

**Work Stealing**
A load balancing technique where idle workers can take work from busy workers.

### Z

**Zero-Copy**
A technique that minimizes memory allocation by reusing existing data structures.

---

## Architecture Diagrams

### High-Level Architecture

```{mermaid}
graph TB
    A[Application] --> B[Logger Facade]
    B --> C[Context Binding]
    C --> D[Enrichers]
    D --> E[Redactors]
    E --> F[Processors]
    F --> G[Queue]
    G --> H[Workers]
    H --> I[Sinks]

    J[Metrics] --> K[Prometheus]
    L[Configuration] --> M[Environment]
    N[Plugins] --> O[Custom Components]

    style A fill:#e1f5fe
    style I fill:#c8e6c9
    style J fill:#fff3e0
```

### Pipeline Flow

```{mermaid}
sequenceDiagram
    participant App as Application
    participant Logger as Logger
    participant Context as Context
    participant Pipeline as Pipeline
    participant Queue as Queue
    participant Workers as Workers
    participant Sinks as Sinks

    App->>Logger: log.info(message, extra)
    Logger->>Context: bind context
    Context->>Pipeline: enrich message
    Pipeline->>Pipeline: redact sensitive data
    Pipeline->>Queue: queue message
    Queue->>Workers: process batch
    Workers->>Sinks: write to destinations
    Sinks-->>App: confirmation
```

### Component Relationships

```{mermaid}
graph LR
    subgraph "Core Components"
        A[Logger] --> B[Context Manager]
        B --> C[Pipeline]
        C --> D[Queue Manager]
        D --> E[Worker Pool]
    end

    subgraph "Plugins"
        F[Sinks] --> G[File Sink]
        F --> H[HTTP Sink]
        F --> I[Stdout Sink]

        J[Processors] --> K[Batch Processor]
        J --> L[Compression Processor]

        M[Enrichers] --> N[Runtime Enricher]
        M --> O[Context Enricher]

        P[Redactors] --> Q[Field Mask]
        P --> R[Regex Mask]
    end

    subgraph "Integration"
        S[FastAPI] --> T[Middleware]
        U[Metrics] --> V[Prometheus]
        W[Configuration] --> X[Environment]
    end
```

---

## License & Credits

### License

fapilog is licensed under the **Apache License 2.0**.

```
Copyright 2024 Chris Haste

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### Credits

#### Core Team

- **Chris Haste** - Project lead and main developer
- **Contributors** - Community members who have contributed code, documentation, and ideas

#### Open Source Dependencies

fapilog builds on the work of many open source projects:

- **structlog** - Structured logging foundation
- **pydantic** - Data validation and settings
- **anyio** - Async I/O utilities
- **asyncio-mqtt** - MQTT client support
- **aiofiles** - Async file operations
- **httpx** - HTTP client library
- **orjson** - Fast JSON serialization
- **prometheus-client** - Metrics collection

#### Inspiration

fapilog draws inspiration from:

- **zerolog** - Go logging library
- **loguru** - Python logging library
- **winston** - Node.js logging library
- **logback** - Java logging framework

### Contributing

We welcome contributions from the community! See the {doc}`Contributing Guide <contributing/index>` for details on:

- Code contributions
- Documentation improvements
- Bug reports
- Feature requests
- Community support

### Acknowledgments

Special thanks to:

- **Early adopters** - Users who provided feedback and testing
- **Open source community** - For building the tools that make fapilog possible
- **Documentation contributors** - For helping make fapilog accessible to everyone

---

_These appendices provide reference information and additional context for fapilog users and contributors._
