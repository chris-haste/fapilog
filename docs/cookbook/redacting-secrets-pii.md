# Redacting secrets and PII in FastAPI logs (Authorization, tokens, fields)

Sensitive data in logs is a security and compliance risk. Authorization headers, API tokens, passwords, and personal data regularly leak into logs. fapilog provides built-in redaction with sensible defaults and extensible patterns.

## Safe by Default

fapilog redacts URL credentials automatically—no configuration required:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging(preset="fastapi")
app = FastAPI(lifespan=lifespan)
```

With this setup, URLs containing credentials are automatically scrubbed:

```python
# What you log
await logger.info("Connecting to database", url="postgres://admin:secret123@db.example.com/mydb")

# What appears in logs
{"message": "Connecting to database", "url": "postgres://db.example.com/mydb"}
```

The `url_credentials` redactor is enabled by default and strips `user:pass@` from any URL-like strings.

## What Gets Redacted by Default

fapilog ships with three built-in redactors:

| Redactor | Enabled by Default | What It Does |
|----------|-------------------|--------------|
| `url_credentials` | Yes | Strips `user:pass@` from URLs |
| `field_mask` | No (Yes with preset) | Masks specific field names |
| `regex_mask` | No (Yes with preset) | Masks fields matching regex patterns |

The default configuration prioritizes safety without being overly aggressive. URL credentials are the most common accidental leak, so they're handled automatically.

### Full Protection with Presets

The `production`, `fastapi`, and `serverless` presets automatically apply the `CREDENTIALS` redaction preset, which masks:

- Passwords: `password`, `passwd`, `pwd`
- API keys: `api_key`, `apikey`, `api_token`
- Tokens: `token`, `access_token`, `refresh_token`, `auth_token`
- Secrets: `secret`, `api_secret`, `client_secret`, `private_key`
- Auth headers: `authorization`, `auth_header`

## Adding Field-Based Redaction

To redact specific fields by name, use `with_redaction()`:

```python
from fapilog import LoggerBuilder

logger = await (
    LoggerBuilder()
    .with_redaction(
        fields=["password", "ssn", "credit_card", "user.api_key"],
        mask="[REDACTED]",
    )
    .build_async()
)

# What you log
await logger.info("User signup", password="hunter2", email="user@example.com")

# What appears in logs
{"message": "User signup", "password": "[REDACTED]", "email": "user@example.com"}
```

### Auto-Prefix Behavior

By default, simple field names (without dots) are automatically prefixed with `data.` to match the log envelope structure:

```python
# These are equivalent:
.with_redaction(fields=["password"])           # Auto-prefixed to data.password
.with_redaction(fields=["data.password"], auto_prefix=False)
```

To disable auto-prefixing:

```python
.with_redaction(fields=["password"], auto_prefix=False)
```

### Nested Field Paths

Field paths support dot notation for nested objects:

```python
logger = await (
    LoggerBuilder()
    .with_redaction(fields=["user.password", "config.api_key"], auto_prefix=False)
    .build_async()
)

await logger.info(
    "Config loaded",
    user={"name": "alice", "password": "secret"},
    config={"api_key": "sk-123", "timeout": 30},
)
# user.password and config.api_key are masked; other fields preserved
```

## Adding Pattern-Based Redaction

For dynamic field names or broader matching, use regex patterns:

```python
logger = await (
    LoggerBuilder()
    .with_redaction(
        patterns=[
            r"(?i).*password.*",     # Any field containing "password"
            r"(?i).*secret.*",       # Any field containing "secret"
            r"(?i).*token.*",        # Any field containing "token"
            r"(?i)context\.auth.*",  # Auth fields in context
        ]
    )
    .build_async()
)
```

Patterns match against the full dot-path of fields (e.g., `context.auth_token`), not field values.

## Using Compliance Presets

For regulation compliance, use built-in redaction presets:

```python
from fapilog import LoggerBuilder

# GDPR compliance
logger = await (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .build_async()
)

# HIPAA compliance
logger = await (
    LoggerBuilder()
    .with_redaction(preset="HIPAA_PHI")
    .build_async()
)

# Multiple regulations
logger = await (
    LoggerBuilder()
    .with_redaction(preset=["GDPR_PII", "PCI_DSS"])
    .build_async()
)
```

Available presets:
- `GDPR_PII` - EU GDPR personal data
- `GDPR_PII_UK` - UK GDPR (includes NHS numbers, NI numbers)
- `CCPA_PII` - California Consumer Privacy Act
- `HIPAA_PHI` - HIPAA Protected Health Information
- `PCI_DSS` - Payment card data
- `CREDENTIALS` - Authentication secrets

### Discovering Presets

```python
from fapilog import LoggerBuilder

