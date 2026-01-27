# Compliance Redaction: What Works and What Doesn't

This guide explains how to use compliance presets effectively and avoid common pitfalls that lead to data exposure.

> **Key insight:** Fapilog redacts based on **field names**, not field content. Understanding this is critical for compliance.

## The Golden Rule

**Redaction works on structured data with predictable field names.**

```python
from fapilog import LoggerBuilder

logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# ✅ WORKS: Named fields are redacted
logger.info("User signup", email="john@example.com", phone="+1-555-1234")
# Output: {"data": {"email": "***", "phone": "***"}}

# ❌ FAILS: PII buried in a string is NOT redacted
logger.info(f"User signed up: john@example.com, phone: +1-555-1234")
# Output: {"message": "User signed up: john@example.com, phone: +1-555-1234"}
```

## What Gets Redacted

Redaction matches **field names** (and paths) against preset definitions:

| Scenario | Redacted? | Why |
|----------|-----------|-----|
| `email="john@example.com"` | ✅ Yes | Field name `email` matches GDPR_PII |
| `user_email="john@example.com"` | ✅ Yes | Pattern `.*email.*` matches |
| `contact={"email": "john@example.com"}` | ✅ Yes | Nested path `contact.email` matches |
| `message="Email: john@example.com"` | ❌ No | Content scanning not performed |
| `notes="Call john@example.com"` | ❌ No | Field name `notes` doesn't match |
| `data="SSN: 123-45-6789"` | ❌ No | `data` is a generic field name |

## What Does NOT Get Redacted

### 1. PII in Message Strings

```python
# ❌ BAD: PII in the message string
logger.info(f"Processing order for {user.email}")
# Output: {"message": "Processing order for john@example.com"}

# ✅ GOOD: PII in named fields
logger.info("Processing order", email=user.email)
# Output: {"message": "Processing order", "data": {"email": "***"}}
```

### 2. PII in Arbitrarily-Named Fields

```python
# ❌ BAD: Field name doesn't match any preset pattern
logger.info("Support ticket", customer_contact="john@example.com")
# Output: {"data": {"customer_contact": "john@example.com"}}

# ✅ GOOD: Use recognized field names
logger.info("Support ticket", email="john@example.com")
# Output: {"data": {"email": "***"}}

# ✅ ALSO GOOD: Add custom fields to cover your domain
logger = (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["customer_contact"])
    .build()
)
```

### 3. PII in Serialized Objects

```python
# ❌ BAD: Serialized JSON string
user_json = '{"email": "john@example.com", "ssn": "123-45-6789"}'
logger.info("User data", payload=user_json)
# Output: {"data": {"payload": "{\"email\": \"john@example.com\", ...}"}}

# ✅ GOOD: Pass as dict, not string
user_data = {"email": "john@example.com", "ssn": "123-45-6789"}
logger.info("User data", **user_data)
# Output: {"data": {"email": "***", "ssn": "***"}}
```

### 4. PII in Exception Messages

```python
# ❌ BAD: PII in exception message
try:
    process_user(email)
except Exception as e:
    logger.error(f"Failed for user {email}: {e}")
# Output: {"message": "Failed for user john@example.com: ..."}

# ✅ GOOD: PII in structured field
try:
    process_user(email)
except Exception as e:
    logger.error("User processing failed", email=email, error=str(e))
# Output: {"data": {"email": "***", "error": "..."}}
```

## Structuring Logs for Compliance

### Use Named Fields for All PII

```python
# Instead of this:
logger.info(f"User {name} ({email}) logged in from {ip}")

# Do this:
logger.info("User logged in", name=name, email=email, ip_address=ip)
```

### Use Context for Request-Scoped PII

```python
from fapilog import LoggerBuilder

logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# Bind user context once
request_logger = logger.bind(
    email=request.user.email,
    ip_address=request.client.host,
)

# All subsequent logs have PII in named fields (and redacted)
request_logger.info("Viewing dashboard")
request_logger.info("Updated settings", setting="theme")
request_logger.warning("Rate limit approaching")
```

