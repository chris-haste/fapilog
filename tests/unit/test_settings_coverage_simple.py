"""
Targeted test coverage for fapilog settings module missing lines.

These tests focus specifically on increasing coverage for uncovered lines
identified in the coverage report.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from fapilog.core.settings import (
    LogLevel,
    PluginDiscoveryMethod,
    ComplianceStandard,
    EncryptionMethod,
    CoreConfig,
    PluginConfig,
    ComplianceConfig,
    SecurityConfig,
    ObservabilityConfig,
    MarketplaceConfig,
    FapilogSettings,
    load_settings,
    get_settings,
    reload_settings,
    reset_settings,
)
from fapilog.core.errors import ConfigurationError


class TestConfigValidationErrors:
    """Test configuration model validation error cases."""

    def test_plugin_config_invalid_marketplace_url(self):
        """Test PluginConfig with invalid marketplace URL."""
        with pytest.raises(ValueError, match="Marketplace URL must start with http"):
            PluginConfig(marketplace_url="invalid-url")

        with pytest.raises(ValueError, match="Marketplace URL must start with http"):
            PluginConfig(marketplace_url="ftp://example.com")

    def test_compliance_config_validation_errors(self):
        """Test ComplianceConfig validation errors."""
        # Compliance enabled without standards
        with pytest.raises(ValueError, match="At least one compliance standard"):
            ComplianceConfig(compliance_enabled=True, compliance_standards=set())

        # Audit integrity checks without audit enabled
        with pytest.raises(ValueError, match="Audit must be enabled"):
            ComplianceConfig(audit_integrity_checks=True, audit_enabled=False)

        # Role-based access without roles
        with pytest.raises(
            ValueError, match="At least one audit access role must be specified"
        ):
            ComplianceConfig(role_based_access_enabled=True, audit_access_roles=set())

    def test_security_config_validation_errors(self):
        """Test SecurityConfig validation errors."""
        # Encryption enabled without key
        with pytest.raises(ValueError, match="Encryption key must be provided"):
            SecurityConfig(encryption_enabled=True, encryption_key=None)

        # Authorization without authentication
        with pytest.raises(ValueError, match="Authentication must be enabled"):
            SecurityConfig(authorization_enabled=True, authentication_enabled=False)

    def test_marketplace_config_invalid_url(self):
        """Test MarketplaceConfig with invalid URL."""
        with pytest.raises(ValueError, match="Marketplace URL must start with http"):
            MarketplaceConfig(marketplace_url="not-a-url")

        with pytest.raises(ValueError, match="Marketplace URL must start with http"):
            MarketplaceConfig(marketplace_url="ftp://example.com")


class TestFapilogSettingsValidation:
    """Test FapilogSettings validation logic."""

    def test_production_debug_validation(self):
        """Test production environment cannot have debug enabled."""
        with pytest.raises(
            ValueError, match="Debug mode cannot be enabled in production"
        ):
            FapilogSettings(environment="production", debug=True)

    def test_production_encryption_compliance_validation(self):
        """Test encryption requirement in production with compliance."""
        compliance_config = ComplianceConfig(
            compliance_enabled=True, compliance_standards={ComplianceStandard.SOX}
        )
        security_config = SecurityConfig(encryption_enabled=False)

        with pytest.raises(
            ValueError, match="Encryption must be enabled in production"
        ):
            FapilogSettings(
                environment="production",
                compliance=compliance_config,
                security=security_config,
            )

    def test_marketplace_consistency_auto_config(self):
        """Test marketplace configuration auto-syncing to plugins."""
        marketplace_config = MarketplaceConfig(
            marketplace_enabled=True,
            marketplace_url="https://custom-marketplace.com",
            marketplace_api_key="test-key-123",
        )
        plugin_config = PluginConfig(marketplace_enabled=False)

        settings = FapilogSettings(
            marketplace=marketplace_config, plugins=plugin_config
        )

        # Should auto-enable plugin marketplace
        assert settings.plugins.marketplace_enabled is True
        assert settings.plugins.marketplace_url == "https://custom-marketplace.com"
        assert settings.plugins.marketplace_api_key == "test-key-123"


class TestAsyncValidation:
    """Test async validation methods."""

    @pytest.mark.asyncio
    async def test_validate_plugin_paths_nonexistent(self):
        """Test plugin path validation with non-existent path."""
        # The validation error occurs at creation time, not async validation
        with pytest.raises(ValueError, match="Discovery path does not exist"):
            PluginConfig(discovery_paths=[Path("/nonexistent/path")])

    @pytest.mark.asyncio
    async def test_validate_plugin_paths_file_not_directory(self):
        """Test plugin path validation with file instead of directory."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # The validation error occurs at creation time, not async validation
            with pytest.raises(ValueError, match="Discovery path is not a directory"):
                PluginConfig(discovery_paths=[temp_path])
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_validate_marketplace_connectivity_success(self):
        """Test successful marketplace connectivity validation."""
        marketplace_config = MarketplaceConfig(
            marketplace_enabled=True, marketplace_url="https://httpbin.org/status/200"
        )
        settings = FapilogSettings(marketplace=marketplace_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(
                return_value=mock_response
            )

            await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_marketplace_connectivity_error_status(self):
        """Test marketplace connectivity validation with error status."""
        marketplace_config = MarketplaceConfig(
            marketplace_enabled=True, marketplace_url="https://httpbin.org/status/404"
        )
        settings = FapilogSettings(marketplace=marketplace_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ConfigurationError, match="Async validation failed"):
                await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_marketplace_connectivity_network_error(self):
        """Test marketplace connectivity validation with network error."""
        marketplace_config = MarketplaceConfig(
            marketplace_enabled=True, marketplace_url="https://httpbin.org/status/200"
        )
        settings = FapilogSettings(marketplace=marketplace_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(ConfigurationError, match="Async validation failed"):
                await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_tracing_endpoint_grpc(self):
        """Test tracing endpoint validation for gRPC (should pass)."""
        observability_config = ObservabilityConfig(
            tracing_enabled=True, tracing_endpoint="grpc://jaeger:14250"
        )
        settings = FapilogSettings(observability=observability_config)

        # Should pass without network validation for gRPC
        await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_tracing_endpoint_http_success(self):
        """Test tracing endpoint validation for HTTP endpoint."""
        observability_config = ObservabilityConfig(
            tracing_enabled=True, tracing_endpoint="https://httpbin.org/status/200"
        )
        settings = FapilogSettings(observability=observability_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(
                return_value=mock_response
            )

            await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_tracing_endpoint_http_error(self):
        """Test tracing endpoint validation for HTTP endpoint with error."""
        observability_config = ObservabilityConfig(
            tracing_enabled=True, tracing_endpoint="https://httpbin.org/status/500"
        )
        settings = FapilogSettings(observability=observability_config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ConfigurationError, match="Async validation failed"):
                await settings.validate_async_fields()

    @pytest.mark.asyncio
    async def test_validate_tracing_endpoint_none(self):
        """Test tracing endpoint validation when endpoint is None."""
        observability_config = ObservabilityConfig(
            tracing_enabled=True, tracing_endpoint=None
        )
        settings = FapilogSettings(observability=observability_config)

        # Should pass when endpoint is None
        await settings.validate_async_fields()


class TestSettingsLoading:
    """Test settings loading functions."""

    def setUp(self):
        """Reset settings before each test."""
        reset_settings()

    @pytest.mark.asyncio
    async def test_load_settings_from_toml_file(self):
        """Test loading settings from TOML file."""
        config_data = {
            "environment": "production",
            "debug": False,
            "config_version": "3.1.0",
            "core": {"log_level": "DEBUG"},
            "security": {"encryption_enabled": True, "encryption_key": "test-key-123"},
        }

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".toml", delete=False
        ) as temp_file:
            import tomli_w

            tomli_w.dump(config_data, temp_file)
            temp_file.flush()
            temp_path = Path(temp_file.name)

        try:
            with patch.dict(os.environ, {"FAPILOG_SKIP_NETWORK_VALIDATION": "1"}):
                settings = await load_settings(config_file=temp_path)
                assert settings.environment == "production"
                assert settings.config_version == "3.1.0"
                assert settings.core.log_level == LogLevel.DEBUG
                assert settings.security.encryption_enabled is True
                assert settings.security.encryption_key == "test-key-123"
                assert settings.config_source == str(temp_path)
                assert settings.last_loaded is not None
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_settings_from_json_file(self):
        """Test loading settings from JSON file."""
        config_data = {
            "environment": "staging",
            "debug": True,
            "core": {"log_level": "WARNING"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            json.dump(config_data, temp_file)
            temp_file.flush()
            temp_path = Path(temp_file.name)

        try:
            settings = await load_settings(config_file=temp_path)
            assert settings.environment == "staging"
            assert settings.debug is True
            assert settings.core.log_level == LogLevel.WARNING
            assert settings.config_source == str(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_settings_unsupported_file_format(self):
        """Test loading settings from unsupported file format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.write("test: value")
            temp_file.flush()
            temp_path = Path(temp_file.name)

        try:
            with pytest.raises(
                ConfigurationError, match="Unsupported configuration file format"
            ):
                await load_settings(config_file=temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_settings_invalid_json(self):
        """Test loading settings from invalid JSON file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_file.write("{invalid json}")
            temp_file.flush()
            temp_path = Path(temp_file.name)

        try:
            with pytest.raises(
                ConfigurationError, match="Failed to load configuration"
            ):
                await load_settings(config_file=temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_settings_with_environment_override(self):
        """Test loading settings with environment override."""
        with patch.dict(os.environ, {"FAPILOG_SKIP_NETWORK_VALIDATION": "1"}):
            settings = await load_settings(environment_override="production")
            assert settings.environment == "production"

    @pytest.mark.asyncio
    async def test_load_settings_configuration_error_passthrough(self):
        """Test that ConfigurationError is passed through."""
        with patch.dict(os.environ, {"FAPILOG_SKIP_NETWORK_VALIDATION": "1"}):
            with pytest.raises(ConfigurationError):
                await load_settings(environment="production", debug=True)

    @pytest.mark.asyncio
    async def test_get_settings_lazy_loading(self):
        """Test get_settings lazy loading."""
        reset_settings()

        with patch.dict(os.environ, {"FAPILOG_SKIP_NETWORK_VALIDATION": "1"}):
            # First call should load defaults
            settings1 = await get_settings()
            assert isinstance(settings1, FapilogSettings)

            # Second call should return same instance
            settings2 = await get_settings()
            assert settings1 is settings2

    @pytest.mark.asyncio
    async def test_reload_settings(self):
        """Test reload_settings function."""
        with patch.dict(os.environ, {"FAPILOG_SKIP_NETWORK_VALIDATION": "1"}):
            # Load initial settings
            initial_settings = await get_settings()
            assert initial_settings.environment == "development"

            # Reload with different configuration
            new_settings = await reload_settings(environment="staging")
            assert new_settings.environment == "staging"

            # Verify new settings are returned by get_settings
            current_settings = await get_settings()
            assert current_settings.environment == "staging"
            assert current_settings is new_settings

    def test_reset_settings(self):
        """Test reset_settings function."""
        reset_settings()
        # Should not raise any errors


class TestFieldValidation:
    """Test specific field validation methods."""

    def test_plugin_config_marketplace_url_validation_valid(self):
        """Test valid marketplace URL validation."""
        # Valid URLs should pass
        config = PluginConfig(marketplace_url="https://example.com")
        assert config.marketplace_url == "https://example.com"

        config = PluginConfig(marketplace_url="http://localhost:8080")
        assert config.marketplace_url == "http://localhost:8080"

    def test_marketplace_config_url_validation_valid(self):
        """Test valid marketplace config URL validation."""
        config = MarketplaceConfig(marketplace_url="https://custom-marketplace.com")
        assert config.marketplace_url == "https://custom-marketplace.com"


class TestEnvironmentVariableLoading:
    """Test environment variable loading."""

    @pytest.mark.asyncio
    async def test_environment_variable_override(self):
        """Test environment variable override in load_settings."""
        test_env = {"FAPILOG_ENVIRONMENT": "production"}

        with patch.dict(os.environ, test_env):
            # environment_override should take precedence over env var
            settings = await load_settings(environment_override="staging")
            assert settings.environment == "staging"

    @pytest.mark.asyncio
    async def test_concurrent_settings_access(self):
        """Test concurrent access to settings loading."""
        reset_settings()

        async def get_settings_task():
            return await get_settings()

        # Load settings concurrently
        tasks = [get_settings_task() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All should return the same instance
        for result in results[1:]:
            assert result is results[0]
