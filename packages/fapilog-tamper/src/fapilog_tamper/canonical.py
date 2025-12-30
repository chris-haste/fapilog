"""
Canonical serialization and base64url helpers for tamper-evident logging.
"""

from __future__ import annotations

import base64
import json
from typing import Any


def canonicalize(event: dict[str, Any]) -> bytes:
    """
    Produce deterministic JSON bytes for the given event.

    - Sorts keys for stability
    - Uses compact separators
    - UTF-8 encoding
    - Excludes any pre-existing ``integrity`` field
    """
    payload = {k: v for k, v in event.items() if k != "integrity"}
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return serialized.encode("utf-8")


def b64url_encode(data: bytes) -> str:
    """Encode bytes using RFC 4648 base64url without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(s: str) -> bytes:
    """Decode RFC 4648 base64url string without requiring padding."""
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)
