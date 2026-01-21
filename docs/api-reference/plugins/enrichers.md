# Enrichers

Plugins that add metadata to log entries before redaction and sinks.

## Contract

Implement `BaseEnricher` methods:

- `async enrich(self, event: dict) -> dict`: required; return additional fields to merge.
- `async start(self) -> None`: optional initialization.
- `async stop(self) -> None`: optional teardown.

```python
from fapilog.plugins.enrichers import BaseEnricher

class MyEnricher:
    name = "my-enricher"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def enrich(self, event: dict) -> dict:
        return {"custom_field": "value"}

    async def health_check(self) -> bool:
        return True
```

## Built-in Enrichers

| Enricher | Name | Description |
|----------|------|-------------|
| `RuntimeInfoEnricher` | `runtime_info` | Adds service, env, version, host, pid, python |
| `ContextVarsEnricher` | `context_vars` | Adds request_id, user_id from ContextVar |
| `KubernetesEnricher` | `kubernetes` / `k8s` | Adds pod, namespace, node from K8s downward API |

### RuntimeInfoEnricher

Adds system and runtime information under the `diagnostics` semantic group:

- `service`: from `FAPILOG_SERVICE` env var (default: "fapilog")
- `env`: from `FAPILOG_ENV` or `ENV` env var (default: "dev")
- `version`: from `FAPILOG_VERSION` env var
- `host`: hostname
- `pid`: process ID
- `python`: Python version

Returns: `{"diagnostics": {"service": "...", "env": "...", "host": "...", "pid": 1234, "python": "3.11.0"}}`

### ContextVarsEnricher

Adds values from context variables under the `context` semantic group when present:

- `request_id`: from fapilog's request context
- `user_id`: from fapilog's user context
- `trace_id`, `span_id`: when OpenTelemetry is available
- `tenant_id`: from event data if present

Returns: `{"context": {"request_id": "...", "user_id": "...", "trace_id": "...", "span_id": "..."}}`

### KubernetesEnricher

Adds Kubernetes metadata from the downward API:

- `pod`: pod name
- `namespace`: Kubernetes namespace
- `node`: node name
- `container`: container name

Requires Kubernetes downward API environment variables to be configured in your pod spec.

## Configuration

Enable enrichers via settings:

```python
from fapilog import Settings

settings = Settings(
    core__enrichers=["runtime_info", "context_vars"],
)
```

Or via environment variable:

```bash
export FAPILOG_CORE__ENRICHERS='["runtime_info", "context_vars", "kubernetes"]'
```

## Runtime Control

Toggle enrichers at runtime:

```python
from fapilog.plugins.enrichers import RuntimeInfoEnricher

# Disable an enricher by name
logger.disable_enricher("context_vars")

# Enable an enricher instance
logger.enable_enricher(RuntimeInfoEnricher())
```

Enrichers run per entry before redactors.
