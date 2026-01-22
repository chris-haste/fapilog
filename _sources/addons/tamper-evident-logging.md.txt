---
orphan: true
---

# Tamper-Evident Logging Add-on (Optional)

This design keeps the core light while offering an opt-in, first-class tamper-evident capability delivered as a separate plugin/package.

## Packaging and Opt-in

- Package: `fapilog-tamper` (separate install). Depends on crypto libs (`cryptography`/`pynacl`) isolated from core.
- Core change: small hook to register an integrity enricher and an integrity sink wrapper via settings (e.g., `settings.integrity_plugin="tamper-sealed"`). If absent, behavior is unchanged.
- Backward compatibility: integrity fields are optional and ignored by default; existing logs remain valid.

## Configuration

- **Recommended (standard plugins)**: use the standard plugin groups exposed by `fapilog-tamper`.

  ```yaml
  core:
    enrichers: [runtime_info, integrity]
    sinks: [sealed]

  enricher_config:
    integrity:
      algorithm: sha256
      chain_state_path: /var/lib/fapilog/chainstate
      key_provider: env
      key_id: audit-key

  sink_config:
    sealed:
      inner_sink: rotating_file
      inner_config:
        directory: /var/log/myapp
      manifest_path: /var/log/myapp/manifests
      sign_manifests: true
  ```

- **Legacy (deprecated)**: `core.integrity_plugin="tamper-sealed"` remains available for backward compatibility and emits a deprecation warning.

## Threat Model Goals

- Detect insertion, deletion, modification, and reordering of log entries.
- Detect truncation or replacement of rotated files.
- Provide cryptographic proof material (manifests, chain roots) that can be verified offline.

## Crypto and Canonicalization

- Per-record MAC: HMAC-SHA256 (default); allow `algo` override; optional Ed25519 signatures.
- Chain: forward hash chain `chain_hash = SHA256(prev_chain_hash || record_mac || seq || timestamp)` with root = 32-byte zero.
- Manifest signing: HMAC or Ed25519 over canonical JSON manifest (sorted keys, UTF-8, no whitespace).
- Canonical record encoding: stable JSON (sorted keys, UTF-8). Non-JSON types must be normalized deterministically.

## Write Path Components (addon)

1. **IntegrityEnricher**: canonicalizes the event payload, computes per-record MAC/signature, injects:
   ```json
   "integrity": {
     "seq": 42,
     "mac": "base64url...",
     "algo": "HMAC-SHA256",
     "key_id": "audit-key-2025Q1",
     "chain_hash": "base64url...",
     "prev_chain_hash": "base64url..."
   }
   ```
2. **ChainState**: tracks `prev_chain_hash` and `seq` per stream/file; persists to a sidecar state (e.g., `.chainstate`) for restart continuity. On restart, can replay the tail of the current file to recover state.
3. **SealedRotatingFileSink** (wraps current rotating sink):
   - Writes JSONL with integrity fields.
   - Rotation: fsync active file, emit signed manifest, optionally gzip data + manifest; enforce append-only opens.
   - Options: `fsync_on_write` (off by default), `fsync_on_rotate` (on by default for integrity mode), `rotate_chain` (reset chain per file vs continuous).
4. **Key management**: uses existing `EncryptionSettings` surfaces:
   - `key_source`: env/file/kms/vault, with `key_id` and optional `version`.
   - Multiple active keys supported; enricher tags `key_id`; verifier selects matching key.

## Manifest Format (JSON)

```json
{
  "version": "1.0",
  "file": "fapilog-20250101-120000.jsonl",
  "created_ts": "...Z",
  "closed_ts": "...Z",
  "record_count": 1234,
  "first_seq": 1,
  "last_seq": 1234,
  "first_ts": "...Z",
  "last_ts": "...Z",
  "root_chain_hash": "base64url...",
  "algo": "HMAC-SHA256",
  "key_id": "audit-key-2025Q1",
  "signature_algo": "HMAC-SHA256",
  "signature": "base64url...",
  "integrity_version": "1.0"
}
```

## Verification Components (addon)

- **Verifier API**: `verify_file(path, manifest_path=None, keys=KeyStore) -> VerifyReport`.
- **CLI**: `fapilog-tamper verify <path> [--manifest ...] [--keys ...] [--continue-chain-from <manifest>]`.
- Checks: recompute per-record MAC, verify chain continuity and `seq` monotonicity, compare root to manifest, verify manifest signature. Report gaps, corruption, wrong keys.
- **Self-checker**: optional coroutine to re-verify recent files and emit compliance alerts via the existing `_send_compliance_alert` hook.

## Config Knobs (addon)

- `tamper.enabled` (default false)
- `tamper.algorithm`, `tamper.key_id`, `tamper.key_source`, `tamper.state_dir`
- `tamper.fsync_on_write`, `tamper.rotate_chain`, `tamper.use_signatures` (Ed25519)
- `tamper.verify_on_close` (run verifier after rotation), `tamper.alert_on_failure`
- `tamper.key_cache_ttl_seconds`, `tamper.use_kms_signing`, `tamper.aws_region`, `tamper.vault_*`, `tamper.azure_*`
- Supported `key_source`: `env`, `file`, `aws-kms`, `gcp-kms`, `azure-keyvault`, `vault` (optional deps `fapilog-tamper[all-kms]`)

## Durability and Performance

- Hash/MAC per record is fast; hashing can be offloaded to worker threads if needed.
- Default to fsync on rotation only; allow per-write fsync for higher assurance.
- Append-only mode; atomic rename on rotation to avoid torn manifests.

## Remote Transport Extension (optional)

- For webhook/remote sinks: add MAC header (e.g., `X-Fapilog-MAC`) over body + nonce + timestamp; require mTLS; maintain replay cache on server side.

## Testing Plan (addon)

- Unit: deterministic MAC, chain continuity, manifest signing/verification, key rotation selection, chain-state recovery.
- Property: random bit-flips/inserts/deletes detected.
- Integration: write/rotate/verify cycles, gzip + manifest, restart recovery.
- Negative: corrupted records, missing manifests, wrong keys, non-monotonic seq, replayed transport payloads.
