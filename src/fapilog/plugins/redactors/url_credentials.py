from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ...core import diagnostics


@dataclass
class UrlCredentialsConfig:
    max_string_length: int = 4096


class UrlCredentialsRedactor:
    name = "url-credentials"

    def __init__(self, *, config: UrlCredentialsConfig | None = None) -> None:
        cfg = config or UrlCredentialsConfig()
        self._max_len = int(cfg.max_string_length)

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


# Minimal PLUGIN_METADATA for discovery
PLUGIN_METADATA = {
    "name": "url-credentials",
    "version": "1.0.0",
    "author": "Fapilog Core",
    "plugin_type": "redactor",
    "entry_point": ("fapilog.plugins.redactors.url_credentials:UrlCredentialsRedactor"),
    "description": ("Strips user:pass@ credentials from URL-like strings."),
    "api_version": "1.0",
}

# Mark referenced for static analyzers
_VULTURE_USED: tuple[object, ...] = (UrlCredentialsRedactor,)
