"""
Plugin metadata handling and validation for Fapilog v3.

This module provides Pydantic v2 models for plugin metadata validation
and compatibility checking.
"""

import importlib.metadata
from typing import Any, Dict, List, Optional

from packaging import version
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PluginCompatibility(BaseModel):
    """Plugin compatibility information."""

    min_fapilog_version: str = Field(description="Minimum required Fapilog version")
    max_fapilog_version: Optional[str] = Field(
        default=None,
        description="Maximum supported Fapilog version (None for no limit)",
    )
    python_version: str = Field(default=">=3.8", description="Required Python version")

    @field_validator("min_fapilog_version", "max_fapilog_version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate version strings."""
        if v is not None:
            try:
                version.parse(v)
            except version.InvalidVersion as exc:
                raise ValueError(f"Invalid version string: {v}") from exc
        return v


class PluginMetadata(BaseModel):
    """Complete plugin metadata specification."""

    name: str = Field(description="Plugin name")
    version: str = Field(description="Plugin version")
    description: str = Field(description="Plugin description")
    author: str = Field(description="Plugin author")
    author_email: Optional[str] = Field(default=None, description="Author email")
    homepage: Optional[str] = Field(default=None, description="Plugin homepage")
    repository: Optional[str] = Field(default=None, description="Source repository")
    license: str = Field(default="MIT", description="Plugin license")

    # Plugin type and interface
    plugin_type: str = Field(
        description="Plugin type (sink, processor, enricher, redactor, alerting)"
    )
    entry_point: str = Field(description="Entry point for plugin loading")

    # Compatibility and dependencies
    compatibility: PluginCompatibility = Field(
        description="Plugin compatibility information"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Additional Python package dependencies",
    )

    # Plugin API contract version (semantic major.minor, e.g., "1.0")
    api_version: str = Field(
        default="1.0",
        description=(
            "Plugin API contract version (semantic 'major.minor'). Defaults to current API."
        ),
    )

    # Plugin configuration
    config_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON schema for plugin configuration"
    )
    default_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Default configuration values"
    )

    # Marketplace information
    tags: List[str] = Field(
        default_factory=list, description="Plugin tags for discovery"
    )
    marketplace_id: Optional[str] = Field(
        default=None, description="Unique marketplace identifier"
    )

    @field_validator("plugin_type")
    @classmethod
    def validate_plugin_type(cls, v: str) -> str:
        """Validate plugin type."""
        valid_types = {"sink", "processor", "enricher", "redactor", "alerting"}
        if v not in valid_types:
            raise ValueError(f"Invalid plugin type: {v}. Must be one of: {valid_types}")
        return v

    @field_validator("version")
    @classmethod
    def validate_version_string(cls, v: str) -> str:
        """Validate version string."""
        try:
            version.parse(v)
        except version.InvalidVersion as exc:
            raise ValueError(f"Invalid version string: {v}") from exc
        return v

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        """Validate API version string is in 'X.Y' format with non-negative ints."""
        from .versioning import parse_api_version

        # Will raise ValueError if invalid
        parse_api_version(v)
        return v


class PluginInfo(BaseModel):
    """Runtime plugin information."""

    metadata: PluginMetadata = Field(description="Plugin metadata")
    loaded: bool = Field(default=False, description="Whether plugin is loaded")
    instance: Optional[Any] = Field(default=None, description="Plugin instance")
    load_error: Optional[str] = Field(default=None, description="Load error message")
    source: str = Field(description=("Plugin source (local, marketplace, etc.)"))

    model_config = ConfigDict(arbitrary_types_allowed=True)


def validate_fapilog_compatibility(plugin_metadata: PluginMetadata) -> bool:
    """
    Validate if plugin is compatible with current Fapilog version.

    Args:
        plugin_metadata: Plugin metadata to validate

    Returns:
        True if compatible, False otherwise
    """
    try:
        try:
            # Prefer installed distribution metadata
            current_version_str = importlib.metadata.version("fapilog")
        except Exception:
            # Fallback to local __version__ if distribution metadata is unavailable
            from fapilog import __version__ as _local_version

            current_version_str = _local_version

        current_version = version.parse(current_version_str)
        # Editable installs may report 0.0.0+local; treat as universally compatible
        if str(current_version).startswith("0.0.0"):
            return True

        # Check minimum version
        min_version_raw = plugin_metadata.compatibility.min_fapilog_version or "0.0.0"
        min_version = version.parse(min_version_raw)
        if current_version < min_version:
            return False

        # Check maximum version if specified
        if plugin_metadata.compatibility.max_fapilog_version:
            max_version = version.parse(
                plugin_metadata.compatibility.max_fapilog_version
            )
            if current_version > max_version:
                return False

        return True

    except Exception:
        # Be permissive on version parsing failures to avoid blocking plugin loading
        return True


def create_plugin_metadata(
    name: str,
    version: str,
    plugin_type: str,
    entry_point: str,
    description: str = "",
    author: str = "",
    **kwargs: Any,
) -> PluginMetadata:
    """
    Helper function to create plugin metadata with sensible defaults.

    Args:
        name: Plugin name
        version: Plugin version
        plugin_type: Plugin type (sink, processor, enricher, etc.)
        entry_point: Entry point for plugin loading
        description: Plugin description
        author: Plugin author
        **kwargs: Additional metadata fields

    Returns:
        PluginMetadata instance
    """
    return PluginMetadata(
        name=name,
        version=version,
        plugin_type=plugin_type,
        entry_point=entry_point,
        description=description,
        author=author,
        compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        **kwargs,
    )
