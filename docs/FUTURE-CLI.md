# Future CLI Plan

- **Runtime & Structure**: Choose Go+Cobra or Node+oclif; commands in subpackages; shared modules for config load/validation, logging, HTTP client, plugin manager, telemetry opt-in, UI helpers (spinners/tables/colors); unified error taxonomy; integration tests with golden files and JSON snapshots; global flags `--format json|table`, `--quiet`, `--verbose`, `--config`, `--cwd`, `--no-color`, `--token`, `--yes`, `--output`.
- **Configuration Lifecycle**: JSON/YAML/TOML schema backed by JSON Schema; loader with precedence (flags > env > config); validation reused by commands; default paths + XDG; errors with line/column; deprecations surfaced.
- **init**: Interactive wizard plus `--non-interactive`; generates config, example pipelines, env templates, `.gitignore` hints; detects existing files and offers merge; optional remote templates; flags `--template`, `--force`.
- **validate**: JSON Schema validation; warn on deprecated fields; static checks for paths/plugins availability; `--strict`; machine-readable output; exit 0 ok, 1 invalid, 2 warnings-only.
- **test**: Accept sample events via stdin/file; emit formatted output; support sinks (console/file/http) with `--dry-run`; latency/size stats; fixtures directory support; `--fail-on-warn`.
- **plugin list/search/install**: Shared manager; `list` shows installed version/status/path/signature; `search` hits registry API with filters (category/maintainer/verified); `install` supports semver ranges, integrity/signature check, cache, rollback; consider `update`/`remove`; global vs project scope.
- **tail**: Follow files/globs; multi-source (files/stdin/socket); regex/JSON filters; formatting templates; rate limits; flags `--since`, `--until`, `--follow`, `--max-lines`; rotation detection; colored levels; `--output json` for piping.
- **analyze**: Run rules/queries (pattern detection, error rates, latency percentiles); saved queries; summary + top findings; non-zero exit on thresholds; pluggable analyzers; `--profile` for timing.
- **benchmark**: Generate synthetic events; configurable rate/size/threads; measure throughput, p50/p95 latency, drops; baseline comparisons; export JSON/CSV; optional flamegraphs if available.
- **doctor**: Check permissions, disk, deps, plugin integrity, config issues, OS limits (ulimit/inotify); suggest fixes; exit 0/1; `--fix` for safe auto-fixes.
- **version**: Print CLI/core/plugin versions; `--all` shows dependencies; `--check-update` against release API; JSON support.
- **UX & Ergonomics**: Consistent flags/exit codes; rich help with examples; shell completions (bash/zsh/fish/pwsh); man page generation; contextual hints on errors; secrets redaction.
- **Security**: Signature verification for plugins; download checksums; sandbox plugin execution when possible; warn on unsigned sources; avoid plaintext tokens in config.
- **Observability**: Structured CLI logs (debug); optional anonymous telemetry toggle; timings per command; `--trace` emits execution trace.
- **Packaging**: Distribute via brew/scoop/npm/apt/cargo per runtime; static builds for macOS/Linux/Windows; reproducible builds + SBOM.
- **Testing & CI**: Matrix across OS; snapshot tests for outputs; e2e coverage for each command; fuzz config parser; contract tests for plugin API; performance budgets for `tail`/`analyze`/`benchmark`.
- **Documentation**: Strong `--help` examples per command; quickstart; doctor troubleshooting; plugin authoring guide; versioning policy; completion/man install steps.

Natural next steps:
1) Confirm language/runtime choice and plugin packaging strategy.
2) Define config schema and starter templates for `init`.
3) Sketch registry API contract for plugin search/install.
