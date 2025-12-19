# Roadmap (Not Yet Shipped)

This page lists planned features that are **not implemented yet**. Today, fapilog ships:

- Async/sync factories and runtime contexts (awaitable async factory)
- Redactors/enrichers, stdout and rotating-file sinks, HTTP client sink
- Metrics hooks and basic CLI commands (`version/settings/emit/flush/drain`)

## Pipeline & Sinks (planned)

- Cloud/remote sinks: AWS CloudWatch, Azure Monitor, GCP Logging, Kafka/webhooks, Splunk/ELK/Loki/Datadog
- Additional processors: sampling, compression, encryption, adaptive batching

## Tooling (planned)

- Expanded CLI commands (filters, tailing, profiles)
- Marketplace providers: ratings, benchmarks, security/compliance signals

## Compliance & Observability (planned)

- Compliance policy packs and attestations
- Deeper observability exports (expanded metrics/tracing hooks)

Progress is tracked in milestones; items move here until they form part of a release.
