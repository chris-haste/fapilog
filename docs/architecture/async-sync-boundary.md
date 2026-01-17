# Async/Sync Boundary Design

This document explains how fapilog handles the boundary between synchronous and asynchronous code, particularly around event loop detection and worker thread management.

## Overview

Fapilog's core is async-first, but most users call it from synchronous code. This creates a fundamental challenge: async operations need an event loop, but sync code typically doesn't have one running.

The solution involves detecting the caller's context and choosing the appropriate strategy:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Code                               │
├─────────────────────┬───────────────────────────────────────┤
│   Sync Context      │         Async Context                 │
│   (no event loop)   │    (event loop running)               │
├─────────────────────┼───────────────────────────────────────┤
│   Thread Loop Mode  │         Bound Loop Mode               │
│   - New thread      │    - Use existing loop                │
│   - Own event loop  │    - Tasks in caller's loop           │
└─────────────────────┴───────────────────────────────────────┘
```

## Key Locations

Two functions contain the critical event loop handling logic:

1. **`_start_plugins_sync()`** in `src/fapilog/__init__.py`
   - Handles plugin startup in sync contexts
   - Must work whether or not an event loop exists

2. **`SyncLoggerFacade.start()`** in `src/fapilog/core/logger.py`
   - Starts the background worker
   - Chooses between bound loop and thread loop modes

## Event Loop Detection

Both functions use the same detection pattern:

```python
try:
    asyncio.get_running_loop()
    # Loop IS running - we're in an async context
except RuntimeError:
    # No loop running - we're in a sync context
```

This is the only reliable way to detect the current context. Other approaches like checking `asyncio.get_event_loop()` are deprecated and unreliable.

## Mode 1: Bound Loop Mode

**When:** Called from within a running event loop (async framework, Jupyter, etc.)

**Behavior:**
- Worker tasks are created directly in the existing loop
- No new threads are spawned for the worker
- Shutdown must happen while the loop is still running

**Why it matters:**
- Async frameworks expect all async work to happen in their loop
- Using a separate thread would break integration with await-based shutdown
- The caller's loop already handles scheduling and execution

```python
# In SyncLoggerFacade.start():
try:
    loop = asyncio.get_running_loop()  # Success = bound mode
    self._worker_loop = loop
    task = loop.create_task(self._worker_main())
    ...
```

## Mode 2: Thread Loop Mode

**When:** Called from sync code with no event loop

**Behavior:**
- Creates a dedicated background thread
- That thread creates and runs its own event loop
- Thread runs until `stop_and_drain()` is called

**Why it exists:**
- Sync code (CLI tools, scripts) has no event loop
- We need an event loop to run async sinks and workers
- Solution: create our own in a background thread

```python
# In SyncLoggerFacade.start():
except RuntimeError:  # No loop = thread mode
    def _run():
        loop_local = asyncio.new_event_loop()
        asyncio.set_event_loop(loop_local)
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
Sync Caller (no loop)           Async Caller (has loop)
       │                               │
       ▼                               ▼
┌─────────────────┐           ┌─────────────────┐
│ SyncLoggerFacade│           │ SyncLoggerFacade│
│    .start()     │           │    .start()     │
└────────┬────────┘           └────────┬────────┘
         │                             │
         ▼                             ▼
  Thread Loop Mode              Bound Loop Mode
         │                             │
         ▼                             ▼
┌─────────────────┐           ┌─────────────────┐
│ Worker Thread   │           │ Caller's Loop   │
│ ┌─────────────┐ │           │ ┌─────────────┐ │
│ │ Event Loop  │ │           │ │Worker Tasks │ │
│ │ ┌─────────┐ │ │           │ └─────────────┘ │
│ │ │ Worker  │ │ │           │ (shared with    │
│ │ │ Tasks   │ │ │           │  caller's work) │
│ │ └─────────┘ │ │           └─────────────────┘
│ └─────────────┘ │
└─────────────────┘
```

## Common Debugging Scenarios

### "My logger isn't flushing on shutdown"

**Cause:** In bound loop mode, shutdown must happen while the event loop is still running. If the loop exits before `stop_and_drain()` completes, logs may be lost.

**Solution:** Ensure `await logger.stop_and_drain()` completes before your async framework shuts down.

### "Logger hangs during startup"

**Cause:** `_start_plugins_sync()` has a 5-second timeout. If a plugin's `start()` method hangs, startup will timeout.

**Solution:** Check plugin implementations. The logger will continue with unstarted plugins (fail-open).

### "asyncio.run() raises 'loop already running'"

**Cause:** Calling sync fapilog APIs from within an async context where someone used `asyncio.run()` instead of the proper detection pattern.

**Solution:** This is handled automatically by fapilog. If you see this error, it's likely in user code - use `await` instead of `asyncio.run()`.

### "Events dropped despite drop_on_full=False"

**Cause:** When `SyncLoggerFacade._enqueue()` is called from the same thread as the worker loop (bound loop mode), events are dropped immediately if the queue is full—regardless of the `drop_on_full` setting.

**Why:** Blocking on the same thread would cause a deadlock. The thread cannot wait on its own event loop to drain the queue.

**Diagnostic:** A warning is emitted with `drop_on_full=False cannot be honored in same-thread context`.

**Solution:** Use `AsyncLoggerFacade` in async contexts. The async facade avoids the same-thread issue entirely by integrating directly with the event loop via `await`.

See also: [Reliability Defaults - Same-thread context behavior](../user-guide/reliability-defaults.md#same-thread-context-behavior)

## Design Principles

1. **Fail-open for logging:** If plugin startup fails, continue with unstarted plugins. Logging should never crash the application.

2. **Detect, don't assume:** Always use `get_running_loop()` to detect context rather than assuming based on the call site.

3. **Minimize thread creation:** Only create worker threads when necessary (sync context). Reuse the caller's loop when available.

4. **Timeouts everywhere:** All cross-thread operations have timeouts to prevent deadlocks.
