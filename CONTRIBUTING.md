# Contributing to fapilog

Thank you for your interest in contributing to fapilog! This document provides guidelines and instructions for contributors to help ensure a smooth development process.

> **Project Naming**: This project is developed in the `fastapi-logger` repository but published to PyPI as `fapilog`. The repository name is descriptive of the project's purpose, while the package name is concise and memorable.

## Table of Contents

- [Project Setup](#project-setup)
- [Development Workflow](#development-workflow)
- [Commit & PR Guidelines](#commit--pr-guidelines)
- [Release Process](#release-process)
- [How to Get Help or Suggest Features](#how-to-get-help-or-suggest-features)

## Project Setup

### Prerequisites

- Python 3.8 or higher
- Git
- pip (Python package installer)

### Local Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/chris-haste/fastapi-logger.git
   cd fastapi-logger
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify the setup**
   ```bash
   hatch run test
   ```

### Development Dependencies

The project uses several development tools that are automatically installed with `pip install -e ".[dev]"`:

- **pytest** - Testing framework
- **ruff** - Linting and code formatting
- **mypy** - Type checking
- **pytest-cov** - Coverage reporting
- **pre-commit** - Git hooks for code quality
- **vulture** - Dead code detection
- **hatch** - Project management and build tool

## Development Workflow

### 1. Create a Feature Branch

Always work on feature branches, never directly on `main`:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

Follow these guidelines when writing code:

- **Follow PEP 8** - Use the project's Ruff configuration for consistent formatting
- **Add type hints** - All new functions should include type annotations
- **Write tests** - New features should include comprehensive tests
- **Update documentation** - Keep README.md and docstrings up to date

### 3. Run Quality Checks

Before committing, ensure your code passes all quality checks:

```bash
# Run linting
hatch run lint

# Run type checking
hatch run typecheck

# Run tests
hatch run test

# Run tests with coverage
hatch run test-cov
```

### 4. Pre-commit Hooks

The project uses pre-commit hooks to automatically check code quality:

```bash
# Install pre-commit hooks (first time only)
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

The hooks will run automatically on staged files when you commit. They include:

- **Ruff** - Linting and code formatting
- **MyPy** - Type checking
- **Vulture** - Dead code detection

### 5. Update CHANGELOG.md

For any user-facing changes, add an entry to `CHANGELOG.md` under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added

- New feature description

### Changed

- Changed behavior description

### Fixed

- Bug fix description
```

Follow the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## Commit & PR Guidelines

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

**Examples:**

```bash
git commit -m "feat: add new Loki sink for log shipping"
git commit -m "fix: handle invalid configuration gracefully"
git commit -m "docs: update README with new examples"
git commit -m "chore(release): v0.1.1"
```

### Pull Request Process

1. **Create a PR** from your feature branch to `main`
2. **Ensure CI passes** - All GitHub Actions checks must pass
3. **Add a description** explaining what the PR does and why
4. **Link related issues** using keywords like "Fixes #123" or "Closes #456"
5. **Request review** from maintainers

**PR Title Format:**

```
<type>(<scope>): <description>
```

**Examples:**

- `feat(sinks): add new file sink with rotation`
- `fix(middleware): handle missing trace headers`
- `docs(readme): add contributing guidelines`

### Code Review Guidelines

- **Be respectful** and constructive in feedback
- **Focus on the code** and its impact
- **Suggest improvements** rather than just pointing out issues
- **Test the changes** locally if possible

## Release Process

### Versioning

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

### Release Steps

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** - Move entries from `[Unreleased]` to new version section
3. **Commit changes** with message `chore(release): vX.Y.Z`
4. **Create and push tag** - `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
5. **Build artifacts** - `python -m build`
6. **Upload to PyPI** (if applicable)

For detailed release instructions, see [RELEASING.md](RELEASING.md).

### Pre-release Checklist

- [ ] All tests pass (`hatch run test`)
- [ ] Linting passes (`hatch run lint`)
- [ ] Type checking passes (`hatch run typecheck`)
- [ ] Coverage threshold met (90% minimum)
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`
- [ ] Documentation updated

## How to Get Help or Suggest Features

### Getting Help

- **GitHub Issues** - Search existing issues before creating new ones
- **GitHub Discussions** - Ask questions and share ideas
- **Documentation** - Check the [README.md](README.md) and [docs/](docs/) folder

### Reporting Bugs

When reporting bugs, please include:

1. **Environment details** - Python version, OS, fapilog version
2. **Reproduction steps** - Clear steps to reproduce the issue
3. **Expected vs actual behavior** - What you expected vs what happened
4. **Code example** - Minimal code that reproduces the issue
5. **Error messages** - Full error traceback if applicable

### Suggesting Features

When suggesting new features:

1. **Check existing issues** - The feature might already be planned
2. **Describe the use case** - Explain why this feature would be useful
3. **Provide examples** - Show how the feature would be used
4. **Consider implementation** - Think about how it might be implemented

### Contributing Guidelines

- **Be respectful** - Treat all contributors with respect
- **Follow the process** - Use the established workflow and tools
- **Test thoroughly** - Ensure your changes work correctly
- **Document changes** - Update documentation as needed
- **Keep it simple** - Prefer simple, readable solutions

## Development Commands Reference

```bash
# Testing
hatch run test              # Run all tests (including slow tests)
hatch run test:pytest -m "not slow"  # Run tests excluding slow tests (faster)
hatch run test-cov          # Run tests with coverage
hatch run test-queue-load   # Run queue load testing

# Code Quality
hatch run lint              # Run Ruff linter
hatch run typecheck         # Run MyPy type checker

# Building
python -m build             # Build distribution packages
hatch build                 # Alternative build command

# Pre-commit
pre-commit install          # Install git hooks
pre-commit run --all-files  # Run all hooks manually
```

## Testing Guidelines

### Writing Tests

- **Test new features** - Every new feature should have tests
- **Test edge cases** - Include tests for error conditions
- **Use descriptive names** - Test names should explain what they test
- **Keep tests simple** - Each test should test one thing
- **Use fixtures** - Reuse common test setup with pytest fixtures

### Test Structure

```python
def test_feature_name():
    """Test description of what this test verifies."""
    # Arrange
    # Act
    # Assert
```

### Running Tests

```bash
# Run all tests
hatch run test

# Run tests excluding slow tests (faster for development)
hatch run test:pytest -m "not slow"

# Run specific test file
pytest tests/test_specific.py

# Run tests with coverage
hatch run test-cov

# Run tests matching pattern
pytest -k "test_name_pattern"
```

**Note**: Some tests are marked as "slow" because they perform intensive performance testing (60+ second stress tests). For faster development cycles, use `hatch run test:pytest -m "not slow"` which excludes these tests and runs ~53% faster.

## Code Style Guidelines

### Python Code

- **Follow PEP 8** - Use the project's Ruff configuration
- **Use type hints** - All functions should have type annotations
- **Write docstrings** - Document public functions and classes
- **Keep functions small** - Aim for single responsibility
- **Use meaningful names** - Variables and functions should be descriptive

### Import Organization

```python
# Standard library imports
import os
import sys

# Third-party imports
import structlog
import pydantic

# Local imports
from fapilog import configure_logging
from fapilog.settings import LoggingSettings
```

## Thank You!

Thank you for contributing to fapilog! Your contributions help make this project better for everyone. If you have any questions about this guide or the contribution process, please don't hesitate to ask.
