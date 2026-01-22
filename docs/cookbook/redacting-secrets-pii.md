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
| `field_mask` | No | Masks specific field names |
| `regex_mask` | No | Masks fields matching regex patterns |

The default configuration prioritizes safety without being overly aggressive. URL credentials are the most common accidental leak, so they're handled automatically.

### Fallback Protection

Even if no redactors are configured, fapilog's fallback stderr sink applies minimal redaction for these sensitive field names:

- `password`, `passwd`, `secret`, `token`
- `api_key`, `apikey`, `api_secret`, `apisecret`
- `authorization`, `auth`, `credential`, `credentials`
- `private_key`, `privatekey`, `access_token`, `refresh_token`

This ensures sensitive data doesn't leak to stderr even in error scenarios.

## Adding Field-Based Redaction

To redact specific fields by name, enable the `field_mask` redactor:

```python
from fapilog import LoggerBuilder

logger = await (
    LoggerBuilder()
    .with_field_mask(
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

### Nested Field Paths

Field paths support dot notation for nested objects:

```python
logger = await (
    LoggerBuilder()
    .with_field_mask(fields=["user.password", "config.api_key"])
    .build_async()
)

await logger.info(
    "Config loaded",
    user={"name": "alice", "password": "secret"},
    config={"api_key": "sk-123", "timeout": 30},
)
# user.password and config.api_key are masked; other fields preserved
```

### Wildcard Support

Use `*` to match all keys at a level:

```python
logger = await (
    LoggerBuilder()
    .with_field_mask(fields=["headers.*", "users[*].password"])
    .build_async()
)
```

## Adding Pattern-Based Redaction

For dynamic field names or broader matching, use regex patterns:

```python
logger = await (
    LoggerBuilder()
    .with_regex_mask(
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

## Combining Multiple Redactors

Redactors run in sequence. Combine them for layered protection:

```python
logger = await (
    LoggerBuilder()
    # Exact field names you know about
    .with_field_mask(fields=["password", "ssn", "credit_card"])
    # Catch-all patterns for fields you might have missed
    .with_regex_mask(patterns=[r"(?i).*secret.*", r"(?i).*key.*"])
    # URL credentials (enabled by default, but explicit here)
    .with_url_credential_redaction()
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
            .with_field_mask(fields=["password"])
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
            .with_regex_mask(patterns=[r"(?i).*ssn.*"])
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
    .with_field_mask(fields=["password"])
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

Configure these if you have deeply nested structures:

```python
logger = await (
    LoggerBuilder()
    .with_field_mask(fields=["password"], max_depth=32, max_keys=5000)
    .build_async()
)
```

Or globally:

```python
logger = await (
    LoggerBuilder()
    .with_redaction_guardrails(max_depth=32, max_keys=10000)
    .build_async()
)
```

## Going Deeper

- [Configuration Reference](../user-guide/configuration.md) - All redaction settings
- [Testing Guide](../user-guide/testing.md) - More testing patterns
