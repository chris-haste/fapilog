# Documentation Guide for AI Agents

## Purpose

This guide provides practical instructions for AI agents to add, update, and maintain documentation in this project following the established professional standards.

## Quick Reference

### When to Use This Guide

- Adding new API documentation
- Updating existing documentation
- Creating new documentation sections
- Fixing documentation issues
- Expanding examples or tutorials

### Key Principles to Remember

- **Consistency first** - Follow established patterns exactly
- **Developer experience** - Make it easy to understand and use
- **Copy-paste ready** - All examples must work immediately
- **Cross-references** - Link to related documentation
- **Template compliance** - Use the API template for all APIs

---

## Adding New API Documentation

### Step 1: Choose Your Approach

You have **two options** for creating API documentation:

#### Option A: Manual Documentation (Traditional)

Follow the manual template below for complete control over formatting.

#### Option B: Automated Documentation with @docs: Markers (Recommended)

Use the `@docs:` marker system to embed documentation directly in your source code. This approach:

- **Automatically generates** technical details (parameters, types, signatures)
- **Applies your template** format consistently
- **Keeps documentation with code** for easier maintenance
- **Reduces duplication** and formatting errors

**Choose Option B (automated) unless you need custom formatting that the template doesn't support.**

### Step 2A: Using the @docs: Marker System (Recommended)

Add `@docs:` markers directly in your Python docstrings:

````python
async def configure_logging(level: str = "INFO") -> None:
    """
    Configure the logging system with the specified settings.

    This function must be called before any logging operations can occur.
    It sets up sinks, processors, and enrichers based on the provided configuration.

    @docs:use_cases
    - **Development environments** need **human-readable logs** for debugging
    - **Production systems** require **structured JSON logs** for aggregation
    - **Security audits** demand **detailed logging** with configurable levels

    @docs:examples
    ```python
    from fapilog import configure_logging

    # Basic configuration
    await configure_logging(level="DEBUG", format="pretty")

    # With custom sinks
    await configure_logging(
        level="INFO",
        format="json",
        sinks=["stdout", "file", "http"]
    )
    ```

    @docs:notes
    - All timestamps are emitted in **RFC3339 UTC format**
    - Configuration is **immutable** after initialization
    - See [Logging Levels](../concepts/logging-levels.md) for details
    """
    pass
````

#### Available @docs: Markers

- **`@docs:use_cases`** - Business context and specific scenarios
- **`@docs:examples`** - Working code examples (copy-paste ready)
- **`@docs:notes`** - Implementation details, caveats, and cross-references

#### What Gets Auto-Generated

The system automatically generates:

- **Function signatures** and parameters
- **Type hints** and default values
- **Environment variables** (referencing env-vars.md)
- **Cross-references** to source code
- **Inheritance** and class hierarchies

#### What You Control

You manually provide:

- **Use cases** with business context
- **Code examples** that demonstrate real usage
- **Notes** with implementation details and warnings
- **Cross-references** to related documentation

### Step 2B: Manual Template (Traditional Approach)

Every API entry MUST follow this exact format if not using @docs: markers:

````markdown
# {API Name}

## Description

Briefly explain what this API does, in plain language. Focus on the behavior and contract rather than implementation detail.

## Parameters

| Name   | Type | Default | Description                   |
| ------ | ---- | ------- | ----------------------------- |
| param1 | str  | "…"     | Description of the parameter. |
| param2 | int  | 100     | Description of the parameter. |

## Environment Variables

| Variable                   | Default      | Description                            |
| -------------------------- | ------------ | -------------------------------------- |
| FAPILOG_EXAMPLE\_\_SETTING | some-default | What this variable controls.           |
| FAPILOG_QUEUE\_\_MAX_SIZE  | 8192         | Bounded queue capacity for log events. |

## Code Examples

```python
from fapilog import {api_name}

# Example usage
result = {api_name}(...)
```
````

## Use Cases

- Business API needs to include a **trace_id** in every response.
- Batch jobs want **non-blocking logging** with backpressure protection.
- Security teams require **URL credential redaction**.

## Notes

- Emit RFC3339 UTC timestamps.
- Mention caveats, gotchas, or related APIs.
- Cross-link to [related concepts](../concepts/pipeline.md) or other APIs if relevant.

````

### Step 3: Fill in Each Section

#### Description Section
- **One paragraph maximum**
- **Plain language** - avoid technical jargon
- **Focus on behavior** - what does it do, not how it works
- **Clear purpose** - why would someone use this?

**Good Example:**

```markdown
## Description

Configures the logging system with the specified settings. This function must be called before any logging operations can occur. It sets up sinks, processors, and enrichers based on the provided configuration.
````

**Bad Example:**

```markdown
## Description

