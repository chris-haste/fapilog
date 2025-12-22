# Redactors

Configure masking of sensitive data.

## Defaults

- Enabled: `FAPILOG_CORE__ENABLE_REDACTORS=true`.
- Order: `field-mask`, `regex-mask`, `url-credentials`.
- Guardrails: depth/keys via `FAPILOG_CORE__REDACTION_MAX_DEPTH`, `FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED`.

## Common configuration

```bash
export FAPILOG_CORE__SENSITIVE_FIELDS_POLICY=password,api_key,secret,token
export FAPILOG_CORE__REDACTORS_ORDER=field-mask,regex-mask,url-credentials
```

## Example

```python
from fapilog import get_logger

logger = get_logger()
logger.info(
    "User credentials",
    username="john",
    password="secret123",
    api_key="sk-123",
    email="john@example.com",
)
# password/api_key/email are masked before reaching sinks
```

## Customizing

- Adjust `sensitive_fields_policy` to add/remove fields for field-mask.
- Override `redactors_order` to change or disable specific stages.
- Add custom regex patterns via settings if needed.
