# Redaction Behavior

This page documents exactly what fapilog redacts, how the pipeline works, and known limitations.

> **Disclaimer:** Redaction is provided as a best-effort mechanism to help protect sensitive data. It matches field names and patterns, not arbitrary field content. You are responsible for testing and verifying redaction meets your compliance requirements before production use. Fapilog and its maintainers accept no liability for data exposure.

```{important}
**Redaction Failure Behavior**

By default (`redaction_fail_mode="warn"`), if the redaction pipeline encounters an unexpected error, the original log event passes through and a diagnostic warning is emitted. For high-security systems handling sensitive data:

- `"closed"` (high-security): Drop the event entirely rather than risk data exposure
- `"open"` (debugging only): Pass event through silently without warning

Configure via builder:
   ```python
   logger = LoggerBuilder().with_fallback_redaction(fail_mode="closed").build()
   ```

Or via settings:
   ```python
   Settings(core=CoreSettings(redaction_fail_mode="closed"))
   ```

See [Reliability Defaults](../user-guide/reliability-defaults.md) for related production settings.
```

## What Gets Redacted

### Field Mask Redactor

Masks specific field paths under `data.*`. With production/fastapi/serverless presets, the `CREDENTIALS` preset fields are masked:

| Field Pattern | Examples |
|---------------|----------|
| Passwords | `data.password`, `data.passwd`, `data.pwd` |
| Secrets | `data.secret`, `data.api_secret`, `data.client_secret` |
| Tokens | `data.token`, `data.access_token`, `data.refresh_token` |
| API Keys | `data.api_key`, `data.apikey`, `data.api_token` |
| Private Keys | `data.private_key`, `data.secret_key`, `data.signing_key` |
| Auth Headers | `data.authorization`, `data.auth_header` |
| Sessions | `data.session_id`, `data.session_token` |
| OTP Codes | `data.otp`, `data.mfa_code`, `data.verification_code` |

**Example:**
```python
# Input
{"data": {"password": "hunter2", "user": "alice"}}

# Output
{"data": {"password": "***", "user": "alice"}}
```

### Regex Mask Redactor

Matches any field path (at any nesting level) containing sensitive keywords:

| Pattern | Matches |
|---------|---------|
| `.*password.*` | `user.password`, `auth.password_hash`, etc. |
| `.*passwd.*` | `old_passwd`, `metadata.passwd`, etc. |
| `.*secret.*` | `client_secret`, `secret_key`, etc. |
| `.*token.*` | `access_token`, `refresh_token`, etc. |
| `.*api.?key.*` | `api_key`, `apikey`, `api-key`, etc. |
| `.*private.?key.*` | `private_key`, `privatekey`, etc. |
| `.*auth.*` | `authorization`, `auth_header`, etc. |
| `.*otp.*` | `otp`, `totp_code`, etc. |

All patterns are case-insensitive.

**Example:**
```python
# Input (field path: request.body.user_password)
{"request": {"body": {"user_password": "secret123"}}}

# Output
{"request": {"body": {"user_password": "***"}}}
```

### URL Credentials Redactor

Strips userinfo (username:password) from URLs in string values:

**Example:**
```python
# Input
{"endpoint": "https://user:pass@api.example.com/v1"}

# Output
{"endpoint": "https://***:***@api.example.com/v1"}
```

## What Does NOT Get Redacted

### PII in Message Strings

```python
# ❌ NOT redacted - PII in message
logger.info(f"User email: {email}")
# Output: {"message": "User email: john@example.com"}

# ✅ Redacted - PII in named field
logger.info("User", email=email)
# Output: {"data": {"email": "***"}}
```

### Arbitrarily-Named Fields

```python
# ❌ NOT redacted - field name doesn't match
logger.info("Contact", customer_contact="john@example.com")
# Output: {"data": {"customer_contact": "john@example.com"}}

# ✅ Redacted - recognized field name
logger.info("Contact", email="john@example.com")
# Output: {"data": {"email": "***"}}
```

### Serialized JSON Strings

```python
# ❌ NOT redacted - JSON as string
payload = '{"email": "john@example.com"}'
logger.info("Data", payload=payload)
# Output: {"data": {"payload": "{\"email\": \"john@example.com\"}"}}

# ✅ Redacted - pass as dict
logger.info("Data", email="john@example.com")
# Output: {"data": {"email": "***"}}
```

## Pipeline Order

Redaction runs in the logger worker loop before envelope serialization:

```
Log Event → Enrichers → Redactors → Serialization → Sinks
```

Redactors execute in order:
1. **field_mask** - Exact path matching first
2. **regex_mask** - Pattern matching second
3. **url_credentials** - URL sanitization last

This order ensures explicit masking takes precedence, followed by broader patterns, then URL cleanup.

(guardrails)=
## Guardrails

Redaction includes safety limits to prevent performance issues with deeply nested or large objects. There are two levels of guardrails: **core pipeline guardrails** that apply globally, and **per-redactor guardrails** that each redactor can configure.

### Core Pipeline Guardrails

These settings apply as outer limits across all redactors:

| Setting | Default | Purpose |
|---------|---------|---------|
| `core.redaction_max_depth` | 6 | Maximum nesting level for all redactors |
| `core.redaction_max_keys_scanned` | 5000 | Maximum keys scanned across all redactors |

Configure via builder:
```python
logger = (
    LoggerBuilder()
    .with_core(redaction_max_depth=8, redaction_max_keys_scanned=10000)
    .build()
)
```

Or via settings:
```python
Settings(core=CoreSettings(redaction_max_depth=8, redaction_max_keys_scanned=10000))
```

### Per-Redactor Guardrails

