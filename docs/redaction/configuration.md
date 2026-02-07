# Redaction Configuration

How to configure redaction using the Builder API, Settings, or environment variables.

## Builder API (Recommended)

The `with_redaction()` method is the unified entry point for all redaction configuration:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_redaction(
        # Compliance presets
        preset="GDPR_PII",
        # Custom fields (auto-prefixed with data.)
        fields=["password", "api_key", "ssn"],
        # Regex patterns for field paths
        patterns=[r"(?i).*secret.*", r"(?i).*token.*"],
        # Custom mask string
        mask="[REDACTED]",
        # URL credential redaction
        url_credentials=True,
        # Performance guardrails
        max_depth=16,
        max_keys=1000,
    )
    .build()
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `preset` | `str \| list[str]` | `None` | Preset name(s) to apply |
| `fields` | `list[str]` | `None` | Field names to redact |
| `patterns` | `list[str]` | `None` | Regex patterns for field paths |
| `mask` | `str` | `"***"` | Replacement string |
| `url_credentials` | `bool` | `None` | Enable/disable URL credential stripping |
| `url_max_length` | `int` | `4096` | Max URL length to scan |
| `block_on_failure` | `bool` | `False` | Block logging if redaction fails |
| `max_depth` | `int` | `16` | Max nesting depth to traverse |
| `max_keys` | `int` | `1000` | Max keys to scan per event |
| `block_fields` | `list[str]` | `None` | Field names to block via field_blocker |
| `max_string_length` | `int` | `None` | Max string length via string_truncate |
| `auto_prefix` | `bool` | `True` | Add `data.` prefix to simple field names |
| `replace` | `bool` | `False` | Replace existing config instead of merging |

### Auto-Prefix Behavior

By default, simple field names (without dots) are automatically prefixed with `data.` to match the log envelope:

```python
# These are equivalent:
.with_redaction(fields=["password"])                        # → data.password
.with_redaction(fields=["data.password"], auto_prefix=False)
```

Fields with dots are not prefixed:

```python
.with_redaction(fields=["context.user.token"])  # Not prefixed (has dots)
```

Disable auto-prefix when you need explicit paths:

```python
.with_redaction(fields=["context.auth.token"], auto_prefix=False)
```

### Additive Configuration

Multiple `with_redaction()` calls are additive by default:

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["internal_id"])  # Added to GDPR fields
    .with_redaction(patterns=[r"(?i).*custom.*"])  # Added to patterns
    .build()
)
```

Use `replace=True` to overwrite:

```python
.with_redaction(fields=["only_this"], replace=True)
```

## Settings Object

For programmatic configuration without the builder:

```python
from fapilog import get_logger, Settings

settings = Settings(
    core={
        "redactors": [
            "field_mask",
            "regex_mask",
            "url_credentials",
            "field_blocker",
            "string_truncate",
        ],
    },
    redactor_config={
        "field_mask": {
            "fields_to_mask": ["data.password", "data.api_key", "data.secret"],
            "mask_string": "***",
        },
        "regex_mask": {
            "patterns": [
                r"(?i).*password.*",
                r"(?i).*secret.*",
                r"(?i).*token.*",
            ],
            "mask_string": "***",
        },
        "field_blocker": {
            "blocked_fields": ["body", "request_body", "payload"],
            "allowed_fields": [],
        },
        "string_truncate": {
            "max_string_length": 1000,
        },
    },
)

logger = get_logger(settings=settings)
```

### Redactor Order

Control the order redactors are applied:

```python
settings = Settings(
    core={
        "redactors": [
            "field_mask",
            "regex_mask",
            "url_credentials",
            "field_blocker",
            "string_truncate",
        ],
    }
)
```

Default order:
1. `field_mask` - Exact field path matching
2. `regex_mask` - Pattern-based matching
3. `url_credentials` - URL credential stripping
4. `field_blocker` - High-risk field blocking
5. `string_truncate` - Long string truncation

### Guardrails

Set limits to prevent performance issues:

```python
settings = Settings(
    core={
        "redaction_max_depth": 16,
        "redaction_max_keys_scanned": 1000,
    }
)
```

## Environment Variables

Configure redaction via environment:

```bash
# Enable specific redactors
export FAPILOG_CORE__REDACTORS='["field_mask", "regex_mask", "url_credentials", "field_blocker", "string_truncate"]'

