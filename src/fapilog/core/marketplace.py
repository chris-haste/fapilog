"""
Plugin marketplace configuration for Fapilog v3.

Provides types and defaults for future remote marketplace integration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarketplaceSettings(BaseModel):
    enabled: bool = Field(default=False, description="Enable marketplace features")
    index_url: str = Field(
        default="https://plugins.fapilog.dev/index.json",
        description="Marketplace index URL",
    )
    timeout_seconds: int = Field(
        default=5,
        ge=1,
        description="HTTP timeout in seconds",
    )
    verify_tls: bool = Field(
        default=True,
        description="Verify TLS certificates",
    )
