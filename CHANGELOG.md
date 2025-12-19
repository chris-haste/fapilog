# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Added Git tag–driven versioning (hatch-vcs) with dynamic __version__ import and docs alignment.
- Hardened HTTP sink (headers/retry/timeout, diagnostics/health) and added env-driven wiring tests.
- Improved CLI reliability with help coverage and end-to-end emit/flush tests; documented exit codes.
- Added concurrent deduplication and nested async lifecycle regressions to test suite.
