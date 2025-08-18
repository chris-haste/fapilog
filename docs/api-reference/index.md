# API Reference

Complete API reference for fapilog, organized by functionality.

```{toctree}
:maxdepth: 3
:caption: API Reference

top-level-functions
logger-methods
context-binding
configuration
plugins/index
lifecycle-results
modules
```

## Overview

The API Reference is organized by functionality to help you quickly find what you need:

- **Top-Level Functions** - Main entry points and utilities
- **Logger Methods** - All available logging methods
- **Context Binding** - Request context and correlation
- **Configuration** - Settings and environment configuration
- **Plugins** - Extensible sinks, enrichers, redactors, and processors
- **Lifecycle & Results** - Runtime management and results
- **API Modules** - Complete auto-generated documentation

## Quick Reference

### Top-Level Functions

- **[get_logger](top-level-functions.md#get_logger)** - Get a ready-to-use logger instance
- **[runtime](top-level-functions.md#runtime)** - Context manager for logger lifecycle
- **[stop_and_drain](top-level-functions.md#stop_and_drain)** - Gracefully stop and flush logs

### Logger Methods

- **[debug](logger-methods.md#debug)** - Log debug messages
- **[info](logger-methods.md#info)** - Log informational messages
- **[warning](logger-methods.md#warning)** - Log warning messages
- **[error](logger-methods.md#error)** - Log error messages
- **[critical](logger-methods.md#critical)** - Log critical messages
- **[exception](logger-methods.md#exception)** - Log exceptions with traceback

### Context Binding

- **[bind](context-binding.md#bind)** - Bind context variables to current request
- **[unbind](context-binding.md#unbind)** - Remove specific context variables
- **[clear_context](context-binding.md#clear_context)** - Clear all context variables

### Configuration

- **[FapilogSettings](configuration.md#fapilogsettings)** - Main configuration class
- **Environment Variables** - All available configuration options
- **Settings Hierarchy** - How configuration is resolved

### Plugins

#### Sinks (Output Plugins)

- **[Stdout JSON Sink](plugins/sinks.md#stdout-json-sink)** - Console output
- **[Rotating File Sink](plugins/sinks.md#rotating-file-sink)** - File output with rotation

#### Enrichers (Input/Context Plugins)

- **[Runtime Info](plugins/enrichers.md#runtime-info-enricher)** - System information
- **[Context Vars](plugins/enrichers.md#context-vars-enricher)** - Request context

#### Redactors (Security Plugins)

- **[Field Mask](plugins/redactors.md#field-mask-redactor)** - Mask specific fields
- **[Regex Mask](plugins/redactors.md#regex-mask-redactor)** - Pattern-based masking
- **[URL Credential Scrubber](plugins/redactors.md#url-credentials-redactor)** - Remove credentials from URLs

#### Processors (Transform Plugins)

- **[Pass-through](plugins/processors.md#pass-through-processor)** - Default no-op processor

### Lifecycle & Results

- **[DrainResult](lifecycle-results.md#drainresult)** - Result of stopping and draining logs

---

_This reference provides both organized overviews and complete auto-generated documentation._