This function initializes the internal logging infrastructure by creating sink instances, setting up processor pipelines, and configuring enrichment mechanisms. It uses dependency injection to wire together the various components.
```

#### Parameters Section

- **Complete coverage** of all public parameters
- **Type information** with Python types (str, int, bool, etc.)
- **Default values** explicitly stated (use "None" if no default)
- **Descriptive explanations** that help developers understand usage

**Good Example:**

| Name   | Type | Default    | Description                                                       |
| ------ | ---- | ---------- | ----------------------------------------------------------------- |
| level  | str  | "INFO"     | Minimum log level to process (DEBUG, INFO, WARN, ERROR)           |
| format | str  | "json"     | Output format: "json" for structured, "pretty" for human-readable |
| sinks  | List | ["stdout"] | List of sink names to write logs to                               |

#### Environment Variables Section

- link to `docs/env-var.md`

**Good Example:**

| Variable                               | Default | Description                                   |
| -------------------------------------- | ------- | --------------------------------------------- |
| FAPILOG_CORE__LOG_LEVEL                | INFO    | Minimum log level for all loggers             |
| FAPILOG_OBSERVABILITY__LOGGING__FORMAT | json    | Output format: json or text                   |
| FAPILOG_CORE__MAX_QUEUE_SIZE           | 10000   | Maximum number of log events in memory buffer |

#### Code Examples Section

- **Import statements** showing how to access the API
- **Basic usage example** that demonstrates core functionality
- **Copy-paste ready** code that developers can use immediately
- **Realistic scenarios** that match actual use cases

**Good Example:**

```python
from fapilog import configure_logging, LoggingSettings

# Basic configuration
settings = LoggingSettings(level="DEBUG", format="pretty")
configure_logging(settings)

# With custom sinks
settings = LoggingSettings(
    level="INFO",
    sinks=["stdout", "file"],
    file_path="/var/log/app.log"
)
configure_logging(settings)
```

#### @docs: Examples Best Practices

When using `@docs:examples` markers:

- **Include import statements** showing how to access the API
- **Show basic usage** that demonstrates core functionality
- **Make examples copy-paste ready** - developers should be able to use them immediately
- **Use realistic scenarios** that match actual use cases
- **Test all examples** before committing to ensure they work

**Good @docs:examples Example:**

````python
@docs:examples
```python
from fapilog import get_async_logger

# Create logger instance
logger = await get_async_logger()

# Basic logging
await logger.info("Application started")
await logger.error("Database connection failed", exc_info=True)

# Structured logging with context
await logger.info(
    "User action",
    user_id="12345",
    action="login",
    ip_address="192.168.1.1",
)

# Cleanup
await logger.drain()
````

````

#### Use Cases Section

- **3-5 specific scenarios** where this API is commonly used
- **Business context** explaining why each use case matters
- **Bold formatting** for key terms and concepts
- **Actionable descriptions** that help developers understand applicability

**Good Example:**

- **Development environments** need **human-readable logs** for debugging and troubleshooting.
- **Production systems** require **structured JSON logs** for log aggregation and analysis.
- **Security audits** demand **detailed logging** with configurable **sensitivity levels**.

#### @docs: Use Cases Best Practices

When using `@docs:use_cases` markers:

- **Focus on business value** - explain why someone would use this API
- **Use bold formatting** for key terms and concepts
- **Provide 3-5 specific scenarios** that cover common use cases
- **Include industry context** when relevant (e.g., "compliance requirements", "security teams")
- **Make them actionable** - developers should understand when to use this API

