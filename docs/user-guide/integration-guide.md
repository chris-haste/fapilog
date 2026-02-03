# Integration Guide

Patterns for common application types.

**See also:** [One FastAPI config for dev + prod](../cookbook/dev-prod-logging-config.md) - Single configuration that adapts to environment automatically.

## FastAPI / async web

```python
from fastapi import FastAPI, Depends
from fapilog.fastapi import FastAPIBuilder, get_request_logger

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .skip_paths(["/health", "/metrics"])
        .build()
)

@app.get("/items/{item_id}")
async def get_item(item_id: str, logger=Depends(get_request_logger)):
    await logger.info("fetch", item_id=item_id)
    return {"item_id": item_id}
```

`FastAPIBuilder` handles lifespan management, request context, and provides FastAPI-specific options like `skip_paths()`, `include_headers()`, and `sample_rate()`. See [FastAPI Integration](fastapi.md) for full documentation.

## CLI / scripts

```python
from fapilog import runtime

def main():
    with runtime() as logger:
        logger.info("job started")
        # ... work ...
        logger.info("job done")

if __name__ == "__main__":
    main()
```

## Batch processing

```python
import asyncio
from fapilog import runtime_async

async def process_items(items):
    async with runtime_async() as logger:
        for item in items:
            await logger.info("item", id=item.id)

asyncio.run(process_items([...]))
```

## Mixed sync/async

For apps with both sync and async parts, prefer async loggers in async contexts and keep sync logging in sync threads. Avoid sharing the same logger across event loops; create per-loop loggers as needed.
