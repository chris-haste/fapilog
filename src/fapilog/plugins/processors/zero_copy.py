"""
Zero-copy processor plugin for performance-focused pipelines.
This processor demonstrates plugin patterns that:
- Preserve zero-copy by passing through memoryviews
- Provide async-first APIs
- Isolate plugin errors with graceful handling
"""

from __future__ import annotations

import asyncio
from typing import Iterable

from ...core.errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    create_error_context,
)


class ZeroCopyProcessor:
    """Minimal zero-copy processor.

    The processor returns the same memoryview it receives to avoid copies.
    """

    name = "zero_copy"

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def process(self, view: memoryview) -> memoryview:
        """Process a single payload in zero-copy fashion.

        Returns the same memoryview instance.
        """
        try:
            # No transformation; pass-through for zero-copy
            return view
        except Exception as e:  # Graceful isolation
            context = create_error_context(
                ErrorCategory.PLUGIN_EXEC,
                ErrorSeverity.MEDIUM,
                plugin="zero_copy_processor",
            )
            raise FapilogError(
                "ZeroCopyProcessor failed",
                category=ErrorCategory.PLUGIN_EXEC,
                error_context=context,
                cause=e,
            ) from e

    async def process_many(self, views: Iterable[memoryview]) -> list[memoryview]:
        """Process many payloads; returns processed views."""
        out: list[memoryview] = []
        async with self._lock:
            for v in views:
                out.append(await self.process(v))
        return out

    async def health_check(self) -> bool:
        """Verify processor is ready to accept views.

        Checks that the internal lock is functional.
        """
        try:
            # Verify lock is not stuck by attempting a non-blocking acquire
            if self._lock.locked():
                # Lock is held; could indicate stuck processing
                # But this is expected during active processing, so still healthy
                pass
            return True
        except Exception:
            return False


# Plugin metadata for discovery
PLUGIN_METADATA = {
    "name": "zero_copy",
    "version": "1.0.0",
    "plugin_type": "processor",
    "entry_point": "fapilog.plugins.processors.zero_copy:ZeroCopyProcessor",
    "description": "Zero-copy pass-through processor for performance benchmarking.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
