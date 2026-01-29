"""Unit tests for size and duration parsers."""

import pytest

from fapilog.core.types import _parse_duration, _parse_rotation_duration, _parse_size


class TestParseSize:
    """Test _parse_size parser function."""

    def test_parse_size_kilobytes(self) -> None:
        """Parse kilobytes to bytes."""
        assert _parse_size("10 KB") == 10 * 1024
        assert _parse_size("1KB") == 1024
        assert _parse_size("5 kb") == 5 * 1024

    def test_parse_size_megabytes(self) -> None:
        """Parse megabytes to bytes."""
        assert _parse_size("10 MB") == 10 * 1024 * 1024
        assert _parse_size("1MB") == 1024 * 1024
        assert _parse_size("50 mb") == 50 * 1024 * 1024

    def test_parse_size_gigabytes(self) -> None:
        """Parse gigabytes to bytes."""
        assert _parse_size("1 GB") == 1024**3
        assert _parse_size("2GB") == 2 * 1024**3

    def test_parse_size_terabytes(self) -> None:
        """Parse terabytes to bytes."""
        assert _parse_size("1 TB") == 1024**4
        assert _parse_size("2TB") == 2 * 1024**4

    def test_parse_size_bytes(self) -> None:
        """Parse bytes unit."""
        assert _parse_size("100 B") == 100
        assert _parse_size("1024B") == 1024
        assert _parse_size("1024 b") == 1024
        assert _parse_size("1024B") == _parse_size("1024 B")

    def test_parse_size_decimal_numbers(self) -> None:
        """Parse decimal numbers."""
        assert _parse_size("10.5 MB") == int(10.5 * 1024 * 1024)
        assert _parse_size("0.5 GB") == int(0.5 * 1024**3)
        assert _parse_size("1.25 KB") == int(1.25 * 1024)

    def test_parse_size_case_insensitive(self) -> None:
        """All case variations work."""
        assert _parse_size("10 MB") == _parse_size("10 mb")
        assert _parse_size("10 MB") == _parse_size("10 Mb")
        assert _parse_size("10 MB") == _parse_size("10 mB")

    def test_parse_size_whitespace_flexible(self) -> None:
        """Whitespace variations work."""
        assert _parse_size("10 MB") == _parse_size("10MB")
        assert _parse_size("10 MB") == _parse_size("10  MB")
        assert _parse_size("10 MB") == _parse_size(" 10 MB ")

    def test_parse_size_integer_passthrough(self) -> None:
        """Integers pass through unchanged."""
        assert _parse_size(10485760) == 10485760
        assert _parse_size(1024) == 1024
        assert _parse_size(0) == 0

    def test_parse_size_numeric_string(self) -> None:
        """Numeric strings are treated as raw bytes."""
        assert _parse_size("10485760") == 10485760
        assert _parse_size("0") == 0

    def test_parse_size_none_passthrough(self) -> None:
        """None passes through unchanged."""
        assert _parse_size(None) is None

    def test_parse_size_invalid_unit(self) -> None:
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("10 XB")

        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("10 PB")

    def test_parse_size_invalid_number(self) -> None:
        """Invalid number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("ten MB")

        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("MB 10")

    def test_parse_size_negative_number(self) -> None:
        """Negative size raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _parse_size(-1024)

        with pytest.raises(ValueError, match="non-negative"):
            _parse_size("-10 MB")

    def test_parse_size_empty_string(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("")

    def test_parse_size_error_message_includes_input(self) -> None:
        """Error message shows original input."""
        with pytest.raises(ValueError, match="'10 XB'"):
            _parse_size("10 XB")


class TestParseDuration:
    """Test _parse_duration parser function."""

    def test_parse_duration_seconds(self) -> None:
        """Parse seconds."""
        assert _parse_duration("5s") == 5.0
        assert _parse_duration("30s") == 30.0
        assert _parse_duration("1S") == 1.0

    def test_parse_duration_minutes(self) -> None:
        """Parse minutes to seconds."""
        assert _parse_duration("1m") == 60.0
        assert _parse_duration("10m") == 600.0
        assert _parse_duration("5M") == 300.0

    def test_parse_duration_hours(self) -> None:
        """Parse hours to seconds."""
        assert _parse_duration("1h") == 3600.0
        assert _parse_duration("2h") == 7200.0
        assert _parse_duration("24H") == 86400.0

    def test_parse_duration_days(self) -> None:
        """Parse days to seconds."""
        assert _parse_duration("1d") == 86400.0
        assert _parse_duration("7d") == 604800.0
        assert _parse_duration("30D") == 2592000.0

    def test_parse_duration_weeks(self) -> None:
        """Parse weeks to seconds."""
        assert _parse_duration("1w") == 604800.0
        assert _parse_duration("2w") == 1209600.0
        assert _parse_duration("4W") == 2419200.0

    def test_parse_duration_rejects_keywords(self) -> None:
        """Non-rotation durations reject keywords."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("hourly")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("daily")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("weekly")

    def test_parse_duration_integer_passthrough(self) -> None:
        """Integers pass through as floats."""
        assert _parse_duration(3600) == 3600.0
        assert _parse_duration(60) == 60.0
        assert _parse_duration(0) == 0.0

    def test_parse_duration_numeric_string(self) -> None:
        """Numeric strings are treated as raw seconds."""
        assert _parse_duration("3600") == 3600.0
        assert _parse_duration("0") == 0.0
        assert _parse_duration("0.25") == 0.25

    def test_parse_duration_float_passthrough(self) -> None:
        """Floats pass through unchanged."""
        assert _parse_duration(3600.5) == 3600.5
        assert _parse_duration(0.5) == 0.5

    def test_parse_duration_none_passthrough(self) -> None:
        """None passes through unchanged."""
        assert _parse_duration(None) is None

    def test_parse_duration_invalid_unit(self) -> None:
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("10x")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("10 min")

    def test_parse_duration_invalid_keyword(self) -> None:
        """Invalid keyword raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("monthly")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("yearly")

    def test_parse_duration_decimal_seconds(self) -> None:
        """Decimal seconds are accepted (AC2)."""
        assert _parse_duration("0.5s") == 0.5
        assert _parse_duration("1.5s") == 1.5
        assert _parse_duration("0.25s") == 0.25

    def test_parse_duration_decimal_minutes(self) -> None:
        """Decimal minutes are accepted (AC2)."""
        assert _parse_duration("0.25m") == 15.0  # 0.25 * 60
        assert _parse_duration("1.5m") == 90.0  # 1.5 * 60

    def test_parse_duration_decimal_hours(self) -> None:
        """Decimal hours are accepted (AC2)."""
        assert _parse_duration("1.5h") == 5400.0  # 1.5 * 3600
        assert _parse_duration("0.5h") == 1800.0  # 0.5 * 3600

    def test_parse_duration_decimal_days(self) -> None:
        """Decimal days are accepted (AC2)."""
        assert _parse_duration("2.5d") == 216000.0  # 2.5 * 86400

    def test_parse_duration_milliseconds(self) -> None:
        """Milliseconds are accepted (AC1)."""
        assert _parse_duration("100ms") == 0.1
        assert _parse_duration("1ms") == 0.001
        assert _parse_duration("1500ms") == 1.5
        assert _parse_duration("100 ms") == 0.1  # with space
        assert _parse_duration("1000MS") == 1.0  # case insensitive

    def test_parse_duration_decimal_milliseconds(self) -> None:
        """Decimal milliseconds are accepted."""
        assert _parse_duration("0.5ms") == 0.0005
        assert _parse_duration("1.5ms") == 0.0015

    def test_parse_duration_invalid_number(self) -> None:
        """Invalid number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("ten s")

    def test_parse_duration_negative_number(self) -> None:
        """Negative duration raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _parse_duration(-60)

        with pytest.raises(ValueError, match="non-negative"):
            _parse_duration("-5s")

    def test_parse_duration_error_message_shows_valid_formats(self) -> None:
        """Error message shows valid formats including ms and decimals (AC3)."""
        with pytest.raises(ValueError) as exc_info:
            _parse_duration("invalid")
        error_msg = str(exc_info.value)
        assert "ms" in error_msg  # mentions milliseconds
        assert (
            "0.5s" in error_msg or "decimal" in error_msg.lower()
        )  # mentions decimals


class TestParseRotationDuration:
    """Test rotation duration keyword support."""

    def test_rotation_duration_accepts_keywords(self) -> None:
        """Rotation keywords are supported."""
        assert _parse_rotation_duration("hourly") == 3600.0
        assert _parse_rotation_duration("daily") == 86400.0
        assert _parse_rotation_duration("weekly") == 604800.0

    def test_rotation_duration_keywords_case_insensitive(self) -> None:
        """Rotation keywords are case insensitive."""
        assert _parse_rotation_duration("HOURLY") == 3600.0
        assert _parse_rotation_duration("Daily") == 86400.0
        assert _parse_rotation_duration("Weekly") == 604800.0

    def test_rotation_duration_accepts_units(self) -> None:
        """Unit durations are still accepted."""
        assert _parse_rotation_duration("5s") == 5.0

    def test_rotation_duration_accepts_milliseconds(self) -> None:
        """Milliseconds are accepted in rotation duration."""
        assert _parse_rotation_duration("500ms") == 0.5

    def test_rotation_duration_accepts_decimals(self) -> None:
        """Decimal durations are accepted in rotation duration."""
        assert _parse_rotation_duration("1.5h") == 5400.0

    def test_rotation_duration_error_message_mentions_keywords(self) -> None:
        """Error message includes keyword hint."""
        with pytest.raises(ValueError, match="hourly"):
            _parse_rotation_duration("invalid")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_size_max_value(self) -> None:
        """Very large sizes work."""
        result = _parse_size("9999 TB")
        assert result > 0

    def test_parse_size_min_value(self) -> None:
        """Zero size works."""
        assert _parse_size("0 MB") == 0
        assert _parse_size(0) == 0

    def test_parse_duration_max_value(self) -> None:
        """Very large durations work."""
        result = _parse_duration("9999w")
        assert result > 0

    def test_parse_duration_min_value(self) -> None:
        """Zero duration works."""
        assert _parse_duration("0s") == 0.0
        assert _parse_duration(0) == 0.0

    def test_parse_duration_backward_compatibility(self) -> None:
        """All existing valid formats continue to work (AC4)."""
        # Integer units (existing)
        assert _parse_duration("30s") == 30.0
        assert _parse_duration("5m") == 300.0
        assert _parse_duration("1h") == 3600.0
        assert _parse_duration("7d") == 604800.0
        assert _parse_duration("2w") == 1209600.0
        # Numeric passthrough (existing)
        assert _parse_duration(0.1) == 0.1
        assert _parse_duration("0.1") == 0.1
        assert _parse_duration(30) == 30.0
