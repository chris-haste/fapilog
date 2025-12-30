"""
Configuration model for tamper-evident logging.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TamperConfig(BaseModel):
    """User-facing configuration for the tamper plugin."""

    enabled: bool = False
    algorithm: Literal["HMAC-SHA256", "Ed25519"] = "HMAC-SHA256"
    key_id: str = ""
    key_source: Literal["env", "file", "kms", "vault"] = "env"
    key_env_var: str = "FAPILOG_TAMPER_KEY"
    key_file_path: str | None = None
    state_dir: str = ".fapilog-chainstate"
    fsync_on_write: bool = False
    fsync_on_rotate: bool = True
    compress_rotated: bool = False
    rotate_chain: bool = False
    verify_on_close: bool = False
    alert_on_failure: bool = True
