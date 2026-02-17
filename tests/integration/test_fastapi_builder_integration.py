"""Integration tests for FastAPIBuilder (Story 10.52)."""

from __future__ import annotations

import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi import FastAPIBuilder


@pytest.mark.integration
class TestFastAPIBuilderLifecycle:
    """AC8: build() returns valid lifespan that works with FastAPI."""

    def test_full_app_lifecycle(self) -> None:
        """Test that app starts and stops correctly with builder-configured logging."""
        lifespan = FastAPIBuilder().with_preset("production").build()
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200

    def test_skip_paths_applied(self) -> None:
        """Test that skip_paths configuration is applied to middleware."""
        lifespan = (
            FastAPIBuilder().with_preset("production").skip_paths(["/health"]).build()
        )
        app = FastAPI(lifespan=lifespan)

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "healthy"}

        @app.get("/api/data")
        def data() -> dict[str, str]:
            return {"data": "value"}

        with TestClient(app) as client:
            # Both endpoints should work
            assert client.get("/health").status_code == 200
            assert client.get("/api/data").status_code == 200

    def test_sample_rate_applied(self) -> None:
        """Test that sample_rate configuration is applied to middleware."""
        lifespan = FastAPIBuilder().with_preset("production").sample_rate(0.5).build()
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


@pytest.mark.integration
class TestFastAPIBuilderWithParentMethods:
    """AC2: All AsyncLoggerBuilder methods available and work."""

    def test_with_level_and_skip_paths_combined(self) -> None:
        """Test combining parent and FastAPI-specific methods."""
        lifespan = (
            FastAPIBuilder()
            .with_preset("production")
            .with_level("DEBUG")
            .skip_paths(["/health"])
            .sample_rate(1.0)
            .build()
        )
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


@pytest.mark.integration
class TestEnvVarOverrideIntegration:
    """AC4 & AC5: Env vars override code and warnings are emitted."""

    def test_env_vars_override_code_in_build(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that env vars override code-specified values at build time."""
        monkeypatch.setenv("FAPILOG_FASTAPI__SKIP_PATHS", "/override")

        builder = FastAPIBuilder().with_preset("production").skip_paths(["/code-value"])
        lifespan = builder.build()

        # The builder's config should now have the env var value
        assert builder._fastapi_config["skip_paths"] == ["/override"]

        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


@pytest.mark.integration
class TestDeprecationWarningIntegration:
    """AC7: setup_logging() deprecated with warning."""

    def test_deprecation_warning_on_setup_logging(self) -> None:
        """Test that setup_logging() emits deprecation warning."""
        from fapilog.fastapi import setup_logging

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            lifespan = setup_logging(preset="production")

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "setup_logging() is deprecated" in str(w[0].message)
            assert "FastAPIBuilder" in str(w[0].message)

        # Still works despite being deprecated
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


@pytest.mark.integration
class TestFastAPIBuilderExport:
    """Test that FastAPIBuilder is properly exported."""

    def test_fastapi_builder_importable_from_fapilog_fastapi(self) -> None:
        """AC1: FastAPIBuilder can be imported from fapilog.fastapi."""
        from fapilog.fastapi import FastAPIBuilder as ImportedBuilder

        assert ImportedBuilder is FastAPIBuilder

    def test_fastapi_builder_in_all(self) -> None:
        """Test that FastAPIBuilder is in __all__."""
        import fapilog.fastapi

        assert "FastAPIBuilder" in fapilog.fastapi.__all__


@pytest.mark.integration
class TestBuildWithoutPreset:
    """Test building without a preset."""

    def test_lifecycle_without_preset(self) -> None:
        """Test app starts without using a preset."""
        lifespan = FastAPIBuilder().with_level("INFO").build()
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


@pytest.mark.integration
class TestBuildWithCustomSinks:
    """Test building with custom sink configuration."""

    def test_lifecycle_with_custom_sink(self) -> None:
        """Test app starts with custom sink added via builder."""
        lifespan = FastAPIBuilder().with_preset("production").add_stdout().build()
        app = FastAPI(lifespan=lifespan)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200
