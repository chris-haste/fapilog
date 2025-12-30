"""
Shared types for tamper-evident logging.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IntegrityFields:
    """Integrity metadata attached to audit events."""

    seq: int
    mac: str  # base64url encoded
    algo: str  # e.g., "HMAC-SHA256"
    key_id: str
    chain_hash: str  # base64url encoded
    prev_chain_hash: str  # base64url encoded


@dataclass
class ChainState:
    """Chain state persisted between events."""

    seq: int
    prev_chain_hash: bytes
    key_id: str