**Good @docs:use_cases Example:**
```python
@docs:use_cases
- **Web applications** need **request-scoped logging** with correlation IDs
- **Microservices** require **distributed tracing** and **structured logging**
- **Batch processing** benefits from **high-throughput** and **non-blocking operations**
- **Security applications** demand **audit logging** with **immutable records**
````

#### Notes Section

- **Implementation details** that developers need to know
- **Caveats and gotchas** to prevent common mistakes
- **Cross-references** to related documentation and APIs
- **Technical specifications** (e.g., timestamp formats, data formats)

**Good Example:**

- All timestamps are emitted in **RFC3339 UTC format**.
- The configuration is **immutable** after initialization - changes require restart.
- See [Logging Levels](../concepts/logging-levels.md) for detailed level descriptions.
- Related: [Custom Sinks](../examples/custom-sinks.md), [Environment Configuration](../config.md)

#### @docs: Notes Best Practices

When using `@docs:notes` markers:

- **Include implementation details** that developers need to know
- **Mention caveats and gotchas** to prevent common mistakes
- **Provide cross-references** to related documentation and APIs
- **Include technical specifications** (e.g., timestamp formats, data formats)
- **Use bold formatting** for important warnings and requirements

**Good @docs:notes Example:**

```python
@docs:notes
- Logger instances are **not thread-safe** - create one per thread/coroutine
- All methods are **async** and should be awaited
- **Always call close()** when done to ensure proper cleanup
- See [Async Logging](../concepts/async-logging.md) for best practices
```

---

## Adding New Documentation Sections

### Step 1: Determine the Section Type

- **Concept documentation** - explains how things work
- **Tutorial documentation** - step-by-step instructions
- **Reference documentation** - complete API coverage
- **Example documentation** - real-world usage patterns

### Step 2: Choose the Right Location

- **User-facing docs** go in the main docs directory
- **Developer docs** go in contributing or development sections
- **Examples** go in the examples directory
- **API docs** go in the api-reference section

### Step 3: Follow the Section Template

#### Concept Documentation

````markdown
# {Concept Name}

## Overview

Brief explanation of what this concept is and why it matters.

## Key Components

- **Component 1**: What it does and how it fits
- **Component 2**: What it does and how it fits
- **Component 3**: What it does and how it fits

## How It Works

Step-by-step explanation of the concept in action.

## Examples

```python
# Practical example showing the concept
```
````

## Related Concepts

- [Related Concept 1](../concepts/related-1.md)
- [Related Concept 2](../concepts/related-2.md)

````

#### Tutorial Documentation

```markdown
# {Tutorial Title}

## Prerequisites

What the user needs to know or have before starting.

## What You'll Learn

Specific outcomes from completing this tutorial.

## Step 1: {First Step}

Detailed explanation with code examples.

## Step 2: {Second Step}

Detailed explanation with code examples.

## Summary

What was accomplished and what to do next.

## Next Steps

- [Related Tutorial](../tutorials/next-tutorial.md)
- [API Reference](../api-reference.md)
````

---

## Updating Existing Documentation

### Step 1: Identify What Needs Updating

- **API changes** - new parameters, removed features, changed behavior
- **Example updates** - code that no longer works
- **Link fixes** - broken cross-references
- **Content improvements** - clarity, accuracy, completeness

### Step 2: Make Minimal Changes

- **Preserve existing structure** unless restructuring is necessary
- **Update only what changed** - don't rewrite unnecessarily
- **Maintain cross-references** - update links if files move
- **Keep examples working** - test all code samples

### Step 3: Update Cross-References

- **Check all links** in the updated section
- **Update file paths** if documentation structure changes
- **Verify target documents** still exist and are relevant
- **Use relative paths** for internal documentation

---

## Documentation Quality Checklist

### Before Submitting

- [ ] **Template compliance** - follows the API template exactly
- [ ] **Complete coverage** - all parameters and options documented
- [ ] **Working examples** - code can be copied and run
- [ ] **Cross-references** - links to related documentation
- [ ] **Consistent terminology** - uses established terms
- [ ] **Clear language** - easy to understand for target audience
- [ ] **Proper formatting** - tables, code blocks, headers correct

### Content Standards

- [ ] **One concept per section** - don't mix multiple topics
- [ ] **Progressive complexity** - simple to advanced
- [ ] **Real-world scenarios** - practical, not theoretical
- [ ] **Error handling** - show how to handle common issues
- [ ] **Best practices** - demonstrate recommended approaches

### Technical Standards

- [ ] **Markdown syntax** - proper formatting and structure
- [ ] **Code highlighting** - correct language tags
- [ ] **Table formatting** - aligned columns and headers
- [ ] **Link validation** - all internal links work
- [ ] **Version compatibility** - examples work with current version

---

## Common Documentation Patterns

### Configuration Documentation

````markdown
## Configuration Options

| Option  | Type | Default | Description         |
| ------- | ---- | ------- | ------------------- |
| enabled | bool | true    | Enable this feature |
| timeout | int  | 30      | Timeout in seconds  |

## Environment Variables

| Variable        | Default | Description              |
| --------------- | ------- | ------------------------ |
| FEATURE_ENABLED | true    | Enable/disable feature   |
| FEATURE_TIMEOUT | 30      | Timeout value in seconds |

## Example Configuration

```python
from fapilog import FeatureSettings

settings = FeatureSettings(
    enabled=True,
    timeout=60
)
```
````

````

### Error Handling Documentation

```markdown
## Error Handling

This API may raise the following exceptions:

- **ConfigurationError**: Invalid configuration parameters
- **ConnectionError**: Unable to connect to external service
- **ValidationError**: Input data validation failed

## Example Error Handling

```python
try:
    result = api_call(data)
except ConfigurationError as e:
    log.error("Invalid configuration", error=str(e))
    # Handle configuration error
except ConnectionError as e:
    log.error("Connection failed", error=str(e))
    # Handle connection error
````

````

### Performance Documentation

