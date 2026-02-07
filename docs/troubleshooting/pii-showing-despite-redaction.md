# PII Showing Despite Redaction

## Symptoms
- Passwords, tokens, or emails appear in logs
- URL credentials (`user:pass@`) still visible

## Most Common Cause: PII in Message Strings

Redactors only process **structured fields** in the log envelope. PII embedded directly in the message string bypasses redaction entirely:

```python
# UNSAFE - these will NOT be redacted
logger.info(f"User {email} logged in")           # f-string
logger.info("User " + email + " logged in")      # concatenation
logger.info("User %s logged in", email)          # %-formatting
logger.info("User {} logged in".format(email))   # .format()

# SAFE - structured fields ARE redacted
logger.info("User logged in", email=email)
logger.info("User logged in", user={"email": email})
```

**Fix:** Always pass sensitive data as structured keyword arguments, not in the message string.

## Quick Fix: Declare Sensitive Data at Log Time

If you can't wait for redactor configuration changes, use `sensitive=` to mask values immediately at log time:

```python
# Values are masked at envelope construction — before queueing or any sink
await logger.info(
    "User signup",
    sensitive={"email": "alice@example.com", "ssn": "123-45-6789"},
)
# Output: {"data": {"sensitive": {"email": "***", "ssn": "***"}}}
```

`pii=` is an alias for teams that prefer that term:

```python
await logger.info("Payment", pii={"card_number": "4111-1111-1111-1111"})
```

This is complementary to redactor configuration — use `sensitive=` for developer-declared intent and redactors as a safety net. See [Declaring Sensitive Data at Log Time](../cookbook/redacting-secrets-pii.md#declaring-sensitive-data-at-log-time) for details.

## Other Causes
- Redactors disabled or order overridden
- Sensitive fields not included in policy
- Guardrails too restrictive for nested data

## Fixes
```bash
# Ensure redactors are enabled
export FAPILOG_CORE__ENABLE_REDACTORS=true

# Add sensitive fields
export FAPILOG_CORE__SENSITIVE_FIELDS_POLICY=password,api_key,secret,token,email

# Keep default order
export FAPILOG_CORE__REDACTORS_ORDER=field-mask,regex-mask,url-credentials

# Optional: adjust guardrails if your data is deep
export FAPILOG_CORE__REDACTION_MAX_DEPTH=8
export FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED=8000
```

Tips:
- Regex redactor masks common secrets by default; add custom patterns if needed.
- Field-mask uses `sensitive_fields_policy` to target specific keys.
- Monitor internal diagnostics to confirm redactors are running if you suspect configuration drift.

## Intentional Bypasses

If sensitive data is appearing only at DEBUG level, check for `unsafe_debug()` calls. This method intentionally **skips the entire redaction pipeline**:

```python
# This bypasses ALL redaction — sensitive data will appear in plain text
logger.unsafe_debug("raw request", body=request_body)
```

`unsafe_debug()` is designed for local debugging only and logs at DEBUG level. If you see unredacted data in production logs, search the codebase for `unsafe_debug` calls and remove them.

See [Bypass: unsafe_debug()](../redaction/behavior.md#bypass-unsafe_debug) for details on how this mechanism works.
