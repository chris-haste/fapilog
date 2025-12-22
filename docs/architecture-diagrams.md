# Architecture Diagrams

High-level flow of the logging pipeline:

```text
Application -> Enrichers -> Redactors -> Processors -> Queue/Batch -> Sinks
```

Key components:
- Background worker processes the queue asynchronously.
- Enrichers add runtime/context metadata.
- Redactors mask sensitive data before sinks.
- Sinks deliver structured logs (stdout/file/http).
```
