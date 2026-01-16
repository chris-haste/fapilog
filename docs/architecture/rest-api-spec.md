# REST API Spec

## Core Library: No REST API

The core fapilog library is a **Python library only** - no web server, no REST API, no complexity.

## Plugin Discovery

Plugins are discovered via standard Python mechanisms:

- **PyPI**: Search for packages with `fapilog-*` naming convention
- **GitHub Topics**: Browse repositories with `fapilog-plugin` topic
- **Entry Points**: Automatic discovery via `fapilog.sinks`, `fapilog.processors`, etc.
