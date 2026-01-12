"""Convenience factories for common sinks."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..core.types import _parse_size
from ..plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig


def rotating_file(
    path: str | Path,
    *,
    rotation: str | int | None = None,
    retention: int | None = None,
    compression: bool = False,
    mode: Literal["json", "text"] = "json",
) -> RotatingFileSink:
    """Create a rotating file sink with human-readable configuration.

    Args:
        path: File path like "logs/app.log" (directory is created if missing).
        rotation: Size-based rotation, e.g. "10 MB" or 10485760 (bytes).
        retention: Number of rotated files to keep (None = unlimited).
        compression: If True, compress rotated files with gzip.
        mode: Output format ("json" or "text").

    Examples:
        >>> from fapilog import get_logger
        >>> from fapilog.sinks import rotating_file
        >>> logger = get_logger(sinks=[rotating_file("logs/app.log")])
        >>> logger.info("started")

        >>> logger = get_logger(
        ...     sinks=[rotating_file("logs/app.log", rotation="10 MB", retention=7)]
        ... )
    """

    path_obj = Path(path)
    directory = path_obj.parent
    filename_prefix = path_obj.stem

    parsed_bytes = 10 * 1024 * 1024 if rotation is None else _parse_size(rotation)
    if parsed_bytes is None:
        raise ValueError("rotation must be a size string or integer")
    max_bytes = parsed_bytes

    config = RotatingFileSinkConfig(
        directory=directory,
        filename_prefix=filename_prefix,
        mode=mode,
        max_bytes=max_bytes,
        max_files=retention,
        compress_rotated=compression,
    )

    return RotatingFileSink(config)


__all__ = ["rotating_file"]
