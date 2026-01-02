"""Test that MemoryMappedPersistence is NOT registered as a sink.

MemoryMappedPersistence is a building block for custom sinks, not a sink itself.
It does not implement the BaseSink protocol (uses open/close instead of start/stop,
and append_line instead of write).
"""

from fapilog.plugins.loader import BUILTIN_SINKS
from fapilog.plugins.sinks import MemoryMappedPersistence


def test_mmap_not_in_builtin_sinks() -> None:
    """MemoryMappedPersistence should not be in sink registry."""
    assert "mmap_persistence" not in BUILTIN_SINKS
    assert "mmap-persistence" not in BUILTIN_SINKS


def test_mmap_still_importable() -> None:
    """MemoryMappedPersistence should still be importable as a building block."""
    # Verify class is accessible
    assert MemoryMappedPersistence is not None
    assert hasattr(MemoryMappedPersistence, "open")
    assert hasattr(MemoryMappedPersistence, "close")
    assert hasattr(MemoryMappedPersistence, "append_line")
