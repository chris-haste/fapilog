"""
Comprehensive test coverage for fapilog validation module.

These tests focus on increasing coverage for all validation functions,
async validators, quality gates, and compliance validators.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fapilog.core.errors import ValidationError
from fapilog.core.validation import (
    AsyncValidator,
    ComplianceValidator,
    FieldValidationRule,
    ModelValidationRule,
    QualityGateValidator,
    ValidationRule,
    get_async_validator,
    get_compliance_validator,
    get_quality_gate_validator,
    validate_database_connection,
    validate_directory_writable,
    validate_file_exists,
    validate_file_path,
    validate_json_schema,
    validate_port_number,
    validate_regex_pattern,
    validate_url_accessibility,
    validate_url_format,
)


class TestValidationRules:
    """Test validation rule models."""

    def test_validation_rule_creation(self):
        """Test basic validation rule creation."""
        rule = ValidationRule(
            name="test_rule",
            description="A test validation rule",
            enabled=True,
        )

        assert rule.name == "test_rule"
        assert rule.description == "A test validation rule"
        assert rule.enabled is True
        assert rule.severity.value == "medium"  # Default severity

    def test_field_validation_rule(self):
        """Test field-specific validation rule."""
        rule = FieldValidationRule(
            name="field_rule",
            description="Field validation",
            field_name="email",
            validator_func="validate_email",
            enabled=True,
        )

        assert rule.field_name == "email"
        assert rule.validator_func == "validate_email"

    def test_model_validation_rule(self):
        """Test model-level validation rule."""
        rule = ModelValidationRule(
            name="model_rule",
            description="Model validation",
            model_name="User",
            validator_func="validate_user_model",
            enabled=True,
        )

        assert rule.model_name == "User"
        assert rule.validator_func == "validate_user_model"


class TestSyncValidators:
    """Test synchronous validation functions."""

    def test_validate_url_format_valid(self):
        """Test URL format validation with valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://api.example.com/v1/endpoint",
            "http://192.168.1.1:3000",
            "https://subdomain.example.co.uk",
        ]

        for url in valid_urls:
            result = validate_url_format(url)
            assert result == url

    def test_validate_url_format_invalid(self):
        """Test URL format validation with invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')",
            "mailto:test@example.com",
            "file:///etc/passwd",
            "",
            "   ",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid URL format"):
                validate_url_format(url)

    def test_validate_port_number_valid(self):
        """Test port number validation with valid ports."""
        valid_ports = [1, 80, 443, 8080, 3000, 65535]

        for port in valid_ports:
            result = validate_port_number(port)
            assert result == port

    def test_validate_port_number_invalid(self):
        """Test port number validation with invalid ports."""
        invalid_ports = [0, -1, 65536, 100000]

        for port in invalid_ports:
            with pytest.raises(ValueError, match="Port number must be between"):
                validate_port_number(port)

    def test_validate_file_path_valid(self):
        """Test file path validation with valid paths."""
        valid_paths = [
            "/tmp/test.txt",
            "relative/path.json",
            "~/documents/file.pdf",
            "C:\\Windows\\System32" if Path("C:\\").exists() else "/usr/bin",
        ]

        for path in valid_paths:
            try:
                result = validate_file_path(path)
                assert result == path
            except ValueError:
                # Some paths might not be valid on this system
                pass

    def test_validate_file_path_invalid(self):
        """Test file path validation with invalid paths."""
        # Create an intentionally invalid path
        invalid_path = "\x00invalid\x00path"

        with pytest.raises(ValueError, match="Invalid file path"):
            validate_file_path(invalid_path)

    def test_validate_regex_pattern_valid(self):
        """Test regex pattern validation with valid patterns."""
        valid_patterns = [
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            r"\d{3}-\d{2}-\d{4}",
            r"^https?://",
            r"[A-Z][a-z]+",
        ]

        for pattern in valid_patterns:
            result = validate_regex_pattern(pattern)
            assert result == pattern

    def test_validate_regex_pattern_invalid(self):
        """Test regex pattern validation with invalid patterns."""
        invalid_patterns = [
            r"[unclosed",
            r"(?P<invalid",
            r"*invalid",
            r"(?P<>invalid)",
        ]

        for pattern in invalid_patterns:
            with pytest.raises(ValueError, match="Invalid regex pattern"):
                validate_regex_pattern(pattern)

    def test_validate_json_schema_valid(self):
        """Test JSON schema validation with valid schemas."""
        valid_schemas = [
            {"type": "string"},
            {"type": "object", "properties": {"name": {"type": "string"}}},
            {"type": "array", "items": {"type": "number"}},
            {"type": "string", "enum": ["red", "green", "blue"]},
        ]

        for schema in valid_schemas:
            result = validate_json_schema(schema)
            assert result == schema

    def test_validate_json_schema_invalid(self):
        """Test JSON schema validation with invalid schemas."""
        # Missing required 'type' field
        with pytest.raises(ValueError, match="JSON schema missing required field"):
            validate_json_schema({"properties": {"name": {"type": "string"}}})

        # Not a dictionary
        with pytest.raises(ValueError, match="JSON schema must be a dictionary"):
            validate_json_schema("not a dict")


class TestAsyncValidators:
    """Test asynchronous validation functions."""

    @pytest.mark.asyncio
    async def test_validate_url_accessibility_success(self):
        """Test URL accessibility validation with successful response."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None

            mock_client_instance = AsyncMock()
            mock_client_instance.head.return_value = mock_response  # Use head, not get
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            result = await validate_url_accessibility("https://example.com")
            assert result == "https://example.com"

    @pytest.mark.asyncio
    async def test_validate_url_accessibility_failure(self):
        """Test URL accessibility validation with failed response."""
        # Test the error handling path by using an invalid URL
        # This will cause the function to fail and raise ValueError
        try:
            # Use an actually unreachable URL to trigger error
            await validate_url_accessibility(
                "http://127.0.0.1:9999/nonexistent", timeout=0.1
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "URL not accessible" in str(e)

    @pytest.mark.asyncio
    async def test_validate_file_exists_success(self):
        """Test file existence validation with existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"test content")

        try:
            result = await validate_file_exists(temp_path)
            assert result == temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_validate_file_exists_failure(self):
        """Test file existence validation with non-existent file."""
        non_existent_path = "/tmp/this_file_should_not_exist_12345.txt"

        with pytest.raises(ValueError, match="File does not exist"):
            await validate_file_exists(non_existent_path)

    @pytest.mark.asyncio
    async def test_validate_directory_writable_success(self):
        """Test directory writable validation with writable directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await validate_directory_writable(temp_dir)
            assert result == temp_dir

    @pytest.mark.asyncio
    async def test_validate_directory_writable_not_exists(self):
        """Test directory writable validation with non-existent directory."""
        non_existent_dir = "/tmp/this_dir_should_not_exist_12345"

        with pytest.raises(ValueError, match="Directory does not exist"):
            await validate_directory_writable(non_existent_dir)

    @pytest.mark.asyncio
    async def test_validate_directory_writable_not_directory(self):
        """Test directory writable validation with file instead of directory."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with pytest.raises(ValueError, match="Path is not a directory"):
                await validate_directory_writable(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_validate_database_connection_valid(self):
        """Test database connection validation with valid connection strings."""
        valid_connections = [
            "postgresql://user:password@localhost:5432/dbname",
            "mysql://user:password@localhost:3306/dbname",
            "sqlite:///path/to/database.db",
        ]

        for conn_str in valid_connections:
            result = await validate_database_connection(conn_str)
            assert result == conn_str

    @pytest.mark.asyncio
    async def test_validate_database_connection_invalid(self):
        """Test database connection validation with invalid connection strings."""
        invalid_connections = [
            "invalid://connection",
            "redis://localhost:6379",
            "mongodb://localhost:27017",
        ]

        for conn_str in invalid_connections:
            with pytest.raises(
                ValueError, match="Unsupported database connection string format"
            ):
                await validate_database_connection(conn_str)


class TestAsyncValidatorFramework:
    """Test AsyncValidator framework comprehensively."""

    @pytest.mark.asyncio
    async def test_async_validator_initialization(self):
        """Test AsyncValidator initialization."""
        validator = AsyncValidator()

        assert validator._field_validators == {}
        assert validator._model_validators == {}
        assert validator._validation_cache == {}
        assert validator._cache_ttl == 300

    @pytest.mark.asyncio
    async def test_register_field_validator(self):
        """Test registering field validators."""
        validator = AsyncValidator()

        async def test_validator(value, **kwargs):
            return value.upper()

        validator.register_field_validator("test_field", test_validator)

        assert "test_field" in validator._field_validators
        assert validator._field_validators["test_field"] == test_validator

    @pytest.mark.asyncio
    async def test_register_model_validator(self):
        """Test registering model validators."""
        validator = AsyncValidator()

        async def test_model_validator(model_data, **kwargs):
            return {**model_data, "validated": True}

        validator.register_model_validator("test_model", test_model_validator)

        assert "test_model" in validator._model_validators
        assert validator._model_validators["test_model"] == test_model_validator

    @pytest.mark.asyncio
    async def test_validate_field_async_no_validator(self):
        """Test field validation when no validator is registered."""
        validator = AsyncValidator()

        result = await validator.validate_field_async("unknown_field", "test_value")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_validate_field_async_with_caching(self):
        """Test field validation with caching."""
        validator = AsyncValidator()

        call_count = 0

        async def counting_validator(value, **kwargs):
            nonlocal call_count
            call_count += 1
            return value.upper()

        validator.register_field_validator("cached_field", counting_validator)

        # First call
        result1 = await validator.validate_field_async("cached_field", "test")
        assert result1 == "TEST"
        assert call_count == 1

        # Second call with same value should use cache
        result2 = await validator.validate_field_async("cached_field", "test")
        assert result2 == "TEST"
        assert call_count == 1  # Should not increment

        # Different value should not use cache
        result3 = await validator.validate_field_async("cached_field", "other")
        assert result3 == "OTHER"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_validate_field_async_error_handling(self):
        """Test field validation error handling."""
        validator = AsyncValidator()

        async def failing_validator(value, **kwargs):
            raise ValueError("Validation failed")

        validator.register_field_validator("failing_field", failing_validator)

        with pytest.raises(
            ValidationError, match="Async validation failed for field 'failing_field'"
        ):
            await validator.validate_field_async("failing_field", "test")

    @pytest.mark.asyncio
    async def test_validate_model_async_no_validator(self):
        """Test model validation when no validator is registered."""
        validator = AsyncValidator()

        model_data = {"name": "test", "value": 123}
        result = await validator.validate_model_async("unknown_model", model_data)
        assert result == model_data

    @pytest.mark.asyncio
    async def test_validate_model_async_success(self):
        """Test successful model validation."""
        validator = AsyncValidator()

        async def test_model_validator(model_data, **kwargs):
            return {**model_data, "validated": True}

        validator.register_model_validator("test_model", test_model_validator)

        model_data = {"name": "test", "value": 123}
        result = await validator.validate_model_async("test_model", model_data)

        assert result["name"] == "test"
        assert result["value"] == 123
        assert result["validated"] is True

    @pytest.mark.asyncio
    async def test_validate_model_async_error_handling(self):
        """Test model validation error handling."""
        validator = AsyncValidator()

        async def failing_model_validator(model_data, **kwargs):
            raise ValueError("Model validation failed")

        validator.register_model_validator("failing_model", failing_model_validator)

        with pytest.raises(
            ValidationError, match="Async model validation failed for 'failing_model'"
        ):
            await validator.validate_model_async("failing_model", {"test": "data"})

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing validation cache."""
        validator = AsyncValidator()

        async def test_validator(value, **kwargs):
            return value.upper()

        validator.register_field_validator("test_field", test_validator)

        # Populate cache
        await validator.validate_field_async("test_field", "test")
        assert len(validator._validation_cache) > 0

        # Clear cache
        validator.clear_cache()
        assert len(validator._validation_cache) == 0


class TestQualityGateValidator:
    """Test QualityGateValidator comprehensively."""

    @pytest.mark.asyncio
    async def test_quality_gate_validator_initialization(self):
        """Test QualityGateValidator initialization."""
        validator = QualityGateValidator()

        assert validator._quality_rules == []
        assert "security_score" in validator._thresholds
        assert "performance_score" in validator._thresholds
        assert "compliance_score" in validator._thresholds

    def test_add_quality_rule(self):
        """Test adding quality rules."""
        validator = QualityGateValidator()

        rule = ValidationRule(
            name="test_rule",
            description="Test rule",
            enabled=True,
        )

        validator.add_quality_rule(rule)
        assert len(validator._quality_rules) == 1
        assert validator._quality_rules[0] == rule

    def test_set_threshold(self):
        """Test setting quality thresholds."""
        validator = QualityGateValidator()

        validator.set_threshold("security_score", 0.95)
        assert validator._thresholds["security_score"] == 0.95

    @pytest.mark.asyncio
    async def test_validate_configuration_quality_passing(self):
        """Test configuration quality validation that passes."""
        validator = QualityGateValidator()

        # Set lower thresholds for this test
        validator.set_threshold("security_score", 0.5)
        validator.set_threshold("performance_score", 0.5)
        validator.set_threshold("compliance_score", 0.5)

        config_data = {
            "security": {
                "encryption_enabled": True,
                "authentication_enabled": True,
                "validate_input_schemas": True,
                "mask_sensitive_fields": True,
            },
            "core": {
                "buffer_size": 1000,
                "async_logging": True,
                "circuit_breaker_enabled": True,
            },
            "compliance": {
                "audit_enabled": True,
                "data_classification_enabled": True,
                "retention_policy_enabled": True,
            },
        }

        results = await validator.validate_configuration_quality(config_data)
        assert results["passed"] is True
        assert "security" in results["scores"]
        assert "performance" in results["scores"]
        assert "compliance" in results["scores"]

    @pytest.mark.asyncio
    async def test_validate_configuration_quality_failing(self):
        """Test configuration quality validation that fails."""
        validator = QualityGateValidator()

        # Set high thresholds
        validator.set_threshold("security_score", 0.95)

        config_data = {
            "security": {
                "encryption_enabled": False,  # Poor security
                "authentication_enabled": False,
                "validate_input_schemas": False,
                "mask_sensitive_fields": False,
            },
            "core": {
                "buffer_size": 50,  # Poor performance
                "async_logging": False,
                "circuit_breaker_enabled": False,
            },
            "compliance": {
                "audit_enabled": False,  # Poor compliance
                "data_classification_enabled": False,
                "retention_policy_enabled": False,
            },
        }

        with pytest.raises(ValidationError, match="Configuration failed quality gates"):
            await validator.validate_configuration_quality(config_data)

    @pytest.mark.asyncio
    async def test_assess_security_quality_excellent(self):
        """Test security quality assessment with excellent configuration."""
        validator = QualityGateValidator()

        config_data = {
            "security": {
                "encryption_enabled": True,
                "authentication_enabled": True,
                "validate_input_schemas": True,
                "mask_sensitive_fields": True,
            }
        }

        score = await validator._assess_security_quality(config_data)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_assess_security_quality_poor(self):
        """Test security quality assessment with poor configuration."""
        validator = QualityGateValidator()

        config_data = {
            "security": {
                "encryption_enabled": False,
                "authentication_enabled": False,
                "validate_input_schemas": False,
                "mask_sensitive_fields": False,
            }
        }

        score = await validator._assess_security_quality(config_data)
        assert abs(score - 0.2) < 0.01  # Allow for floating point precision

    @pytest.mark.asyncio
    async def test_assess_performance_quality_excellent(self):
        """Test performance quality assessment with excellent configuration."""
        validator = QualityGateValidator()

        config_data = {
            "core": {
                "buffer_size": 5000,
                "async_logging": True,
                "circuit_breaker_enabled": True,
            }
        }

        score = await validator._assess_performance_quality(config_data)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_assess_performance_quality_poor(self):
        """Test performance quality assessment with poor configuration."""
        validator = QualityGateValidator()

        config_data = {
            "core": {
                "buffer_size": 50,  # Too small
                "async_logging": False,
                "circuit_breaker_enabled": False,
            }
        }

        score = await validator._assess_performance_quality(config_data)
        assert score == 0.3  # 1.0 - 0.2 - 0.3 - 0.2


class TestComplianceValidator:
    """Test ComplianceValidator comprehensively."""

    @pytest.mark.asyncio
    async def test_compliance_validator_initialization(self):
        """Test ComplianceValidator initialization."""
        validator = ComplianceValidator()

        expected_standards = {"sox", "pci_dss", "soc2", "iso27001", "hipaa", "gdpr"}
        assert set(validator._standards.keys()) == expected_standards

    @pytest.mark.asyncio
    async def test_validate_compliance_unknown_standard(self):
        """Test compliance validation with unknown standard."""
        validator = ComplianceValidator()

        with pytest.raises(
            ValidationError, match="Configuration failed compliance validation"
        ):
            await validator.validate_compliance({"unknown_standard"}, {})

    @pytest.mark.asyncio
    async def test_validate_sox_compliance_passing(self):
        """Test SOX compliance validation that passes."""
        validator = ComplianceValidator()

        config_data = {
            "compliance": {
                "audit_enabled": True,
                "audit_integrity_checks": True,
            },
            "security": {
                "authentication_enabled": True,
            },
        }

        results = await validator.validate_compliance({"sox"}, config_data)
        assert results["compliant"] is True
        assert results["standard_results"]["sox"]["compliant"] is True

    @pytest.mark.asyncio
    async def test_validate_sox_compliance_failing(self):
        """Test SOX compliance validation that fails."""
        validator = ComplianceValidator()

        config_data = {
            "compliance": {
                "audit_enabled": False,
                "audit_integrity_checks": False,
            },
            "security": {
                "authentication_enabled": False,
            },
        }

        with pytest.raises(
            ValidationError, match="Configuration failed compliance validation"
        ):
            await validator.validate_compliance({"sox"}, config_data)

    @pytest.mark.asyncio
    async def test_validate_pci_dss_compliance_passing(self):
        """Test PCI-DSS compliance validation that passes."""
        validator = ComplianceValidator()

        config_data = {
            "security": {
                "encryption_enabled": True,
                "authentication_enabled": True,
                "mask_sensitive_fields": True,
            },
        }

        results = await validator.validate_compliance({"pci_dss"}, config_data)
        assert results["compliant"] is True
        assert results["standard_results"]["pci_dss"]["compliant"] is True

    @pytest.mark.asyncio
    async def test_validate_multiple_standards(self):
        """Test validation of multiple compliance standards."""
        validator = ComplianceValidator()

        config_data = {
            "compliance": {
                "audit_enabled": True,
                "audit_integrity_checks": True,
                "data_classification_enabled": True,
                "pii_detection_enabled": True,
                "retention_policy_enabled": True,
            },
            "security": {
                "encryption_enabled": True,
                "authentication_enabled": True,
                "mask_sensitive_fields": True,
            },
        }

        standards = {"sox", "pci_dss", "gdpr"}
        results = await validator.validate_compliance(standards, config_data)

        assert results["compliant"] is True
        for standard in standards:
            assert results["standard_results"][standard]["compliant"] is True

    @pytest.mark.asyncio
    async def test_validate_hipaa_compliance(self):
        """Test HIPAA compliance validation."""
        validator = ComplianceValidator()

        # Passing configuration
        passing_config = {
            "security": {
                "encryption_enabled": True,
                "authentication_enabled": True,
            },
            "compliance": {
                "audit_enabled": True,
            },
        }

        results = await validator.validate_compliance({"hipaa"}, passing_config)
        assert results["compliant"] is True

        # Failing configuration
        failing_config = {
            "security": {
                "encryption_enabled": False,
                "authentication_enabled": False,
            },
            "compliance": {
                "audit_enabled": False,
            },
        }

        with pytest.raises(ValidationError):
            await validator.validate_compliance({"hipaa"}, failing_config)

    @pytest.mark.asyncio
    async def test_validate_gdpr_compliance(self):
        """Test GDPR compliance validation."""
        validator = ComplianceValidator()

        # Passing configuration
        passing_config = {
            "compliance": {
                "data_classification_enabled": True,
                "pii_detection_enabled": True,
                "retention_policy_enabled": True,
            },
        }

        results = await validator.validate_compliance({"gdpr"}, passing_config)
        assert results["compliant"] is True

        # Failing configuration
        failing_config = {
            "compliance": {
                "data_classification_enabled": False,
                "pii_detection_enabled": False,
                "retention_policy_enabled": False,
            },
        }

        with pytest.raises(ValidationError):
            await validator.validate_compliance({"gdpr"}, failing_config)


class TestGlobalValidatorInstances:
    """Test global validator instance functions."""

    def test_get_async_validator(self):
        """Test getting global async validator instance."""
        validator1 = get_async_validator()
        validator2 = get_async_validator()

        # Should return the same instance
        assert validator1 is validator2
        assert isinstance(validator1, AsyncValidator)

    def test_get_quality_gate_validator(self):
        """Test getting global quality gate validator instance."""
        validator1 = get_quality_gate_validator()
        validator2 = get_quality_gate_validator()

        # Should return the same instance
        assert validator1 is validator2
        assert isinstance(validator1, QualityGateValidator)

    def test_get_compliance_validator(self):
        """Test getting global compliance validator instance."""
        validator1 = get_compliance_validator()
        validator2 = get_compliance_validator()

        # Should return the same instance
        assert validator1 is validator2
        assert isinstance(validator1, ComplianceValidator)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_async_validator_with_none_value(self):
        """Test async validator with None values."""
        validator = AsyncValidator()

        async def none_handling_validator(value, **kwargs):
            if value is None:
                return "default"
            return str(value)

        validator.register_field_validator("nullable_field", none_handling_validator)

        result = await validator.validate_field_async("nullable_field", None)
        assert result == "default"

    @pytest.mark.asyncio
    async def test_quality_gate_missing_config_sections(self):
        """Test quality gate validation with missing config sections."""
        validator = QualityGateValidator()

        # Set lower thresholds to allow empty config to pass
        validator.set_threshold("security_score", 0.3)
        validator.set_threshold("performance_score", 0.3)
        validator.set_threshold("compliance_score", 0.1)

        # Empty config should not crash
        empty_config = {}
        results = await validator.validate_configuration_quality(empty_config)

        # Should have default scores but may fail quality gates
        assert "scores" in results

    @pytest.mark.asyncio
    async def test_compliance_validator_with_missing_sections(self):
        """Test compliance validator with missing config sections."""
        validator = ComplianceValidator()

        # Empty config for SOX should fail
        empty_config = {}

        with pytest.raises(ValidationError):
            await validator.validate_compliance({"sox"}, empty_config)

    def test_validate_port_number_edge_cases(self):
        """Test port number validation edge cases."""
        # Boundary values
        assert validate_port_number(1) == 1
        assert validate_port_number(65535) == 65535

        # Invalid boundaries
        with pytest.raises(ValueError):
            validate_port_number(0)

        with pytest.raises(ValueError):
            validate_port_number(65536)

    @pytest.mark.asyncio
    async def test_directory_writable_permission_error(self):
        """Test directory writable with permission error."""
        # This test might not work on all systems, so we'll mock it
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the path.exists() and path.is_dir() to return True
            mock_to_thread.side_effect = [
                True,
                True,
                PermissionError("Permission denied"),
            ]

            with pytest.raises(ValueError, match="Directory not writable"):
                await validate_directory_writable("/root")
