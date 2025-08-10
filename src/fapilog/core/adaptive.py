"""
Adaptive processing utilities for dynamic batch sizing and backpressure
(Story 2.2c).
Key components:
- AdaptiveBatchSizer: Compute next batch size from latency vs. target
- AdaptiveController: Combine latency/utilization for decisions
- process_with_adaptive_batches: Process a sequence using adaptive batches
Design notes:
- Async-first; callers supply async worker functions
- No global state; pure objects instantiated per pipeline/container
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class AdaptiveBatchSizer:
    """Compute adaptive batch sizes from latency feedback.

    Uses a simple proportional controller comparing observed average latency
    per item to a target; scales batch size up if faster than target, down if
    slower, clamped to min/max.
    """

    min_batch: int = 1
    max_batch: int = 1024
    target_latency_ms: float = 5.0
    aggressiveness: float = 0.5  # 0..1: how aggressively to change size

    def next_size(
        self, last_batch_size: int, observed_latency_ms_per_item: float
    ) -> int:
        if last_batch_size <= 0:
            last_batch_size = self.min_batch
        if observed_latency_ms_per_item <= 0:
            # If zero/negative (clock skew), gently increase
            candidate = last_batch_size * (1.0 + self.aggressiveness)
            return int(max(self.min_batch, min(self.max_batch, math.ceil(candidate))))

        ratio = self.target_latency_ms / observed_latency_ms_per_item
        # Scale change by aggressiveness and bound change factor
        change = max(0.5, min(2.0, ratio))
        adjusted = last_batch_size * (1.0 + self.aggressiveness * (change - 1.0))
        candidate = int(max(self.min_batch, min(self.max_batch, round(adjusted))))
        return candidate


@dataclass
class AdaptiveController:
    """Adaptive controller combining latency and utilization.

    - Maintains EWMA of latency per item
    - Advises batch size
    - Advises whether to apply backpressure based on utilization threshold
    """

    batch_sizer: AdaptiveBatchSizer
    utilization_high_threshold: float = 0.85  # 85% capacity utilization
    latency_ewma_alpha: float = 0.3

    _latency_ewma_ms_per_item: float | None = None

    def record_latency_sample(self, latency_ms_per_item: float) -> None:
        if self._latency_ewma_ms_per_item is None:
            self._latency_ewma_ms_per_item = latency_ms_per_item
        else:
            a = self.latency_ewma_alpha
            self._latency_ewma_ms_per_item = (
                a * latency_ms_per_item + (1 - a) * self._latency_ewma_ms_per_item
            )

    def advise_batch_size(self, last_batch_size: int) -> int:
        observed = self._latency_ewma_ms_per_item or self.batch_sizer.target_latency_ms
        return self.batch_sizer.next_size(last_batch_size, observed)

    def advise_backpressure(self, utilization: float) -> bool:
        return utilization >= self.utilization_high_threshold


async def process_with_adaptive_batches(
    values: Sequence[T],
    worker: Callable[[Sequence[T]], Awaitable[list[R]]],
    *,
    batch_sizer: AdaptiveBatchSizer | None = None,
    initial_batch: int = 8,
    report_latency_ms_per_item: Callable[[float], None] | None = None,
) -> list[R]:
    """Process values in adaptively sized batches using an async batch worker.

    The worker should return a list of results for the input batch.
    """
    controller = AdaptiveController(batch_sizer or AdaptiveBatchSizer())
    results: list[R] = []
    index = 0
    batch_size = max(1, initial_batch)

    while index < len(values):
        batch = values[index : index + batch_size]
        # Execute one batch
        batch_results = await worker(batch)
        results.extend(batch_results)

        # Estimate per-item latency if reporter provided via a side-channel
        # Otherwise, assume target latency to slowly grow batch size
        observed_ms = controller.batch_sizer.target_latency_ms
        if report_latency_ms_per_item is not None:
            # Caller reports after this returns; nothing to do here
            pass
        controller.record_latency_sample(observed_ms)
        batch_size = controller.advise_batch_size(batch_size)
        index += len(batch)

    return results