# List all available presets
presets = LoggerBuilder.list_redaction_presets()
print(presets)  # ['CCPA_PII', 'CREDENTIALS', 'GDPR_PII', ...]

# Get preset details
info = LoggerBuilder.get_redaction_preset_info("GDPR_PII")
print(info["description"])  # "GDPR Article 4 personal data identifiers"
print(info["fields"][:5])   # ['email', 'phone', 'name', ...]
```

## Combining Presets with Custom Fields

Presets and custom fields are additive:

```python
logger = await (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["internal_user_id", "employee_badge"])
    .build_async()
)
```

## Configuration via Settings

You can also configure redaction through Settings:

```python
from fapilog import Settings

settings = Settings()

# Enable specific redactors
settings.core.redactors = ["field_mask", "regex_mask", "url_credentials"]

# Configure field_mask
settings.redactor_config.field_mask.fields_to_mask = [
    "password",
    "authorization",
    "api_key",
]
settings.redactor_config.field_mask.mask_string = "[REDACTED]"

# Configure regex_mask
settings.redactor_config.regex_mask.patterns = [
    r"(?i).*secret.*",
    r"(?i).*token.*",
]
```

Or via environment variables:

```bash
export FAPILOG_CORE__REDACTORS='["field_mask", "url_credentials"]'
export FAPILOG_REDACTOR_CONFIG__FIELD_MASK__FIELDS_TO_MASK='["password", "ssn"]'
```

## Testing Your Redaction Rules

Verify that sensitive data is actually redacted before deploying:

```python
import pytest
from fapilog import LoggerBuilder
from fapilog.testing import capture_logs


@pytest.mark.asyncio
async def test_password_is_redacted():
    """Verify password fields are masked in log output."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(fields=["password"])
            .build_async()
        )
        await logger.info("Login attempt", username="alice", password="hunter2")

    # Password value should not appear
    assert "hunter2" not in logs.text
    # Mask should appear instead
    assert "***" in logs.text or "[REDACTED]" in logs.text


@pytest.mark.asyncio
async def test_ssn_pattern_redacted():
    """Verify SSN-like fields are caught by regex pattern."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(patterns=[r"(?i).*ssn.*"])
            .build_async()
        )
        await logger.info("User data", user_ssn="123-45-6789")

    assert "123-45-6789" not in logs.text


@pytest.mark.asyncio
async def test_url_credentials_stripped():
    """Verify URL credentials are removed by default."""
    async with capture_logs() as logs:
        logger = await LoggerBuilder().build_async()
        await logger.info(
            "Database URL",
            url="postgres://admin:supersecret@db.example.com/app",
        )

    # Credentials should be stripped
    assert "supersecret" not in logs.text
    assert "admin:" not in logs.text
    # Host should remain
    assert "db.example.com" in logs.text
```

### CI/CD Redaction Verification

Add a test that fails if sensitive patterns appear in logs:

```python
FORBIDDEN_PATTERNS = [
    r"\b[A-Za-z0-9]{32,}\b",  # Long tokens
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN format
    r"password\s*[:=]\s*\S+",  # password=value
]


@pytest.mark.asyncio
async def test_no_sensitive_patterns_in_logs():
    """Fail if any forbidden pattern appears in log output."""
    import re

    async with capture_logs() as logs:
        # Run your application code here
        pass

    for pattern in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, logs.text, re.IGNORECASE)
        assert not matches, f"Sensitive pattern found: {pattern} -> {matches}"
```

## Auditing What Gets Redacted

To see what redaction is happening, enable diagnostics:

```python
from fapilog import LoggerBuilder

logger = await (
    LoggerBuilder()
    .with_redaction(fields=["password"])
    .with_diagnostics(enabled=True)
    .build_async()
)
```

Diagnostics will log warnings if redaction encounters issues (max depth exceeded, unredactable fields, etc.).

## Performance Guardrails

Redactors have built-in limits to prevent performance issues with deeply nested or large objects:

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_depth` | 16 | Maximum nesting level to traverse |
| `max_keys_scanned` | 1000 | Maximum keys to examine |

Configure these via `with_redaction()`:

```python
logger = await (
    LoggerBuilder()
    .with_redaction(fields=["password"], max_depth=32, max_keys=5000)
    .build_async()
)
```

## Going Deeper

- [Redaction Presets](../redaction/presets.md) - Full preset documentation
- [Redaction Configuration](../redaction/configuration.md) - Complete redaction configuration
- [Configuration Reference](../user-guide/configuration.md) - All settings options
