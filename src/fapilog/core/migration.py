"""
Configuration migration and versioning support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping

from .settings import LATEST_CONFIG_SCHEMA_VERSION


@dataclass
class MigrationResult:
    migrated: Mapping[str, Any]
    from_version: str
    to_version: str
    did_migrate: bool


MigrationFunc = Callable[[Mapping[str, Any]], Mapping[str, Any]]


_MIGRATIONS: dict[str, MigrationFunc] = {}


def register_migration(from_version: str, func: MigrationFunc) -> None:
    _MIGRATIONS[from_version] = func


def migrate_to_latest(data: Mapping[str, Any]) -> MigrationResult:
    """Migrate arbitrary settings-like mapping to the latest schema version.

    Applies chained migrations until the version equals
    LATEST_CONFIG_SCHEMA_VERSION.
    """
    current_version = str(data.get("schema_version", "1.0"))
    if current_version == LATEST_CONFIG_SCHEMA_VERSION:
        return MigrationResult(data, current_version, current_version, False)

    # Copy to mutable for updates
    working: MutableMapping[str, Any] = dict(data)
    visited = set()

    while current_version != LATEST_CONFIG_SCHEMA_VERSION:
        if current_version in visited:
            # Safety: avoid cycles
            break
        visited.add(current_version)

        migrator = _MIGRATIONS.get(current_version)
        if migrator is None:
            # Default migration: bump version only
            working["schema_version"] = LATEST_CONFIG_SCHEMA_VERSION
            break
        working = dict(migrator(working))
        current_version = str(working.get("schema_version", current_version))

    # Ensure final version
    working["schema_version"] = LATEST_CONFIG_SCHEMA_VERSION
    return MigrationResult(
        working,
        str(data.get("schema_version", "1.0")),
        LATEST_CONFIG_SCHEMA_VERSION,
        True,
    )
