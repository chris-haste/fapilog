"""
Tests for IntegrityEnricher and chain state persistence in fapilog-tamper.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from fapilog.core import diagnostics
from fapilog.plugins.enrichers import BaseEnricher

# Add fapilog-tamper to path before importing
_tamper_src = (
    Path(__file__).resolve().parents[2] / "packages" / "fapilog-tamper" / "src"
)
if _tamper_src.exists():
    sys.path.insert(0, str(_tamper_src))

# Skip entire module if fapilog-tamper is not available
try:
    import fapilog_tamper  # noqa: F401
except ImportError:
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _fixed_event(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "event": "login",
        "user": "alice",
        "timestamp": "2025-01-01T00:00:00Z",
    }
    if extra:
        base.update(extra)
    return base


@pytest.mark.asyncio
async def test_enricher_protocol_and_hmac_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enricher should implement BaseEnricher, compute HMAC, and chain hashes."""
    monkeypatch.setenv("TAMPER_KEY_ENV", _b64url(b"K" * 32))

    from fapilog_tamper.canonical import b64url_decode, b64url_encode, canonicalize
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import GENESIS_HASH, IntegrityEnricher

    cfg = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="TAMPER_KEY_ENV",
        key_id="audit-key",
        state_dir=str(tmp_path),
    )
    enricher = IntegrityEnricher(cfg, stream_id="stream1")
    assert isinstance(enricher, BaseEnricher)

    await enricher.start()
    event = _fixed_event()
    result = await enricher.enrich(dict(event))
    await enricher.stop()

    integrity = result["integrity"]
    payload = canonicalize(event)
    expected_mac = hmac.new(b"K" * 32, payload, hashlib.sha256).digest()
    expected_chain_input = (
        GENESIS_HASH
        + expected_mac
        + (1).to_bytes(8, "big")
        + event["timestamp"].encode("utf-8")
    )
    expected_chain = hashlib.sha256(expected_chain_input).digest()

    assert integrity["seq"] == 1
    assert integrity["mac"] == b64url_encode(expected_mac)
    assert integrity["algo"] == "HMAC-SHA256"
    assert integrity["key_id"] == "audit-key"
    assert integrity["prev_chain_hash"] == b64url_encode(GENESIS_HASH)
    assert integrity["chain_hash"] == b64url_encode(expected_chain)
    # Ensure prev_chain_hash decoded equals genesis
    assert b64url_decode(integrity["prev_chain_hash"]) == GENESIS_HASH


@pytest.mark.asyncio
async def test_chain_hash_linkage_and_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chain hashes should link and persist across restarts."""
    monkeypatch.setenv("TAMPER_KEY_ENV", _b64url(b"A" * 32))

    from fapilog_tamper.canonical import b64url_decode, b64url_encode, canonicalize
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import GENESIS_HASH, IntegrityEnricher

    cfg = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="TAMPER_KEY_ENV",
        key_id="kid",
        state_dir=str(tmp_path),
    )

    enricher1 = IntegrityEnricher(cfg, stream_id="audit")
    await enricher1.start()
    event1 = _fixed_event({"timestamp": "2025-02-01T00:00:00Z"})
    event2 = _fixed_event({"timestamp": "2025-02-01T00:00:01Z"})

    r1 = await enricher1.enrich(dict(event1))
    r2 = await enricher1.enrich(dict(event2))
    await enricher1.stop()

    prev_hash_1 = b64url_decode(r1["integrity"]["chain_hash"])
    mac2 = hmac.new(b"A" * 32, canonicalize(event2), hashlib.sha256).digest()
    chain_input2 = (
        prev_hash_1
        + mac2
        + (2).to_bytes(8, "big")
        + event2["timestamp"].encode("utf-8")
    )
    expected_chain2 = hashlib.sha256(chain_input2).digest()

    assert r2["integrity"]["prev_chain_hash"] == b64url_encode(prev_hash_1)
    assert r2["integrity"]["chain_hash"] == b64url_encode(expected_chain2)

    enricher2 = IntegrityEnricher(cfg, stream_id="audit")
    await enricher2.start()
    event3 = _fixed_event({"timestamp": "2025-02-01T00:00:02Z"})
    r3 = await enricher2.enrich(dict(event3))
    await enricher2.stop()

    assert r3["integrity"]["seq"] == 3
    assert r3["integrity"]["prev_chain_hash"] == r2["integrity"]["chain_hash"]
    assert b64url_decode(r3["integrity"]["prev_chain_hash"]) != GENESIS_HASH


@pytest.mark.asyncio
async def test_ed25519_signature(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ed25519 signatures should verify with the public key when optional dep available."""
    nacl = pytest.importorskip("nacl.signing")
    signing_key = nacl.SigningKey(b"\x11" * 32)
    monkeypatch.setenv("TAMPER_KEY_ENV", _b64url(signing_key.encode()))

    from fapilog_tamper.canonical import b64url_decode, canonicalize
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher

    cfg = TamperConfig(
        enabled=True,
        algorithm="Ed25519",
        key_source="env",
        key_env_var="TAMPER_KEY_ENV",
        state_dir=str(tmp_path),
    )
    enricher = IntegrityEnricher(cfg)
    await enricher.start()
    event = _fixed_event()
    r = await enricher.enrich(dict(event))
    await enricher.stop()

    signature = b64url_decode(r["integrity"]["mac"])
    payload = canonicalize(event)
    signing_key.verify_key.verify(payload, signature)  # will raise if invalid


