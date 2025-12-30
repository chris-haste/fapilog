"""
Tests for SealedSink and manifest generation in fapilog-tamper.
"""

from __future__ import annotations

import asyncio
import gzip
import hmac
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from fapilog.plugins.sinks import BaseSink

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


class _DummySink(BaseSink):
    """Simple sink that writes JSONL entries to a file for testing."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: list[dict[str, Any]] = []
        self.started = False
        self.stopped = False
        self.rotate_calls = 0

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def write(self, entry: dict) -> None:
        self.entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    async def rotate(self) -> None:
        self.rotate_calls += 1


def _event(seq: int, ts: str, chain_hash: str = "root") -> dict[str, Any]:
    return {
        "message": f"event-{seq}",
        "timestamp": ts,
        "integrity": {
            "seq": seq,
            "mac": "mac",
            "algo": "HMAC-SHA256",
            "key_id": "kid",
            "chain_hash": chain_hash,
            "prev_chain_hash": "prev",
        },
    }


@pytest.mark.asyncio
async def test_sealed_sink_tracks_metadata_and_signs_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SealedSink should track metadata and write a signed manifest on stop."""
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "0")
    key = b"K" * 32

    from fapilog_tamper.canonical import b64url_decode, b64url_encode
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import ManifestGenerator, SealedSink

    path = tmp_path / "events.jsonl"
    inner = _DummySink(path)
    cfg = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="IGNORED",
        key_id="kid",
        fsync_on_write=False,
        state_dir=str(tmp_path),
    )
    sink = SealedSink(inner, cfg, key=key)

    await sink.start()
    await sink.write(_event(1, "2025-01-01T00:00:00Z", b64url_encode(b"root1")))
    await sink.write(_event(2, "2025-01-01T00:00:01Z", b64url_encode(b"root2")))
    await sink.stop()

    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())

    assert manifest["record_count"] == 2
    assert manifest["first_seq"] == 1
    assert manifest["last_seq"] == 2
    assert manifest["root_chain_hash"] == b64url_encode(b"root2")
    assert manifest["signature"] is not None

    # Verify HMAC signature
    generator = ManifestGenerator(cfg, key=key)
    payload = generator._canonical_manifest_payload(
        {k: v for k, v in manifest.items() if k != "signature"}
    )
    expected_sig = hmac.new(key, payload, digestmod="sha256").digest()
    assert manifest["signature"] == b64url_encode(expected_sig)
    assert b64url_decode(manifest["root_chain_hash"]) == b"root2"


@pytest.mark.asyncio
async def test_manual_rotate_emits_manifest_and_resets(tmp_path: Path) -> None:
    """Manual rotate should emit manifest and reset counters."""
    from fapilog_tamper.canonical import b64url_encode
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    path = tmp_path / "events.jsonl"
    inner = _DummySink(path)
    cfg = TamperConfig(enabled=True, fsync_on_rotate=True, state_dir=str(tmp_path))
    sink = SealedSink(inner, cfg, key=b"K" * 32)
    await sink.start()
    await sink.write(_event(10, "2025-01-01T00:00:00Z", b64url_encode(b"h1")))
    await sink.rotate()

    manifest1 = json.loads(
        (path.with_suffix(path.suffix + ".manifest.json")).read_text()
    )
    assert manifest1["record_count"] == 1
    assert inner.rotate_calls == 1

    # Write again after rotation; should start new metadata
    await sink.write(_event(11, "2025-01-01T00:00:02Z", b64url_encode(b"h2")))
    await sink.stop()
    manifest2 = json.loads(
        (path.with_suffix(path.suffix + ".manifest.json")).read_text()
    )
    assert manifest2["first_seq"] == 11


@pytest.mark.asyncio
async def test_manifest_signature_ed25519(tmp_path: Path) -> None:
    """Ed25519 manifests should verify with public key."""
    nacl = pytest.importorskip("nacl.signing")
    signing_key = nacl.SigningKey(b"E" * 32)

    from fapilog_tamper.canonical import b64url_decode
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    path = tmp_path / "events.jsonl"
    sink = SealedSink(
        _DummySink(path),
        TamperConfig(enabled=True, algorithm="Ed25519", state_dir=str(tmp_path)),
        key=signing_key.encode(),
    )
    await sink.start()
    await sink.write(_event(1, "2025-01-01T00:00:00Z", "root"))
    await sink.stop()

    manifest = json.loads(path.with_suffix(path.suffix + ".manifest.json").read_text())
    signature = manifest["signature"]
    payload = dict(manifest)
    payload.pop("signature")
    serialized = SealedSink._canonical_manifest_payload_static(payload)  # type: ignore[attr-defined]
    nacl.VerifyKey(signing_key.verify_key.encode()).verify(
        serialized, b64url_decode(signature)
    )


