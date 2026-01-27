# Testing Redaction

How to verify that sensitive data is actually redacted before deploying to production.

## Basic Verification

Use `capture_logs` to test redaction:

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
    assert "***" in logs.text
    # Non-sensitive data preserved
    assert "alice" in logs.text
```

## Testing Preset Coverage

Verify compliance presets cover expected fields:

```python
@pytest.mark.asyncio
async def test_gdpr_preset_redacts_email():
    """GDPR preset should redact email addresses."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .build_async()
        )
        await logger.info("User signup", email="test@example.com", name="John Doe")

    assert "test@example.com" not in logs.text
    assert "John Doe" not in logs.text  # name is also PII


@pytest.mark.asyncio
async def test_hipaa_preset_redacts_mrn():
    """HIPAA preset should redact medical record numbers."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="HIPAA_PHI")
            .build_async()
        )
        await logger.info("Patient visit", mrn="MRN-12345", ssn="123-45-6789")

    assert "MRN-12345" not in logs.text
    assert "123-45-6789" not in logs.text
```

## Testing Pattern Matching

Verify regex patterns catch variations:

```python
@pytest.mark.asyncio
async def test_pattern_catches_variations():
    """Pattern should catch password variations."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(patterns=[r"(?i).*password.*"])
            .build_async()
        )
        await logger.info(
            "Auth data",
            user_password="secret1",
            password_hash="abc123",
            old_passwd="secret2",
        )

    assert "secret1" not in logs.text
    assert "abc123" not in logs.text
    # Note: "passwd" doesn't match "password" pattern
    # Add separate pattern if needed
```

## Testing URL Credential Stripping

```python
@pytest.mark.asyncio
async def test_url_credentials_stripped():
    """URL credentials should be stripped by default."""
    async with capture_logs() as logs:
        logger = await LoggerBuilder().build_async()
        await logger.info(
            "Database connection",
            url="postgres://admin:supersecret@db.example.com/app",
        )

    # Credentials stripped
    assert "supersecret" not in logs.text
    assert "admin:" not in logs.text
    # Host preserved
    assert "db.example.com" in logs.text
```

## Testing Limitations

Document expected behavior for unsupported scenarios:

```python
@pytest.mark.asyncio
async def test_message_string_not_redacted():
    """PII in message string is NOT redacted - this is expected."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .build_async()
        )
        # WRONG way to log PII
        await logger.info("User email: test@example.com")

    # PII IS exposed - this test documents the limitation
    assert "test@example.com" in logs.text


@pytest.mark.asyncio
async def test_arbitrary_field_name_not_redacted():
    """Arbitrary field names are NOT redacted unless configured."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .build_async()
        )
        # Field name "customer_contact" not in GDPR preset
        await logger.info("Ticket", customer_contact="test@example.com")

    # NOT redacted - field name doesn't match
    assert "test@example.com" in logs.text
```

## CI/CD Verification

### Forbidden Patterns Test

Fail CI if sensitive patterns appear in logs:

```python
import re

FORBIDDEN_PATTERNS = [
    r"\b[A-Za-z0-9]{32,}\b",      # Long tokens
    r"\b\d{3}-\d{2}-\d{4}\b",     # SSN format
    r"password\s*[:=]\s*\S+",     # password=value
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # Email addresses
]


@pytest.mark.asyncio
async def test_no_sensitive_patterns_in_logs():
    """Fail if any forbidden pattern appears in log output."""
    async with capture_logs() as logs:
        # Run your application code here
        # ...
        pass

    for pattern in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, logs.text, re.IGNORECASE)
        assert not matches, f"Sensitive pattern found: {pattern} -> {matches}"
```

### Production Config Verification

Verify production configuration is correct:

```python
from fapilog import LoggerBuilder


def test_production_preset_enables_redaction():
    """Production preset should have all redactors enabled."""
    builder = LoggerBuilder().with_preset("production")
    config = builder._config

    # Verify redactors are configured
    assert "field_mask" in config.get("core", {}).get("redactors", [])
    assert "regex_mask" in config.get("core", {}).get("redactors", [])
    assert "url_credentials" in config.get("core", {}).get("redactors", [])
```

## Audit Testing

Generate evidence for compliance audits:

```python
from fapilog import LoggerBuilder


def test_gdpr_preset_field_coverage():
    """Document all fields covered by GDPR preset for audit."""
    info = LoggerBuilder.get_redaction_preset_info("GDPR_PII")

    # Verify required categories are covered
    fields = set(info["fields"])

    # Contact info
    assert "email" in fields
    assert "phone" in fields
    assert "address" in fields

    # Personal identifiers
    assert "name" in fields
    assert "dob" in fields

    # Online identifiers
    assert "ip_address" in fields
    assert "cookie_id" in fields

    # Print for audit documentation
    print(f"\nGDPR_PII covers {len(fields)} fields:")
    for field in sorted(fields):
        print(f"  - {field}")
```

## Integration Testing

Test redaction with actual sinks:

```python
import json
import tempfile
from pathlib import Path

import pytest
from fapilog import LoggerBuilder


@pytest.mark.asyncio
async def test_file_sink_receives_redacted_data():
    """Verify redacted data reaches file sink."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "app.log"

        logger = await (
            LoggerBuilder()
            .with_redaction(preset="CREDENTIALS")
            .add_file(directory=tmpdir, filename="app.log")
            .build_async()
        )

        await logger.info("Auth event", password="secret123", user="alice")
        await logger.shutdown()

        # Read and verify file contents
        content = log_file.read_text()
        log_entry = json.loads(content.strip())

        assert log_entry["data"]["password"] == "***"
        assert log_entry["data"]["user"] == "alice"
        assert "secret123" not in content
```

## Checklist

Before deploying:

- [ ] Test each preset you use covers expected fields
- [ ] Test custom fields are redacted
- [ ] Test patterns catch expected variations
- [ ] Document known limitations (message strings, arbitrary fields)
- [ ] Add forbidden pattern tests to CI
- [ ] Verify production config enables redaction
- [ ] Generate audit evidence for compliance

## Related

- [Presets Reference](presets.md) - Complete field lists
- [Behavior](behavior.md) - What gets redacted and when
- [Compliance Cookbook](../cookbook/compliance-redaction.md) - What works and what doesn't
