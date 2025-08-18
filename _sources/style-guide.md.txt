# Documentation Style Guide

**Ensure all documentation is clear, consistent, and easy to maintain.**

This guide establishes standards for all documentation contributors to follow. It ensures our documentation remains professional, accessible, and maintainable as the project grows.

**See also:** [Contributing](contributing.md), [API Reference](api-reference.md), [User Guide](user-guide.md)

---

## Table of Contents

- [Documentation Principles](#documentation-principles)
- [Structure & Organization](#structure--organization)
- [Content Standards](#content-standards)
- [Code Examples](#code-examples)
- [Formatting & Style](#formatting--style)
- [Navigation & Links](#navigation--links)
- [Review Process](#review-process)

---

## Documentation Principles

### **Our Documentation Philosophy**

- **Developer-Centric** - Written for developers, by developers
- **Progressive Disclosure** - From basic concepts to advanced features
- **Copy-Paste Ready** - All examples work immediately
- **Cross-Referenced** - Links between related topics
- **Maintainable** - Single source of truth for each topic

### **Quality Standards**

- ✅ **Clear and concise** - Easy to understand
- ✅ **Comprehensive** - Cover all important topics
- ✅ **Accurate** - Always up to date with code
- ✅ **Consistent** - Same style and format throughout
- ✅ **Accessible** - Work for all users

---

## Structure & Organization

### **Documentation Hierarchy**

All documentation must follow the established hierarchy:

```
📚 Fapilog Documentation
├── 🎯 Introduction (introduction.md)
├── 📖 Primer (primer.md)
├── 🚀 Quickstart (quickstart.md)
├── 🏗️ Core Concepts (core-concepts.md)
├── 📚 User Guide (user-guide.md)
├── ⚙️ Configuration (config.md)
├── 📖 API Reference (api-reference.md)
├── 🛠️ Examples & Recipes (examples/index.md)
├── 🔧 Troubleshooting (troubleshooting.md)
├── ❓ FAQ (faq.md)
├── 🤝 Contributing (contributing.md)
└── 📝 Style Guide (style-guide.md)
```

### **Content Placement Guidelines**

**Where to place new content:**

- **Concepts & Architecture** → [Core Concepts](core-concepts.md)
- **Step-by-step tutorials** → [User Guide](user-guide.md)
- **Technical reference** → [API Reference](api-reference.md)
- **Real-world examples** → [Examples & Recipes](examples/index.md)
- **Common issues** → [Troubleshooting](troubleshooting.md)
- **Questions & answers** → [FAQ](faq.md)

### **No Duplication Policy**

- **Consolidate content** - Don't repeat information
- **Reference rather than repeat** - Link to existing content
- **Single source of truth** - Each topic has one authoritative location
- **Cross-reference liberally** - Connect related topics

---

## Content Standards

### **Feature Documentation Checklist**

For each feature or component, include:

**Required Elements:**

- ✅ **Feature name** (as heading)
- ✅ **Description** - What is this feature?
- ✅ **Purpose/Benefit** - Why does it matter? What problem does it solve?
- ✅ **High-level example** - Copy-paste-ready code snippet
- ✅ **Cross-references** - "See also" links to related content

**Example Structure:**

````markdown
## Feature Name

**Brief description of what this feature does.**

### Purpose

Explain why this feature exists and what problems it solves.

### Usage

```python
# Copy-paste ready example
from fapilog import configure_logging
configure_logging()
```
````

### Configuration

Describe configuration options and their effects.

### See Also

- [Related Feature](link-to-related.md)
- [API Reference](api-reference.md#relevant-section)

````

### **API Documentation Checklist**

For each API function, class, or method:

**Required Elements:**
- ✅ **API name** (as heading)
- ✅ **Simple introduction** - What is this API?
- ✅ **Purpose** - When and why should it be used?
- ✅ **Code examples** - Copy-paste-ready, minimal, and correct
- ✅ **Parameters** - All parameters with types and descriptions
- ✅ **Defaults** - Clearly state default values
- ✅ **Options** - List and describe all options and allowable values
- ✅ **Cross-references** - "See also" links to related APIs

**Example Structure:**
```markdown
## configure_logging()

**Configure the Fapilog logging system with the given settings.**

### Purpose

Initialize the logging system with sinks, enrichers, and middleware as configured.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `settings` | `LoggingSettings` | `None` | Complete configuration object |
| `app` | `Any` | `None` | FastAPI app instance |

### Example

```python
from fapilog import configure_logging
from fapilog.settings import LoggingSettings

# Basic configuration
configure_logging()

# Custom configuration
settings = LoggingSettings(level="DEBUG", sinks=["stdout"])
configure_logging(settings=settings)
````

### See Also

- [LoggingSettings](api-reference.md#loggingsettings)
- [User Guide - Configuration](user-guide.md#configuration)

````

---

## Code Examples

### **Code Block Standards**

**Language Specification:**
```python
# Always specify the language for syntax highlighting
from fapilog import configure_logging
configure_logging()
````

```bash
# Shell commands
pip install fapilog
python -m pytest tests/
```

```json
# Configuration examples
{
  "level": "INFO",
  "sinks": ["stdout", "file"],
  "format": "json"
}
```

### **Code Example Guidelines**

**✅ Do:**

- Keep examples minimal and focused
- Use realistic but simple scenarios
- Include expected output when helpful
- Test all examples before publishing
- Use consistent naming conventions

**❌ Don't:**

- Include unnecessary complexity
- Use placeholder values like "example.com"
- Mix multiple concepts in one example
- Use outdated APIs or patterns

**Good Example:**

```python
from fapilog import configure_logging, log

# Configure logging
configure_logging()

# Basic logging
log.info("Application started", version="1.0.0")
log.error("Database connection failed", database="postgres")
```

**Bad Example:**

```python
# Too complex for basic example
from fapilog import configure_logging, log
from fapilog.settings import LoggingSettings
from fapilog.sinks import CustomSink
from fapilog.enrichers import CustomEnricher

settings = LoggingSettings(
    level="DEBUG",
    sinks=["stdout", "file", "loki"],
    custom_sinks={"custom": CustomSink()},
    enrichers=[CustomEnricher()]
)
configure_logging(settings=settings)
```

### **Error Handling Examples**

**Include error scenarios:**

```python
from fapilog.exceptions import ConfigurationError

try:
    configure_logging(settings=invalid_settings)
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    # Handle error appropriately
```

---

## Formatting & Style

### **Headings & Structure**

**Heading Hierarchy:**

```markdown
# Main Section (H1)

## Subsection (H2)

### Sub-subsection (H3)

#### Detail Section (H4)
```

**Heading Guidelines:**

- Use sentence case (capitalize only first word and proper nouns)
- Be descriptive and specific
- Maintain logical hierarchy
- Don't skip heading levels

**Good Headings:**

- `## Installation`
- `### Configuration options`
- `#### Environment variables`

**Bad Headings:**

- `## INSTALLATION` (all caps)
- `### Config Options` (inconsistent case)
- `## 1. Installation` (numbered)

### **Text Formatting**

**Emphasis:**

- **Bold** for important terms, warnings, or key concepts
- _Italic_ for new terms on first use
- `Code` for inline code, file names, or commands

**Lists:**

- Use bullet points for related items
- Use numbered lists for steps or sequences
- Keep items parallel in structure

**Tables:**

- Use for structured data (parameters, options, comparisons)
- Include headers for all columns
- Align content appropriately

### **Line Length & Spacing**

- **Line length:** Keep under 100 characters
- **One sentence per line** for easier diffs and reviews
- **Consistent spacing** around headings and sections
- **Clear paragraph breaks** for readability

---

## Navigation & Links

### **Internal Links**

**Relative links for documentation:**

```markdown
[User Guide](user-guide.md)
[API Reference](api-reference.md#configure_logging)
[Examples](examples/index.md)
```

**Cross-references:**

```markdown
### See Also

- [User Guide - Configuration](user-guide.md#configuration)
- [API Reference - LoggingSettings](api-reference.md#loggingsettings)
- [Examples - Basic Setup](examples/index.md#basic-setup)
```

### **Link Guidelines**

**✅ Do:**

- Use relative links for internal documentation
- Check that links are valid and up to date
- Add "See also" sections for related content
- Use descriptive link text

**❌ Don't:**

- Use absolute URLs for internal links
- Create broken or outdated links
- Use generic text like "click here"
- Link to implementation details

### **Navigation Structure**

**Ensure sidebar navigation matches:**

- Required documentation hierarchy
- Logical grouping of related topics
- Progressive learning path
- Clear entry points for different user types

---

## Review Process

### **Pre-Submission Checklist**

Before submitting documentation changes:

- [ ] **Content accuracy** - Information is correct and up to date
- [ ] **Style consistency** - Follows this style guide
- [ ] **Code examples** - All examples tested and working
- [ ] **Links valid** - All internal and external links work
- [ ] **No duplication** - Content doesn't repeat existing information
- [ ] **Cross-references** - Added appropriate "See also" links
- [ ] **Grammar and spelling** - Content is well-written

### **Review Guidelines**

**For reviewers:**

- Focus on clarity and accuracy
- Check for consistency with style guide
- Verify code examples work
- Ensure appropriate cross-references
- Suggest improvements constructively

**For authors:**

- Address all review feedback
- Test code examples after changes
- Update related documentation if needed
- Keep changes focused and minimal

### **Automation & Tools**

**Available tools:**

- **Link checkers** - Verify all links work
- **Spell checkers** - Catch typos and errors
- **Markdown linters** - Ensure proper formatting
- **Build verification** - Confirm documentation builds correctly

**Usage:**

```bash
# Check documentation build
cd docs
sphinx-build -b html . _build/html

# Check for broken links
# (Use appropriate link checker for your setup)
```

---

## Examples

### **Good Documentation Example**

````markdown
## Structured Logging

**Transform your application logs into rich, structured data.**

### Purpose

Structured logging provides machine-readable logs that work seamlessly with modern observability tools. Instead of text messages, you get JSON objects with context and metadata.

### Usage

```python
from fapilog import configure_logging, log

configure_logging()

# Structured logging with context
log.info("User logged in",
         user_id="123",
         ip_address="192.168.1.100",
         duration_ms=45.2)
```
````

**Output:**

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "info",
  "event": "User logged in",
  "user_id": "123",
  "ip_address": "192.168.1.100",
  "duration_ms": 45.2
}
```

### Configuration

Enable structured logging with the `format` setting:

```python
from fapilog.settings import LoggingSettings

settings = LoggingSettings(format="json")  # Default
configure_logging(settings=settings)
```

### See Also

- [API Reference - Logging Interface](api-reference.md#logging-interface)
- [User Guide - Basic Usage](user-guide.md#basic-usage)
- [Examples - Structured Logging](examples/index.md#structured-logging)

````

### **Bad Documentation Example**

```markdown
## Logging

You can log stuff.

```python
# Do logging
log.info("stuff")
````

This logs stuff to the console.

````

**Problems:**
- Vague description
- No purpose or benefit explained
- Poor code example
- No configuration details
- No cross-references
- Inconsistent formatting

---

## Updates to This Guide

### **Proposing Changes**

1. **Create an issue** - Discuss the proposed change
2. **Submit a PR** - Include rationale and examples
3. **Get consensus** - Major changes require maintainer approval
4. **Update related docs** - Ensure consistency across the project

### **Change Categories**

**Minor changes** (typos, clarifications):
- Can be merged with single maintainer approval
- No impact on existing documentation

**Major changes** (new sections, format changes):
- Require consensus from maintainers
- May require updates to existing documentation
- Should include migration guidance

---

## Quick Reference

### **Common Patterns**

**Feature introduction:**
```markdown
## Feature Name

**Brief description.**

### Purpose
Why this feature exists.

### Usage
```python
# Example code
````

### See Also

- [Related content](link.md)

````

**API documentation:**
```markdown
## function_name()

**Brief description.**

### Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `param` | `Type` | `default` | Description |

### Example
```python
# Usage example
````

### See Also

- [Related API](link.md)

````

**Configuration guide:**
```markdown
## Configuration Option

**What this option does.**

### Environment Variable
```bash
export FAPILOG_OPTION=value
````

### Programmatic

```python
settings = LoggingSettings(option="value")
```

### Default

`default_value`

````

### **Formatting Cheat Sheet**

| Element | Markdown | Use Case |
|---------|----------|----------|
| **Bold** | `**text**` | Important terms, warnings |
| *Italic* | `*text*` | New terms, emphasis |
| `Code` | `` `text` `` | Inline code, commands |
| [Link](url) | `[text](url)` | Internal/external links |
| ```python | ```python` | Code blocks |
| | ` | ` | Inline code |

---

## Thank You!

Thank you for helping maintain high-quality documentation for Fapilog! Following this style guide ensures our documentation remains professional, accessible, and valuable for all users.

**Questions about this guide?**
- 💬 **Discussions**: [GitHub Discussions](https://github.com/chris-haste/fastapi-logger/discussions)
- 🐛 **Issues**: [GitHub Issues](https://github.com/chris-haste/fastapi-logger/issues)
- 📚 **Documentation**: [Contributing](contributing.md), [API Reference](api-reference.md)
````
