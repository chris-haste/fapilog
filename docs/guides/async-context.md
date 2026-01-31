# Async Context Propagation

This guide explains how to preserve logging context across async boundaries in Python.

## The Problem

Python's `contextvars` propagate correctly across `await` boundaries, but **not** automatically into:

- `asyncio.create_task()` - new tasks may not inherit context (pre-Python 3.11)
- `ThreadPoolExecutor` / `run_in_executor()` - threads don't inherit context
- `asyncio.gather()` with tasks created separately

This means request IDs, user IDs, and trace context can silently vanish in background tasks.

## Solution: Context Propagation Helpers

Fapilog provides three helpers to explicitly preserve context:

```python
from fapilog import (
    create_task_with_context,
    run_in_executor_with_context,
    preserve_context,
)
```

## create_task_with_context

Use this when spawning background tasks that need access to the current logging context.

```python
import asyncio
import fapilog

async def background_work():
    logger = fapilog.get_logger()
    logger.info("background task")  # includes request_id from parent

async def main():
    logger = fapilog.get_logger().bind(request_id="req-123")
    logger.info("main task")

    # Without helper - context may be lost
    task1 = asyncio.create_task(background_work())

    # With helper - context explicitly preserved
    task2 = fapilog.create_task_with_context(background_work())

    await asyncio.gather(task1, task2)
```

### With Task Names

```python
task = fapilog.create_task_with_context(
    background_work(),
    name="process-order-123"
)
```

## run_in_executor_with_context

Use this when running synchronous code in a thread pool while preserving context.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import fapilog

def sync_work():
    # Context variables from caller are available here
    logger = fapilog.get_logger()
    logger.info("sync work in thread")  # includes request_id

async def main():
    logger = fapilog.get_logger().bind(request_id="req-456")
    executor = ThreadPoolExecutor(max_workers=2)

    # Context preserved in the executor thread
    await fapilog.run_in_executor_with_context(executor, sync_work)

    # Also works with the default executor (None)
    await fapilog.run_in_executor_with_context(None, sync_work)
```

### Passing Arguments

```python
def process_item(item_id: str, priority: int) -> dict:
    logger = fapilog.get_logger()
    logger.info("processing", item_id=item_id)
    return {"status": "done"}

result = await fapilog.run_in_executor_with_context(
    executor,
    process_item,
    "item-123",
    priority=1,
)
```

## preserve_context Decorator

Use this decorator on async functions that may be scheduled as tasks, ensuring they always preserve context from their call site.

```python
import asyncio
import fapilog

@fapilog.preserve_context
async def worker():
    logger = fapilog.get_logger()
    logger.info("worker")  # has parent context

async def main():
    logger = fapilog.get_logger().bind(user_id="user-789")

    # Even when scheduled as task, context is preserved
    await asyncio.gather(worker(), worker())

    # Also works with create_task
    task = asyncio.create_task(worker())
    await task
```

## Context Isolation

Each task gets a **copy** of the context. Modifications in child tasks don't affect the parent:

```python
import contextvars
import fapilog

request_id = contextvars.ContextVar("request_id")

async def child_task():
    # This modification is local to the child
    request_id.set("child-override")

async def main():
    request_id.set("parent-value")

    task = fapilog.create_task_with_context(child_task())
    await task

    # Parent still sees original value
    assert request_id.get() == "parent-value"
```

## FastAPI Integration

Context helpers work well with FastAPI background tasks:

```python
from fastapi import FastAPI, BackgroundTasks
import fapilog

app = FastAPI()

async def send_notification(user_id: str):
    logger = fapilog.get_logger()
    # request_id from the request context is available here
    logger.info("sending notification", user_id=user_id)

@app.post("/orders")
async def create_order(background_tasks: BackgroundTasks):
    logger = fapilog.get_logger().bind(request_id="req-abc")

    # Use create_task_with_context for context-aware background work
    task = fapilog.create_task_with_context(
        send_notification("user-123")
    )

    return {"status": "created"}
```

## When to Use Each Helper

| Scenario | Helper |
|----------|--------|
| Spawning a background task | `create_task_with_context()` |
| Running sync code in a thread | `run_in_executor_with_context()` |
| Function that's often scheduled as a task | `@preserve_context` decorator |

## Performance

Context copying via `contextvars.copy_context()` is fast (~100ns), negligible compared to task creation overhead.
