# Redaction Behavior

This page documents exactly what fapilog redacts, how the pipeline works, and known limitations.

> **Disclaimer:** Redaction is provided as a best-effort mechanism to help protect sensitive data. It matches field names and patterns, not arbitrary field content. You are responsible for testing and verifying redaction meets your compliance requirements before production use. Fapilog and its maintainers accept no liability for data exposure.

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

## Guardrails

Redaction includes safety limits to prevent performance issues with deeply nested or large objects:

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_depth` | 16 | Maximum nesting level to traverse |
| `max_keys_scanned` | 1000 | Maximum keys to examine per event |

If limits are exceeded:
- A diagnostic warning is emitted
- Remaining fields are not scanned
- Best-effort redaction is applied to already-scanned fields

Configure via builder:
```python
logger = (
    LoggerBuilder()
    .with_redaction(fields=["password"], max_depth=32, max_keys=5000)
    .build()
)
```

## Failure Handling

Redactors never raise exceptions upstream. If redaction fails:
- The original value is preserved (fail-open by default)
- A diagnostic entry is recorded with `{ redactor, reason }`
- Logging continues

To fail-closed (block logging on redaction failure):
```python
.with_redaction(fields=["password"], block_on_failure=True)
```

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
