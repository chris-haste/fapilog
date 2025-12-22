# Serialization Errors

## Symptoms
- JSON encoding errors
- Stack traces mentioning non-serializable objects
- Malformed log output

## Causes
- Passing complex objects in log kwargs
- Circular references
- Non-JSON types (datetime, Decimal) without conversion

## Fixes
```python
from fapilog import get_async_logger

logger = await get_async_logger()

payload = {
    "user_id": user.id,
    "created_at": user.created_at.isoformat(),  # convert datetime
    "preferences": dict(user.preferences),       # convert custom objects
}

await logger.info("User data", **payload)
```

Tips:
- Convert datetimes to ISO strings, enums to strings, complex objects to dicts.
- Keep kwargs shallow; avoid deeply nested custom classes.
