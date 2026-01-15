# Pipeline Stage Ordering

Internal architecture documentation for fapilog's log event processing pipeline.

## Overview

Log events flow through a fixed sequence of processing stages in `LoggerWorker._flush_batch()`. The ordering is intentional and cannot be changed without breaking data flow guarantees.

```
┌──────────┐   ┌───────────┐   ┌───────────┐   ┌────────────┐   ┌──────┐
│ FILTERS  │──▶│ ENRICHERS │──▶│ REDACTORS │──▶│ PROCESSORS │──▶│ SINK │
└──────────┘   └───────────┘   └───────────┘   └────────────┘   └──────┘
     1              2               3               4              5
```

## Stage Details

### Stage 1: Filters

**Purpose:** Drop unwanted events before any processing cost is incurred.

**Input:** Raw event dict from queue
**Output:** Event dict (pass) or `None` (drop)

**Why first?**
- Avoids wasting cycles on events that will be discarded
- Filters see the original event before any transformation
- Level filtering, sampling, and rate limiting happen here

**Error handling:** On error, original event passes through (fail-safe).

**Implementation:** `LoggerWorker._apply_filters()` → `filter_in_order()`

### Stage 2: Enrichers

**Purpose:** Add contextual metadata to events.

**Input:** Filtered event dict
**Output:** Enriched event dict

**Why after filters?**
- Dropped events don't waste enrichment cycles
- Enrichers may perform expensive operations (runtime info, external lookups)

**Error handling:** On error, original event passes through (fail-safe).

**Implementation:** `LoggerWorker._apply_enrichers()` → `enrich_parallel()`

### Stage 3: Redactors

**Purpose:** Mask sensitive data before output.

**Input:** Enriched event dict
**Output:** Redacted event dict

**Why after enrichers?**
- Redactors must see enriched fields to mask them
- Example: Request context enricher adds `user_email`, redactor masks it
- If redactors ran before enrichers, sensitive enriched data would leak

**Error handling:** On error, original event passes through (fail-safe).

**Implementation:** `LoggerWorker._apply_redactors()` → `redact_in_order()`

### Stage 4: Processors

**Purpose:** Transform serialized bytes before sink write.

**Input:** `SerializedView` (memoryview of JSON bytes)
**Output:** Transformed `SerializedView`

**Why after redaction?**
- Operates on final, redacted payload
- Common uses: compression, encryption, batching

**Conditional:** Only runs when `serialize_in_flush` is enabled and sink supports serialized writes.

**Error handling:** On error, original view preserved (fail-safe).

**Implementation:** `LoggerWorker._apply_processors()`

### Stage 5: Sink

**Purpose:** Write event to destination.

**Input:** Event dict or `SerializedView`
**Output:** None (side effect: write to destination)

**Error handling:**
- Errors logged via diagnostics system
- Event dropped on sink failure
- Counter incremented for dropped events

**Implementation:** `sink.write()` or `sink.write_serialized()`

## Error Handling Summary

| Stage | On Error | Rationale |
|-------|----------|-----------|
| Filters | Pass through | Don't drop events due to filter bugs |
| Enrichers | Pass through | Missing metadata is better than lost events |
| Redactors | Pass through | Risky, but losing events is worse |
| Processors | Preserve original | Uncompressed data is still valid |
| Sink | Drop + log | Can't write = can't deliver |

## Key Invariants

1. **Stage order is fixed** - Changing order breaks data flow guarantees
2. **Stages 1-4 are fail-safe** - Errors don't drop events
3. **Redactors always see enriched data** - Security guarantee
4. **Processors see redacted data** - No sensitive data in compressed output

## Code Reference

See: `src/fapilog/core/worker.py:_flush_batch()`

## Related Documentation

- [Pipeline Architecture](../core-concepts/pipeline-architecture.md) - User-facing conceptual overview
- [Batching & Backpressure](../core-concepts/batching-backpressure.md) - Queue behavior
