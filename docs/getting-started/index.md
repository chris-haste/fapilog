# Getting Started

Get up and running with fapilog in minutes.

```{toctree}
:maxdepth: 2
:caption: Getting Started

installation
quickstart
hello-world
```

## Quick Start

Want to start logging immediately? Here's the fastest path:

```python
from fapilog import get_logger

# Zero-config logging - works out of the box
logger = get_logger()
logger.info("Hello, fapilog!")
```

**That's it!** fapilog automatically:

- Chooses the best output format for your environment
- Sets up async processing
- Handles context binding
- Manages resources

## What You'll Learn

1. **[Installation](installation.md)** - Get fapilog running in your project
2. **[Quickstart](quickstart.md)** - Zero-config logging in 2 minutes
3. **[Hello World](hello-world.md)** - Complete walkthrough with examples

## Next Steps

After getting started, dive into:

- **[Core Concepts](../core-concepts/index.md)** - Understand how fapilog works
- **[User Guide](../user-guide/index.md)** - Learn practical usage patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation

---

_Get logging in minutes, not hours._
