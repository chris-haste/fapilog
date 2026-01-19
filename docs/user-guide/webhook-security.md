# Webhook Security

This guide covers secure authentication for the WebhookSink.

## Authentication Modes

WebhookSink supports two authentication modes:

| Mode     | Header                      | Description                              |
| -------- | --------------------------- | ---------------------------------------- |
| `hmac`   | `X-Fapilog-Signature-256`   | HMAC-SHA256 signature (recommended)      |
| `header` | `X-Webhook-Secret`          | Raw secret in header (deprecated)        |

## HMAC Signature Mode (Default)

HMAC mode computes a signature of the payload using your secret key. The secret is never transmitted over the wire. This is the default mode as of v0.4.

### Configuration

```python
from fapilog.plugins.sinks.webhook import WebhookSink, WebhookSinkConfig

config = WebhookSinkConfig(
    endpoint="https://your-server.com/webhook",
    secret="your-secret-key",
    # signature_mode defaults to "hmac"
)
sink = WebhookSink(config=config)
```

### Headers Sent

| Header | Description |
|--------|-------------|
| `X-Fapilog-Signature-256` | HMAC-SHA256 signature: `sha256=<hex-digest>` |
| `X-Fapilog-Timestamp` | Unix timestamp when request was signed |

### How It Works

1. Fapilog captures the current Unix timestamp
2. Serializes the payload as compact JSON (`separators=(",", ":")`)
3. Computes `HMAC-SHA256(secret, "{timestamp}.{json_payload}")`
4. Sends signature in `X-Fapilog-Signature-256` and timestamp in `X-Fapilog-Timestamp`
5. Receiver verifies signature and rejects stale requests

### Replay Protection

The timestamp in the signature prevents replay attacks. Receivers should:

1. Extract the timestamp from `X-Fapilog-Timestamp`
2. Reject requests where the timestamp is too old or too far in the future
3. Verify the signature includes the timestamp

A tolerance of 5 minutes (300 seconds) is recommended to account for clock skew.

### Receiver-Side Verification

#### FastAPI Example

```python
import hmac
import hashlib
import time
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
WEBHOOK_SECRET = "your-secret-key"
TIMESTAMP_TOLERANCE = 300  # 5 minutes


def verify_webhook(
    payload: bytes,
    signature: str,
    timestamp_str: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Fapilog webhook signature and timestamp.

    Raises HTTPException if verification fails.
    """
    # Check timestamp freshness
    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    if abs(time.time() - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=401, detail="Request too old or too new")

    # Verify signature includes timestamp
    if not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid signature format")

    message = f"{timestamp}.{payload.decode()}".encode()
    expected = "sha256=" + hmac.new(
        secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Fapilog-Signature-256", "")
    timestamp = request.headers.get("X-Fapilog-Timestamp", "")

    verify_webhook(body, signature, timestamp, WEBHOOK_SECRET, TIMESTAMP_TOLERANCE)

    # Process the verified payload
    import json
    data = json.loads(body)
    return {"status": "received", "events": len(data) if isinstance(data, list) else 1}
```

#### Flask Example

```python
import hmac
import hashlib
import time
from flask import Flask, request, abort

app = Flask(__name__)
WEBHOOK_SECRET = "your-secret-key"
TIMESTAMP_TOLERANCE = 300  # 5 minutes


def verify_webhook(
    payload: bytes,
    signature: str,
    timestamp_str: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify Fapilog webhook signature and timestamp."""
    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - timestamp) > tolerance_seconds:
        return False

    if not signature.startswith("sha256="):
        return False

    message = f"{timestamp}.{payload.decode()}".encode()
    expected = "sha256=" + hmac.new(
        secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.route("/webhook", methods=["POST"])
def receive_webhook():
    signature = request.headers.get("X-Fapilog-Signature-256", "")
    timestamp = request.headers.get("X-Fapilog-Timestamp", "")

    if not verify_webhook(request.data, signature, timestamp, WEBHOOK_SECRET):
        abort(401)
    return {"status": "received"}
```

## Legacy Header Mode (Deprecated)

The legacy `header` mode sends the secret directly in the `X-Webhook-Secret` header. This mode is deprecated and will emit a warning.

### Security Risks

Sending secrets in headers increases exposure via:

- Proxy server logs (many log headers by default)
- CDN/WAF request logging
- Network monitoring tools
- Accidental logging in receiving applications

### Migration Path

1. Update your webhook receivers to verify HMAC signatures with timestamp
2. Handle the new `X-Fapilog-Timestamp` header and include it in signature verification
3. Add replay protection by rejecting stale requests
4. Remove legacy `X-Webhook-Secret` handling from receivers

> **Note:** As of v0.4, HMAC is the default. The signature format changed from `HMAC(payload)` to `HMAC(timestamp.payload)` for replay protection.

## Best Practices

1. **Use HMAC mode** for all new webhooks
2. **Rotate secrets regularly** and update both sender and receiver
3. **Use constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks
4. **Validate payload structure** after signature verification
5. **Log signature failures** for security monitoring (without logging the secret)

## Troubleshooting

### Signature Mismatch

Common causes:

- **Missing timestamp in signature**: The signature is computed over `{timestamp}.{payload}`, not just the payload. Ensure you include the timestamp from the `X-Fapilog-Timestamp` header.
- **Different JSON serialization**: Fapilog uses compact JSON (`separators=(",", ":")`). Ensure your verification uses the raw request body, not re-serialized JSON.
- **Encoding issues**: Ensure both sides use UTF-8 encoding for the secret.
- **Whitespace differences**: The signature is computed on the exact bytes sent. Don't strip or modify the payload before verification.

### Testing Signatures

```python
import hmac
import hashlib
import json
import time

secret = "test-secret"
payload = {"message": "hello", "level": "info"}
timestamp = int(time.time())

# Compute signature the same way Fapilog does
json_body = json.dumps(payload, separators=(",", ":"))
message = f"{timestamp}.{json_body}".encode()
signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

print(f"X-Fapilog-Timestamp: {timestamp}")
print(f"X-Fapilog-Signature-256: sha256={signature}")
```

### Clock Skew

If you see "Request too old or too new" errors:

1. Ensure both sender and receiver have synchronized clocks (use NTP)
2. Increase the tolerance if needed (default 300 seconds is generous)
3. Check for timezone issues in timestamp handling