@pytest.mark.asyncio
async def test_concurrent_enrichment_thread_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent enrich calls should produce unique, monotonic sequences."""
    monkeypatch.setenv("TAMPER_KEY_ENV", _b64url(b"B" * 32))

    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher

    cfg = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="TAMPER_KEY_ENV",
        state_dir=str(tmp_path),
    )
    enricher = IntegrityEnricher(cfg)
    await enricher.start()

    async def _do_enrich(idx: int) -> dict[str, Any]:
        base_ts = datetime(2025, 2, 1, 0, 0, idx, tzinfo=timezone.utc)
        ev = _fixed_event({"timestamp": base_ts.isoformat().replace("+00:00", "Z")})
        return await enricher.enrich(ev)

    results: list[dict[str, Any]] = await asyncio.gather(
        *(_do_enrich(i) for i in range(50))
    )
    await enricher.stop()

    seqs = sorted(r["integrity"]["seq"] for r in results)
    assert seqs == list(range(1, 51))
    assert len({r["integrity"]["chain_hash"] for r in results}) == 50


@pytest.mark.asyncio
async def test_chain_state_persistence_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ChainStatePersistence should save and load state atomically."""
    from fapilog_tamper.chain_state import (
        GENESIS_HASH,
        ChainState,
        ChainStatePersistence,
    )

    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "1")
    persistence = ChainStatePersistence(state_dir=str(tmp_path), stream_id="audit")
    state = ChainState(seq=5, prev_chain_hash=b"Z" * 32, key_id="kid")
    await persistence.save(state)
    loaded = await persistence.load()

    assert loaded.seq == 5
    assert loaded.key_id == "kid"
    assert loaded.prev_chain_hash == state.prev_chain_hash

    # Corrupt the file and ensure recovery to genesis
    state_path = Path(tmp_path) / "audit.chainstate"
    state_path.write_text("{not-json}")
    diagnostics._reset_for_tests()
    messages: list[dict[str, Any]] = []
    diagnostics.set_writer_for_tests(lambda p: messages.append(p))
    recovered = await persistence.load()

    assert recovered.seq == 0
    assert recovered.prev_chain_hash == GENESIS_HASH
    assert any(msg.get("component") == "tamper" for msg in messages)


@pytest.mark.asyncio
async def test_key_loading_env_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keys should load from env and file; missing key disables enrichment."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher

    key_bytes = b"M" * 32
    monkeypatch.setenv("TAMPER_KEY_ENV", _b64url(key_bytes))
    cfg_env = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="TAMPER_KEY_ENV",
        state_dir=str(tmp_path),
    )
    enricher_env = IntegrityEnricher(cfg_env, stream_id="env")
    await enricher_env.start()
    r_env = await enricher_env.enrich(_fixed_event())
    await enricher_env.stop()
    assert r_env["integrity"]["seq"] == 1

    key_file = tmp_path / "key.bin"
    key_file.write_bytes(key_bytes)
    cfg_file = TamperConfig(
        enabled=True,
        key_source="file",
        key_file_path=str(key_file),
        state_dir=str(tmp_path),
    )
    enricher_file = IntegrityEnricher(cfg_file, stream_id="file")
    await enricher_file.start()
    r_file = await enricher_file.enrich(_fixed_event())
    await enricher_file.stop()
    assert r_file["integrity"]["seq"] == 1

    cfg_missing = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="MISSING_KEY",
        state_dir=str(tmp_path),
    )
    enricher_missing = IntegrityEnricher(cfg_missing, stream_id="missing")
    await enricher_missing.start()
    r_missing = await enricher_missing.enrich(_fixed_event())
    await enricher_missing.stop()
    assert r_missing == {}


