from __future__ import annotations

from typing import Iterable, List

from ...core.processing import process_in_parallel


class BaseProcessor:
    """Base interface for processors with async API."""

    async def process(self, view: memoryview) -> memoryview:
        return view

    async def process_many(self, views: Iterable[memoryview]) -> int:
        count = 0
        for v in views:
            _ = await self.process(v)
            count += 1
        return count


async def process_parallel(
    views: list[memoryview],
    processors: Iterable[BaseProcessor],
    *,
    concurrency: int = 5,
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
            out.append(await p.process(v))
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