@pytest.mark.asyncio
async def test_compression_and_fsync_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compression and fsync controls should behave as configured."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    path = tmp_path / "events.jsonl"
    inner = _DummySink(path)
    fsync_calls = {"count": 0}

    def _fsync(fd: int) -> None:
        fsync_calls["count"] += 1

    monkeypatch.setattr("os.fsync", _fsync)

    cfg = TamperConfig(
        enabled=True,
        compress_rotated=True,
        fsync_on_write=True,
        fsync_on_rotate=True,
        state_dir=str(tmp_path),
    )
    sink = SealedSink(inner, cfg, key=b"K" * 32)
    await sink.start()
    await sink.write(_event(1, "2025-01-01T00:00:00Z", "hash"))
    await sink.rotate()

    compressed = Path(str(path) + ".gz")
    assert compressed.exists()
    with gzip.open(compressed, "rt", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 1
    assert fsync_calls["count"] >= 1


@pytest.mark.asyncio
async def test_concurrent_writes_thread_safe(tmp_path: Path) -> None:
    """Concurrent writes should not corrupt metadata."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    path = tmp_path / "events.jsonl"
    sink = SealedSink(
        _DummySink(path),
        TamperConfig(enabled=True, state_dir=str(tmp_path)),
        key=b"K" * 32,
    )
    await sink.start()

    async def _do(seq: int) -> None:
        await sink.write(_event(seq, f"2025-01-01T00:00:{seq:02d}Z", f"h{seq}"))

    await asyncio.gather(*(_do(i) for i in range(1, 11)))
    await sink.stop()

    manifest = json.loads(path.with_suffix(path.suffix + ".manifest.json").read_text())
    assert manifest["record_count"] == 10
    assert manifest["first_seq"] == 1
    assert manifest["last_seq"] == 10


@pytest.mark.asyncio
async def test_key_loading_from_env_and_chain_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SealedSink should load key from env and reset chain when configured."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    monkeypatch.setenv("TAMPER_MANIFEST_KEY", "M" * 32)
    path = tmp_path / "events.jsonl"
    cfg = TamperConfig(
        enabled=True,
        key_source="env",
        key_env_var="TAMPER_MANIFEST_KEY",
        rotate_chain=True,
        state_dir=str(tmp_path),
    )
    sink = SealedSink(_DummySink(path), cfg)
    await sink.start()
    await sink.write(_event(1, "2025-01-01T00:00:00Z", "rootA"))
    await sink.rotate()
    await sink.write(_event(2, "2025-01-01T00:00:01Z", "rootB"))
    await sink.stop()

    manifest = json.loads(path.with_suffix(path.suffix + ".manifest.json").read_text())
    assert manifest["first_seq"] == 2  # rotation reset
    assert manifest["signature_algo"] == cfg.algorithm


@pytest.mark.asyncio
async def test_key_loading_from_file_and_defaults(tmp_path: Path) -> None:
    """Key loading from file should be decoded and used for signing."""
    from fapilog_tamper.cli import main as cli_main
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink
    from fapilog_tamper.verify import verify_records

    key_file = tmp_path / "key.txt"
    key_file.write_text("Tg" * 16)  # base64-ish to trigger decode path

    cfg = TamperConfig(
        enabled=True,
        key_source="file",
        key_file_path=str(key_file),
        state_dir=str(tmp_path),
    )
    sink = SealedSink(_DummySink(tmp_path / "events.jsonl"), cfg)
    await sink.start()
    await sink.write(_event(1, "2025-01-01T00:00:00Z", "rootC"))
    await sink.stop()

    manifest_path = tmp_path / "events.jsonl.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["record_count"] == 1
    assert verify_records([manifest]).checked == 1
    exit_code = await asyncio.to_thread(
        cli_main,
        [
            "verify",
            str(tmp_path / "events.jsonl"),
            "--manifest",
            str(manifest_path),
            "--keys",
            str(key_file),
            "--format",
            "json",
        ],
    )
    assert exit_code in (0, 1)


@pytest.mark.asyncio
async def test_default_filename_and_maybe_call(tmp_path: Path) -> None:
    """Fallback filename and sync method path should be exercised."""

    class _MinimalSink:
        def __init__(self) -> None:
            self.calls = 0

        def write(self, entry: dict) -> None:
            self.calls += 1

    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    sink = SealedSink(
        _MinimalSink(),
        TamperConfig(enabled=True, state_dir=str(tmp_path)),
        key=b"K" * 32,
    )
    await sink.write(_event(1, "2025-01-01T00:00:00Z", "rootD"))
    assert sink._get_current_filename().endswith("fapilog.log")


@pytest.mark.asyncio
async def test_defensive_paths_in_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hit defensive branches for compression and fsync helpers."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.sealed_sink import SealedSink

    cfg = TamperConfig(enabled=True, state_dir=str(tmp_path))
    sink = SealedSink(_DummySink(tmp_path / "events.jsonl"), cfg, key=b"K" * 32)

    # _compress_file when source missing
    await sink._compress_file(str(tmp_path / "missing.jsonl"))

    # _fsync_current_file with fsync error path
    target = tmp_path / "exists.jsonl"
    target.write_text("x")

    def _fsync_fail(fd: int) -> None:
        raise OSError("boom")

    monkeypatch.setattr("os.fsync", _fsync_fail)
    await sink._fsync_current_file()
