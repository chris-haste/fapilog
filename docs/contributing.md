# Contributing

Guidelines for contributing to Fapilog, including development setup, code style, testing, and documentation standards.

Thank you for your interest in contributing to Fapilog! This guide will help you get started with development, understand our processes, and make your contributions as effective as possible.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style & Standards](#code-style--standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Standards](#documentation-standards)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)
- [Community Guidelines](#community-guidelines)

---

## Getting Started

### **Before You Begin**

- **Check existing issues** - Your idea might already be discussed
- **Read the documentation** - Understand the project's goals and architecture
- **Join discussions** - Use GitHub Discussions for questions and ideas
- **Start small** - Begin with documentation or small bug fixes

### **Types of Contributions**

We welcome all types of contributions:

- 🐛 **Bug fixes** - Help improve reliability
- ✨ **New features** - Add functionality users need
- 📚 **Documentation** - Improve clarity and completeness
- 🧪 **Tests** - Increase coverage and reliability
- 🔧 **Tooling** - Improve development experience
- 💡 **Ideas** - Suggest improvements and new features

---

## Development Setup

### **Prerequisites**

- **Python 3.8+** (project supports 3.8, 3.9, 3.10, 3.11, 3.12)
- **Git** - Version control
- **pip** - Package management
- **hatch** - Project management (installed automatically)

### **Local Development Setup**

**1. Clone the repository:**

```bash
git clone https://github.com/chris-haste/fastapi-logger.git
cd fastapi-logger
```

**2. Create and activate a virtual environment:**

```bash
# Create virtual environment
python -m venv .venv

# Activate (Unix/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

**3. Install development dependencies:**

```bash
# Install in editable mode with all dev dependencies
pip install -e ".[dev]"

# Or using hatch
hatch env create
hatch shell
```

**4. Verify the setup:**

```bash
# Run tests to ensure everything works
hatch run test

# Run linting
hatch run lint

# Run type checking
hatch run typecheck
```

### **Development Dependencies**

The project uses these development tools:

| Tool           | Purpose                | Command               |
| -------------- | ---------------------- | --------------------- |
| **pytest**     | Testing framework      | `hatch run test`      |
| **ruff**       | Linting and formatting | `hatch run lint`      |
| **mypy**       | Type checking          | `hatch run typecheck` |
| **pytest-cov** | Coverage reporting     | `hatch run test-cov`  |
| **pre-commit** | Git hooks              | `pre-commit install`  |
| **vulture**    | Dead code detection    | `vulture src/ tests/` |
| **hatch**      | Project management     | `hatch --help`        |

### **IDE Setup**

**VS Code (Recommended):**

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

**PyCharm:**

- Set project interpreter to `.venv/bin/python`
- Enable type checking
- Configure pytest as test runner

---

## Code Style & Standards

### **Python Code Style**

We follow **PEP 8** with project-specific configurations:

**Line Length:** 88 characters (Black/Ruff default)
**Import Order:** Standard library → Third-party → Local
**Type Hints:** Required for all public functions
**Docstrings:** Google style for all public APIs

### **Code Formatting**

**Automatic formatting with Ruff:**

```bash
# Format code
hatch run lint:format

# Check formatting
hatch run lint:lint
```

**Import organization:**

```python
# Standard library imports
import os
import sys
from typing import Any, Dict, Optional

# Third-party imports
import structlog
import pydantic
from fastapi import FastAPI

# Local imports
from fapilog import configure_logging
from fapilog.settings import LoggingSettings
```

### **Type Hints**

**Required for all public functions:**

```python
from typing import Any, Dict, Optional

def configure_logging(
    settings: Optional[LoggingSettings] = None,
    app: Optional[Any] = None
) -> None:
    """Configure logging with the given settings."""
    pass

async def write_log(
    event_dict: Dict[str, Any]
) -> None:
    """Write log event to all configured sinks."""
    pass
```

### **Docstrings**

**Google style for all public APIs:**

```python
def configure_logging(
    settings: Optional[LoggingSettings] = None,
    app: Optional[Any] = None
) -> None:
    """Configure Fapilog with the given settings.

    Args:
        settings: Logging configuration. If None, created from environment.
        app: FastAPI app instance. If provided, middleware is registered.

    Raises:
        ConfigurationError: If settings are invalid.

    Example:
        >>> configure_logging()
        >>> configure_logging(settings=LoggingSettings(level="DEBUG"))
    """
    pass
```

### **Naming Conventions**

- **Functions/Methods:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private functions:** `_leading_underscore`
- **Protected functions:** `_leading_underscore`

---

## Testing Guidelines

### **Test Structure**

**File naming:** `test_*.py` or `*_test.py`
**Class naming:** `Test*`
**Function naming:** `test_*`

```python
# tests/test_bootstrap.py
import pytest
from fapilog import configure_logging, log

class TestBootstrap:
    """Test bootstrap functionality."""

    def test_configure_logging_defaults(self):
        """Test configure_logging with default settings."""
        # Arrange
        # Act
        configure_logging()
        # Assert
        assert log is not None

    @pytest.mark.asyncio
    async def test_async_logging(self):
        """Test async logging functionality."""
        # Arrange
        configure_logging()
        # Act
        log.info("Test message")
        # Assert
        # Verify log was written
```

### **Test Categories**

**Unit Tests:**

- Test individual functions and classes
- Mock external dependencies
- Fast execution

**Integration Tests:**

- Test component interactions
- Use real dependencies when possible
- Mark with `@pytest.mark.integration`

**Performance Tests:**

- Test performance characteristics
- Mark with `@pytest.mark.slow`
- Use realistic data volumes

### **Running Tests**

```bash
# Run all tests
hatch run test

# Run with coverage
hatch run test-cov

# Run specific test file
pytest tests/test_bootstrap.py

# Run tests matching pattern
pytest -k "test_configure"

# Run integration tests only
pytest -m integration

# Run slow tests only
pytest -m slow

# Run queue load testing
hatch run test-queue-load
```

### **Coverage Requirements**

- **Minimum coverage:** 90%
- **New code:** 100% coverage required
- **Critical paths:** 100% coverage required

**Coverage report:**

```bash
hatch run test-cov
# Generates HTML report in htmlcov/
```

### **Test Best Practices**

1. **Arrange-Act-Assert** pattern
2. **Descriptive test names** that explain what's tested
3. **One assertion per test** when possible
4. **Use fixtures** for common setup
5. **Mock external dependencies**
6. **Test edge cases and error conditions**

---

## Documentation Standards

### **Code Documentation**

**All public APIs must have docstrings:**

```python
def configure_logging(
    settings: Optional[LoggingSettings] = None,
    app: Optional[Any] = None
) -> None:
    """Configure Fapilog logging system.

    This function initializes the logging system with the provided settings
    or environment variables. It sets up sinks, enrichers, and middleware
    as configured.

    Args:
        settings: Complete logging configuration. If None, created from
            environment variables using LoggingSettings.from_env().
        app: FastAPI application instance. If provided, TraceIDMiddleware
            is automatically registered and exception handlers are added.

    Raises:
        ConfigurationError: If settings are invalid or required dependencies
            are missing (e.g., httpx for Loki sink).

    Example:
        Basic configuration with defaults:
        >>> configure_logging()

        Custom configuration:
        >>> settings = LoggingSettings(level="DEBUG", sinks=["stdout"])
        >>> configure_logging(settings=settings)

        FastAPI integration:
        >>> app = FastAPI()
        >>> configure_logging(app=app)
    """
```

### **Documentation Structure**

**API Reference (`docs/api-reference.md`):**

- Complete function signatures
- Parameter descriptions with types
- Return value descriptions
- Usage examples
- Error handling information

**User Guide (`docs/user-guide.md`):**

- Step-by-step tutorials
- Real-world examples
- Best practices
- Troubleshooting guides

**Examples (`docs/examples/`):**

- Copy-paste ready code
- Complete working examples
- Different use cases and scenarios

### **Documentation Guidelines**

1. **Write for developers** - Assume technical knowledge
2. **Include examples** - Every feature should have examples
3. **Keep it current** - Update docs with code changes
4. **Cross-reference** - Link between related topics
5. **Test examples** - All code examples should work

---

## Pull Request Process

### **Before Submitting**

1. **Ensure tests pass:**

   ```bash
   hatch run test
   hatch run lint
   hatch run typecheck
   ```

2. **Update documentation:**

   - Add docstrings for new functions
   - Update API reference if needed
   - Add examples for new features

3. **Update CHANGELOG.md:**

   ```markdown
   ## [Unreleased]

   ### Added

   - New feature description

   ### Changed

   - Changed behavior description

   ### Fixed

   - Bug fix description
   ```

### **Creating a Pull Request**

1. **Fork the repository**
2. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make your changes** following the style guidelines

4. **Commit with conventional commits:**

   ```bash
   git commit -m "feat: add new Loki sink configuration"
   git commit -m "fix: handle invalid log levels gracefully"
   git commit -m "docs: update API reference with examples"
   ```

5. **Push and create PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

### **Pull Request Guidelines**

**Title format:**

```
<type>(<scope>): <description>
```

**Examples:**

- `feat(sinks): add file rotation support`
- `fix(middleware): handle missing trace headers`
- `docs(api): add comprehensive examples`
- `test(queue): add performance benchmarks`

**Description template:**

```markdown
## Description

Brief description of what this PR does.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Test addition
- [ ] Refactoring

## Testing

- [ ] Tests pass locally
- [ ] Coverage maintained/improved
- [ ] New tests added for new functionality

## Documentation

- [ ] Docstrings updated
- [ ] API reference updated
- [ ] Examples added/updated

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### **Code Review Process**

1. **Automated checks must pass:**

   - Linting (Ruff)
   - Type checking (MyPy)
   - Tests (pytest)
   - Coverage (90% minimum)

2. **Review criteria:**

   - Code quality and style
   - Test coverage and quality
   - Documentation completeness
   - Performance impact
   - Backward compatibility

3. **Review feedback:**
   - Be constructive and respectful
   - Focus on the code, not the person
   - Suggest improvements
   - Explain reasoning

---

## Release Process

### **Versioning**

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** - Incompatible API changes
- **MINOR** - Backward-compatible new functionality
- **PATCH** - Backward-compatible bug fixes

### **Pre-release Checklist**

- [ ] All tests pass (`hatch run test`)
- [ ] Linting passes (`hatch run lint`)
- [ ] Type checking passes (`hatch run typecheck`)
- [ ] Coverage threshold met (90% minimum)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`

### **Release Steps**

1. **Update version in `pyproject.toml`:**

   ```toml
   version = "0.1.3"
   ```

2. **Update CHANGELOG.md:**

   ```markdown
   ## [0.1.3] - 2024-01-15

   ### Added

   - New feature description

   ### Changed

   - Changed behavior description

   ### Fixed

   - Bug fix description
   ```

3. **Commit and tag:**

   ```bash
   git commit -m "chore(release): v0.1.3"
   git tag -a v0.1.3 -m "Release v0.1.3"
   git push origin main --tags
   ```

4. **GitHub Actions will automatically:**
   - Run all tests
   - Build distribution packages
   - Publish to PyPI (if on main branch)

### **Post-release**

- [ ] Verify PyPI package is correct
- [ ] Update documentation if needed
- [ ] Announce on GitHub Discussions
- [ ] Monitor for any issues

---

## Community Guidelines

### **Code of Conduct**

We are committed to providing a welcoming and inspiring community for all. Please:

- **Be respectful** - Treat everyone with respect
- **Be constructive** - Provide helpful, constructive feedback
- **Be collaborative** - Work together to improve the project
- **Be inclusive** - Welcome contributions from all backgrounds

### **Getting Help**

**Before asking for help:**

1. **Check the documentation** - [User Guide](user-guide.md), [API Reference](api-reference.md)
2. **Search existing issues** - Your question might already be answered
3. **Try the examples** - [Examples & Recipes](examples/index.md)

**When asking for help:**

- **Be specific** - Describe your exact problem
- **Provide context** - Include environment details, code examples
- **Show effort** - Demonstrate what you've already tried
- **Be patient** - Maintainers are volunteers

### **Reporting Issues**

**Bug reports should include:**

1. **Environment details:**

   - Python version
   - Operating system
   - Fapilog version
   - Dependencies versions

2. **Reproduction steps:**

   - Clear, step-by-step instructions
   - Minimal code example
   - Expected vs actual behavior

3. **Additional context:**
   - Error messages and tracebacks
   - Logs (if applicable)
   - Screenshots (if relevant)

**Example bug report:**

````markdown
## Bug Description

Brief description of the issue.

## Environment

- Python: 3.11.0
- OS: Ubuntu 22.04
- Fapilog: 0.1.2
- FastAPI: 0.104.1

## Steps to Reproduce

1. Install fapilog: `pip install fapilog`
2. Run this code:
   ```python
   from fapilog import configure_logging
   configure_logging()
   ```
````

3. Observe error: `ConfigurationError: Invalid setting`

## Expected Behavior

Configuration should work with defaults.

## Actual Behavior

Configuration fails with error.

## Additional Context

Error occurs only in Docker containers.

````

### **Feature Requests**

**When suggesting features:**

1. **Describe the use case** - Why is this feature needed?
2. **Provide examples** - How would it be used?
3. **Consider implementation** - Is it feasible?
4. **Check existing issues** - Is it already planned?

**Example feature request:**
```markdown
## Feature Description
Add support for custom log formats.

## Use Case
Users need to output logs in specific formats for legacy systems.

## Proposed API
```python
settings = LoggingSettings(
    format="custom",
    custom_format="{timestamp} [{level}] {message}"
)
````

## Implementation Notes

Would require extending the formatter system.

````

---

## Development Commands Reference

### **Testing Commands**

```bash
# Run all tests
hatch run test

# Run tests with coverage
hatch run test-cov

# Run specific test file
pytest tests/test_bootstrap.py

# Run tests matching pattern
pytest -k "test_configure"

# Run integration tests
pytest -m integration

# Run slow tests
pytest -m slow

# Run queue load testing
hatch run test-queue-load
````

### **Code Quality Commands**

```bash
# Run linting
hatch run lint:lint

# Format code
hatch run lint:format

# Run type checking
hatch run typecheck

# Run all quality checks
hatch run lint && hatch run typecheck && hatch run test
```

### **Build Commands**

```bash
# Build distribution packages
python -m build

# Or using hatch
hatch build

# Clean build artifacts
rm -rf dist/ build/ *.egg-info/
```

### **Pre-commit Hooks**

```bash
# Install pre-commit hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
```

### **Documentation Commands**

```bash
# Build documentation
cd docs
sphinx-build -b html . _build/html

# Serve documentation locally
python -m http.server -d _build/html 8000
```

---

## Project Structure

```
fastapi-logger/
├── src/fapilog/           # Main package
│   ├── __init__.py
│   ├── bootstrap.py       # Configuration
│   ├── middleware.py      # FastAPI middleware
│   ├── settings.py        # Settings model
│   ├── sinks/            # Output sinks
│   ├── _internal/        # Internal utilities
│   └── exceptions.py     # Custom exceptions
├── tests/                # Test suite
│   ├── test_bootstrap.py
│   ├── test_middleware.py
│   └── ...
├── docs/                 # Documentation
│   ├── api-reference.md
│   ├── user-guide.md
│   └── ...
├── examples/             # Code examples
│   ├── 01_basic_setup.py
│   ├── 05_fastapi_basic.py
│   └── ...
├── scripts/              # Development scripts
├── .github/              # GitHub workflows
├── pyproject.toml        # Project configuration
├── tox.ini              # Tox configuration
└── README.md            # Project overview
```

---

## Thank You!

Thank you for contributing to Fapilog! Your contributions help make this project better for everyone in the FastAPI ecosystem.

**Questions or need help?**

- 📚 **Documentation**: [User Guide](user-guide.md), [API Reference](api-reference.md)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/chris-haste/fastapi-logger/discussions)
- 🐛 **Issues**: [GitHub Issues](https://github.com/chris-haste/fastapi-logger/issues)
- 📖 **Examples**: [Examples & Recipes](examples/index.md)

**Happy coding! 🚀**
