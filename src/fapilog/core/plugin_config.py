"""
Plugin Configuration Validation with Quality Gates for Fapilog v3.

This module provides comprehensive plugin configuration validation,
quality gates, compatibility checks, and security validation.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from packaging import version

from pydantic import BaseModel, Field, field_validator

from .errors import PluginError, ValidationError, ErrorCategory, ErrorSeverity
from .validation import get_quality_gate_validator, QualityGateValidator


class PluginVersion(BaseModel):
    """Plugin version information."""

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)
    pre_release: Optional[str] = None
    build: Optional[str] = None

    @classmethod
    def from_string(cls, version_str: str) -> "PluginVersion":
        """Parse version from string."""
        try:
            parsed = version.parse(version_str)
            pre_release: Optional[str] = None
            if parsed.pre is not None:
                # packaging.version returns a tuple like ("a", 1) for pre-release
                try:
                    pre_release = str(parsed.pre[0])
                except Exception:
                    pre_release = str(parsed.pre)

            return cls(
                major=parsed.major,
                minor=parsed.minor,
                patch=parsed.micro,
                pre_release=pre_release,
                build=str(parsed.local) if parsed.local else None,
            )
        except Exception as e:
            raise ValueError(f"Invalid version format: {version_str}") from e

    def to_string(self) -> str:
        """Convert to string representation."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            base += f"-{self.pre_release}"
        if self.build:
            base += f"+{self.build}"
        return base

    def __str__(self) -> str:
        """String representation."""
        return self.to_string()


class PluginDependency(BaseModel):
    """Plugin dependency specification."""

    name: str
    version_constraint: str = "*"
    optional: bool = False

    @field_validator("version_constraint")
    @classmethod
    def validate_version_constraint(cls, v: str) -> str:
        """Validate version constraint format."""
        if v == "*":
            return v

        # Basic validation for common patterns
        valid_patterns = [
            r"^\d+\.\d+\.\d+$",  # exact version
            r"^>=\d+\.\d+\.\d+$",  # minimum version
            r"^>\d+\.\d+\.\d+$",  # greater than
            r"^<=\d+\.\d+\.\d+$",  # maximum version
            r"^<\d+\.\d+\.\d+$",  # less than
            r"^~\d+\.\d+\.\d+$",  # compatible version
            r"^\^\d+\.\d+\.\d+$",  # caret version
        ]

        import re

        for pattern in valid_patterns:
            if re.match(pattern, v):
                return v

        raise ValueError(f"Invalid version constraint format: {v}")


