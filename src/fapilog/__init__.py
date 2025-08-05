"""
Fapilog v3 - Revolutionary async-first logging library for Python applications.

This module provides the core async-first logging functionality with zero-copy
operations, universal plugin ecosystem, and enterprise compliance features.
"""

from .containers.container import AsyncLoggingContainer
from .core.events import EventCategory, EventSeverity, LogEvent
from .core.logger import AsyncLogger
from .core.settings import UniversalSettings
from .plugins.marketplace import PluginMarketplace
from .plugins.registry import PluginRegistry

__version__ = "3.0.0-alpha.1"
__author__ = "Chris Haste"
__email__ = "chris@haste.dev"

__all__ = [
    # Core classes
    "AsyncLogger",
    "UniversalSettings",
    "LogEvent",
    "EventCategory",
    "EventSeverity",
    # Container architecture
    "AsyncLoggingContainer",
    # Plugin ecosystem
    "PluginRegistry",
    "PluginMarketplace",
]

# Version info for compatibility
VERSION = __version__
