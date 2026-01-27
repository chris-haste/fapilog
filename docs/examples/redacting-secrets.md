# Redacting Secrets

Built-in redactors mask sensitive data. By default, only URL credentials are redacted. Use a preset for full protection.

## Default Behavior (URL Credentials Only)

```python
from fapilog import get_logger

logger = get_logger()

# URL credentials are stripped by default
logger.info("Connecting", url="https://user:secret@api.example.com")
# Output: url="https://***:***@api.example.com"

# Field values are NOT masked without a preset
logger.info("Login", password="secret123")
# Output: password="secret123" (not redacted!)
```

## Full Protection with Presets

Use `production`, `fastapi`, or `serverless` preset for automatic field masking:

```python
from fapilog import get_logger

logger = get_logger(preset="production")

logger.info(
    "User credentials",
    username="john",
    password="secret123",
    api_key="sk-abc",
)
```

Output (masked):

```json
{
  "message": "User credentials",
  "data": {
    "username": "john",
    "password": "***",
    "api_key": "***"
  }
}
```

## Custom Redaction with Builder

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_redaction(fields=["password", "ssn", "credit_card"])
    .with_redaction(patterns=[r"(?i).*secret.*"])
    .build()
)

logger.info("Signup", password="hunter2", user_secret="abc")
# Both fields redacted
```

## Compliance Presets

```python
from fapilog import LoggerBuilder

# GDPR compliance
logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# Multiple regulations
logger = LoggerBuilder().with_redaction(preset=["HIPAA_PHI", "PCI_DSS"]).build()
```

Notes:
- Default `get_logger()` only redacts URL credentials (`user:pass@host`)
- Use `preset="production"` or `preset="fastapi"` for full field redaction
- Configure custom fields with `.with_redaction(fields=[...])`
- Use compliance presets for regulation-specific protection

## Learn More

- **[Redaction Documentation](../redaction/index.md)** - Complete redaction guide
- **[Presets Reference](../redaction/presets.md)** - All compliance presets and field lists
- **[Compliance Cookbook](../cookbook/compliance-redaction.md)** - What works and what doesn't
