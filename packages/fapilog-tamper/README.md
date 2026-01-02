# fapilog-tamper

Tamper-evident logging add-on for fapilog. This package provides:

- **IntegrityEnricher** - Adds per-record MAC/signatures and hash chains
- **SealedSink** - Generates signed manifests on file rotation
- **Verification tools** - CLI and API for chain verification

## Installation

```bash
pip install ./packages/fapilog-tamper
```

For Ed25519 signature support, install the optional group:

```bash
pip install './packages/fapilog-tamper[signatures]'
```

For enterprise key management (AWS KMS, GCP KMS, Azure Key Vault, Vault):

```bash
pip install './packages/fapilog-tamper[all-kms]'
```

## Usage

### Via Settings (Recommended)

```python
import fapilog
from fapilog import Settings

settings = Settings(
    core__enrichers=["integrity"],
    core__sinks=["sealed"],
    enricher_config__integrity__algorithm="HMAC-SHA256",
    enricher_config__integrity__key_id="audit-key-2025",
)

with fapilog.runtime(settings=settings) as logger:
    logger.info("Tamper-evident log entry")
```

### Via Direct Plugin Loading

```python
from fapilog.plugins import load_plugin

# Load the integrity enricher
enricher = load_plugin("fapilog.enrichers", "integrity", {
    "algorithm": "HMAC-SHA256",
    "key_id": "audit-key-2025",
    "key_source": "env",
})

# Load the sealed sink
sink = load_plugin("fapilog.sinks", "sealed", {
    "inner_sink": "rotating_file",
    "sign_manifests": True,
})
```

### Environment Variables

```bash
export FAPILOG_TAMPER_KEY="<base64url-encoded-32-byte-key>"
export FAPILOG_TAMPER_KEY_ID="audit-key-2025"
```

## Enterprise key management

- `key_source`: `env`, `file`, `aws-kms`, `gcp-kms`, `azure-keyvault`, `vault`
- `key_cache_ttl_seconds`: cache duration for locally exported keys/data keys (default 5 minutes)
- `use_kms_signing`: call cloud/Vault APIs for signing so keys never leave the service
- Optional per-provider knobs:
  - AWS: `aws_region`
  - Vault: `vault_addr`, `vault_auth_method` (`token`/`approle`/`kubernetes`), `vault_role`
  - Azure: `azure_tenant_id`, `azure_client_id`

Example:

```python
cfg = TamperConfig(
    enabled=True,
    key_id="alias/audit-2025",
    key_source="aws-kms",
    use_kms_signing=True,
    key_cache_ttl_seconds=300,
)
```
