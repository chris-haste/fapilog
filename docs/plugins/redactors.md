# Redactors

Redactors transform structured log events to remove or mask sensitive data before serialization and sink emission. The Redactors stage executes after Enrichers and before Sinks, preserving the async-first, non-blocking guarantees of the runtime pipeline.

## Stage Placement and Lifecycle

- Runs in the logger worker loop; no new threads or loops are created
- Sequential, deterministic application in configured order
- Errors are contained; events are not dropped due to redaction errors
- Each redactor supports optional async `start`/`stop` lifecycle

## Built-in Redactors

- FieldMaskRedactor: masks selected fields identified by dotted paths across nested dicts and lists.

Example:

```python
from fapilog.plugins.redactors.field_mask import FieldMaskRedactor, FieldMaskConfig

redactor = FieldMaskRedactor(
    config=FieldMaskConfig(
        fields_to_mask=[
            "user.password",
            "payment.card.number",
            "items.value",
        ],
        mask_string="***",
        block_on_unredactable=False,
        max_depth=16,
        max_keys_scanned=1000,
    )
)
```

## Configuration

Core settings include:

- `core.enable_redactors`: enable/disable the stage
- `core.redactors_order`: ordered list of redactor plugin names
- `core.redaction_max_depth`, `core.redaction_max_keys_scanned`: guardrail plumbing used by redactors

FieldMaskRedactor config:

- `fields_to_mask: list[str]`
- `mask_string: str` (default `***`)
- `block_on_unredactable: bool` (default `False`)
- `max_depth: int` (default `16`)
- `max_keys_scanned: int` (default `1000`)

## Authoring Custom Redactors

A custom redactor implements the `BaseRedactor` protocol with async methods and returns a new event mapping:

```python
from typing import Protocol

class BaseRedactor(Protocol):
    name: str
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def redact(self, event: dict) -> dict: ...
```

Register via entry points using the `fapilog.redactors` group in your package metadata.

## Diagnostics and Metrics

- Each redactor execution is timed via the shared plugin timer
- Failures are recorded in plugin error metrics (when metrics are enabled)
- Structured diagnostics are emitted via `core.diagnostics.warn` for guardrail or policy warnings

## Integration Order

At runtime the effective order is: Enricher → Redactor → Processor → Sink.
Redaction occurs pre-serialization. See also Redaction Guarantees for policy and guardrails: [docs/redaction-guarantees.md](../redaction-guarantees.md)
