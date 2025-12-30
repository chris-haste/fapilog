# fapilog-tamper

Tamper-evident logging add-on for fapilog. This package registers the
`tamper-sealed` integrity plugin and ships the core types and helpers used by
subsequent stories (enricher, sealed sink, verification).

## Installation

```bash
pip install ./packages/fapilog-tamper
```

For Ed25519 signature support, install the optional group:

```bash
pip install './packages/fapilog-tamper[signatures]'
```

## Usage

```python
from fapilog.plugins.integrity import load_integrity_plugin

plugin = load_integrity_plugin("tamper-sealed")
enricher = plugin.get_enricher()
```

The initial release provides placeholder components; subsequent stories layer on
full tamper-evident enrichment, sealed sinks, manifests, and verification.
