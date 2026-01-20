# Enrichers

Add contextual metadata to log entries. Implement `BaseEnricher`.

## Implementing an enricher

```python
from fapilog.plugins import BaseEnricher

class MyEnricher(BaseEnricher):
    name = "my_enricher"

    async def enrich(self, entry: dict) -> dict:
        # Return a dict targeting semantic groups (context, diagnostics, data)
        # These fields are deep-merged into the event
        return {"context": {"service": "billing"}}
```

**Important:** Enrichers return fields to deep-merge into the event, not the full event itself. Return dicts targeting semantic groups like `context`, `diagnostics`, or `data`. See [Plugin Error Handling](error-handling.md) for patterns including error containment.

## Registering an enricher

- Declare an entry point under `fapilog.enrichers` in `pyproject.toml`.
- Provide `PLUGIN_METADATA` with `plugin_type: "enricher"` and compatible API version.

## Built-in enrichers

- `runtime_info` (host, pid, python, service/env/version)
- `context_vars` (request/user IDs from ContextVar)
- `kubernetes` (pod/namespace/node/container/deployment from Downward API env vars)

## Usage

Enrichers run before redaction and sinks. You can enable/disable at runtime via `logger.enable_enricher` / `logger.disable_enricher` (sync/async facades).

## Configuration Pattern

Use Pydantic v2 models for enricher configuration:

```python
from pydantic import BaseModel, ConfigDict, Field
from fapilog.plugins import BaseEnricher, parse_plugin_config


class MyEnricherConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service_name: str = Field(default="unknown")
    include_host: bool = True


class MyEnricher(BaseEnricher):
    name = "my_enricher"

    def __init__(
        self,
        *,
        config: MyEnricherConfig | dict | None = None,
        **kwargs: object,
    ) -> None:
        cfg = parse_plugin_config(MyEnricherConfig, config, **kwargs)
        self._service_name = cfg.service_name
        self._include_host = cfg.include_host

    async def enrich(self, entry: dict) -> dict:
        result = {"context": {"service": self._service_name}}
        if self._include_host:
            import socket
            result["diagnostics"] = {"host": socket.gethostname()}
        return result
```

## Kubernetes Enricher

Adds pod metadata when running in Kubernetes using only environment variables (Downward API). No K8s API calls or volume mounts required.

```python
from fapilog import get_logger, Settings

settings = Settings()
settings.core.enrichers = ["kubernetes"]
logger = get_logger(settings=settings)
logger.info("processing request")
```

### Fields Added (default prefix `k8s_`)

- `k8s_pod`, `k8s_namespace`, `k8s_node`, `k8s_container`, `k8s_cluster`
- `k8s_deployment` extracted from pod name (`my-app-7d4b8c9f6-abc12` → `my-app`)

### Minimal Deployment Snippet

```yaml
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: POD_NAMESPACE
    valueFrom:
      fieldRef:
        fieldPath: metadata.namespace
  - name: NODE_NAME
    valueFrom:
      fieldRef:
        fieldPath: spec.nodeName
  - name: CONTAINER_NAME
    value: "main"          # static; Kubernetes does not inject automatically
  - name: CLUSTER_NAME
    value: "prod-cluster"  # optional, set by your tooling
```

Config options:

```python
from fapilog.plugins.enrichers import KubernetesEnricher

enricher = KubernetesEnricher(prefix="k8s_", skip_if_not_k8s=True)
```