Each redactor has its own guardrails (used when less restrictive than core):

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_depth` | 16 | Per-redactor traversal limit |
| `max_keys_scanned` | 1000 | Per-redactor key limit |

Configure via builder:
```python
logger = (
    LoggerBuilder()
    .with_redaction(fields=["password"], max_depth=32, max_keys=5000)
    .build()
)
```

### Guardrail Precedence

The **more restrictive** value always applies:

| Core Setting | Plugin Setting | Effective Value |
|--------------|----------------|-----------------|
| `max_depth=6` | `max_depth=16` | 6 (core wins) |
| `max_depth=20` | `max_depth=5` | 5 (plugin wins) |
| `max_depth=None` | `max_depth=16` | 16 (plugin default) |

This ensures that core guardrails act as hard limits that cannot be exceeded by individual redactor configurations.

### Guardrail Behavior (`on_guardrail_exceeded`)

The FieldMaskRedactor supports configurable behavior when guardrails are exceeded via the `on_guardrail_exceeded` option:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `"warn"` | Emit diagnostic, continue with partial redaction | Development, debugging |
| `"drop"` | Emit diagnostic, drop the entire event | High-security compliance |
| `"replace_subtree"` (default) | Emit diagnostic, replace unscanned subtree with mask | Balanced security/availability |

To opt into fail-open behavior for debugging:
```python
from fapilog.plugins.redactors.field_mask import FieldMaskConfig

Settings(
    redactor_config=RedactorConfig(
        field_mask=FieldMaskConfig(
            fields_to_mask=["password"],
            max_depth=4,
            on_guardrail_exceeded="warn",  # Fail-open for debugging
        )
    )
)
```

**Trade-offs:**

| Mode | Security | Availability | Data Loss |
|------|----------|--------------|-----------|
| `"warn"` | Low (unredacted data may leak) | High (events pass through) | None |
| `"drop"` | High (no unredacted data) | Low (events dropped) | Full event |
| `"replace_subtree"` | Medium (subtree masked) | Medium (event preserved) | Subtree only |

**Example with `replace_subtree`:**

```python
# Event with depth exceeding max_depth=2
event = {"level1": {"level2": {"level3": {"password": "secret"}}}}

# Result: unscanned subtree replaced with mask
{"level1": {"level2": "***"}}
```

## Failure Handling

Fapilog provides multiple layers of redaction failure protection:

### Redaction Settings Relationship

| Setting | Scope | Purpose | Default |
|---------|-------|---------|---------|
| `redactor_config.field_mask.block_on_unredactable` | Per-redactor | Drop event when redactor can't process a value | `True` |
| `redactor_config.field_mask.on_guardrail_exceeded` | Per-redactor | Behavior when depth/keys guardrails hit | `"replace_subtree"` |
| `core.fallback_redact_mode` | Fallback sink | How to redact payloads on stderr fallback | `"minimal"` |
| `core.redaction_fail_mode` | Global pipeline | What to do when `_apply_redactors()` throws | `"warn"` |

All redaction settings default to **fail-closed** behavior to prevent PII leakage. To opt into fail-open behavior for debugging, explicitly set:
- `block_on_unredactable=False`
- `on_guardrail_exceeded="warn"`
- `redaction_fail_mode="open"`

### Per-Redactor Behavior (`block_on_unredactable`)

Individual redactors can block on unparseable values:
```python
.with_redaction(fields=["password"], block_on_unredactable=True)
```

When a redactor encounters a value it cannot process:
- `True` (default): Log event is dropped, diagnostic warning emitted
- `False`: Original value preserved, diagnostic warning emitted

### Global Pipeline Behavior (`redaction_fail_mode`)

Controls what happens when the entire redaction pipeline fails unexpectedly:

```python
# Production/FastAPI/Serverless presets default to "warn"
Settings(preset="production")  # redaction_fail_mode="warn"

# Explicit configuration
Settings(core=CoreSettings(redaction_fail_mode="closed"))
```

| Mode | Behavior | Use Case |
|------|----------|----------|
| `"open"` | Pass original event through | Development, debugging |
| `"warn"` | Pass event through + emit diagnostic | Production (default) |
| `"closed"` | Drop event entirely | High-security compliance |

### Fallback Redaction (`fallback_redact_mode`)

When a sink fails and falls back to stderr, this controls redaction:

| Mode | Behavior |
|------|----------|
| `"minimal"` | Apply built-in sensitive field masking (default) |
| `"inherit"` | Use pipeline redactors (requires pipeline context) |
| `"none"` | No redaction (opt-in to legacy behavior, emits warning) |

For serialized payloads, `"minimal"` mode deserializes, redacts, and re-serializes. If JSON parsing fails, raw output is written with a diagnostic warning.

## Nested Objects and Arrays

Redaction traverses nested structures:

```python
# Nested objects - redacted
{"user": {"profile": {"email": "x@y.com"}}}
# → {"user": {"profile": {"email": "***"}}}

# Arrays - each element checked
{"users": [{"email": "a@b.com"}, {"email": "c@d.com"}]}
# → {"users": [{"email": "***"}, {"email": "***"}]}
```

Wildcard patterns in field paths:
```python
.with_redaction(fields=["users[*].email"])  # All emails in users array
.with_redaction(fields=["data.*.secret"])   # Any secret under data
```

## Deterministic Behavior

For the same input and configuration:
- Redaction is deterministic
- Field order is preserved
- Mask string is consistent

This ensures logs are predictable and testable.

## Related

- [Presets Reference](presets.md) - Complete field lists
- [Configuration](configuration.md) - How to configure
- [Testing](testing.md) - Verify redaction in CI
- [Compliance Cookbook](../cookbook/compliance-redaction.md) - What works and what doesn't
