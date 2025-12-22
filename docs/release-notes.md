# Release Notes

Changelog and upgrade guides for fapilog.

## Current Version

**fapilog 3.0.0-alpha.1** - _Released: January 2024_

### What's New in 3.0.0

- **Complete rewrite** - Built from the ground up for performance
- **Async-first design** - Non-blocking logging operations
- **Plugin architecture** - Extensible sinks, processors, and enrichers
- **Built-in redaction** - Automatic data masking and security
- **Metrics integration** - Prometheus and observability support
- **FastAPI integration** - Native web framework support

### Breaking Changes

- **API redesign** - New logging interface and methods
- **Configuration changes** - New environment variable structure
- **Plugin system** - Different plugin interface and lifecycle

### Migration Guide

See the v3 migration guide in the repository wiki for detailed upgrade instructions (to be published).

## Previous Versions

### fapilog 2.x Series

**fapilog 2.5.0** - _Released: December 2023_

- Bug fixes and performance improvements
- Enhanced error handling
- Better documentation

**fapilog 2.4.0** - _Released: November 2023_

- New sink implementations
- Improved configuration validation
- Better async support

**fapilog 2.3.0** - _Released: October 2023_

- Plugin system improvements
- Enhanced metrics collection
- Better error reporting

### fapilog 1.x Series

**fapilog 1.8.0** - _Released: September 2023_

- Stability improvements
- Bug fixes
- Performance optimizations

**fapilog 1.7.0** - _Released: August 2023_

- New features and improvements
- Better compatibility
- Enhanced documentation

## Upgrade Guides

### Upgrading to 3.0.0

The 3.0.0 release is a major rewrite with significant changes:

#### 1. Update Dependencies

```bash
# Remove old version
pip uninstall fapilog

# Install new version
pip install fapilog==3.0.0-alpha.1
```

#### 2. Update Import Statements

**Before (2.x):**

```python
from fapilog import Logger

logger = Logger()
logger.info("Message")
```

**After (3.0.0):**

```python
from fapilog import get_logger

logger = get_logger()
logger.info("Message")
```

#### 3. Update Configuration

**Before (2.x):**

```bash
export FAPILOG_LOG_LEVEL=INFO
export FAPILOG_OUTPUT_FORMAT=json
```

**After (3.0.0):**

```bash
export FAPILOG_CORE__LOG_LEVEL=INFO
export FAPILOG_OBSERVABILITY__LOGGING__FORMAT=json
```

#### 4. Update Plugin Code

**Before (2.x):**

```python
from fapilog.plugins import BaseSink

class CustomSink(BaseSink):
    def write(self, message):
        # Old interface
        pass
```

**After (3.0.0):**

```python
from fapilog.plugins.sinks import BaseSink

class CustomSink(BaseSink):
    async def write(self, entry: dict) -> None:
        # New async interface
        pass
```

### Upgrading from 1.x to 2.x

#### 1. Update Dependencies

```bash
pip install --upgrade fapilog>=2.0.0
```

#### 2. Check Breaking Changes

- Review configuration changes
- Update plugin implementations
- Test thoroughly in development

#### 3. Update Configuration

```bash
# New environment variables
export FAPILOG_LOG_LEVEL=INFO
export FAPILOG_OUTPUT_FORMAT=json
export FAPILOG_ENABLE_METRICS=true
```

## Compatibility

### Python Versions

| fapilog Version | Python 3.7 | Python 3.8 | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 |
| --------------- | ---------- | ---------- | ---------- | ----------- | ----------- | ----------- |
| 3.0.0+          | ❌         | ⚠️         | ✅         | ✅          | ✅          | ✅          |
| 2.x             | ✅         | ✅         | ✅         | ✅          | ✅          | ⚠️          |
| 1.x             | ✅         | ✅         | ✅         | ⚠️          | ❌          | ❌          |

### Framework Compatibility

| Framework | fapilog 3.0.0+ | fapilog 2.x | fapilog 1.x |
| --------- | -------------- | ----------- | ----------- |
| FastAPI   | ✅ Native      | ✅ Plugin   | ⚠️ Basic    |
| Django    | ✅ Plugin      | ✅ Plugin   | ✅ Plugin   |
| Flask     | ✅ Plugin      | ✅ Plugin   | ✅ Plugin   |
| Tornado   | ✅ Plugin      | ✅ Plugin   | ✅ Plugin   |

## Deprecation Policy

### Deprecation Timeline

- **Deprecation notice** - 6 months before removal
- **Deprecation warning** - 3 months before removal
- **Feature removal** - After deprecation period

### Currently Deprecated

- **fapilog 2.x** - Will be supported until December 2024
- **Python 3.7** - End of life, no longer supported
- **Old plugin interface** - Replaced with new system

## Roadmap

### Upcoming Releases

#### fapilog 3.0.0 (Q1 2024)

- **Stable release** - Production-ready 3.0.0
- **Performance optimizations** - Further speed improvements
- **Enhanced plugins** - More plugin types and capabilities

#### fapilog 3.1.0 (Q2 2024)

- **Advanced redaction** - Machine learning-based PII detection
- **Distributed tracing** - OpenTelemetry integration
- **Cloud integration** - AWS, GCP, Azure sinks

#### fapilog 3.2.0 (Q3 2024)

- **Real-time analytics** - Log analysis and insights
- **Advanced metrics** - Custom dashboards and alerting
- **Enterprise features** - Compliance and audit tools

### Long-term Vision

- **AI-powered logging** - Intelligent log analysis and insights
- **Universal compatibility** - Support for all major frameworks
- **Cloud-native** - Built for modern cloud environments
- **Enterprise ready** - Compliance, security, and scalability

## Support

### Version Support

- **Current version** - Full support and features
- **Previous version** - Bug fixes and security updates
- **Legacy versions** - Security updates only

### Getting Help

- **Documentation** - This site and guides
- **GitHub Issues** - Bug reports and feature requests
- **Discussions** - Community support and questions
- **Professional Support** - Enterprise users (contact sales)

---

_Stay up to date with the latest releases and features. Check the [changelog](https://github.com/your-username/fapilog/blob/main/CHANGELOG.md) for detailed information._