class PluginMetadata(BaseModel):
    """Comprehensive plugin metadata."""

    # Basic information
    name: str = Field(min_length=1, max_length=100)
    version: PluginVersion
    description: str = Field(max_length=500)
    author: str = Field(max_length=100)

    # Plugin classification
    plugin_type: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=50)
    tags: Set[str] = Field(default_factory=set)

    # Compatibility
    fapilog_version_min: str = "3.0.0"
    fapilog_version_max: Optional[str] = None
    python_version_min: str = "3.8"
    python_version_max: Optional[str] = None

    # Dependencies
    dependencies: List[PluginDependency] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)

    # Entry points and interfaces
    entry_point: str
    interfaces: List[str] = Field(default_factory=list)

    # Security and validation
    signature: Optional[str] = None
    checksum: Optional[str] = None
    trusted_publisher: bool = False

    # Performance characteristics
    async_compatible: bool = True
    thread_safe: bool = True
    resource_intensive: bool = False
    estimated_memory_mb: Optional[int] = Field(default=None, ge=1, le=1024)

    # Configuration schema
    config_schema: Optional[Dict[str, Any]] = None

    @field_validator("plugin_type")
    @classmethod
    def validate_plugin_type(cls, v: str) -> str:
        """Validate plugin type."""
        valid_types = {
            "sink",
            "enricher",
            "processor",
            "filter",
            "formatter",
            "transport",
            "serializer",
            "middleware",
            "extension",
        }
        if v not in valid_types:
            raise ValueError(f"Invalid plugin type: {v}. Must be one of {valid_types}")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate plugin category."""
        valid_categories = {
            "core",
            "enterprise",
            "community",
            "experimental",
            "security",
            "monitoring",
            "integration",
            "utility",
        }
        if v not in valid_categories:
            raise ValueError(
                f"Invalid category: {v}. Must be one of {valid_categories}"
            )
        return v


class PluginQualityMetrics(BaseModel):
    """Plugin quality metrics for quality gate validation."""

    # Code quality
    code_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    test_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    documentation_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Security metrics
    security_scan_passed: bool = False
    vulnerability_count: int = Field(default=0, ge=0)
    security_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Performance metrics
    performance_benchmarked: bool = False
    memory_usage_mb: Optional[float] = Field(default=None, ge=0.0)
    cpu_usage_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Reliability metrics
    error_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uptime_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Compliance metrics
    compliance_validated: bool = False
    license_compatible: bool = False


class PluginConfigurationValidator:
    """
    Plugin configuration validator with comprehensive quality gates.

    Validates plugin configurations, metadata, dependencies, security,
    and compliance requirements to ensure high-quality plugin ecosystem.
    """

    def __init__(self) -> None:
        """Initialize plugin configuration validator."""
        self.quality_validator = get_quality_gate_validator()
        self._quality_thresholds = {
            "min_code_coverage": 0.8,
            "min_test_coverage": 0.9,
            "min_documentation_coverage": 0.7,
            "max_vulnerability_count": 0,
            "min_security_score": 0.8,
            "max_memory_usage_mb": 100.0,
            "max_cpu_usage_percent": 10.0,
            "max_error_rate": 0.01,
            "min_uptime_percent": 99.0,
        }

    async def validate_plugin_configuration(
        self,
        metadata: PluginMetadata,
        quality_metrics: Optional[PluginQualityMetrics] = None,
    ) -> Dict[str, Any]:
        """
        Validate complete plugin configuration with quality gates.

        Args:
            metadata: Plugin metadata to validate
            quality_metrics: Optional quality metrics for validation

        Returns:
            Validation results with quality assessment

        Raises:
            ValidationError: If validation fails
        """
        valid: bool = True
        quality_passed: bool = True
        security_passed: bool = True
        compatibility_passed: bool = True
        violations: List[str] = []
        warnings: List[str] = []
        quality_scores: Dict[str, float] = {}

        # Validate metadata
        try:
            await self._validate_metadata(metadata)
        except ValidationError as e:
            valid = False
            violations.append(f"Metadata validation failed: {e}")

        # Validate compatibility
        try:
            await self._validate_compatibility(metadata)
        except ValidationError as e:
            compatibility_passed = False
            violations.append(f"Compatibility validation failed: {e}")

        # Validate dependencies
        try:
            await self._validate_dependencies(metadata)
        except ValidationError as e:
            valid = False
            violations.append(f"Dependency validation failed: {e}")

        # Validate security
        try:
            await self._validate_security(metadata)
        except ValidationError as e:
            security_passed = False
            violations.append(f"Security validation failed: {e}")

        # Validate quality gates if metrics provided
        if quality_metrics:
            try:
                quality_results = await self._validate_quality_gates(quality_metrics)
                quality_scores = quality_results["scores"]
                if not quality_results["passed"]:
                    quality_passed = False
                    violations.extend(quality_results["violations"])
            except ValidationError as e:
                quality_passed = False
                violations.append(f"Quality gate validation failed: {e}")

        # Overall validation result
        if violations:
            raise ValidationError(
                f"Plugin configuration validation failed: {'; '.join(violations)}",
                validation_results={
                    "valid": valid,
                    "quality_passed": quality_passed,
                    "security_passed": security_passed,
                    "compatibility_passed": compatibility_passed,
                    "violations": violations,
                    "warnings": warnings,
                    "quality_scores": quality_scores,
                },
            )

        return {
            "valid": valid,
            "quality_passed": quality_passed,
            "security_passed": security_passed,
            "compatibility_passed": compatibility_passed,
            "violations": violations,
            "warnings": warnings,
            "quality_scores": quality_scores,
        }

    async def _validate_metadata(self, metadata: PluginMetadata) -> None:
        """Validate plugin metadata."""
        # Validate version format
        try:
            version.parse(metadata.version.to_string())
        except Exception as e:
            raise ValidationError(
                f"Invalid plugin version format: {metadata.version}"
            ) from e

        # Validate entry point format
        if ":" not in metadata.entry_point:
            raise ValidationError(
                f"Invalid entry point format: {metadata.entry_point}. Expected 'module:class'"
            )

        # Validate interfaces
        valid_interfaces = {
            "fapilog.sinks.Sink",
            "fapilog.enrichers.Enricher",
            "fapilog.processors.Processor",
            "fapilog.filters.Filter",
            "fapilog.formatters.Formatter",
            "fapilog.transports.Transport",
            "fapilog.serializers.Serializer",
            "fapilog.middleware.Middleware",
            "fapilog.extensions.Extension",
        }

        for interface in metadata.interfaces:
            if interface not in valid_interfaces:
                raise ValidationError(
                    f"Unknown interface: {interface}. Must be one of {valid_interfaces}"
                )

    async def _validate_compatibility(self, metadata: PluginMetadata) -> None:
        """Validate plugin compatibility requirements."""
        current_fapilog_version = "3.0.0"  # This would come from the actual version

        # Check Fapilog version compatibility
        min_version = version.parse(metadata.fapilog_version_min)
        current_version = version.parse(current_fapilog_version)

        if current_version < min_version:
            raise ValidationError(
                f"Plugin requires Fapilog {metadata.fapilog_version_min}, but current version is {current_fapilog_version}"
            )

        if metadata.fapilog_version_max:
            max_version = version.parse(metadata.fapilog_version_max)
            if current_version > max_version:
                raise ValidationError(
                    f"Plugin supports Fapilog up to {metadata.fapilog_version_max}, but current version is {current_fapilog_version}"
                )

        # Check Python version compatibility
        import sys

        current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
        min_python = metadata.python_version_min

        if version.parse(current_python) < version.parse(min_python):
            raise ValidationError(
                f"Plugin requires Python {min_python}, but current version is {current_python}"
            )

    async def _validate_dependencies(self, metadata: PluginMetadata) -> None:
        """Validate plugin dependencies."""
        for dependency in metadata.dependencies:
            # Check if dependency is available (simplified check)
            try:
                import importlib

                importlib.import_module(dependency.name.replace("-", "_"))
            except ImportError:
                if not dependency.optional:
                    raise ValidationError(
                        f"Required dependency not found: {dependency.name}"
                    )

        # Check for system dependencies
        for sys_dep in metadata.system_dependencies:
            # This is a simplified check - in practice, you'd check system packages
            if sys_dep in [
                "gcc",
                "make",
                "cmake",
            ] and not await self._check_system_dependency(sys_dep):
                raise ValidationError(
                    f"Required system dependency not found: {sys_dep}"
                )

    async def _validate_security(self, metadata: PluginMetadata) -> None:
        """Validate plugin security requirements."""
        # Check signature if required
        if not metadata.trusted_publisher and not metadata.signature:
            raise ValidationError(
                "Plugin from untrusted publisher must have a valid signature"
            )

        # Validate checksum if provided
        if metadata.checksum and len(metadata.checksum) < 32:
            raise ValidationError("Plugin checksum appears to be invalid (too short)")

        # Check for potentially dangerous entry points
        dangerous_modules = ["os", "subprocess", "sys", "__builtins__"]
        entry_module = metadata.entry_point.split(":")[0]

        if any(danger in entry_module for danger in dangerous_modules):
            raise ValidationError(
                f"Plugin entry point uses potentially dangerous module: {entry_module}"
            )

    async def _validate_quality_gates(
        self, quality_metrics: PluginQualityMetrics
    ) -> Dict[str, Any]:
        """Validate plugin against quality gates."""
        passed: bool = True
        violations: List[str] = []
        scores: Dict[str, float] = {}

        # Code coverage check
        if quality_metrics.code_coverage is not None:
            scores["code_coverage"] = quality_metrics.code_coverage
            if (
                quality_metrics.code_coverage
                < self._quality_thresholds["min_code_coverage"]
            ):
                passed = False
                violations.append(
                    f"Code coverage {quality_metrics.code_coverage:.2f} below threshold {self._quality_thresholds['min_code_coverage']:.2f}"
                )

        # Test coverage check
        if quality_metrics.test_coverage is not None:
            scores["test_coverage"] = quality_metrics.test_coverage
            if (
                quality_metrics.test_coverage
                < self._quality_thresholds["min_test_coverage"]
            ):
                passed = False
                violations.append(
                    f"Test coverage {quality_metrics.test_coverage:.2f} below threshold {self._quality_thresholds['min_test_coverage']:.2f}"
                )

        # Security check
        if (
            quality_metrics.vulnerability_count
            > self._quality_thresholds["max_vulnerability_count"]
        ):
            passed = False
            violations.append(
                f"Vulnerability count {quality_metrics.vulnerability_count} exceeds threshold {self._quality_thresholds['max_vulnerability_count']}"
            )

        # Performance checks
        if quality_metrics.memory_usage_mb is not None:
            if (
                quality_metrics.memory_usage_mb
                > self._quality_thresholds["max_memory_usage_mb"]
            ):
                passed = False
                violations.append(
                    f"Memory usage {quality_metrics.memory_usage_mb:.1f}MB exceeds threshold {self._quality_thresholds['max_memory_usage_mb']:.1f}MB"
                )

        # Mandatory quality checks
        if not quality_metrics.security_scan_passed:
            passed = False
            violations.append("Security scan must pass")

        if not quality_metrics.compliance_validated:
            passed = False
            violations.append("Compliance validation required")

        if not quality_metrics.license_compatible:
            passed = False
            violations.append("License compatibility check failed")

        return {"passed": passed, "violations": violations, "scores": scores}

    async def _check_system_dependency(self, dependency: str) -> bool:
        """Check if system dependency is available."""
        import subprocess

        try:
            # Check if command exists
            result = await asyncio.create_subprocess_exec(
                "which",
                dependency,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.wait()
            return result.returncode == 0
        except Exception:
            return False

    def set_quality_threshold(self, metric: str, threshold: float) -> None:
        """Set quality threshold for a specific metric."""
        self._quality_thresholds[metric] = threshold

    def get_quality_thresholds(self) -> Dict[str, float]:
        """Get current quality thresholds."""
        return self._quality_thresholds.copy()


class PluginConfigurationManager:
    """
    Plugin configuration manager for centralized configuration handling.

    Manages plugin configurations, validates against quality gates,
    and provides configuration lifecycle management.
    """

    def __init__(self) -> None:
        """Initialize plugin configuration manager."""
        self.validator = PluginConfigurationValidator()
        self._loaded_configs: Dict[str, PluginMetadata] = {}
        self._config_cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def load_plugin_config(
        self, config_path: Path, validate_quality: bool = True
    ) -> PluginMetadata:
        """
        Load and validate plugin configuration from file.

        Args:
            config_path: Path to plugin configuration file
            validate_quality: Whether to validate against quality gates

        Returns:
            Validated plugin metadata

        Raises:
            PluginError: If configuration loading fails
        """
        async with self._lock:
            try:
                # Load configuration file
                if not config_path.exists():
                    raise PluginError(
                        f"Plugin configuration file not found: {config_path}"
                    )

                # Parse configuration based on file type
                content = await asyncio.to_thread(config_path.read_text)

                if config_path.suffix.lower() == ".json":
                    import json

                    config_data = json.loads(content)
                elif config_path.suffix.lower() in [".yaml", ".yml"]:
                    import yaml

                    config_data = yaml.safe_load(content)
                elif config_path.suffix.lower() == ".toml":
                    import tomllib

                    config_data = tomllib.loads(content)
                else:
                    raise PluginError(
                        f"Unsupported configuration file format: {config_path.suffix}"
                    )

                # Create metadata object
                metadata = PluginMetadata(**config_data)

                # Validate configuration
                if validate_quality:
                    await self.validator.validate_plugin_configuration(metadata)

                # Cache configuration
                self._loaded_configs[metadata.name] = metadata

                return metadata

            except Exception as e:
                if isinstance(e, (PluginError, ValidationError)):
                    raise

                raise PluginError(
                    f"Failed to load plugin configuration: {e}",
                    config_path=str(config_path),
                    cause=e,
                ) from e

    async def validate_plugin_compatibility(
        self, plugin_name: str, target_plugins: List[str]
    ) -> Dict[str, Any]:
        """
        Validate compatibility between plugins.

        Args:
            plugin_name: Name of plugin to validate
            target_plugins: List of plugins to check compatibility with

        Returns:
            Compatibility validation results
        """
        if plugin_name not in self._loaded_configs:
            raise PluginError(f"Plugin configuration not loaded: {plugin_name}")

        plugin_config = self._loaded_configs[plugin_name]
        compatible: bool = True
        conflicts: List[str] = []
        missing_dependencies: List[str] = []

        # Check dependencies
        for dependency in plugin_config.dependencies:
            if dependency.name not in target_plugins and not dependency.optional:
                compatible = False
                missing_dependencies.append(dependency.name)

        # Check for interface conflicts (simplified)
        for target_plugin_name in target_plugins:
            if target_plugin_name in self._loaded_configs:
                target_config = self._loaded_configs[target_plugin_name]

                # Check for conflicting interfaces
                common_interfaces = set(plugin_config.interfaces) & set(
                    target_config.interfaces
                )
                if (
                    common_interfaces
                    and plugin_config.plugin_type == target_config.plugin_type
                ):
                    compatible = False
                    conflicts.append(
                        f"Interface conflict with {target_plugin_name}: {', '.join(sorted(common_interfaces))}"
                    )

        return {
            "compatible": compatible,
            "conflicts": conflicts,
            "missing_dependencies": missing_dependencies,
        }

    def get_loaded_configs(self) -> Dict[str, PluginMetadata]:
        """Get all loaded plugin configurations."""
        return self._loaded_configs.copy()

    def get_plugin_config(self, plugin_name: str) -> Optional[PluginMetadata]:
        """Get configuration for a specific plugin."""
        return self._loaded_configs.get(plugin_name)


# Global plugin configuration manager
_plugin_config_manager: Optional[PluginConfigurationManager] = None
_plugin_config_lock = asyncio.Lock()


async def get_plugin_configuration_manager() -> PluginConfigurationManager:
    """Get global plugin configuration manager instance."""
    global _plugin_config_manager

    if _plugin_config_manager is None:
        async with _plugin_config_lock:
            if _plugin_config_manager is None:
                _plugin_config_manager = PluginConfigurationManager()

    return _plugin_config_manager
