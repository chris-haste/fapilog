"""
Sealed sink wrapper that emits signed manifests on rotation.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fapilog.plugins.sinks import BaseSink

from .canonical import b64url_decode, b64url_encode
from .config import TamperConfig

try:  # Optional Ed25519 dependency
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover - optional dep
    SigningKey = None  # type: ignore[assignment]


@dataclass
class FileMetadata:
    """Tracks metadata for the current file."""

    filename: str
    created_ts: datetime
    record_count: int = 0
    first_seq: int | None = None
    last_seq: int | None = None
    first_ts: str | None = None
    last_ts: str | None = None
    root_chain_hash: bytes | None = None
    continues_from: str | None = None


class ManifestGenerator:
    """Generates signed manifests for rotated files."""

    def __init__(self, config: TamperConfig, key: bytes | None) -> None:
        self._config = config
        self._key = key
        self._signing_key: SigningKey | None = None
        if self._config.algorithm == "Ed25519" and key and SigningKey:
            try:
                self._signing_key = SigningKey(key)
            except Exception:  # pragma: no cover - defensive path
                self._signing_key = None

    def generate(self, metadata: FileMetadata, closed_ts: datetime) -> dict[str, Any]:
        manifest = {
            "version": "1.0",
            "file": metadata.filename,
            "created_ts": metadata.created_ts.isoformat().replace("+00:00", "Z"),
            "closed_ts": closed_ts.isoformat().replace("+00:00", "Z"),
            "record_count": metadata.record_count,
            "first_seq": metadata.first_seq,
            "last_seq": metadata.last_seq,
            "first_ts": metadata.first_ts,
            "last_ts": metadata.last_ts,
            "root_chain_hash": b64url_encode(metadata.root_chain_hash)
            if metadata.root_chain_hash
            else None,
            "algo": self._config.algorithm,
            "key_id": self._config.key_id,
            "signature_algo": self._config.algorithm,
            "integrity_version": "1.0",
        }
        if metadata.continues_from is not None:
            manifest["continues_from"] = metadata.continues_from

        signature = self._sign_manifest(manifest)
        if signature:
            manifest["signature"] = b64url_encode(signature)
        return manifest

    def _sign_manifest(self, manifest: dict[str, Any]) -> bytes | None:
        if not self._key:
            return None
        payload = self._canonical_manifest_payload(manifest)
        if self._config.algorithm == "HMAC-SHA256":
            return hmac.new(self._key, payload, hashlib.sha256).digest()
        if self._config.algorithm == "Ed25519" and self._signing_key:
            return self._signing_key.sign(payload).signature
        return None  # pragma: no cover - unsupported algorithm guard

    @staticmethod
    def _canonical_manifest_payload(manifest: dict[str, Any]) -> bytes:
        payload = {k: v for k, v in manifest.items() if k != "signature"}
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return serialized.encode("utf-8")


class SealedSink(BaseSink):
    """Sink wrapper that generates signed manifests on rotation."""

    def __init__(
        self, inner_sink: BaseSink, config: TamperConfig, *, key: bytes | None = None
    ) -> None:
        self._inner = inner_sink
        self._config = config
        self._key = key
        self._signing_key: SigningKey | None = None
        self._lock = asyncio.Lock()
        self._current_file: FileMetadata | None = None
        self._previous_root: str | None = None
        self._manifest_generator: ManifestGenerator | None = None

    async def start(self) -> None:
        await self._maybe_call(self._inner, "start")
        await self._load_key_if_needed()
        self._manifest_generator = ManifestGenerator(self._config, self._key)
        self._current_file = FileMetadata(
            filename=self._get_current_filename(),
            created_ts=datetime.now(timezone.utc),
            continues_from=self._previous_root
            if not self._config.rotate_chain
            else None,
        )

    async def stop(self) -> None:
        if self._current_file and self._current_file.record_count > 0:
            await self._emit_manifest()
        await self._maybe_call(self._inner, "stop")

    async def write(self, entry: dict[str, Any]) -> None:
        if self._current_file is None:
            self._current_file = FileMetadata(
                filename=self._get_current_filename(),
                created_ts=datetime.now(timezone.utc),
                continues_from=self._previous_root
                if not self._config.rotate_chain
                else None,
            )

        async with self._lock:
            integrity = entry.get("integrity", {}) if isinstance(entry, dict) else {}
            seq = integrity.get("seq")
            chain_hash = integrity.get("chain_hash")
            ts = entry.get("timestamp") if isinstance(entry, dict) else None

            if self._current_file.first_seq is None:
                self._current_file.first_seq = seq
                self._current_file.first_ts = ts

            self._current_file.last_seq = seq
            self._current_file.last_ts = ts
            self._current_file.record_count += 1
            if chain_hash:
                try:
                    self._current_file.root_chain_hash = b64url_decode(chain_hash)
                except Exception:
                    self._current_file.root_chain_hash = None

        await self._maybe_call(self._inner, "write", entry)

        if self._config.fsync_on_write:
            await self._fsync_current_file()

    async def rotate(self) -> None:
        async with self._lock:
            await self._emit_manifest()
            await self._maybe_call(self._inner, "rotate")
            self._current_file = FileMetadata(
                filename=self._get_current_filename(),
                created_ts=datetime.now(timezone.utc),
                continues_from=self._previous_root
                if not self._config.rotate_chain
                else None,
            )

    async def _emit_manifest(self) -> None:
        if not self._current_file:  # pragma: no cover - defensive
            return
        if self._manifest_generator is None:
            self._manifest_generator = ManifestGenerator(self._config, self._key)

        manifest = self._manifest_generator.generate(
            self._current_file,
            closed_ts=datetime.now(timezone.utc),
        )
        manifest_path = Path(self._current_file.filename + ".manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            manifest_path.write_text,
            json.dumps(manifest, separators=(",", ":"), ensure_ascii=False),
            "utf-8",
        )
        # Update chain continuity tracker
        root_hash = manifest.get("root_chain_hash")
        if root_hash:
            self._previous_root = root_hash
        if self._config.compress_rotated:
            await self._compress_file(self._current_file.filename)

    async def _compress_file(self, filename: str) -> None:
        src = Path(filename)
        if not src.exists():
            return
        dest = Path(str(filename) + ".gz")
        temp_dest = dest.with_suffix(dest.suffix + ".tmp")

        def _do_compress() -> None:
            with open(src, "rb") as f_in, gzip.open(temp_dest, "wb") as f_out:
                while True:
                    chunk = f_in.read(8192)
                    if not chunk:
                        break
                    f_out.write(chunk)
                f_out.flush()
                os.fsync(f_out.fileno())
            os.replace(temp_dest, dest)
            try:
                os.remove(src)
            except Exception:  # pragma: no cover - best effort cleanup
                pass

        await asyncio.to_thread(_do_compress)

    async def _fsync_current_file(self) -> None:
        filename = self._get_current_filename()
        path = Path(filename)
        if not path.exists():
            return

        def _do_fsync() -> None:
            try:
                with open(path, "rb") as f:
                    os.fsync(f.fileno())
            except Exception:  # pragma: no cover - fsync best effort
                return

        await asyncio.to_thread(_do_fsync)

    async def write_serialized(self, view: Any) -> Any:
        """Delegate serialized writes when supported by the inner sink."""
        writer = getattr(self._inner, "write_serialized", None)
        if writer is None:
            return await self.write(view)
        if asyncio.iscoroutinefunction(writer):
            return await writer(view)
        try:
            return writer(view)
        except Exception:  # pragma: no cover - delegate failure guarded
            return None

    def _get_current_filename(self) -> str:
        for attr in ("path", "file_path", "filename", "name"):
            if hasattr(self._inner, attr):
                candidate = getattr(self._inner, attr)
                if callable(candidate):
                    candidate = candidate()
                if candidate:
                    return str(candidate)
        return str(Path(self._config.state_dir) / "fapilog.log")

    async def _maybe_call(self, obj: Any, method: str, *args: Any) -> Any:
        target = getattr(obj, method, None)
        if target is None:
            return None
        if asyncio.iscoroutinefunction(target):
            return await target(*args)
        try:
            return target(*args)
        except Exception:  # pragma: no cover - defensive guard
            return None

    async def _load_key_if_needed(self) -> None:
        if self._key:
            return
        raw: bytes | None = None
        if self._config.key_source == "env":
            env_val = os.getenv(self._config.key_env_var)
            raw = env_val.encode("utf-8") if env_val else None
        elif self._config.key_source == "file" and self._config.key_file_path:
            try:
                raw = await asyncio.to_thread(
                    Path(self._config.key_file_path).read_bytes
                )
            except Exception:  # pragma: no cover - file read error handled
                raw = None

        if raw is None:
            return
        self._key = self._decode_key(raw)
        if self._config.algorithm == "Ed25519" and self._key and SigningKey:
            try:
                self._signing_key = SigningKey(self._key)
            except Exception:  # pragma: no cover - defensive
                self._signing_key = None

    @staticmethod
    def _decode_key(raw: bytes) -> bytes | None:
        padding = b"=" * (-len(raw) % 4)
        candidates = []
        try:
            candidates.append(b64url_decode((raw + padding).decode("ascii")))
        except Exception:  # pragma: no cover - decode failure path
            pass
        candidates.append(raw)
        for candidate in candidates:
            if len(candidate) == 32:
                return candidate
        return None  # pragma: no cover - invalid length

    @staticmethod
    def _canonical_manifest_payload_static(manifest: dict[str, Any]) -> bytes:
        """Expose canonicalization for test verification."""
        return ManifestGenerator._canonical_manifest_payload(manifest)
