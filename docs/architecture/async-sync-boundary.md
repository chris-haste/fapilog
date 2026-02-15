# Async/Sync Boundary Design

This document explains how fapilog handles the boundary between synchronous and asynchronous code, particularly around worker thread management.

## Overview

Fapilog's core is async-first, but most users call it from synchronous code. The logging pipeline always runs on a **dedicated background thread** with its own event loop, regardless of the caller's context. The only work on the caller's thread is `try_enqueue()` — a fast, non-blocking put onto a thread-safe queue.

```
┌─────────────────────────────────────────────────────────────┐
│                     User Code                               │
├─────────────────────┬───────────────────────────────────────┤
│   Sync Context      │         Async Context                 │
│   (no event loop)   │    (event loop running)               │
├─────────────────────┴───────────────────────────────────────┤
│              Dedicated Worker Thread                         │
│              - Own event loop                                │
│              - Worker tasks, sinks, monitors                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Locations

1. **`_start_plugins_sync()`** in `src/fapilog/__init__.py`
   - Handles plugin startup in sync contexts
   - Must work whether or not an event loop exists

2. **`SyncLoggerFacade.start()` / `AsyncLoggerFacade.start()`** in `src/fapilog/core/logger.py`
   - Always creates a dedicated background thread with its own event loop
   - Worker tasks, pressure monitor, and sinks run on the thread's loop

## Dedicated Thread Architecture

**`start()` always:**
- Creates a new `asyncio.new_event_loop()` in a background thread
- Spawns worker tasks on that loop
- Signals readiness via `threading.Event`

**Enqueue path:**
- Both sync and async facades call `try_enqueue()` directly on the thread-safe queue
- No `run_coroutine_threadsafe`, no `await` — microseconds per event

**Drain path:**
- Sets the stop flag, waits for worker thread to join
- `AsyncLoggerFacade` uses `asyncio.to_thread()` to call `_drain_thread_mode()`

```python
# In start():
def _run():
    loop_local = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_local)
    # Create worker tasks, monitor, etc.
    loop_local.run_forever()  # Until stopped

self._worker_thread = threading.Thread(target=_run, daemon=True)
self._worker_thread.start()
```

## Plugin Startup Edge Case

`_start_plugins_sync()` has an additional challenge: it needs to run async plugin `start()` methods from a sync context, but it might be called from within an async context (where `asyncio.run()` would fail).

**Solution:**

```python
try:
    asyncio.get_running_loop()
    # Can't use asyncio.run() here - "loop already running" error
    # Offload to a thread that has no loop
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_sync)  # _run_sync uses asyncio.run()
        return future.result(timeout=5.0)
except RuntimeError:
    # No loop - safe to use asyncio.run() directly
    return asyncio.run(...)
```

## Thread/Loop Relationship Diagram

```
Caller Thread                    Worker Thread
     │                               │
     ▼                               ▼
┌─────────────────┐          ┌─────────────────┐
│ SyncLoggerFacade│          │ Dedicated Loop   │
│ or AsyncLogger  │          │ ┌─────────────┐ │
│                 │ enqueue  │ │ Worker Tasks │ │
│ try_enqueue() ──┼─────────►│ │ (dequeue,   │ │
│   (µseconds)    │          │ │  process,   │ │
│                 │          │ │  sink write) │ │
└─────────────────┘          │ └─────────────┘ │
                             │ ┌─────────────┐ │
                             │ │ Monitor     │ │
                             │ │ (pressure)  │ │
                             │ └─────────────┘ │
                             └─────────────────┘
```

## Common Debugging Scenarios

### "My logger isn't flushing on shutdown"

**Cause:** The worker thread needs time to process remaining items. If the process exits before `stop_and_drain()` completes, logs may be lost.

**Solution:** Ensure `await logger.stop_and_drain()` (or the sync equivalent) completes before your application shuts down. Use `runtime()` / `runtime_async()` context managers for automatic cleanup.

### "Logger hangs during startup"

**Cause:** `_start_plugins_sync()` has a 5-second timeout. If a plugin's `start()` method hangs, startup will timeout.

**Solution:** Check plugin implementations. The logger will continue with unstarted plugins (fail-open).

### "asyncio.run() raises 'loop already running'"

**Cause:** Calling sync fapilog APIs from within an async context where someone used `asyncio.run()` instead of the proper detection pattern.

**Solution:** This is handled automatically by fapilog. If you see this error, it's likely in user code — use `await` instead of `asyncio.run()`.

### "Events dropped despite drop_on_full=False"

**Cause:** With the dedicated thread architecture, `try_enqueue()` is always non-blocking. The `drop_on_full=False` setting cannot be honored because the caller thread cannot block waiting for queue space on the worker thread's loop.

**Diagnostic:** A warning is emitted at startup when `drop_on_full=False` is configured with `SyncLoggerFacade`.

**Solution:** Size your queue appropriately (`core.max_queue_size`) to handle burst traffic without dropping.

## Design Principles

1. **Fail-open for logging:** If plugin startup fails, continue with unstarted plugins. Logging should never crash the application.

2. **Isolation by default:** The logging pipeline always runs on its own thread, preventing sink I/O from affecting the caller's event loop.

3. **Non-blocking hot path:** `try_enqueue()` never blocks the caller — it either succeeds or drops immediately.

4. **Timeouts everywhere:** All cross-thread operations have timeouts to prevent deadlocks.
