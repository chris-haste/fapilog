---
orphan: true
---

# Tamper-Evident Logging: Enterprise Key Management

Tamper-evident logging in fapilog is delivered as the `fapilog-tamper` add-on. This guide focuses on enterprise key management—how to integrate cloud KMS and Vault, keep keys out of the app process, and operate with rotation and attestation requirements.

## Overview

- **Features**: HMAC/Ed25519 per-record signatures, forward hash chains, sealed rotation manifests, cross-file verification.
- **Key sources**: `env`, `file`, `aws-kms`, `gcp-kms`, `azure-keyvault`, `vault`.
- **Signing modes**: Local (exported data keys) or provider-native signing (`use_kms_signing=True`) so key material never leaves the KMS/Vault.
- **Caching**: `key_cache_ttl_seconds` (default 300s) for data keys; caches auto-expire and refresh.

## Installation

```bash
pip install './packages/fapilog-tamper[all-kms]'
```

Or pick a provider:

- AWS: `pip install './packages/fapilog-tamper[aws]'`
- GCP: `pip install './packages/fapilog-tamper[gcp]'`
- Azure: `pip install './packages/fapilog-tamper[azure]'`
- Vault: `pip install './packages/fapilog-tamper[vault]'`

## Configuration (Pydantic model)

```python
from fapilog_tamper import TamperConfig

cfg = TamperConfig(
    enabled=True,
    key_id="alias/audit-2025",
    key_source="aws-kms",        # env | file | aws-kms | gcp-kms | azure-keyvault | vault
    use_kms_signing=True,        # prefer provider Sign/Verify so keys stay in KMS/Vault
    key_cache_ttl_seconds=300,   # data-key cache when exporting
    aws_region="us-east-1",      # optional
    vault_addr="https://vault.example.com",
    vault_auth_method="approle", # token | approle | kubernetes
    vault_role="audit-writer",
    azure_tenant_id="...",
    azure_client_id="...",
)
```

## Provider behaviors

| Provider | Exports key? | Signing path | Notes |
|----------|--------------|--------------|-------|
| `aws-kms` | Data key via `GenerateDataKey` (cached by TTL) | `Sign/Verify` with `use_kms_signing=True` | Respects AWS credential chain; region optional |
| `gcp-kms` | No | `mac_sign` / `mac_verify` | Uses ADC; key_id is full resource name |
| `azure-keyvault` | No | `CryptographyClient.sign/verify` (HS256) | Supports managed identity or client credential |
| `vault` | No | Transit `sign_data` / `verify_signed_data` | Auth: token/env, AppRole, Kubernetes (JWT mounted) |
| `env` / `file` | Yes | Local HMAC-SHA256 or Ed25519 | Development/on-prem convenience |

## Using the provider in the add-on

```python
from fapilog_tamper import TamperSealedPlugin

plugin = TamperSealedPlugin
enricher = plugin.get_enricher(cfg.model_dump())
sink = plugin.wrap_sink(rotating_sink, cfg.model_dump())
```

- **Enricher** computes MAC/signature per record; when `use_kms_signing=True` it delegates to the provider.
- **SealedSink** signs manifests with the same provider; manifests include `key_id` and `signature_algo` for verifier lookup.
- **Verifier** consumes keys from env/file stores today; manifests remain verifiable when the key is available (exported or cached).

## Operational guidance

- Prefer `use_kms_signing=True` in regulated environments; fall back to exported data keys only when latency requirements demand it.
- Set `key_cache_ttl_seconds` to your rotation policy; low TTL narrows exposure if a data key is compromised.
- Never log credentials or secrets; the implementation avoids logging tokens and clears cached keys on shutdown.
- Run `fapilog-tamper verify <file> --manifest <file.manifest.json>` in CI or SOAR pipelines to attest to log integrity.

## Troubleshooting

- Missing SDK: clear `ImportError` messages suggest the correct `[extra]`.
- Auth failures: validate IAM/AppRole/service principals outside the app first; the provider uses default credential chains.
- Vault transit path: `key_id` should point to the transit key name (e.g., `transit/keys/audit`).

## See also

- Story detail: Story 4.18 (Enterprise Key Management) in `docs/stories/fapilog-audit/`
- Add-on overview: [Tamper-Evident Logging](../addons/tamper-evident-logging.md)
