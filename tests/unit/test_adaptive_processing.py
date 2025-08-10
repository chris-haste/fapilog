import asyncio
from typing import List, Sequence

import pytest

from fapilog.core.adaptive import (
    AdaptiveBatchSizer,
    AdaptiveController,
    process_with_adaptive_batches,
)


def test_adaptive_batch_sizer_increases_when_fast() -> None:
    s = AdaptiveBatchSizer(
        min_batch=1, max_batch=128, target_latency_ms=5.0, aggressiveness=0.5
    )
    # Observed faster than target -> increase
    n1 = s.next_size(8, observed_latency_ms_per_item=2.5)
    assert n1 > 8
    # Observed slower than target -> decrease
    n2 = s.next_size(n1, observed_latency_ms_per_item=20.0)
    assert n2 < n1


def test_adaptive_controller_backpressure_and_ewma() -> None:
    s = AdaptiveBatchSizer()
    c = AdaptiveController(s)
    c.record_latency_sample(10.0)
    c.record_latency_sample(5.0)
    # EWMA converges between 10 and 5; advised size computed without error
    advised = c.advise_batch_size(8)
    assert advised >= 1
    assert c.advise_backpressure(0.9) is True
    assert c.advise_backpressure(0.1) is False


@pytest.mark.asyncio
async def test_process_with_adaptive_batches_runs_all_values() -> None:
    async def batch_worker(batch: Sequence[int]) -> List[int]:
        # pretend work
        await asyncio.sleep(0.001)
        return [x * 2 for x in batch]

    values = list(range(25))
    out = await process_with_adaptive_batches(values, batch_worker, initial_batch=4)
    assert out == [x * 2 for x in values]
