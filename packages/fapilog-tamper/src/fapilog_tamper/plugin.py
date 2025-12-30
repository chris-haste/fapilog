"""
Integrity plugin entry point for tamper-evident logging.
"""

from __future__ import annotations

from typing import Any

from .config import TamperConfig
from .enricher import IntegrityEnricher
from .sealed_sink import SealedSink


class _TamperSealedPlugin:
    """
    Entry point object exposed via ``fapilog.integrity``.

    Subsequent stories will replace the placeholder enricher and sink wrapper
    with full tamper-evident implementations.
    """

    name = "tamper-sealed"

    def _load_config(self, config: dict[str, Any] | None) -> TamperConfig:
        return TamperConfig(**(config or {}))

    def _require_crypto(self) -> None:
        """Ensure crypto dependency is available; defer import until needed."""
        try:
            import cryptography  # noqa: F401
        except Exception as exc:  # pragma: no cover - defensive path
            raise RuntimeError(
                "cryptography is required for fapilog-tamper; install the package "
                "with crypto extras"
            ) from exc

    def get_enricher(self, config: dict[str, Any] | None = None) -> Any:
        """Return IntegrityEnricher configured for the stream."""
        self._require_crypto()
        cfg = self._load_config(config)
        return IntegrityEnricher(cfg)

    def wrap_sink(self, sink: Any, config: dict[str, Any] | None = None) -> Any:
        """Wrap a sink with sealing logic and manifest generation."""
        self._require_crypto()
        cfg = self._load_config(config)
        return SealedSink(sink, cfg)


# Entry point target; exposes an instance to integrate with fapilog pipeline
TamperSealedPluginClass = _TamperSealedPlugin
TamperSealedPlugin = _TamperSealedPlugin()
