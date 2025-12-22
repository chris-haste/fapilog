# Changelog

All notable changes to this project will be documented in this file. This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2025-12-22

- Backpressure configuration now honored: `drop_on_full` waits instead of dropping when set to false; sink/enricher/redactor failures emit diagnostics.
- FastAPI request/response logging middleware added (sampling, header redaction, skip paths) and exported alongside context middleware.
- Metrics dependency is optional via extras; Prometheus exporter disables gracefully when absent; docs updated for lean core + extras.
- New reliability defaults and quality signals docs; coverage badge added (~90%).
- Release workflow now extracts the latest changelog section for GitHub releases and guards builds if the changelog is missing a section.

## [0.3.1] - Documentation release

- Documentation updates and alignment.

## [0.3.0] - Initial release of fapilog

- First public release.
