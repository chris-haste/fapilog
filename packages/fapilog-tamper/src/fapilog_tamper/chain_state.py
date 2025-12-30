"""
Chain state persistence for tamper-evident logging.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .canonical import b64url_decode, b64url_encode
from .types import ChainState

GENESIS_HASH = b"\x00" * 32


class ChainStatePersistence:
    """Persists chain state to disk for restart recovery."""

    def __init__(self, state_dir: str, stream_id: str) -> None:
        self._path = Path(state_dir) / f"{stream_id}.chainstate"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def load(self) -> ChainState:
        """Load state from disk or return genesis state."""
        if not self._path.exists():
            return ChainState(seq=0, prev_chain_hash=GENESIS_HASH, key_id="")
        try:
            text = await asyncio.to_thread(self._path.read_text, encoding="utf-8")
            data = json.loads(text)
            return ChainState(
                seq=int(data.get("seq", 0)),
                prev_chain_hash=b64url_decode(data["prev_chain_hash"]),
                key_id=data.get("key_id", ""),
            )
        except Exception as exc:
            try:
                from fapilog.core import diagnostics

                diagnostics.warn(
                    "tamper", "chain state corrupt, resetting", error=str(exc)
                )
            except Exception:
                pass
            return ChainState(seq=0, prev_chain_hash=GENESIS_HASH, key_id="")

    async def save(self, state: ChainState) -> None:
        """Atomically persist state to disk."""
        data = {
            "seq": state.seq,
            "prev_chain_hash": b64url_encode(state.prev_chain_hash),
            "key_id": state.key_id,
            "last_updated": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        serialized = json.dumps(data, separators=(",", ":"), sort_keys=True)
        temp_path = self._path.with_suffix(".tmp")

        def _write_atomic() -> None:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self._path)

        await asyncio.to_thread(_write_atomic)
