"""
Plugin Marketplace Configuration for Fapilog v3.

This module provides marketplace configuration, plugin discovery,
publishing, and ecosystem growth management capabilities.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field, field_validator

from .errors import ErrorCategory, ErrorSeverity, PluginError
from .plugin_config import PluginMetadata, PluginQualityMetrics


class MarketplaceEndpoint(BaseModel):
    """Marketplace API endpoint configuration."""

    url: str
    api_key: Optional[str] = None
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    retry_count: int = Field(default=3, ge=0, le=10)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate marketplace URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Marketplace URL must start with http:// or https://")
        return v.rstrip("/")


class PluginSearchCriteria(BaseModel):
    """Plugin search criteria for marketplace queries."""

    query: Optional[str] = None
    plugin_type: Optional[str] = None
    category: Optional[str] = None
    tags: Set[str] = Field(default_factory=set)
    author: Optional[str] = None
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    min_rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    verified_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PluginRating(BaseModel):
    """Plugin rating and review information."""

    rating: float = Field(ge=0.0, le=5.0)
    review_count: int = Field(ge=0)
    reviews: List[str] = Field(default_factory=list)
    average_rating: float = Field(ge=0.0, le=5.0)


class PluginDownloadInfo(BaseModel):
    """Plugin download information."""

    download_count: int = Field(ge=0)
    download_url: str
    size_bytes: int = Field(ge=0)
    last_updated: datetime

    @field_validator("download_url")
    @classmethod
    def validate_download_url(cls, v: str) -> str:
        """Validate download URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Download URL must start with http:// or https://")
        return v


class MarketplacePluginInfo(BaseModel):
    """Complete plugin information from marketplace."""

    # Core metadata
    metadata: PluginMetadata

    # Marketplace-specific data
    plugin_id: str
    publisher: str
    verified_publisher: bool = False
    published_date: datetime
    last_updated: datetime

    # Quality and ratings
    quality_metrics: Optional[PluginQualityMetrics] = None
    rating_info: Optional[PluginRating] = None

    # Download information
    download_info: PluginDownloadInfo

    # Security information
    security_verified: bool = False
    signature_verified: bool = False
    virus_scan_passed: bool = False

    # Compatibility
    compatibility_tested: bool = False
    supported_platforms: Set[str] = Field(default_factory=set)

    # License information
    license: str
    license_url: Optional[str] = None


class PluginPublishRequest(BaseModel):
    """Request model for publishing plugins to marketplace."""

    metadata: PluginMetadata
    quality_metrics: Optional[PluginQualityMetrics] = None
    package_path: Path
    changelog: str = ""
    release_notes: str = ""

    # Publishing options
    visibility: str = Field(default="public", pattern=r"^(public|private|unlisted)$")
    auto_update_enabled: bool = True
    beta_release: bool = False

    @field_validator("package_path")
    @classmethod
    def validate_package_path(cls, v: Path) -> Path:
        """Validate package path exists."""
        if not v.exists():
            raise ValueError(f"Package file does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Package path is not a file: {v}")
        return v


