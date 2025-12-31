# fapilog-tamper

Tamper-evident logging add-on for fapilog. This package registers the
`tamper-sealed` integrity plugin and ships the core types and helpers used by
subsequent stories (enricher, sealed sink, verification).

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

```python
from fapilog.plugins.integrity import load_integrity_plugin

plugin = load_integrity_plugin("tamper-sealed")
enricher = plugin.get_enricher()
```

The initial release provides placeholder components; subsequent stories layer on
full tamper-evident enrichment, sealed sinks, manifests, and verification.

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
