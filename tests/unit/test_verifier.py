"""
Tests for verification API and CLI in fapilog-tamper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Add fapilog-tamper to path before importing
_tamper_src = (
    Path(__file__).resolve().parents[2] / "packages" / "fapilog-tamper" / "src"
)
if _tamper_src.exists():
    sys.path.insert(0, str(_tamper_src))

try:
    from fapilog_tamper.canonical import b64url_encode, canonicalize
except ImportError:
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


def _hmac_key() -> bytes:
    return b"K" * 32


def _build_record(
    seq: int, ts: str, key: bytes, key_id: str = "kid"
) -> tuple[dict, bytes]:
    payload = {"msg": f"r{seq}", "timestamp": ts}
    mac = _compute_mac(payload, key)
    prev_hash = b"\x00" * 32 if seq == 1 else _build_record.prev_hash
    chain_hash = _compute_chain_hash(prev_hash, mac, seq, ts)
    record = {
        **payload,
        "integrity": {
            "seq": seq,
            "mac": b64url_encode(mac),
            "algo": "HMAC-SHA256",
            "key_id": key_id,
            "chain_hash": b64url_encode(chain_hash),
            "prev_chain_hash": b64url_encode(prev_hash),
        },
    }
    _build_record.prev_hash = chain_hash
    return record, chain_hash


def _compute_mac(payload: dict[str, Any], key: bytes) -> bytes:
    import hashlib
    import hmac

    return hmac.new(key, canonicalize(payload), hashlib.sha256).digest()


def _compute_chain_hash(prev_hash: bytes, mac: bytes, seq: int, ts: str) -> bytes:
    import hashlib

    return hashlib.sha256(
        prev_hash + mac + seq.to_bytes(8, "big") + ts.encode("utf-8")
    ).digest()


# Initialize mutable attribute for previous hash tracking
_build_record.prev_hash = b"\x00" * 32  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_verify_record_and_chain_valid(tmp_path: Path) -> None:
    """verify_record and verify_chain should accept valid data and catch gaps/breaks."""
    from fapilog_tamper.verify import EnvKeyStore, Verifier

    key = _hmac_key()
    os.environ["KID_ENV"] = b64url_encode(key)
    store = EnvKeyStore()
    verifier = Verifier(store)

    r1, _ = _build_record(1, "2025-01-01T00:00:00Z", key, "KID_ENV")
    r2, _ = _build_record(2, "2025-01-01T00:00:01Z", key, "KID_ENV")
    assert verifier.verify_record(r1, key, "HMAC-SHA256") is True
    assert verifier.verify_record(r2, key, "HMAC-SHA256") is True
    chain_errors = verifier.verify_chain([r1, r2])
    assert chain_errors == []

    # Tamper prev_chain_hash and seq gap
    r2_bad = dict(r2)
    r2_bad["integrity"] = dict(r2["integrity"])
    r2_bad["integrity"]["prev_chain_hash"] = "mismatch"
    r2_bad["integrity"]["seq"] = 4
    errors = verifier.verify_chain([r1, r2_bad])
    assert any(e.error_type == "chain_break" for e in errors)
    assert any(e.error_type == "seq_gap" for e in errors)


@pytest.mark.asyncio
async def test_verify_file_with_manifest_and_tamper(tmp_path: Path) -> None:
    """verify_file should stream JSONL, validate MACs, chain, and manifest signature."""
    from fapilog_tamper.verify import EnvKeyStore, Verifier, VerifyError, write_manifest

    key = _hmac_key()
    os.environ["KID_ENV"] = b64url_encode(key)
    store = EnvKeyStore()
    verifier = Verifier(store)

    records: list[dict] = []
    for seq in (1, 2, 3):
        rec, _ = _build_record(seq, f"2025-01-01T00:00:0{seq}Z", key, "KID_ENV")
        records.append(rec)

    log_path = tmp_path / "audit.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    manifest_path = write_manifest(
        log_path, records, key, "KID_ENV", algo="HMAC-SHA256"
    )
    report = await verifier.verify_file(log_path, manifest_path=manifest_path)
    assert report.valid is True
    assert report.records_checked == 3
    assert report.manifest_valid is True
    assert report.manifest_signature_valid is True

    # Tamper MAC
    tampered_records = list(records)
    tampered = dict(tampered_records[1])
    tampered["integrity"] = dict(tampered["integrity"])
    tampered["integrity"]["mac"] = b64url_encode(b"badmac")
    tampered_records[1] = tampered
    with open(log_path, "w", encoding="utf-8") as f:
        for rec in tampered_records:
            f.write(json.dumps(rec) + "\n")
    report_bad = await verifier.verify_file(log_path, manifest_path=manifest_path)
    assert report_bad.valid is False
    assert any(e.error_type == "mac_mismatch" for e in report_bad.errors)
    assert isinstance(report_bad.errors[0], VerifyError)


def test_key_store_file_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EnvKeyStore and FileKeyStore should return expected keys."""
    from fapilog_tamper.verify import EnvKeyStore, FileKeyStore

    key = _hmac_key()
    monkeypatch.setenv("KID_FILE", b64url_encode(key))
    env_store = EnvKeyStore()
    assert env_store.get_key("KID_FILE") == key

    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    (key_dir / "kid.key").write_bytes(key)
    file_store = FileKeyStore(key_dir)
    assert file_store.get_key("kid") == key