@pytest.mark.asyncio
async def test_enricher_disabled_and_missing_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabled enricher or missing Ed25519 key should no-op."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher

    disabled_cfg = TamperConfig(enabled=False, state_dir=str(tmp_path))
    disabled = IntegrityEnricher(disabled_cfg)
    out_disabled = await disabled.enrich(_fixed_event())
    assert out_disabled == {}

    ed_cfg = TamperConfig(
        enabled=True,
        algorithm="Ed25519",
        key_source="env",
        key_env_var="NO_ED_KEY",
        state_dir=str(tmp_path),
    )
    ed_enricher = IntegrityEnricher(ed_cfg)
    await ed_enricher.start()
    out_ed = await ed_enricher.enrich(_fixed_event())
    await ed_enricher.stop()
    assert out_ed == {}


def test_decode_key_invalid_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid key lengths and bad base64 should warn and return None."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher

    cfg = TamperConfig(enabled=True)
    enricher = IntegrityEnricher(cfg)
    messages: list[dict[str, Any]] = []
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "1")
    diagnostics._reset_for_tests()
    diagnostics.set_writer_for_tests(lambda p: messages.append(p))

    # Base64 decode error path and invalid length path
    result = enricher._decode_key(b"@@@")
    assert result is None
    assert any(m["message"] == "invalid key length" for m in messages)


def test_sink_and_enricher_helpers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test SealedSink and IntegrityEnricher directly; cli/manifests/verify covered."""
    from fapilog_tamper import (
        ChainStatePersistence,
        IntegrityEnricher,
        canonicalize,
    )
    from fapilog_tamper.canonical import b64url_decode, b64url_encode
    from fapilog_tamper.cli import main as cli_main
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import FileMetadata, ManifestGenerator, SealedSink
    from fapilog_tamper.verify import verify_records

    class _Sink:
        def __init__(self) -> None:
            self.entries: list[Any] = []

        async def write(self, entry: Any) -> None:
            self.entries.append(("write", entry))

        async def write_serialized(self, entry: Any) -> None:
            self.entries.append(("write_serialized", entry))

    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "0")
    pytest.importorskip("cryptography")

    cfg = TamperConfig(enabled=True, state_dir=str(tmp_path))
    # Create enricher directly (standard plugin path)
    enricher = IntegrityEnricher(config=cfg)
    assert isinstance(enricher, IntegrityEnricher)

    sink_inner = _Sink()
    sink = SealedSink(sink_inner, cfg, key=b"K" * 32)
    # Create wrapped sink directly via SealedSink
    wrapped = SealedSink(_Sink(), cfg, key=b"K" * 32)
    null_sink = SealedSink(object(), cfg, key=b"K" * 32)
    asyncio.run(sink.write({"k": "v"}))
    asyncio.run(sink.write_serialized({"k": "v2"}))
    asyncio.run(wrapped.write({"k": "v3"}))
    asyncio.run(null_sink.write({"noop": True}))
    asyncio.run(null_sink.write_serialized({"noop": True}))
    assert ("write", {"k": "v"}) in sink_inner.entries
    assert ("write_serialized", {"k": "v2"}) in sink_inner.entries
    assert hasattr(wrapped, "_inner")

    # Manifest generator helper
    generator = ManifestGenerator(cfg, key=b"K" * 32)
    metadata = FileMetadata(
        filename="f",
        created_ts=datetime.utcnow(),
        record_count=1,
        first_seq=1,
        last_seq=1,
        first_ts="t1",
        last_ts="t1",
        root_chain_hash=b"r",
        continues_from=None,
    )
    manifest = generator.generate(metadata, datetime.utcnow())
    assert manifest["record_count"] == 1
    report = verify_records([{"a": 1}])
    assert report.valid is True and report.checked == 1

    ChainStatePersistence(state_dir=str(tmp_path), stream_id="x")
    assert b64url_decode(b64url_encode(b"test")) == b"test"
    assert canonicalize({"z": 1, "a": 2}).startswith(b'{"a":2')

    log_path = tmp_path / "f"
    log_path.write_text("{}\n")
    exit_code = cli_main(["verify", str(log_path), "--format", "json"])
    assert exit_code in (0, 1, 2)
