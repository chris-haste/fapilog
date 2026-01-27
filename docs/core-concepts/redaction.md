# Redaction

Keep passwords, API keys, and other secrets out of your logs—automatically.

## Quick Start: Enable Full Redaction

Use the `production` or `fastapi` preset for automatic redaction of passwords, API keys, tokens, and other sensitive fields:

```python
from fapilog import get_logger

# Full redaction enabled: passwords, tokens, API keys masked automatically
logger = get_logger(preset="production")
logger.info("User login", password="secret123")  # password auto-redacted
```

Without a preset, only URL credentials are stripped by default (e.g., `user:pass@host` becomes `***:***@host`).

## What gets redacted

| What | Example | When |
|------|---------|------|
| **Passwords in URLs** | `https://user:secret@api.com` → `https://***:***@api.com` | Always (default) |
| **Sensitive field names** | `password`, `api_key`, `token`, `secret`, `ssn`, `credit_card` | With `production`/`fastapi` preset |
| **Patterns you define** | Custom regex for company-specific secrets | Manual configuration |

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
# Both fields redacted: password="***", api_key="***"
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
logger.info("Login", password="secret123")  # password=***
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

## Important notes

- **Use a preset for production** - Without `production` or `fastapi` preset, only URL credentials are masked. Passwords and API keys in fields won't be redacted.
- **Redaction happens before sinks** - Secrets are masked before logs leave your application, so they never reach CloudWatch, files, or any destination.
- **Test your redaction** - Log a test event with sensitive fields and verify they're masked before deploying.

See also: [plugins/redactors](../plugins/redactors.md) for creating custom redactors.