@pytest.mark.asyncio
async def test_verify_chain_across_files(tmp_path: Path) -> None:
    """Cross-file verification should respect continues_from."""
    from fapilog_tamper.verify import (
        EnvKeyStore,
        Verifier,
        verify_chain_across_files,
        write_manifest,
    )

    key = _hmac_key()
    os.environ["KID_ENV"] = b64url_encode(key)
    store = EnvKeyStore()
    Verifier(store)

    # File 1
    records1: list[dict] = []
    for seq in (1, 2):
        rec, _ = _build_record(seq, f"2025-01-01T00:00:0{seq}Z", key, "KID_ENV")
        records1.append(rec)
    path1 = tmp_path / "f1.jsonl"
    with open(path1, "w", encoding="utf-8") as f:
        for rec in records1:
            f.write(json.dumps(rec) + "\n")
    manifest1 = write_manifest(path1, records1, key, "KID_ENV", algo="HMAC-SHA256")

    # File 2 continues chain
    records2: list[dict] = []
    for seq in (3, 4):
        rec, _ = _build_record(seq, f"2025-01-01T00:00:0{seq}Z", key, "KID_ENV")
        records2.append(rec)
    path2 = tmp_path / "f2.jsonl"
    with open(path2, "w", encoding="utf-8") as f:
        for rec in records2:
            f.write(json.dumps(rec) + "\n")
    write_manifest(
        path2, records2, key, "KID_ENV", algo="HMAC-SHA256", continues_from=manifest1
    )

    report = await verify_chain_across_files([path1, path2], store)
    assert report.valid is True
    assert report.manifest_valid is True

    # Tamper order
    bad_report = await verify_chain_across_files([path2, path1], store)
    assert bad_report.valid is False
    assert bad_report.chain_valid is False


def test_cli_verify_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI verify command should return 0 on success, 1 on failure, and support JSON output."""
    key = _hmac_key()
    monkeypatch.setenv("KID_ENV", b64url_encode(key))

    records: list[dict] = []
    for seq in (1, 2):
        rec, _ = _build_record(seq, f"2025-01-01T00:00:0{seq}Z", key, "KID_ENV")
        records.append(rec)

    log_path = tmp_path / "audit.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    from fapilog_tamper.verify import write_manifest

    manifest_path = write_manifest(
        log_path, records, key, "KID_ENV", algo="HMAC-SHA256"
    )

    cmd_base = [
        sys.executable,
        "-m",
        "fapilog_tamper.cli",
        "verify",
        str(log_path),
        "--manifest",
        str(manifest_path),
        "--key-env",
        "KID_ENV",
        "--format",
        "json",
    ]
    # Pass PYTHONPATH so subprocess can find fapilog_tamper
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_tamper_src) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(cmd_base, capture_output=True, text=True, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["valid"] is True

    # Tamper file and expect failure
    tampered = dict(records[1])
    tampered["integrity"] = dict(tampered["integrity"])
    tampered["integrity"]["mac"] = b64url_encode(b"badmac")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(records[0]) + "\n")
        f.write(json.dumps(tampered) + "\n")
    result_bad = subprocess.run(cmd_base, capture_output=True, text=True, env=env)
    assert result_bad.returncode == 1
    assert "mac_mismatch" in result_bad.stdout or "mac_mismatch" in result_bad.stderr


@pytest.mark.asyncio
async def test_self_checker_emits_warning(tmp_path: Path) -> None:
    """run_self_check should warn via diagnostics on failure."""
    from fapilog_tamper.verify import EnvKeyStore, Verifier, run_self_check

    from fapilog.core import diagnostics

    key = _hmac_key()
    os.environ["KID_ENV"] = b64url_encode(key)
    store = EnvKeyStore()
    verifier = Verifier(store)

    log_path = tmp_path / "audit.jsonl"
    # Intentionally write corrupted record to trigger warning
    log_path.write_text(json.dumps({"bad": "record"}))

    os.environ["FAPILOG_CORE__INTERNAL_LOGGING_ENABLED"] = "1"
    diagnostics._reset_for_tests()
    messages: list[dict[str, Any]] = []
    diagnostics.set_writer_for_tests(lambda p: messages.append(p))
    await run_self_check([log_path], verifier)
    assert messages  # warning emitted for missing MAC/chain issues
