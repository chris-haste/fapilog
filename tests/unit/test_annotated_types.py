"""Test Pydantic Annotated types."""

import pytest
from pydantic import BaseModel, ValidationError

from fapilog.core.types import (
    DurationField,
    OptionalDurationField,
    OptionalRotationDurationField,
    OptionalSizeField,
    RotationDurationField,
    SizeField,
)


class TestSizeField:
    """Test SizeField Annotated type."""

    def test_size_field_accepts_string(self) -> None:
        """SizeField accepts string input."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size="10 MB")
        assert m.size == 10 * 1024 * 1024
        assert isinstance(m.size, int)

    def test_size_field_accepts_integer(self) -> None:
        """SizeField accepts integer input."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size=1048576)
        assert m.size == 1048576

    def test_size_field_validation_error(self) -> None:
        """SizeField raises ValidationError on invalid input."""

        class Model(BaseModel):
            size: SizeField

        with pytest.raises(ValidationError) as exc_info:
            Model(size="10 XB")

        error = exc_info.value.errors()[0]
        assert "Invalid size format" in str(error["ctx"]["error"])

    def test_size_field_type_annotation(self) -> None:
        """SizeField resolves to int for type checkers."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size="10 MB")
        assert isinstance(m.size, int)


class TestDurationField:
    """Test DurationField Annotated type."""

    def test_duration_field_accepts_string(self) -> None:
        """DurationField accepts string input."""

        class Model(BaseModel):
            duration: DurationField

        m = Model(duration="1h")
        assert m.duration == 3600.0
        assert isinstance(m.duration, float)

    def test_duration_field_accepts_number(self) -> None:
        """DurationField accepts numeric input."""

        class Model(BaseModel):
            duration: DurationField

        m = Model(duration=3600)
        assert m.duration == 3600.0

        m2 = Model(duration=3600.5)
        assert m2.duration == 3600.5

    def test_duration_field_rejects_keywords(self) -> None:
        """DurationField rejects rotation keywords."""

        class Model(BaseModel):
            duration: DurationField

        with pytest.raises(ValidationError) as exc_info:
            Model(duration="daily")

        error = exc_info.value.errors()[0]
        assert "Invalid duration format" in str(error["ctx"]["error"])

    def test_duration_field_validation_error(self) -> None:
        """DurationField raises ValidationError on invalid input."""

        class Model(BaseModel):
            duration: DurationField

        with pytest.raises(ValidationError) as exc_info:
            Model(duration="invalid")

        error = exc_info.value.errors()[0]
        assert "Invalid duration format" in str(error["ctx"]["error"])


class TestOptionalFields:
    """Test optional variants."""

    def test_optional_size_field_accepts_none(self) -> None:
        """OptionalSizeField accepts None."""

        class Model(BaseModel):
            size: OptionalSizeField

        m = Model(size=None)
        assert m.size is None

    def test_optional_size_field_accepts_value(self) -> None:
        """OptionalSizeField accepts values."""

        class Model(BaseModel):
            size: OptionalSizeField

        m = Model(size="10 MB")
        assert m.size == 10 * 1024 * 1024

    def test_optional_duration_field_accepts_none(self) -> None:
        """OptionalDurationField accepts None."""

        class Model(BaseModel):
            duration: OptionalDurationField

        m = Model(duration=None)
        assert m.duration is None

    def test_optional_duration_field_accepts_value(self) -> None:
        """OptionalDurationField accepts values."""

        class Model(BaseModel):
            duration: OptionalDurationField

        m = Model(duration="1h")
        assert m.duration == 3600.0


class TestRotationDurationField:
    """Test rotation duration fields."""

    def test_rotation_duration_field_accepts_keyword(self) -> None:
        """RotationDurationField accepts rotation keywords."""

        class Model(BaseModel):
            duration: RotationDurationField

        m = Model(duration="daily")
        assert m.duration == 86400.0

    def test_optional_rotation_duration_field_accepts_none(self) -> None:
        """OptionalRotationDurationField accepts None."""

        class Model(BaseModel):
            duration: OptionalRotationDurationField

        m = Model(duration=None)
        assert m.duration is None


class TestFieldDefaults:
    """Test fields with default values."""

    def test_size_field_with_default(self) -> None:
        """SizeField works with default values."""

        class Model(BaseModel):
            size: SizeField = 1024

        m1 = Model()
        assert m1.size == 1024

        m2 = Model(size="10 MB")
        assert m2.size == 10 * 1024 * 1024

    def test_optional_field_defaults_to_none(self) -> None:
        """Optional fields default to None."""

        class Model(BaseModel):
            size: OptionalSizeField = None
            duration: OptionalDurationField = None

        m = Model()
        assert m.size is None
        assert m.duration is None
