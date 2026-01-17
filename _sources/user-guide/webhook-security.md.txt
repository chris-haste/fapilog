# Webhook Security

This guide covers secure authentication for the WebhookSink.

## Authentication Modes

WebhookSink supports two authentication modes:

| Mode     | Header                      | Description                              |
| -------- | --------------------------- | ---------------------------------------- |
| `hmac`   | `X-Fapilog-Signature-256`   | HMAC-SHA256 signature (recommended)      |
| `header` | `X-Webhook-Secret`          | Raw secret in header (deprecated)        |

## HMAC Signature Mode (Recommended)

HMAC mode computes a signature of the payload using your secret key. The secret is never transmitted over the wire.

### Configuration

```python
from fapilog.plugins.sinks.webhook import WebhookSink, WebhookSinkConfig

config = WebhookSinkConfig(
    endpoint="https://your-server.com/webhook",
    secret="your-secret-key",
    signature_mode="hmac",  # Recommended
)
sink = WebhookSink(config=config)
```

### How It Works

1. Fapilog serializes the payload as compact JSON (`separators=(",", ":")`)
2. Computes `HMAC-SHA256(secret, payload_bytes)`
3. Sends the signature in `X-Fapilog-Signature-256: sha256=<hex-digest>`
4. Receiver verifies by computing the same HMAC and comparing

### Receiver-Side Verification

#### FastAPI Example

```python
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
WEBHOOK_SECRET = "your-secret-key"


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from Fapilog webhook."""
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Fapilog-Signature-256", "")

    if not verify_signature(body, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process the verified payload
    import json
    data = json.loads(body)
    return {"status": "received", "events": len(data) if isinstance(data, list) else 1}
```

#### Flask Example

```python
import hmac
import hashlib
from flask import Flask, request, abort

app = Flask(__name__)
WEBHOOK_SECRET = "your-secret-key"


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.route("/webhook", methods=["POST"])
def receive_webhook():
    signature = request.headers.get("X-Fapilog-Signature-256", "")
    if not verify_signature(request.data, signature, WEBHOOK_SECRET):
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

1. Update your webhook receivers to verify HMAC signatures
2. Update Fapilog configuration to use `signature_mode="hmac"`
3. Remove legacy `X-Webhook-Secret` handling from receivers

## Best Practices

1. **Use HMAC mode** for all new webhooks
2. **Rotate secrets regularly** and update both sender and receiver
3. **Use constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks
4. **Validate payload structure** after signature verification
5. **Log signature failures** for security monitoring (without logging the secret)

## Troubleshooting

### Signature Mismatch

Common causes:

- **Different JSON serialization**: Fapilog uses compact JSON (`separators=(",", ":")`). Ensure your verification uses the raw request body, not re-serialized JSON.
- **Encoding issues**: Ensure both sides use UTF-8 encoding for the secret.
- **Whitespace differences**: The signature is computed on the exact bytes sent. Don't strip or modify the payload before verification.

### Testing Signatures

```python
import hmac
import hashlib
import json

secret = "test-secret"
payload = {"message": "hello", "level": "info"}

# Compute signature the same way Fapilog does
body = json.dumps(payload, separators=(",", ":")).encode()
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
print(f"sha256={signature}")
```
