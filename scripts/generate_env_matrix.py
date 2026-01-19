"""Generate env vars matrix from Pydantic Settings (auto-generated doc).

By default writes to docs/env-vars.generated.md.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from fapilog.core.settings import Settings


def _iter_fields(model: BaseModel) -> Iterable[tuple[str, Any, Any, str]]:
    """Yield (name, annotation, default, description) from the class.

    Accessing model_fields on an instance is deprecated in Pydantic v2.
    """
    for name, field in type(model).model_fields.items():
        default = field.default if field.default is not None else "—"
        desc = getattr(field, "description", None) or ""
        yield name, field.annotation, default, desc


def flatten(prefix: str, model: BaseModel) -> list[tuple[str, Any, str, str]]:
    rows: list[tuple[str, Any, str, str]] = []
    for name, annotation, default, desc in _iter_fields(model):
        key_base = f"{prefix}__{name}" if prefix else f"FAPILOG_{name}"
        key = key_base.upper()
        typ = getattr(annotation, "__name__", str(annotation))

        value = getattr(model, name, None)
        if isinstance(value, BaseModel):
            rows.extend(flatten(key, value))
        else:
            rows.append((key, typ, str(default), str(desc)))
    return rows


def render_env_markdown(rows: list[tuple[str, Any, str, str]]) -> str:
    lines = [
        (
            "<!-- AUTO-GENERATED: do not edit by hand. "
            "Run scripts/generate_env_matrix.py -->"
        ),
        "# Environment Variables",
        "",
        "| Variable | Type | Default | Description |",
        "|----------|------|---------|-------------|",
    ]
    for var, typ, default, desc in sorted(set(rows)):
        # Keep each markdown row within linter line length
        description = desc or "<!-- TODO: fill description -->"
        lines.append(f"| `{var}` | {typ} | {default} | {description} |")
    lines.append("")
    return "\n".join(lines)


def _collect_settings_tree(
    model: BaseModel,
) -> list[tuple[str, str, str, str]]:
    """Collect (path, type, default, description) for scalar fields.

    Recurses through nested BaseModel fields and returns a flat list with
    dotted paths starting at the root model name.
    """
    out: list[tuple[str, str, str, str]] = []
    root = type(model).__name__
    for name, ann, default, desc in _iter_fields(model):
        value = getattr(model, name, None)
        path = f"{root}.{name}"
        typ = getattr(ann, "__name__", str(ann))
        if isinstance(value, BaseModel):
            nested = _collect_settings_tree(value)
            # rewrite nested paths with our root path
            for p, t, d, de in nested:
                out.append((f"{root}.{p.split('.', 1)[1]}", t, d, de))
        else:
            out.append((path, typ, str(default), str(desc)))
    return out


def render_settings_guide(settings: Settings) -> str:
    lines: list[str] = [
        (
            "<!-- AUTO-GENERATED: do not edit by hand. "
            "Run scripts/generate_env_matrix.py -->"
        ),
        "# Settings Reference",
        "",
        "This guide documents Settings groups and fields.",
        "",
    ]
    # Top-level groups only (skip the root scalar fields)
    groups = [
        ("core", settings.core),
        ("security", settings.security),
        ("observability", settings.observability),
        ("plugins", settings.plugins),
    ]
    for group_name, group_model in groups:
        lines.append(f"## {group_name}")
        lines.append("")
        lines.append("| Field | Type | Default | Description |")
        lines.append("|-------|------|---------|-------------|")
        for name, ann, default, desc in _iter_fields(group_model):
            value = getattr(group_model, name, None)
            if isinstance(value, BaseModel):
                # Nested subsection
                lines.append("")
                lines.append(f"### {group_name}.{name}")
                lines.append("")
                lines.append("| Field | Type | Default | Description |")
                lines.append("|-------|------|---------|-------------|")
                for n2, a2, d2, de2 in _iter_fields(value):
                    t2 = getattr(a2, "__name__", str(a2))
                    desc2 = de2 or ""
                    lines.append(
                        f"| `{group_name}.{name}.{n2}` | {t2} | {d2} | {desc2} |"
                    )
            else:
                typ = getattr(ann, "__name__", str(ann))
                ds = desc or ""
                lines.append(f"| `{group_name}.{name}` | {typ} | {default} | {ds} |")
        lines.append("")
    return "\n".join(lines)


def _scan_local_plugin_metadata(paths: list[Path]) -> list[dict[str, Any]]:
    """Best-effort static scan for PLUGIN_METADATA without importing modules.

    Parses Python files to extract a top-level PLUGIN_METADATA dict. Values that
    are not literals are stringified. Derives plugin_type from folder name when
    missing.
    """
    results: list[dict[str, Any]] = []
    for base in paths:
        if not base.exists() or not base.is_dir():
            continue
        for py in base.glob("*.py"):
            try:
                src = py.read_text(encoding="utf-8")
                tree = ast.parse(src)
                md: dict[str, Any] | None = None
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        # look for PLUGIN_METADATA = {...}
                        if any(
                            isinstance(t, ast.Name) and t.id == "PLUGIN_METADATA"
                            for t in node.targets
                        ) and isinstance(node.value, ast.Dict):
                            md = {}
                            for k, v in zip(
                                node.value.keys, node.value.values, strict=False
                            ):
                                key = None
                                if isinstance(k, ast.Constant) and isinstance(
                                    k.value, str
                                ):
                                    key = k.value
                                else:
                                    continue
                                if isinstance(v, ast.Constant):
                                    md[key] = v.value
                                else:
                                    try:
                                        md[key] = ast.unparse(v)  # type: ignore[attr-defined]
                                    except Exception:
                                        md[key] = "<expr>"
                if md:
                    # derive type from folder when missing
                    if "plugin_type" not in md:
                        parent = py.parent.name
                        if parent.endswith("sinks"):
                            md["plugin_type"] = "sink"
                        elif parent.endswith("redactors"):
                            md["plugin_type"] = "redactor"
                        elif parent.endswith("enrichers"):
                            md["plugin_type"] = "enricher"
                        elif parent.endswith("processors"):
                            md["plugin_type"] = "processor"
                    results.append(md)
            except Exception:
                continue
    return results


def render_plugin_guide(plugin_map: dict[str, Any]) -> str:
    lines: list[str] = [
        (
            "<!-- AUTO-GENERATED: do not edit by hand. "
            "Run scripts/generate_env_matrix.py -->"
        ),
        "# Plugin Catalog",
        "",
        "| Name | Type | Version | API | Author | Description |",
        "|------|------|---------|-----|--------|-------------|",
    ]
    for _, info in sorted(plugin_map.items()):
        try:
            md = info.metadata  # PluginMetadata
            api = getattr(md, "api_version", "")
            lines.append(
                f"| {md.name} | {md.plugin_type} | {md.version} | "
                f"{api} | {md.author or ''} | {md.description} |"
            )
        except Exception:
            continue
    lines.append("")
    return "\n".join(lines)


def render_plugin_guide_from_metadata(
    metas: list[dict[str, Any]],
    discovered: dict[str, Any] | None = None,
) -> str:
    """Render plugin table from static metadata and optional discovery map.

    Static metadata is used for local built-ins to avoid import-time failures.
    Discovery entries are included for anything not already covered.
    """
    rows: list[tuple[str, str, str, str, str, str]] = []
    taken: set[str] = set()
    for md in metas:
        name = str(md.get("name", "?"))
        plugin_type = str(md.get("plugin_type", "?"))
        version = str(md.get("version", "?"))
        api = str(md.get("api_version", ""))
        author = str(md.get("author", ""))
        desc = str(md.get("description", ""))
        rows.append((name, plugin_type, version, api, author, desc))
        taken.add(name)
    if discovered:
        for _, info in sorted(discovered.items()):
            try:
                md = info.metadata
                if md.name in taken:
                    continue
                # Skip entries that failed to load
                if "Failed to load" in (md.description or ""):
                    continue
                api = getattr(md, "api_version", "")
                rows.append(
                    (
                        md.name,
                        md.plugin_type,
                        md.version,
                        api,
                        md.author or "",
                        md.description,
                    )
                )
            except Exception:
                continue
    lines: list[str] = [
        (
            "<!-- AUTO-GENERATED: do not edit by hand. "
            "Run scripts/generate_env_matrix.py -->"
        ),
        "# Plugin Catalog",
        "",
        "| Name | Type | Version | API | Author | Description |",
        "|------|------|---------|-----|--------|-------------|",
    ]
    for name, ptype, ver, api, author, desc in sorted(rows):
        lines.append(f"| {name} | {ptype} | {ver} | {api} | {author} | {desc} |")
    lines.append("")
    return "\n".join(lines)


def render_schema_guide(
    settings: Settings,
    envelope_schema: Path | None,
) -> str:
    lines: list[str] = [
        (
            "<!-- AUTO-GENERATED: do not edit by hand. "
            "Run scripts/generate_env_matrix.py -->"
        ),
        "# Schema Guide",
        "",
        "## Settings JSON Schemas",
    ]

    def _add_schema(title: str, model: BaseModel) -> None:
        schema = type(model).model_json_schema()
        lines.append("")
        lines.append(f"### {title}")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(
                schema,
                indent=2,
                sort_keys=True,
            )
        )
        lines.append("```")

    _add_schema("CoreSettings", settings.core)
    _add_schema("SecuritySettings", settings.security)
    _add_schema("ObservabilitySettings", settings.observability)
    _add_schema("PluginsSettings", settings.plugins)

    lines.append("")
    lines.append("## LogEnvelope Schema")
    if envelope_schema and envelope_schema.exists():
        try:
            data = json.loads(envelope_schema.read_text(encoding="utf-8"))
            lines.append("")
            lines.append("### LogEnvelope v1.x (from file)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(data, indent=2, sort_keys=True))
            lines.append("```")
        except Exception:
            lines.append("")
            lines.append("_Failed to read envelope schema file._")
    else:
        lines.append("")
        lines.append("_Envelope schema file not found._")
    return "\n".join(lines)


async def _discover_plugins() -> dict[str, Any]:
    """Plugin discovery removed - return empty dict."""
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/env-vars.md"),
        help=(
            "Output Markdown file (default: docs/env-vars.md). "
            "Pre-commit and CI will keep this in sync."
        ),
    )
    parser.add_argument(
        "--settings-guide",
        type=Path,
        default=Path("docs/settings-guide.md"),
        help="Write nested settings reference to this path.",
    )
    parser.add_argument(
        "--schema-guide",
        type=Path,
        default=Path("docs/schema-guide.md"),
        help="Write JSON schema guide to this path.",
    )
    parser.add_argument(
        "--envelope-schema",
        type=Path,
        default=Path("schemas/log_envelope_v1.json"),
        help="Path to LogEnvelope JSON Schema file (optional).",
    )
    parser.add_argument(
        "--plugin-guide",
        type=Path,
        default=Path("docs/plugin-guide.md"),
        help="Write plugin catalog to this path.",
    )
    args = parser.parse_args()

    cfg = Settings()
    rows = flatten("", cfg)
    env_md = render_env_markdown(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(env_md, encoding="utf-8")

    # Settings guide
    settings_md = render_settings_guide(cfg)
    args.settings_guide.parent.mkdir(parents=True, exist_ok=True)
    args.settings_guide.write_text(settings_md, encoding="utf-8")

    # Schema guide
    schema_md = render_schema_guide(cfg, args.envelope_schema)
    args.schema_guide.parent.mkdir(parents=True, exist_ok=True)
    args.schema_guide.write_text(schema_md, encoding="utf-8")

    # Plugin catalog
    try:
        plugin_map = asyncio.run(_discover_plugins())
        local_metas = _scan_local_plugin_metadata(
            [
                Path("src/fapilog/plugins/sinks"),
                Path("src/fapilog/plugins/redactors"),
                Path("src/fapilog/plugins/enrichers"),
                Path("src/fapilog/plugins/processors"),
            ]
        )
        plugin_md = render_plugin_guide_from_metadata(local_metas, plugin_map)
        args.plugin_guide.parent.mkdir(parents=True, exist_ok=True)
        args.plugin_guide.write_text(plugin_md, encoding="utf-8")
    except Exception:
        # Best-effort: skip catalog if discovery fails locally
        pass


if __name__ == "__main__":
    main()
