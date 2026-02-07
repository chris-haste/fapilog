# Redactors

Redactors transform structured log events to remove or mask sensitive data before serialization and sink emission. The Redactors stage executes after Enrichers and before Sinks, preserving the async-first, non-blocking guarantees of the runtime pipeline.

!!! warning "PII in Message Strings Is Not Redacted"

    Redactors only process **structured fields** in the log envelope.
    PII embedded in the message string will pass through unchanged.

    ```python
    # UNSAFE - email will NOT be redacted
    logger.info(f"User {email} logged in")
    logger.info("User " + email + " logged in")

    # SAFE - email field will be redacted
    logger.info("User logged in", email=email)
    logger.info("User logged in", user={"email": email})
    ```

    See [PII Showing Despite Redaction](../troubleshooting/pii-showing-despite-redaction.md)
    for more details.

## Stage Placement and Lifecycle

- Runs in the logger worker loop; no new threads or loops are created
- Sequential, deterministic application in configured order
- Errors are contained; events are not dropped due to redaction errors
- Each redactor supports optional async `start`/`stop` lifecycle

## Built-in Redactors

Fapilog ships with five built-in redactors. The first three are the core masking layer; the last two provide policy enforcement and size control.

### FieldMaskRedactor

Masks selected fields identified by dotted paths across nested dicts and lists.

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

### RegexMaskRedactor

Matches field paths at any nesting level against regex patterns. All patterns are validated at config time to prevent ReDoS (see [Regex Pattern Safety](../redaction/configuration.md#regex-pattern-safety)).

```python
from fapilog.plugins.redactors.regex_mask import RegexMaskRedactor, RegexMaskConfig

redactor = RegexMaskRedactor(
    config=RegexMaskConfig(
        patterns=[
            r"(?i).*password.*",
            r"(?i).*secret.*",
            r"(?i).*token.*",
        ],
        mask_string="***",
        block_on_unredactable=False,
    )
)
```

### UrlCredentialsRedactor

Strips `user:password@` credentials from URL-like strings found in any field value. Enabled by default (no preset required).

```python
from fapilog.plugins.redactors.url_credentials import (
    UrlCredentialsRedactor,
    UrlCredentialsConfig,
)

redactor = UrlCredentialsRedactor(
    config=UrlCredentialsConfig(
        max_string_length=4096,  # Max URL length to scan
    )
)
```

(fieldblockerredactor)=
### FieldBlockerRedactor

Blocks high-risk field names (e.g., `body`, `payload`, `raw`) by replacing their values entirely. Designed to catch accidental logging of request/response bodies. Enabled by default in the `hardened` preset.

```python
from fapilog.plugins.redactors.field_blocker import (
    FieldBlockerRedactor,
    FieldBlockerConfig,
)

redactor = FieldBlockerRedactor(
    config=FieldBlockerConfig(
        blocked_fields=["body", "request_body", "response_body", "payload"],
        allowed_fields=[],          # Exemptions from the blocklist
        replacement="[REDACTED:HIGH_RISK_FIELD]",
    )
)
```

Builder API shortcut:

```python
logger = LoggerBuilder().with_redaction(block_fields=["body", "payload"]).build()
```

Each blocked field emits a policy-violation diagnostic. Monitor violations with the `fapilog_policy_violations_total` metric (see [Redaction Metrics](../core-concepts/metrics.md#redaction-metrics)).

(stringtruncateredactor)=
### StringTruncateRedactor

Truncates string values exceeding a configured length and appends a `[truncated]` marker. Disabled by default (`max_string_length=None` means no traversal). Useful for preventing oversized log events from body dumps or stack traces.

```python
from fapilog.plugins.redactors.string_truncate import (
    StringTruncateRedactor,
    StringTruncateConfig,
)

redactor = StringTruncateRedactor(
    config=StringTruncateConfig(
        max_string_length=1000,  # None = disabled (default)
    )
)
```

Builder API shortcut:

```python
logger = LoggerBuilder().with_redaction(max_string_length=1000).build()
```

## Configuration

Core settings include:

- `core.enable_redactors`: enable/disable the stage
- `core.redactors_order`: ordered list of redactor plugin names
- `core.redaction_max_depth`, `core.redaction_max_keys_scanned`: guardrail plumbing used by redactors

### FieldMaskRedactor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `fields_to_mask` | `list[str]` | `[]` | Dotted field paths to mask |
| `mask_string` | `str` | `"***"` | Replacement string |
| `block_on_unredactable` | `bool` | `False` | Drop event if a value can't be processed |
| `max_depth` | `int` | `16` | Per-redactor traversal depth limit |
| `max_keys_scanned` | `int` | `1000` | Per-redactor key scan limit |
| `on_guardrail_exceeded` | `str` | `"replace_subtree"` | `"warn"`, `"drop"`, or `"replace_subtree"` |

### RegexMaskRedactor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `patterns` | `list[str]` | `[]` | Regex patterns matched against field paths |
| `mask_string` | `str` | `"***"` | Replacement string |
| `block_on_unredactable` | `bool` | `False` | Drop event if a value can't be processed |
| `allow_unsafe_patterns` | `bool` | `False` | Bypass ReDoS validation |

### UrlCredentialsRedactor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_string_length` | `int` | `4096` | Max URL length to scan |

### FieldBlockerRedactor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `blocked_fields` | `list[str]` | `["body", "request_body", ...]` | Field names to block (case-insensitive) |
| `allowed_fields` | `list[str]` | `[]` | Exemptions from the blocklist |
| `replacement` | `str` | `"[REDACTED:HIGH_RISK_FIELD]"` | Replacement string |
| `max_depth` | `int` | `16` | Per-redactor traversal depth limit |
| `max_keys_scanned` | `int` | `1000` | Per-redactor key scan limit |
| `on_guardrail_exceeded` | `str` | `"warn"` | `"warn"` or `"drop"` only |

### StringTruncateRedactor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_string_length` | `int \| None` | `None` | Max string length; `None` disables the redactor |
| `max_depth` | `int` | `16` | Per-redactor traversal depth limit |
| `max_keys_scanned` | `int` | `1000` | Per-redactor key scan limit |
| `on_guardrail_exceeded` | `str` | `"warn"` | `"warn"` or `"drop"` only |

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
- Redaction operational metrics (`fapilog_redacted_fields_total`, `fapilog_policy_violations_total`, etc.) are recorded automatically — see [Redaction Metrics](../core-concepts/metrics.md#redaction-metrics)

## Integration Order

At runtime the effective order is: Enricher → Redactor → Processor → Sink.
Redaction occurs pre-serialization. See [Redaction Behavior](../redaction/behavior.md) for policy and guardrails.
