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

    async def process_many(self, views: Iterable[memoryview]) -> int:
        """Process many payloads; returns the number processed.

        Uses a lock to model shared state protection if extended.
        """
        count = 0
        async with self._lock:
            for v in views:
                _ = await self.process(v)
                count += 1
        return count
