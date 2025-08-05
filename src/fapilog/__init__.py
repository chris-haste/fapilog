"""
Fapilog v3 - Revolutionary async-first logging library for Python applications.

This module provides the core async-first logging functionality with zero-copy
operations, universal plugin ecosystem, and enterprise compliance features.
"""

from .core.logger import AsyncLogger
from .core.settings import UniversalSettings
from .core.events import LogEvent, EventCategory, EventSeverity
from .containers.container import AsyncLoggingContainer
from .plugins.registry import PluginRegistry
from .plugins.marketplace import PluginMarketplace

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