```markdown
## Performance Characteristics

- **Memory usage**: O(n) where n is the number of items
- **Time complexity**: O(log n) for lookups
- **Concurrency**: Thread-safe for read operations

## Performance Tips

- Use **batching** for multiple operations
- Enable **caching** for frequently accessed data
- Monitor **memory usage** with large datasets
````

---

## Troubleshooting Documentation Issues

### Common Problems

#### Broken Links

- **Symptom**: Links return 404 or point to wrong content
- **Solution**: Update file paths, verify target documents exist
- **Prevention**: Use relative paths, test all links

#### Template Non-Compliance

- **Symptom**: API documentation doesn't follow standard format
- **Solution**: Restructure to match the mandatory template
- **Prevention**: Use the template checklist before submitting

#### Outdated Examples

- **Symptom**: Code examples don't work or are deprecated
- **Solution**: Update examples to match current API
- **Prevention**: Test all examples regularly

#### Inconsistent Terminology

- **Symptom**: Same concepts called different names
- **Solution**: Standardize on established terms
- **Prevention**: Review existing documentation for terminology

### Getting Help

- **Check existing documentation** for similar patterns
- **Review the style guide** for formatting standards
- **Ask for clarification** if requirements are unclear
- **Test your changes** before submitting

---

## Best Practices Summary

### Do's

- ✅ **Follow the API template** exactly for all API documentation
- ✅ **Use clear, simple language** appropriate for the audience
- ✅ **Provide working examples** that can be copied immediately
- ✅ **Cross-reference related content** to help navigation
- ✅ **Test all code samples** before submitting
- ✅ **Use consistent terminology** throughout

### Don'ts

- ❌ **Skip template sections** - all are required
- ❌ **Use technical jargon** without explanation
- ❌ **Provide untested examples** that might not work
- ❌ **Create broken links** to non-existent content
- ❌ **Mix multiple topics** in a single section
- ❌ **Assume reader knowledge** of internal implementation

### Remember

- **Consistency is key** - follow established patterns
- **Developer experience matters** - make it easy to use
- **Quality over quantity** - better to do less well than more poorly
- **Maintenance is ongoing** - documentation needs regular updates
- **Community feedback** helps improve documentation quality

---

## Quick Commands for AI Agents

### When Adding API Documentation

#### Using @docs: Markers (Recommended)

1. **Identify the API** and its public interface
2. **Add @docs: markers** to the docstring following the guidelines above
3. **Build documentation** to auto-generate the formatted output
4. **Test all examples** to ensure they work
5. **Check cross-references** and update links
6. **Verify the generated output** matches your template requirements

#### Using Manual Template

1. **Identify the API** and its public interface
2. **Copy the template** exactly as shown above
3. **Fill in each section** following the guidelines
4. **Test all examples** to ensure they work
5. **Check cross-references** and update links
6. **Validate template compliance** using the checklist

### When Updating Documentation

1. **Identify what changed** and what needs updating
2. **Make minimal changes** to preserve existing structure
3. **Update examples** to match current API
4. **Fix broken links** and cross-references
5. **Test updated content** for accuracy
6. **Verify template compliance** if updating API docs

### When Creating New Sections

1. **Choose the right location** based on content type
2. **Use the appropriate template** for the section type
3. **Follow established patterns** from similar sections
4. **Add cross-references** to related content
5. **Test all examples** and code samples
6. **Update navigation** if adding major sections

---

## Automated Documentation System

### How It Works

The `@docs:` marker system is powered by a custom Sphinx extension that:

1. **Parses** `@docs:` markers from your Python docstrings
2. **Applies** the standardized fapilog API template format
3. **Generates** professional documentation automatically
4. **Integrates** seamlessly with existing Sphinx autodoc system

### System Components

- **`custom_autodoc.py`** - Custom Sphinx extension that processes @docs: markers
- **Template Engine** - Automatically formats content according to your standards
- **Integration** - Works with existing autodoc for functions, classes, and methods

### Benefits

- **Consistency**: All API docs follow the exact same template
- **Maintainability**: Documentation lives with the code
- **Automation**: Technical details are auto-generated
- **Flexibility**: You control business context and examples
- **Quality**: Professional, copy-paste ready documentation

### Getting Started

1. **Choose an API** to document (function, class, or method)
2. **Add the basic description** in the docstring
3. **Add `@docs:use_cases`** with 3-5 business scenarios
4. **Add `@docs:examples`** with working code
5. **Add `@docs:notes`** with caveats and cross-references
6. **Build the documentation** to see the formatted output

### Example Files

- **`test_api.py`** - Complete examples of the @docs: system in action
- **`custom_autodoc.py`** - The custom Sphinx extension implementation

---

This guide ensures that all documentation maintains the professional quality and consistency that developers expect from this project.
