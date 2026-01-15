# Common Testing Patterns (ref: implement)

## Parametrized Tests

Test multiple scenarios without duplication:

```python
@pytest.mark.parametrize("input_value,expected", [
    (0, 0),
    (1, 1),
    (-1, 1),
    (100, 100),
    (-100, 100),
])
def test_absolute_value(input_value, expected):
    assert absolute(input_value) == expected
```

## Testing Exceptions

```python
# Test that specific exception is raised
def test_invalid_email_raises_validation_error():
    with pytest.raises(ValidationError, match="Invalid email"):
        validate_email("not-an-email")

# Test exception message contains specific text
def test_negative_age_error_message():
    with pytest.raises(ValueError) as exc_info:
        create_user(age=-5)
    assert "age must be positive" in str(exc_info.value)
```

## Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_fetch_data():
    result = await fetch_data_async("user_123")
    assert result["status"] == "success"
```

## Testing with Temporary Files

```python
def test_save_config(tmp_path):
    # pytest provides tmp_path fixture
    config_file = tmp_path / "config.json"

    save_config({"key": "value"}, config_file)

    assert config_file.exists()
    assert config_file.read_text() == '{"key": "value"}'
```

## Testing Time-Dependent Code

```python
from freezegun import freeze_time
from datetime import datetime

@freeze_time("2024-01-15 10:00:00")
def test_timestamp_generation():
    result = create_timestamp()
    assert result == datetime(2024, 1, 15, 10, 0, 0)
```

## Testing with Databases

```python
@pytest.fixture(scope="function")
def db_session():
    """Create isolated database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()

def test_create_user(db_session):
    user = User(name="Alice")
    db_session.add(user)
    db_session.commit()

    found = db_session.query(User).filter_by(name="Alice").first()
    assert found is not None
    assert found.name == "Alice"
```

## Testing API Calls

```python
def test_api_success(mocker):
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"data": "value"}

    result = fetch_from_api("https://api.example.com")

    assert result == {"data": "value"}
    mock_get.assert_called_once_with("https://api.example.com")

def test_api_retry_on_failure(mocker):
    mock_get = mocker.patch('requests.get')
    # First two calls fail, third succeeds
    mock_get.side_effect = [
        requests.exceptions.ConnectionError(),
        requests.exceptions.ConnectionError(),
        mocker.Mock(status_code=200, json=lambda: {"data": "value"})
    ]

    result = fetch_with_retry("https://api.example.com")

    assert result == {"data": "value"}
    assert mock_get.call_count == 3
```

## Testing Logging

```python
def test_error_logged(caplog):
    with caplog.at_level(logging.ERROR):
        process_with_error()

    assert "Error occurred" in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)
```

## Testing Context Managers

```python
def test_context_manager_cleanup():
    mock_resource = Mock()

    with ResourceManager(mock_resource) as manager:
        manager.do_work()

    mock_resource.cleanup.assert_called_once()
```

## Monkeypatching Environment

```python
def test_uses_production_url(monkeypatch):
    monkeypatch.setenv("API_URL", "https://prod.api.com")

    config = load_config()

    assert config.api_url == "https://prod.api.com"
```

## Testing Randomness

```python
def test_random_selection_uses_seed():
    random.seed(42)
    result1 = select_random_item([1, 2, 3, 4, 5])

    random.seed(42)
    result2 = select_random_item([1, 2, 3, 4, 5])

    assert result1 == result2
```

## Property-Based Testing with Hypothesis

```python
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_addition_commutative(a, b):
    assert add(a, b) == add(b, a)

@given(st.lists(st.integers()))
def test_sort_idempotent(lst):
    sorted_once = sorted(lst)
    sorted_twice = sorted(sorted_once)
    assert sorted_once == sorted_twice
```
