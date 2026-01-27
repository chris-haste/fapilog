# Redaction

```{toctree}
:maxdepth: 2
:hidden:

presets
configuration
behavior
testing
```

Keep passwords, API keys, PII, and other sensitive data out of your logs.

> **Disclaimer:** Redaction is provided as a best-effort mechanism to help protect sensitive data. It matches field names and patterns, not arbitrary field content. You are responsible for testing and verifying redaction meets your compliance requirements before production use. Fapilog and its maintainers accept no liability for data exposure resulting from misconfiguration, incomplete coverage, or reliance on redaction without adequate verification.

## Quick Start

```python
from fapilog import get_logger

# Production preset: auto-redacts passwords, API keys, tokens
logger = get_logger(preset="production")

logger.info("User login", password="secret123", api_key="sk-abc")
# Output: {"data": {"password": "***", "api_key": "***"}}
```

## Compliance Presets

One-liner protection for GDPR, HIPAA, PCI-DSS:

```python
from fapilog import LoggerBuilder

# GDPR compliance
logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# Multiple regulations
logger = LoggerBuilder().with_redaction(preset=["HIPAA_PHI", "PCI_DSS"]).build()
```

See [Presets Reference](presets.md) for complete field lists.

## Custom Redaction

```python
logger = (
    LoggerBuilder()
    .with_redaction(
        fields=["password", "ssn", "internal_id"],
        patterns=[r"(?i).*secret.*"],
    )
    .build()
)
```

See [Configuration](configuration.md) for all options.

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Field-name matching** | Redaction matches field names, not content. `email="x@y.com"` is redacted; `"Email: x@y.com"` in a message is not. |
| **Auto-prefix** | Simple field names like `"password"` are prefixed to `"data.password"` to match the log envelope. |
| **Additive** | Multiple `with_redaction()` calls merge fields/patterns. Use `replace=True` to overwrite. |
| **Pre-serialization** | Redaction happens before logs reach any sink (file, CloudWatch, etc.). |

## What Gets Redacted

| Scenario | Redacted? | Why |
|----------|-----------|-----|
| `email="john@example.com"` | ✅ Yes | Field name matches |
| `user={"email": "john@example.com"}` | ✅ Yes | Nested path matches |
| `f"User email: {email}"` | ❌ No | Content in message string |
| `notes="Call john@example.com"` | ❌ No | Field name `notes` doesn't match |

See [Behavior](behavior.md) for detailed coverage.

## Documentation

| Page | Description |
|------|-------------|
| [Presets Reference](presets.md) | Complete field lists for all compliance presets |
| [Configuration](configuration.md) | Builder API, Settings, environment variables |
| [Behavior](behavior.md) | What gets redacted, pipeline order, limitations |
| [Testing](testing.md) | How to verify redaction in CI |

## Cookbooks

- [Compliance Redaction](../cookbook/compliance-redaction.md) - What works and what doesn't
- [Redacting Secrets & PII](../cookbook/redacting-secrets-pii.md) - Practical examples