class MarketplaceCache:
    """Local cache for marketplace data to improve performance."""

    def __init__(
        self, cache_dir: Path, max_size_mb: int = 100, ttl_seconds: int = 3600
    ):
        """
        Initialize marketplace cache.

        Args:
            cache_dir: Directory for cache storage
            max_size_mb: Maximum cache size in MB
            ttl_seconds: Time to live for cached items
        """
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self.ttl_seconds = ttl_seconds
        self._cache_index: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        # Create cache directory
        cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        async with self._lock:
            cache_file = self.cache_dir / f"{self._hash_key(key)}.json"

            if not cache_file.exists():
                return None

            try:
                content = await asyncio.to_thread(cache_file.read_text)
                data = json.loads(content)

                # Check TTL
                timestamp = data.get("timestamp", 0)
                if (
                    datetime.now(timezone.utc).timestamp() - timestamp
                    > self.ttl_seconds
                ):
                    await asyncio.to_thread(cache_file.unlink, missing_ok=True)
                    return None

                return data.get("value")

            except Exception:
                # Remove corrupted cache file
                await asyncio.to_thread(cache_file.unlink, missing_ok=True)
                return None

    async def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        async with self._lock:
            # Check cache size and cleanup if needed
            await self._cleanup_if_needed()

            cache_file = self.cache_dir / f"{self._hash_key(key)}.json"

            data = {
                "timestamp": datetime.now(timezone.utc).timestamp(),
                "value": value,
            }

            try:
                content = json.dumps(data, default=str)
                await asyncio.to_thread(cache_file.write_text, content)
            except Exception:
                # Ignore cache write failures
                pass

    async def clear(self) -> None:
        """Clear all cached items."""
        async with self._lock:
            for cache_file in self.cache_dir.glob("*.json"):
                await asyncio.to_thread(cache_file.unlink, missing_ok=True)
            self._cache_index.clear()

    def _hash_key(self, key: str) -> str:
        """Generate hash for cache key."""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    async def _cleanup_if_needed(self) -> None:
        """Clean up cache if size exceeds limit."""
        total_size = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.json") if f.exists()
        )

        if total_size > self.max_size_mb * 1024 * 1024:
            # Remove oldest files
            cache_files = list(self.cache_dir.glob("*.json"))
            cache_files.sort(key=lambda f: f.stat().st_mtime)

            for cache_file in cache_files[: len(cache_files) // 2]:
                await asyncio.to_thread(cache_file.unlink, missing_ok=True)


class MarketplaceClient:
    """
    Client for interacting with Fapilog plugin marketplace.

    Provides functionality for searching, downloading, and publishing plugins
    to the marketplace with caching and error handling.
    """

    def __init__(
        self,
        endpoint: MarketplaceEndpoint,
        cache_dir: Optional[Path] = None,
        cache_enabled: bool = True,
    ):
        """
        Initialize marketplace client.

        Args:
            endpoint: Marketplace endpoint configuration
            cache_dir: Directory for local cache
            cache_enabled: Whether to use local caching
        """
        self.endpoint = endpoint
        self.cache_enabled = cache_enabled

        if cache_enabled:
            if cache_dir is None:
                cache_dir = Path.home() / ".fapilog" / "marketplace_cache"
            self.cache: Optional[MarketplaceCache] = MarketplaceCache(cache_dir)
        else:
            self.cache = None

        self._client_session: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "MarketplaceClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client_session is None:
            async with self._lock:
                if self._client_session is None:
                    headers = {"User-Agent": "Fapilog/3.0.0"}
                    if self.endpoint.api_key:
                        headers["Authorization"] = f"Bearer {self.endpoint.api_key}"

                    self._client_session = httpx.AsyncClient(
                        timeout=self.endpoint.timeout,
                        headers=headers,
                    )

    async def close(self) -> None:
        """Close HTTP client session."""
        if self._client_session:
            await self._client_session.aclose()
            self._client_session = None

    async def search_plugins(
        self, criteria: PluginSearchCriteria
    ) -> List[MarketplacePluginInfo]:
        """
        Search for plugins in the marketplace.

        Args:
            criteria: Search criteria

        Returns:
            List of matching plugins

        Raises:
            PluginError: If search fails
        """
        await self._ensure_client()

        # Check cache first
        cache_key = f"search:{criteria.model_dump_json()}"
        if self.cache_enabled and self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                return [MarketplacePluginInfo(**plugin) for plugin in cached_result]

        try:
            url = urljoin(self.endpoint.url, "/api/v1/plugins/search")
            params = criteria.model_dump(exclude_none=True)

            assert self._client_session is not None
            response = await self._client_session.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            plugins = [
                MarketplacePluginInfo(**plugin_data) for plugin_data in data["plugins"]
            ]

            # Cache results
            if self.cache_enabled and self.cache:
                await self.cache.set(
                    cache_key, [plugin.model_dump() for plugin in plugins]
                )

            return plugins

        except Exception as e:
            raise PluginError(
                f"Failed to search marketplace: {e}",
                marketplace_url=self.endpoint.url,
                cause=e,
            ) from e

    async def get_plugin_info(self, plugin_id: str) -> Optional[MarketplacePluginInfo]:
        """
        Get detailed information about a specific plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin information or None if not found

        Raises:
            PluginError: If request fails
        """
        await self._ensure_client()

        # Check cache first
        cache_key = f"plugin_info:{plugin_id}"
        if self.cache_enabled and self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                return MarketplacePluginInfo(**cached_result)

        try:
            url = urljoin(self.endpoint.url, f"/api/v1/plugins/{plugin_id}")

            assert self._client_session is not None
            response = await self._client_session.get(url)
            if response.status_code == 404:
                return None

            response.raise_for_status()

            data = response.json()
            plugin_info = MarketplacePluginInfo(**data)

            # Cache result
            if self.cache_enabled and self.cache:
                await self.cache.set(cache_key, plugin_info.model_dump())

            return plugin_info

        except Exception as e:
            if isinstance(e, PluginError):
                raise

            raise PluginError(
                f"Failed to get plugin info: {e}",
                plugin_id=plugin_id,
                cause=e,
            ) from e

    async def download_plugin(
        self, plugin_info: MarketplacePluginInfo, download_dir: Path
    ) -> Path:
        """
        Download a plugin from the marketplace.

        Args:
            plugin_info: Plugin information from marketplace
            download_dir: Directory to download plugin to

        Returns:
            Path to downloaded plugin file

        Raises:
            PluginError: If download fails
        """
        await self._ensure_client()

        try:
            download_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            plugin_filename = (
                f"{plugin_info.metadata.name}-{plugin_info.metadata.version}.tar.gz"
            )
            download_path = download_dir / plugin_filename

            # Download plugin
            assert self._client_session is not None
            response = await self._client_session.get(
                plugin_info.download_info.download_url
            )
            response.raise_for_status()

            # Write to file
            await asyncio.to_thread(download_path.write_bytes, response.content)

            # Verify file size
            actual_size = download_path.stat().st_size
            expected_size = plugin_info.download_info.size_bytes

            if actual_size != expected_size:
                download_path.unlink(missing_ok=True)
                raise PluginError(
                    f"Downloaded file size mismatch: expected {expected_size}, got {actual_size}",
                    plugin_id=plugin_info.plugin_id,
                )

            return download_path

        except Exception as e:
            if isinstance(e, PluginError):
                raise

            raise PluginError(
                f"Failed to download plugin: {e}",
                plugin_id=plugin_info.plugin_id,
                cause=e,
            ) from e

    async def publish_plugin(
        self, publish_request: PluginPublishRequest
    ) -> Dict[str, Any]:
        """
        Publish a plugin to the marketplace.

        Args:
            publish_request: Plugin publishing request

        Returns:
            Publishing result information

        Raises:
            PluginError: If publishing fails
        """
        await self._ensure_client()

        if not self.endpoint.api_key:
            raise PluginError(
                "API key required for publishing plugins",
            )

        try:
            url = urljoin(self.endpoint.url, "/api/v1/plugins/publish")

            # Prepare multipart form data
            files = {
                "package": (
                    publish_request.package_path.name,
                    publish_request.package_path.read_bytes(),
                    "application/gzip",
                )
            }

            data = {
                "metadata": publish_request.metadata.model_dump_json(),
                "changelog": publish_request.changelog,
                "release_notes": publish_request.release_notes,
                "visibility": publish_request.visibility,
                "auto_update_enabled": publish_request.auto_update_enabled,
                "beta_release": publish_request.beta_release,
            }

            if publish_request.quality_metrics:
                data["quality_metrics"] = (
                    publish_request.quality_metrics.model_dump_json()
                )

            assert self._client_session is not None
            response = await self._client_session.post(url, data=data, files=files)
            response.raise_for_status()

            publish_result: Dict[str, Any] = response.json()
            return publish_result

        except Exception as e:
            if isinstance(e, PluginError):
                raise

            raise PluginError(
                f"Failed to publish plugin: {e}",
                category=ErrorCategory.EXTERNAL,
                severity=ErrorSeverity.HIGH,
                plugin_name=publish_request.metadata.name,
                cause=e,
            ) from e

    async def get_plugin_updates(
        self, installed_plugins: List[PluginMetadata]
    ) -> List[MarketplacePluginInfo]:
        """
        Check for updates to installed plugins.

        Args:
            installed_plugins: List of currently installed plugins

        Returns:
            List of plugins with available updates
        """
        updates = []

        for plugin in installed_plugins:
            try:
                # Search for the plugin in marketplace
                criteria = PluginSearchCriteria(
                    query=plugin.name,
                    author=plugin.author,
                    limit=1,
                )

                search_results = await self.search_plugins(criteria)

                if search_results:
                    marketplace_plugin = search_results[0]

                    # Compare versions
                    from packaging import version

                    current_version = version.parse(plugin.version.to_string())
                    available_version = version.parse(
                        marketplace_plugin.metadata.version.to_string()
                    )

                    if available_version > current_version:
                        updates.append(marketplace_plugin)

            except Exception:
                # Continue checking other plugins if one fails
                continue

        return updates

    async def clear_cache(self) -> None:
        """Clear local marketplace cache."""
        if self.cache_enabled and self.cache:
            await self.cache.clear()


class MarketplaceManager:
    """
    High-level marketplace manager for plugin ecosystem growth.

    Provides centralized management of marketplace interactions,
    plugin discovery, and ecosystem growth features.
    """

    def __init__(
        self,
        endpoint: MarketplaceEndpoint,
        cache_enabled: bool = True,
        auto_update_enabled: bool = False,
    ):
        """
        Initialize marketplace manager.

        Args:
            endpoint: Marketplace endpoint configuration
            cache_enabled: Whether to enable local caching
            auto_update_enabled: Whether to automatically check for updates
        """
        self.endpoint = endpoint
        self.cache_enabled = cache_enabled
        self.auto_update_enabled = auto_update_enabled
        self._client: Optional[MarketplaceClient] = None
        self._update_check_task: Optional[asyncio.Task] = None
        self._installed_plugins: Dict[str, PluginMetadata] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize marketplace manager."""
        async with self._lock:
            if self._client is None:
                self._client = MarketplaceClient(
                    endpoint=self.endpoint,
                    cache_enabled=self.cache_enabled,
                )
                await self._client._ensure_client()

            # Start auto-update checker if enabled
            if self.auto_update_enabled and self._update_check_task is None:
                self._update_check_task = asyncio.create_task(self._auto_update_loop())

    async def cleanup(self) -> None:
        """Clean up marketplace manager resources."""
        async with self._lock:
            # Stop auto-update task
            if self._update_check_task:
                self._update_check_task.cancel()
                try:
                    await self._update_check_task
                except asyncio.CancelledError:
                    pass
                self._update_check_task = None

            # Close client
            if self._client:
                await self._client.close()
                self._client = None

    async def discover_plugins(
        self, criteria: PluginSearchCriteria
    ) -> List[MarketplacePluginInfo]:
        """
        Discover plugins in the marketplace.

        Args:
            criteria: Search criteria

        Returns:
            List of discovered plugins
        """
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.search_plugins(criteria)

    async def install_plugin(
        self, plugin_id: str, install_dir: Path
    ) -> MarketplacePluginInfo:
        """
        Install a plugin from the marketplace.

        Args:
            plugin_id: Plugin identifier
            install_dir: Directory to install plugin to

        Returns:
            Installed plugin information

        Raises:
            PluginError: If installation fails
        """
        if self._client is None:
            await self.initialize()

        # Get plugin information
        assert self._client is not None
        plugin_info = await self._client.get_plugin_info(plugin_id)
        if not plugin_info:
            raise PluginError(
                f"Plugin not found in marketplace: {plugin_id}",
                category=ErrorCategory.PLUGIN_CONFIG,
                severity=ErrorSeverity.HIGH,
                plugin_id=plugin_id,
            )

        # Download plugin
        download_dir = install_dir / "downloads"
        assert self._client is not None
        await self._client.download_plugin(plugin_info, download_dir)

        # Extract and install (simplified)
        extracted_dir = install_dir / plugin_info.metadata.name
        extracted_dir.mkdir(parents=True, exist_ok=True)

        # TODO: Add actual extraction logic here

        # Track installed plugin
        self._installed_plugins[plugin_info.metadata.name] = plugin_info.metadata

        return plugin_info

    async def check_for_updates(self) -> List[MarketplacePluginInfo]:
        """
        Check for updates to installed plugins.

        Returns:
            List of plugins with available updates
        """
        if self._client is None:
            await self.initialize()

        if not self._installed_plugins:
            return []

        assert self._client is not None
        return await self._client.get_plugin_updates(
            list(self._installed_plugins.values())
        )

    async def register_installed_plugin(self, metadata: PluginMetadata) -> None:
        """Register an installed plugin with the manager."""
        self._installed_plugins[metadata.name] = metadata

    async def _auto_update_loop(self) -> None:
        """Auto-update check loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour

                updates = await self.check_for_updates()
                if updates:
                    # Log available updates (in practice, you'd emit events)
                    pass

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                pass


# Global marketplace manager
_marketplace_manager: Optional[MarketplaceManager] = None
_marketplace_lock = asyncio.Lock()


async def get_marketplace_manager() -> Optional[MarketplaceManager]:
    """Get global marketplace manager instance."""
    global _marketplace_manager
    return _marketplace_manager


async def initialize_marketplace_manager(
    endpoint: MarketplaceEndpoint,
    cache_enabled: bool = True,
    auto_update_enabled: bool = False,
) -> MarketplaceManager:
    """
    Initialize global marketplace manager.

    Args:
        endpoint: Marketplace endpoint configuration
        cache_enabled: Whether to enable caching
        auto_update_enabled: Whether to enable auto-updates

    Returns:
        MarketplaceManager instance
    """
    global _marketplace_manager

    async with _marketplace_lock:
        if _marketplace_manager is not None:
            await _marketplace_manager.cleanup()

        _marketplace_manager = MarketplaceManager(
            endpoint=endpoint,
            cache_enabled=cache_enabled,
            auto_update_enabled=auto_update_enabled,
        )

        await _marketplace_manager.initialize()
        return _marketplace_manager


async def cleanup_marketplace_manager() -> None:
    """Clean up global marketplace manager."""
    global _marketplace_manager

    if _marketplace_manager:
        async with _marketplace_lock:
            if _marketplace_manager:
                await _marketplace_manager.cleanup()
                _marketplace_manager = None
