# Redaction Guarantee

This page documents exactly what fapilog redacts under each configuration.

> **Secure Default:** URL credential redaction (`url_credentials`) is enabled by default in all configurations. Additional redactors (`field_mask`, `regex_mask`) are available via `preset="production"` or explicit configuration. See [Reliability Defaults](reliability-defaults.md) for details.

## Quick Reference

| Configuration | field_mask | regex_mask | url_credentials | Protection Level |
|---------------|------------|------------|-----------------|------------------|
| `Settings()` (no preset) | No | No | **Yes** | Basic (URL credentials scrubbed) |
| `preset="dev"` | No | No | No | None (explicit opt-out) |
| `preset="production"` | Yes | Yes | Yes | Standard |
| `preset="fastapi"` | No | No | No | None (explicit opt-out) |
| `preset="minimal"` | No | No | No | None (explicit opt-out) |

## Production Preset Details

When using `preset="production"`, three redactors are enabled in order:

### 1. field_mask Redactor

Masks specific field paths under `metadata.*`:

- `metadata.password`
- `metadata.api_key`
- `metadata.token`
- `metadata.secret`
- `metadata.authorization`
- `metadata.api_secret`
- `metadata.private_key`
- `metadata.ssn`
- `metadata.credit_card`

**Example:**
```python
# Input
{"metadata": {"password": "hunter2", "user": "alice"}}

# Output
{"metadata": {"password": "***", "user": "alice"}}
```

### 2. regex_mask Redactor

Matches any field path (at any nesting level) containing sensitive keywords:

| Pattern | Matches |
|---------|---------|
| `.*password.*` | `user.password`, `auth.password_hash`, etc. |
| `.*passwd.*` | `old_passwd`, `metadata.passwd`, etc. |
| `.*api[_-]?key.*` | `api_key`, `apikey`, `api-key`, etc. |
| `.*secret.*` | `client_secret`, `secret_key`, etc. |
| `.*token.*` | `access_token`, `refresh_token`, etc. |
| `.*authorization.*` | `authorization`, `auth.authorization`, etc. |
| `.*private[_-]?key.*` | `private_key`, `privatekey`, etc. |
| `.*ssn.*` | `user.ssn`, `ssn_number`, etc. |
| `.*credit[_-]?card.*` | `credit_card`, `creditcard`, etc. |

All patterns are case-insensitive.

**Example:**
```python
# Input (field path: request.body.user_password)
{"request": {"body": {"user_password": "secret123"}}}

# Output
{"request": {"body": {"user_password": "***"}}}
```

### 3. url_credentials Redactor

Strips userinfo (username:password) from URLs in string values:

**Example:**
```python
# Input
{"endpoint": "https://user:pass@api.example.com/v1"}

# Output
{"endpoint": "https://***:***@api.example.com/v1"}
```

## Enabling Redaction Without Presets

If you're not using a preset, you must explicitly configure redactors:

```python
from fapilog import Settings

settings = Settings(
    core={"redactors": ["field_mask", "regex_mask", "url_credentials"]},
    redactor_config={
        "field_mask": {
            "fields_to_mask": ["password", "api_key", "secret"],
        },
        "regex_mask": {
            "patterns": [
                r"(?i).*password.*",
                r"(?i).*secret.*",
                r"(?i).*token.*",
            ],
        },
    },
)
```

## Customizing Production Redaction

To modify the production preset's redaction behavior:

```python
from fapilog import Settings
from fapilog.core.presets import get_preset

# Start from production preset
config = get_preset("production")

# Add custom patterns
config["redactor_config"]["regex_mask"]["patterns"].append(
    r"(?i).*internal_id.*"
)

# Or remove a redactor
config["core"]["redactors"].remove("regex_mask")

settings = Settings(**config)
```

## Disabling Redaction

URL credential redaction is enabled by default for security. To disable all redaction (not recommended for production):

```python
settings = Settings(
    core={"redactors": []},  # Empty list disables all redaction
)
```

Or disable the redactors stage entirely:

```python
settings = Settings(
    core={"enable_redactors": False},
)
```

> **Note:** The `dev`, `fastapi`, and `minimal` presets explicitly set `redactors: []` to disable redaction for development visibility and debugging. This is intentional - if you need URL credential protection in development, use `Settings()` without a preset or use `preset="production"`.

## Guardrails

Redaction includes safety limits to prevent performance issues:

- **max_depth**: Maximum recursion depth (default: 16 for regex_mask)
- **max_keys_scanned**: Maximum keys to scan per event (default: 1000)

If limits are exceeded, a diagnostic warning is emitted and remaining fields are not scanned.

## CI Protection

The tests in `tests/unit/test_redaction_defaults.py` validate that:

1. Default `Settings()` has `url_credentials` enabled for secure defaults
2. Production preset enables `field_mask`, `regex_mask`, and `url_credentials`
3. All documented fields and patterns are configured
4. Non-production presets (`dev`, `fastapi`, `minimal`) explicitly set `redactors: []` to opt-out

If these tests fail, update both code AND documentation to maintain alignment.
