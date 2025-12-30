"""
Integrity enricher that computes MACs and maintains hash chains.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fapilog.plugins.enrichers import BaseEnricher

from .canonical import b64url_encode, canonicalize
from .chain_state import GENESIS_HASH, ChainState, ChainStatePersistence
from .config import TamperConfig

try:  # Optional Ed25519 dependency
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover - optional dep
    SigningKey = None  # type: ignore[assignment]


class IntegrityEnricher(BaseEnricher):
    """Enricher that adds tamper-evident MAC and chain fields."""

    name = "tamper-sealed"

    def __init__(self, config: TamperConfig, stream_id: str = "default") -> None:
        self._config = config
        self._stream_id = stream_id
        self._lock = asyncio.Lock()
        self._key: bytes | None = None
        self._signing_key: SigningKey | None = None
        self._state: ChainState | None = None
        self._persistence: ChainStatePersistence | None = None

    async def start(self) -> None:
        self._persistence = ChainStatePersistence(
            state_dir=self._config.state_dir, stream_id=self._stream_id
        )
        self._key, self._signing_key = await self._load_keys()
        self._state = await self._persistence.load()
        if self._state.key_id == "":
            self._state.key_id = self._config.key_id

    async def stop(self) -> None:
        if self._state and self._persistence:
            await self._persistence.save(self._state)
        # Best-effort clearing of sensitive material
        self._key = None
        self._signing_key = None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self._config.enabled:
            return {}
        if self._config.algorithm == "Ed25519" and not self._signing_key:
            return {}
        if self._config.algorithm == "HMAC-SHA256" and not self._key:
            return {}

        # Ensure state exists
        if self._state is None:
            self._state = ChainState(seq=0, prev_chain_hash=GENESIS_HASH, key_id="")

        payload = canonicalize(event)
        timestamp_value = event.get("timestamp") or datetime.now(timezone.utc)
        if isinstance(timestamp_value, datetime):
            ts_str = (
                timestamp_value.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        else:
            ts_str = str(timestamp_value)

        async with self._lock:
            seq = self._state.seq + 1

            mac = self._compute_mac(payload)

            chain_input = (
                self._state.prev_chain_hash
                + mac
                + seq.to_bytes(8, "big")
                + ts_str.encode("utf-8")
            )
            chain_hash = hashlib.sha256(chain_input).digest()
            prev_chain_hash = self._state.prev_chain_hash

            # Update state
            self._state.seq = seq
            self._state.prev_chain_hash = chain_hash
            if self._state.key_id == "":
                self._state.key_id = self._config.key_id

        return {
            "integrity": {
                "seq": seq,
                "mac": b64url_encode(mac),
                "algo": self._config.algorithm,
                "key_id": self._config.key_id,
                "chain_hash": b64url_encode(chain_hash),
                "prev_chain_hash": b64url_encode(prev_chain_hash),
            }
        }

    async def _load_keys(self) -> tuple[bytes | None, SigningKey | None]:
        """Load key material based on configuration."""
        raw: bytes | None = None
        if self._config.key_source == "env":
            env_val = os.getenv(self._config.key_env_var)
            if env_val:
                raw = env_val.encode("utf-8")
            else:
                self._warn("key not found in env", source="env")
        elif self._config.key_source == "file":
            if not self._config.key_file_path:
                self._warn("key_file_path not provided", source="file")
            else:
                try:
                    raw = await asyncio.to_thread(
                        Path(self._config.key_file_path).read_bytes
                    )
                except FileNotFoundError:
                    self._warn("key file not found", source="file")
                except Exception as exc:  # pragma: no cover - defensive
                    self._warn("failed to read key file", source="file", error=str(exc))
        else:
            self._warn("unsupported key source", source=self._config.key_source)

        key_bytes = self._decode_key(raw) if raw is not None else None
        if key_bytes is None:
            return None, None

        if self._config.algorithm == "HMAC-SHA256":
            return key_bytes, None
        if self._config.algorithm == "Ed25519":
            if SigningKey is None:  # pragma: no cover - optional dep path
                self._warn("pynacl not installed for Ed25519", source="ed25519")
                return None, None
            try:
                signing_key = SigningKey(key_bytes)
                return key_bytes, signing_key
            except Exception as exc:  # pragma: no cover - defensive
                self._warn(
                    "failed to create signing key", source="ed25519", error=str(exc)
                )
                return None, None
        self._warn("unsupported algorithm", source=self._config.algorithm)
        return None, None

    def _decode_key(self, raw: bytes) -> bytes | None:
        """Decode key material from base64url or raw bytes, enforcing 32 bytes."""
        candidates = []
        padding = b"=" * (-len(raw) % 4)
        try:
            decoded = base64.urlsafe_b64decode(raw + padding)
            candidates.append(decoded)
        except Exception:
            pass
        candidates.append(raw)
        for candidate in candidates:
            if len(candidate) == 32:
                return candidate
        self._warn("invalid key length", length=len(raw))
        return None

    def _compute_mac(self, payload: bytes) -> bytes:
        if self._config.algorithm == "HMAC-SHA256":
            assert self._key is not None  # for type checkers
            return hmac.new(self._key, payload, hashlib.sha256).digest()
        assert self._signing_key is not None  # pragma: no cover - guarded above
        return self._signing_key.sign(payload).signature

    def _warn(self, message: str, **fields: Any) -> None:
        try:
            from fapilog.core import diagnostics

            diagnostics.warn("tamper", message, **fields)
        except Exception:
            pass
