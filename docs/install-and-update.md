## Install and Update Flows

This guide provides copy-ready commands for installing `fapilog`, enabling optional features via extras, using separate plugin packages, working with constraints/lockfiles and private indexes, and performing safe upgrades with version compatibility.

### Quick Install

- Pip:

```bash
pip install "fapilog>=3,<4"
```

- uv:

```bash
uv add "fapilog>=3,<4"
```

### Enable Optional Features via Extras

The project publishes optional integrations via extras. Choose only what you need:

- Pip:

```bash
pip install "fapilog[enterprise]"
pip install "fapilog[fastapi]"
pip install "fapilog[loki]"
pip install "fapilog[cloud]"
pip install "fapilog[siem]"
pip install "fapilog[dev]"
pip install "fapilog[docs]"
pip install "fapilog[all]"
```

- uv:

```bash
uv add "fapilog[enterprise]"
uv add "fapilog[fastapi]"
uv add "fapilog[loki]"
uv add "fapilog[cloud]"
uv add "fapilog[siem]"
uv add "fapilog[dev]"
uv add "fapilog[docs]"
uv add "fapilog[all]"
```

Notes:

- Extras install optional dependencies only. Core logging works without extras.
- Use a single command to combine extras, e.g. `pip install "fapilog[cloud,siem]"`.
- The FastAPI integration is import-guarded. If the extra is not installed, `fapilog.fastapi.AVAILABLE` will be `False` and the integration will remain inactive.

### Enabling internal diagnostics (development)

To surface structured WARN diagnostics for internal, non-fatal errors:

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
```

These messages aid debugging without affecting application stability.

### Separate Plugin Packages

The ecosystem also supports separate `fapilog-*` plugin packages. Install them alongside core:

- Pip:

```bash
pip install "fapilog>=3,<4" fapilog-sample-plugin
```

- uv:

```bash
uv add "fapilog>=3,<4" fapilog-sample-plugin
```

Version guards in plugins should declare compatibility, for example in a plugin's metadata: `Requires-Dist: fapilog (>=3,<4)`.

### Constraints and Lockfiles

For deterministic builds in CI and production:

- Pip with constraints:

```bash
# constraints.txt pins exact versions
cat > constraints.txt <<'CTR'
fapilog>=3,<4
# pin transitive deps as needed, e.g.
# httpx==0.27.2
CTR

pip install -r requirements.txt -c constraints.txt
```

Example `requirements.txt`:

```text
fapilog[enterprise]
fapilog-sample-plugin
```

- uv lock:

```bash
# Add dependencies and produce uv.lock
uv add "fapilog[enterprise]" fapilog-sample-plugin

# Recreate lock on upgrades
uv lock --upgrade-package fapilog
```

### Private Indexes (Artifactory, Nexus, etc.)

- Pip (one-off):

```bash
pip install --index-url "https://<host>/simple" --extra-index-url "https://pypi.org/simple" "fapilog[enterprise]"
```

- Pip (environment):

```bash
export PIP_INDEX_URL="https://<host>/simple"
export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"
pip install "fapilog[enterprise]"
```

- uv (project configuration in `pyproject.toml`):

```toml
[tool.uv]
index-url = "https://<host>/simple"
extra-index-url = ["https://pypi.org/simple"]
```

Or environment variables:

```bash
export UV_INDEX_URL="https://<host>/simple"
export UV_EXTRA_INDEX_URL="https://pypi.org/simple"
uv add "fapilog[enterprise]"
```

### Upgrade and Compatibility Guidance

- Show current versions:

```bash
python -c "import fapilog, pkgutil; print('fapilog', getattr(fapilog, '__version__', 'unknown'))"
```

- Pip upgrade (respecting major range):

```bash
pip install -U "fapilog>=3,<4"
```

- uv upgrade:

```bash
uv lock --upgrade-package fapilog
uv sync
```

Compatibility tips:

- Keep plugins within the same major range as core, e.g., `fapilog (>=3,<4)`.
- Prefer constraints/locks in CI to avoid surprise minor bumps.
- When enabling extras, confirm optional deps are compatible with your Python version.

### Common Errors

- "No matching distribution found": Verify Python version and indexes.
- Import errors after install: Confirm the correct extra was installed.
- Private index auth issues: Provide credentials via netrc, keychain, or per-tool auth config.
