"""
Caching module for fapilog.

This module provides high-performance caching implementations with dual
sync/async interfaces for optimal performance in both synchronous and
asynchronous logging scenarios.
"""

from .cache import CacheProtocol, HighPerformanceLRUCache

__all__ = ["HighPerformanceLRUCache", "CacheProtocol"]
