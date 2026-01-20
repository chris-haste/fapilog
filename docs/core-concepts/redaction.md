# Redaction

Mask sensitive data before it reaches sinks.

## Quick Start: Enable Full Redaction

Use the `production` or `fastapi` preset for automatic redaction of passwords, API keys, tokens, and other sensitive fields:

```python
from fapilog import get_logger

# Full redaction enabled: passwords, tokens, API keys masked automatically
logger = get_logger(preset="production")
logger.info("User login", password="secret123")  # password auto-redacted
```

Without a preset, only URL credentials are stripped by default (e.g., `user:pass@host` becomes `***:***@host`).

## Built-in redactors

| Redactor | What it masks | Default |
|----------|---------------|---------|
| **url-credentials** | `user:pass@` in URL strings | Yes |
| **field-mask** | Configured fields (password, api_key, etc.) | Preset only |
| **regex-mask** | Values matching sensitive patterns | Preset only |

## Default behavior

By default (no preset), only `url-credentials` is active:

```python
logger = get_logger()  # Only URL credential stripping
logger.info("Connecting", url="https://user:pass@api.example.com")
# url becomes: https://***:***@api.example.com

logger.info("Login", password="secret")  # NOT redacted without preset!
```

## Full redaction with presets

The `production` and `fastapi` presets enable all three redactors with sensible defaults:

```python
logger = get_logger(preset="production")
logger.info("Auth", password="secret", api_key="sk-123")
# Both fields redacted: password="[REDACTED]", api_key="[REDACTED]"
```

Fields masked by `production`/`fastapi` presets:
- password, api_key, token, secret
- authorization, api_secret, private_key
- ssn, credit_card

## Manual configuration

Enable full redaction without a preset:

### Using the Builder API

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_redaction(fields=["password", "api_key", "ssn"])
    .with_redaction(patterns=["secret.*", "token.*"])
    .build()
)
logger.info("Login", password="secret123")  # password=[REDACTED]
```

### Using Environment Variables

```bash
export FAPILOG_CORE__REDACTORS='["field_mask","regex_mask","url_credentials"]'
export FAPILOG_CORE__SENSITIVE_FIELDS_POLICY=password,api_key,secret,token
```

### Using Settings

```python
from fapilog import get_logger, Settings

settings = Settings(
    core={
        "redactors": ["field_mask", "regex_mask", "url_credentials"],
        "sensitive_fields_policy": ["password", "api_key", "secret"],
    }
)
logger = get_logger(settings=settings)
```

## Guardrails

Limit traversal depth for performance:

```bash
export FAPILOG_CORE__REDACTION_MAX_DEPTH=8
export FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED=5000
```

## Usage notes

- Redactors run after enrichment, before sinks
- Order is deterministic: field-mask → regex-mask → url-credentials
- Disabling redactors allows sensitive fields to reach sinks unmasked

See also: [plugins/redactors](../plugins/redactors.md) for implementation details.