# Configure field mask
export FAPILOG_REDACTOR_CONFIG__FIELD_MASK__FIELDS_TO_MASK='["password", "api_key"]'
export FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MASK_STRING='[REDACTED]'

# Configure regex mask
export FAPILOG_REDACTOR_CONFIG__REGEX_MASK__PATTERNS='["(?i).*secret.*", "(?i).*token.*"]'

# Configure field blocker
export FAPILOG_REDACTOR_CONFIG__FIELD_BLOCKER__BLOCKED_FIELDS='["body", "request_body", "payload"]'
export FAPILOG_REDACTOR_CONFIG__FIELD_BLOCKER__REPLACEMENT='[BLOCKED]'

# Configure string truncate
export FAPILOG_REDACTOR_CONFIG__STRING_TRUNCATE__MAX_STRING_LENGTH=1000

# Guardrails
export FAPILOG_CORE__REDACTION_MAX_DEPTH=16
export FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED=1000
```

(default-behavior-by-preset)=
## Default Behavior by Preset

| Configuration | field_mask | regex_mask | url_credentials | field_blocker | string_truncate |
|---------------|------------|------------|-----------------|---------------|-----------------|
| `Settings()` (no preset) | No | No | **Yes** | No | No |
| `preset="dev"` | No | No | No | No | No |
| `preset="production"` | Yes | Yes | Yes | No | No |
| `preset="serverless"` | Yes | Yes | Yes | No | No |
| `preset="fastapi"` | Yes | Yes | Yes | No | No |
| `preset="hardened"` | Yes | Yes | Yes | **Yes** | No |
| `preset="minimal"` | No | No | No | No | No |

The `production`, `fastapi`, and `serverless` presets automatically apply the `CREDENTIALS` redaction preset. The `hardened` preset additionally enables `field_blocker` with default blocked fields and applies the `HIPAA_PHI` and `PCI_DSS` presets.

## Disabling Redaction

URL credential redaction is enabled by default. To disable all redaction:

```python
# Via Settings
settings = Settings(
    core={"redactors": []},  # Empty list disables all
)

# Or disable the redactors stage entirely
settings = Settings(
    core={"enable_redactors": False},
)
```

> **Note:** The `dev` and `minimal` presets explicitly disable redaction for development visibility.

## Extending Production Preset

To add compliance presets to the production configuration:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")  # Includes CREDENTIALS
    .with_redaction(preset="HIPAA_PHI")  # Add HIPAA protection
    .with_redaction(fields=["internal_id"])  # Add custom fields
    .build()
)
```

(regex-pattern-safety)=
## Regex Pattern Safety

The `regex-mask` redactor validates patterns at config time to prevent ReDoS (Regular Expression Denial of Service) attacks. Patterns with these constructs are rejected:

- **Nested quantifiers**: `(a+)+`, `(a*)*`, `(a+)*`
- **Alternation with quantifiers**: `(a|aa)+`, `(foo|foobar)*`
- **Wildcards in bounded repetition**: `(.*a){10,}`

### Safe Patterns

```python
# These are safe and accepted
patterns = [
    r"user\.email",              # Literal path
    r"user\..*\.secret",         # Simple wildcard
    r"request\.headers\.[^.]+",  # Character class
    r"(password|secret|token)",  # Alternation without quantifier
]
```

### Patterns to Avoid

```python
# These are rejected by default
patterns = [
    r"(a+)+",           # Nested quantifiers - exponential backtracking
    r"(a|aa)+",         # Overlapping alternation - exponential backtracking
    r"(.*a){10,}",      # Wildcard in repetition - exponential backtracking
]
```

### Escape Hatch

If you understand the risks and need to use a pattern that triggers validation:

```python
from fapilog.redaction import RegexMaskConfig

config = RegexMaskConfig(
    patterns=[r"(complex|pattern)+"],
    allow_unsafe_patterns=True,  # Bypasses ReDoS validation
)
```

> **Warning:** Only use `allow_unsafe_patterns=True` if you've verified the pattern won't cause catastrophic backtracking with your data.

## Related

- [Presets Reference](presets.md) - Complete field lists
- [Behavior](behavior.md) - What gets redacted and when
- [Testing](testing.md) - Verify redaction in CI