### Pass Objects, Not Strings

```python
# ❌ Avoid string interpolation
logger.info(f"Order {order.id} for {order.customer_email}")

# ✅ Pass structured data
logger.info("Order placed", order_id=order.id, email=order.customer_email)

# ✅ Or unpack relevant fields
logger.info("Order placed", **order.to_log_dict())
```

## Testing Your Redaction

Before deploying, verify PII is actually redacted:

```python
import pytest
from fapilog import LoggerBuilder
from fapilog.testing import capture_logs


@pytest.mark.asyncio
async def test_email_redacted_in_named_field():
    """Email in named field should be redacted."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .build_async()
        )
        await logger.info("signup", email="test@example.com")

    assert "test@example.com" not in logs.text
    assert "***" in logs.text


@pytest.mark.asyncio
async def test_email_in_message_NOT_redacted():
    """Email in message string is NOT redacted - this is expected behavior."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .build_async()
        )
        # This is the WRONG way to log PII
        await logger.info("User email: test@example.com")

    # PII IS exposed - this test documents the limitation
    assert "test@example.com" in logs.text


@pytest.mark.asyncio
async def test_custom_field_requires_explicit_config():
    """Custom field names need explicit configuration."""
    async with capture_logs() as logs:
        logger = await (
            LoggerBuilder()
            .with_redaction(preset="GDPR_PII")
            .with_redaction(fields=["customer_contact"])  # Add custom field
            .build_async()
        )
        await logger.info("ticket", customer_contact="test@example.com")

    assert "test@example.com" not in logs.text
```

## Compliance Checklist

Before going to production with compliance redaction:

- [ ] **Audit your logging calls** - Search codebase for f-strings and `.format()` in log calls
- [ ] **Use structured fields** - All PII should be in named fields, not message strings
- [ ] **Add domain-specific fields** - Extend presets with your custom field names
- [ ] **Test redaction** - Write tests that verify PII is masked
- [ ] **Review preset coverage** - Check [Presets Reference](../redaction/presets.md) for what's covered
- [ ] **Document gaps** - Note any PII that can't be redacted (e.g., user-generated content)

## Common Patterns by Regulation

### GDPR (EU)

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["customer_id", "account_ref"])  # Your domain fields
    .build()
)

# Always use named fields for Article 4 personal data
logger.info(
    "Data subject request",
    email=user.email,           # Redacted
    name=user.full_name,        # Redacted
    ip_address=request.ip,      # Redacted
    request_type="erasure",     # Not PII, preserved
)
```

### HIPAA (US Healthcare)

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="HIPAA_PHI")
    .with_redaction(fields=["chart_number", "room_number"])
    .build()
)

# All 18 PHI identifiers should be in named fields
logger.info(
    "Patient admission",
    mrn=patient.medical_record_number,  # Redacted
    dob=patient.date_of_birth,          # Redacted
    ssn=patient.ssn,                    # Redacted
    admission_type="emergency",         # Not PHI, preserved
)
```

### PCI-DSS (Payment Cards)

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="PCI_DSS")
    .build()
)

# Never log full card numbers, but if you must log payment events:
logger.info(
    "Payment processed",
    card_number=card.pan,        # Redacted (but don't log this!)
    cardholder=card.name,        # Redacted
    amount=transaction.amount,   # Not cardholder data, preserved
    last_four=card.pan[-4:],     # Consider if this is acceptable
)
```

## Summary

| Do | Don't |
|----|-------|
| Use named fields for PII | Embed PII in message strings |
| Pass dicts, not JSON strings | Serialize objects before logging |
| Bind PII to context | Interpolate PII in f-strings |
| Extend presets with your fields | Assume all field names are covered |
| Test redaction in CI | Deploy without verification |

## Related

- [Redaction Presets](../redaction/presets.md) - Complete field reference
- [Redaction Behavior](../redaction/behavior.md) - Configuration details
- [Redacting Secrets](redacting-secrets-pii.md) - Authentication secrets
