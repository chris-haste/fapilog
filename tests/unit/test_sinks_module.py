from pathlib import Path

from fapilog.plugins.sinks.rotating_file import RotatingFileSink
from fapilog.sinks import rotating_file


class TestRotatingFileFactory:
    """Tests for rotating_file() convenience function."""

    def test_rotating_file_minimal(self) -> None:
        sink = rotating_file("logs/app.log")

        assert isinstance(sink, RotatingFileSink)
        assert sink._cfg.directory == Path("logs")
        assert sink._cfg.filename_prefix == "app"
        assert sink._cfg.max_bytes == 10 * 1024 * 1024
        assert sink._cfg.max_files is None
        assert sink._cfg.compress_rotated is False
        assert sink._cfg.mode == "json"

    def test_rotating_file_with_rotation_string(self) -> None:
        sink = rotating_file("logs/app.log", rotation="50 MB")

        assert sink._cfg.max_bytes == 50 * 1024 * 1024

    def test_rotating_file_with_quoted_rotation_string(self) -> None:
        sink = rotating_file("logs/app.log", rotation='"10 MB"')

        assert sink._cfg.max_bytes == 10 * 1024 * 1024

    def test_rotating_file_with_rotation_int(self) -> None:
        sink = rotating_file("logs/app.log", rotation=1024)

        assert sink._cfg.max_bytes == 1024

    def test_rotating_file_with_retention(self) -> None:
        sink = rotating_file("logs/app.log", retention=5)

        assert sink._cfg.max_files == 5

    def test_rotating_file_with_compression(self) -> None:
        sink = rotating_file("logs/app.log", compression=True)

        assert sink._cfg.compress_rotated is True

    def test_rotating_file_mode_text(self) -> None:
        sink = rotating_file("logs/app.log", mode="text")

        assert sink._cfg.mode == "text"

    def test_rotating_file_nested_path(self) -> None:
        sink = rotating_file("logs/api/requests.log")

        assert sink._cfg.directory == Path("logs/api")
        assert sink._cfg.filename_prefix == "requests"

    def test_rotating_file_path_object(self) -> None:
        sink = rotating_file(Path("logs/app.log"))

        assert sink._cfg.directory == Path("logs")
        assert sink._cfg.filename_prefix == "app"

    def test_rotating_file_full_config(self) -> None:
        sink = rotating_file(
            "logs/app.log",
            rotation="100 MB",
            retention=10,
            compression=True,
            mode="text",
        )

        assert sink._cfg.directory == Path("logs")
        assert sink._cfg.filename_prefix == "app"
        assert sink._cfg.max_bytes == 100 * 1024 * 1024
        assert sink._cfg.max_files == 10
        assert sink._cfg.compress_rotated is True
        assert sink._cfg.mode == "text"
