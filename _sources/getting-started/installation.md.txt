# Installation

Get fapilog running in your Python project.

## Quick Install

```bash
pip install fapilog
```

## Installation Options

### Basic Installation

```bash
# Core functionality only
pip install fapilog
```

### With Extras

```bash
# FastAPI integration
pip install fapilog[fastapi]

# Development tools
pip install fapilog[dev]

# All extras
pip install fapilog[all]
```

### From Source

```bash
git clone https://github.com/your-username/fapilog.git
cd fapilog
pip install -e .
```

## Python Version Support

| Python Version | Status             | Notes                      |
| -------------- | ------------------ | -------------------------- |
| 3.9+           | ✅ Full Support    | Recommended minimum        |
| 3.8            | ⚠️ Limited Support | Some features may not work |
| 3.7            | ❌ Not Supported   | End of life                |

## Dependencies

### Required Dependencies

fapilog automatically installs these core dependencies:

- `structlog` - Structured logging foundation
- `pydantic` - Settings and validation
- `anyio` - Async I/O utilities

### Optional Dependencies

Install these based on your needs:

```bash
# FastAPI integration
pip install fastapi

# HTTP sinks
pip install httpx

# File rotation
pip install aiofiles

# Metrics
pip install prometheus-client
```

## Environment Setup

### Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate (Unix/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install fapilog
pip install fapilog
```

### Conda Environment

```bash
# Create conda environment
conda create -n fapilog python=3.11

# Activate
conda activate fapilog

# Install
pip install fapilog
```

## Verification

Test your installation:

```python
from fapilog import get_logger

# Should work without errors
logger = get_logger()
print("✅ fapilog installed successfully!")
```

## Troubleshooting

### Common Issues

**Import Error: No module named 'fapilog'**

```bash
# Check if installed
pip list | grep fapilog

# Reinstall if needed
pip install --force-reinstall fapilog
```

**Version Conflicts**

```bash
# Check for conflicts
pip check fapilog

# Install in clean environment
python -m venv fresh_env
source fresh_env/bin/activate
pip install fapilog
```

**Permission Errors**

```bash
# Use user installation
pip install --user fapilog

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install fapilog
```

## Next Steps

- **[Quickstart](quickstart.md)** - Start logging in 2 minutes
- **[Hello World](hello-world.md)** - Complete walkthrough
- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture

---

_Ready to start logging? Move on to the [Quickstart](quickstart.md)._
