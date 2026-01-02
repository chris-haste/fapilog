# Context Enrichment


Attach business/request metadata to every log entry.

## Binding context

```python
from fapilog import runtime

with runtime() as logger:
    logger.bind(request_id="req-1", user_id="u-123")
    logger.info("Request started")
    logger.clear_context()
```

## Async pattern

```python
import asyncio
from fapilog import runtime_async

async def handle(user_id: str):
    async with runtime_async() as logger:
        logger.bind(user_id=user_id)
        await logger.info("Handling user")
        logger.clear_context()

asyncio.run(handle("u-1"))
```

## Built-in enrichers

- `runtime-info`: service/env/version/host/pid/python.
- `context-vars`: request/user IDs from ContextVar when present.

## Runtime Enricher Control

You can dynamically enable or disable enrichers at runtime.

### Disabling an Enricher

```python
from fapilog import get_logger

logger = get_logger()

# Disable the context_vars enricher by name
logger.disable_enricher("context_vars")

# Logs after this point won't include context variables
logger.info("No context vars here")
```

### Enabling an Enricher

```python
from fapilog import get_logger
from fapilog.plugins.enrichers import RuntimeInfoEnricher

logger = get_logger()

# Add a new enricher instance at runtime
logger.enable_enricher(RuntimeInfoEnricher())

# Logs after this point include runtime info
logger.info("Now with runtime info")
```

### Common Patterns

**Conditional enrichment based on environment:**

```python
import os
from fapilog import get_logger
from fapilog.plugins.enrichers import RuntimeInfoEnricher

logger = get_logger()

if os.getenv("ENABLE_DETAILED_LOGGING"):
    logger.enable_enricher(RuntimeInfoEnricher())
```

**Temporarily disable enrichers for performance:**

```python
def process_large_batch(items, logger):
    # Disable verbose enrichers during high-volume processing
    logger.disable_enricher("runtime_info")
    
    for item in items:
        logger.debug("processing", item_id=item.id)
    
    # Re-enable after batch
    logger.enable_enricher(RuntimeInfoEnricher())
```

### Important Notes

- `enable_enricher()` adds the enricher if no enricher with the same `name` exists
- `disable_enricher()` removes all enrichers matching the given name
- Changes take effect for subsequent log calls (not retroactively)
- Enrichers must have a `name` attribute to be enabled/disabled by name

## Tips

- Bind per request/task; clear when done.
- Avoid deeply nested objects for better performance; use simple dicts/strings/numbers.
