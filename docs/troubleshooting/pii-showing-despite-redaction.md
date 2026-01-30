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
