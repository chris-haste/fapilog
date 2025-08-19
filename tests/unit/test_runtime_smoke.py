from __future__ import annotations

from fapilog import runtime


def test_runtime_context_manager_smoke() -> None:
    with runtime() as logger:
        logger.debug("runtime-smoke")
