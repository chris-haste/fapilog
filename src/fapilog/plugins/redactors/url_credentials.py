from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from ...core import diagnostics
from ..utils import parse_plugin_config


class UrlCredentialsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    max_string_length: int = Field(default=4096, ge=1)


class UrlCredentialsRedactor:
    name = "url_credentials"

    def __init__(
        self, *, config: UrlCredentialsConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(UrlCredentialsConfig, config, **kwargs)
        self._max_len = cfg.max_string_length

    async def start(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def stop(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def redact(self, event: dict) -> dict:
        root = dict(event)
        try:
            self._strip_credentials(root, depth=0, scanned=0)
        except Exception:
            # Defensive: contain any unexpected errors
            diagnostics.warn(
                "redactor",
                "url-credentials redaction error",
            )
        return root

    def _strip_credentials(self, node: Any, *, depth: int, scanned: int) -> int:
        # Depth/scan guardrails: reuse conservative defaults
        if depth > 16 or scanned > 1000:
            return scanned
        if isinstance(node, dict):
            for k, v in list(node.items()):
                scanned += 1
                if isinstance(v, str):
                    node[k] = self._scrub_string(v)
                elif isinstance(v, (dict, list)):
                    scanned = self._strip_credentials(
                        v, depth=depth + 1, scanned=scanned
                    )
        elif isinstance(node, list):
            for idx, item in enumerate(list(node)):
                scanned += 1
                if isinstance(item, str):
                    node[idx] = self._scrub_string(item)
                elif isinstance(item, (dict, list)):
                    scanned = self._strip_credentials(
                        item, depth=depth + 1, scanned=scanned
                    )
        return scanned

    def _scrub_string(self, value: str) -> str:
        if not value or len(value) > self._max_len:
            return value
        try:
            parts = urlsplit(value)
            # Only scrub if there's userinfo (username or password)
            if parts.username or parts.password:
                # Reconstruct netloc without userinfo
                netloc = parts.hostname or ""
                if parts.port:
                    netloc = f"{netloc}:{parts.port}"
                return urlunsplit(
                    (
                        parts.scheme,
                        netloc,
                        parts.path,
                        parts.query,
                        parts.fragment,
                    )
                )
        except Exception:
            # Not a parseable URL; leave as-is
            return value
        return value

    async def health_check(self) -> bool:
        """Verify URL parsing capability is available.

        Checks that urllib.parse is functional and config is valid.
        """
        try:
            # Verify max_len is positive
            if self._max_len <= 0:
                return False
            # Verify URL parsing works
            parts = urlsplit("https://user:pass@example.com/path")
            _ = urlunsplit((parts.scheme, parts.hostname or "", "", "", ""))
            return True
        except Exception:
            return False


# Plugin metadata for discovery
PLUGIN_METADATA = {
    "name": "url_credentials",
    "version": "1.0.0",
    "author": "Fapilog Core",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.url_credentials:UrlCredentialsRedactor",
    "description": "Strips user:pass@ credentials from URL-like strings.",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}

# Mark referenced for static analyzers
_VULTURE_USED: tuple[object, ...] = (UrlCredentialsRedactor,)
