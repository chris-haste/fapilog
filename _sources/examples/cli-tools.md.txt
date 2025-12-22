# Logging in Scripts/CLIs

This is about using fapilog inside your own command-line scripts; there is no built-in `fapilog` CLI yet.

Use the sync logger with `runtime()` in command-line scripts.

```python
from fapilog import runtime

def main():
    with runtime() as logger:
        logger.info("CLI started")
        # do work
        logger.info("CLI finished", status="ok")

if __name__ == "__main__":
    main()
```

Notes:
- `runtime()` drains automatically on exit.
- Keep logging lightweight; stdout sink is default.
