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

## Regex Pattern Safety

The `regex-mask` redactor validates patterns at config time to prevent ReDoS (Regular Expression Denial of Service) attacks. Patterns with these constructs are rejected:

- **Nested quantifiers**: `(a+)+`, `(a*)*`, `(a+)*`
- **Alternation with quantifiers**: `(a|aa)+`, `(foo|foobar)*`
- **Wildcards in bounded repetition**: `(.*a){10,}`

### Safe patterns

```python
# These are safe and accepted
patterns = [
    r"user\.email",              # Literal path
    r"user\..*\.secret",         # Simple wildcard
    r"request\.headers\.[^.]+",  # Character class
    r"(password|secret|token)",  # Alternation without quantifier
]
```

### Patterns to avoid

```python
# These are rejected by default
patterns = [
    r"(a+)+",           # Nested quantifiers - exponential backtracking
    r"(a|aa)+",         # Overlapping alternation - exponential backtracking
    r"(.*a){10,}",      # Wildcard in repetition - exponential backtracking
]
```

### Escape hatch

If you understand the risks and need to use a pattern that triggers validation, use `allow_unsafe_patterns=True`:

```python
config = RegexMaskConfig(
    patterns=[r"(complex|pattern)+"],
    allow_unsafe_patterns=True,  # Bypasses ReDoS validation
)
```
