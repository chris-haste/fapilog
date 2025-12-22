# Redacting Secrets


Built-in redactors mask sensitive fields by default.

```python
from fapilog import get_logger

logger = get_logger()

logger.info(
    "User credentials",
    username="john",
    password="secret123",
    api_key="sk-abc",
    email="john@example.com",
)
```

Output (masked):

```json
{
  "message": "User credentials",
  "username": "john",
  "password": "***REDACTED***",
  "api_key": "***REDACTED***",
  "email": "***REDACTED***"
}
```

Notes:
- Redactors are enabled by default; configure `FAPILOG_CORE__SENSITIVE_FIELDS_POLICY` to add field names.
- Regex redactor catches common secrets (password/token/email) by default.
