from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ...core.processing import process_in_parallel
from ...metrics.metrics import MetricsCollector, plugin_timer
from ..loader import register_builtin
from .size_guard import SizeGuardProcessor
from .zero_copy import ZeroCopyProcessor


@runtime_checkable
class BaseProcessor(Protocol):
    """Authoring contract for processors that transform serialized views.

    Processors operate on memoryview slices of serialized payloads and return a
    new memoryview. Implementations must be async and should avoid copying where
    possible. Errors propagate to allow caller isolation/metrics to record them.

    Attributes:
        name: Unique identifier for this processor type (e.g., "zero_copy").
    """

    name: str  # Plugin identifier for discovery and configuration

    async def start(self) -> None:  # Optional lifecycle hook
        """Initialize processor resources (optional)."""

    async def stop(self) -> None:  # Optional lifecycle hook
        """Release processor resources (optional)."""

    async def process(self, view: memoryview) -> memoryview:
        """Transform a single view and return the processed view."""

    async def process_many(self, views: Iterable[memoryview]) -> list[memoryview]:
        """Process multiple views, returning processed views in order."""
        return [await self.process(v) for v in views]

    async def health_check(self) -> bool:  # pragma: no cover - optional
        """Return True if the processor is healthy. Default: assume healthy."""
        return True


async def process_parallel(
    views: list[memoryview],
    processors: Iterable[BaseProcessor],
    *,
    concurrency: int = 5,
    metrics: MetricsCollector | None = None,
) -> list[memoryview]:
    """
    Run each processor across views in parallel, returning processed views per
    processor.

    The function returns a list of processed views produced by the last
    processor in order.
    """
    processor_list: list[BaseProcessor] = list(processors)
    current_views: list[memoryview] = list(views)

    async def run_processor(p: BaseProcessor) -> list[memoryview]:
        # Process sequentially within a single processor for determinism;
        # parallelism is across processors
        out: list[memoryview] = []
        for v in current_views:
            try:
                async with plugin_timer(metrics, p.__class__.__name__):
                    processed = await p.process(v)
            except Exception:
                # Propagate to caller; upstream handles isolation and metrics
                raise
            else:
                out.append(processed)
                if metrics is not None:
                    await metrics.record_event_processed()
        return out

    processed_lists_raw = await process_in_parallel(
        processor_list,
        run_processor,
        limit=concurrency,
        return_exceptions=True,
    )
    # Filter out exceptions, keep only successful lists
    processed_lists: list[list[memoryview]] = [
        pl for pl in processed_lists_raw if not isinstance(pl, BaseException)
    ]
    # If multiple processors, return the result of the last one applied
    # element-wise
    if not processed_lists:
        return current_views
    return processed_lists[-1]


# Register built-ins
register_builtin(
    "fapilog.processors",
    "zero_copy",
    ZeroCopyProcessor,
    aliases=["zero-copy"],
)
register_builtin(
    "fapilog.processors",
    "size_guard",
    SizeGuardProcessor,
    aliases=["size-guard"],
)

__all__ = [
    "BaseProcessor",
    "process_parallel",
    "ZeroCopyProcessor",
    "SizeGuardProcessor",
]
