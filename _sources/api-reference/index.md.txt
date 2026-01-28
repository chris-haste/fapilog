# API Reference

Complete API reference for fapilog, organized by functionality.

```{toctree}
:maxdepth: 2
:titlesonly:
:caption: API Reference

top-level-functions
builder
logger-methods
context-binding
audit-trail
configuration
configuration-map
types
plugins/index
lifecycle-results
modules
```

## Overview

The API Reference is organized by functionality to help you quickly find what you need:

- **Top-Level Functions** (`top-level-functions`) - Main entry points and utilities
- **Builder API** (`builder`) - Fluent configuration with `LoggerBuilder`
- **Logger Methods** (`logger-methods`) - All available logging methods
- **Context Binding** (`context-binding`) - Request context and correlation
- **Configuration** (`configuration`) - Settings and environment configuration
- **Configuration Map** (`configuration-map`) - Complete reference: setting → env var → builder method
- **Types** (`types`) - Reusable size/duration types
- **Plugins** (`plugins/index`) - Extensible sinks, enrichers, redactors, and processors
- **Lifecycle & Results** (`lifecycle-results`) - Runtime management and results
- **API Modules** (`modules`) - Complete auto-generated documentation

## Quick Reference

### Top-Level Functions

- **get_logger** - Ready-to-use logger instance (cached by name)
- **get_async_logger** - Async logger factory (cached by name)
- **runtime** - Context manager for logger lifecycle
- **runtime_async** - Async context manager for lifecycle
- **get_cached_loggers** - Inspect cached logger names
- **clear_logger_cache** - Drain and clear all cached loggers

### Builder API

- **LoggerBuilder** - Fluent builder for sync loggers
- **AsyncLoggerBuilder** - Fluent builder for async loggers

### Logger Methods

- **debug/info/warning/error/exception** - Log events with structured payloads
- **context helpers** - `bind`, `unbind`, `clear_context`

### Plugins

- **Sinks / Enrichers / Redactors / Processors** - Extensible plugin contracts and built-ins

### Lifecycle & Results

- **DrainResult** - Result of stopping and draining logs

---

_This reference provides both organized overviews and complete auto-generated documentation._
