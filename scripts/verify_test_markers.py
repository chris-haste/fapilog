#!/usr/bin/env python3
"""
Verify test markers and report unmarked tests (treated as standard).

Usage:
    python scripts/verify_test_markers.py [--strict] <path>
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

RISK_MARKERS = {"critical", "security", "standard"}
TYPE_MARKERS = {"integration", "slow", "flaky", "postgres", "property"}
OTHER_ALLOWED_MARKERS = {
    "asyncio",
    "benchmark",
    "enterprise",
    "filterwarnings",
    "parametrize",
    "skip",
    "skipif",
    "usefixtures",
    "xfail",
}
ALLOWED_MARKERS = RISK_MARKERS | TYPE_MARKERS | OTHER_ALLOWED_MARKERS


@dataclass
class MarkerIssue:
    file: Path
    line: int
    name: str
    issue: str


class TestMarkerVisitor(ast.NodeVisitor):
    """Find test functions and check their markers."""

    def __init__(self, filepath: Path, module_markers: set[str]):
        self.filepath = filepath
        self.module_markers = module_markers
        self.class_markers_stack: list[set[str]] = []
        self.unmarked: list[MarkerIssue] = []
        self.unknown: list[MarkerIssue] = []
        self.conflicts: list[MarkerIssue] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_markers = self._get_pytest_markers(node)
        self.class_markers_stack.append(class_markers)
        self.generic_visit(node)
        self.class_markers_stack.pop()

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not node.name.startswith("test_"):
            return

        inherited = set(self.module_markers)
        for class_markers in self.class_markers_stack:
            inherited |= class_markers
        markers = inherited | self._get_pytest_markers(node)

        unknown = markers - ALLOWED_MARKERS
        if unknown:
            self.unknown.append(
                MarkerIssue(
                    self.filepath,
                    node.lineno,
                    node.name,
                    f"unknown markers: {sorted(unknown)}",
                )
            )

        if "flaky" in markers and ("critical" in markers or "security" in markers):
            self.conflicts.append(
                MarkerIssue(
                    self.filepath,
                    node.lineno,
                    node.name,
                    "flaky cannot be combined with critical/security",
                )
            )

        has_risk = bool(markers & RISK_MARKERS)
        if not has_risk:
            self.unmarked.append(
                MarkerIssue(
                    self.filepath,
                    node.lineno,
                    node.name,
                    "missing risk marker",
                )
            )

    def _get_pytest_markers(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> set[str]:
        """Extract pytest.mark.X decorators from a node with decorator_list."""
        markers = set()

        for decorator in node.decorator_list:
            marker = _extract_marker_name(decorator)
            if marker:
                markers.add(marker)

        return markers


def _extract_marker_name(node: ast.AST) -> str | None:
    """Extract pytest.mark.X name from decorator or marker node."""
    target = None
    if isinstance(node, ast.Attribute):
        target = node
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        target = node.func

    if not target:
        return None

    if (
        isinstance(target.value, ast.Attribute)
        and isinstance(target.value.value, ast.Name)
        and target.value.value.id == "pytest"
        and target.value.attr == "mark"
    ):
        return target.attr

    return None


def _extract_markers_from_node(node: ast.AST) -> set[str]:
    """Extract markers from pytestmark assignments."""
    markers = set()
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            markers |= _extract_markers_from_node(elt)
    else:
        marker = _extract_marker_name(node)
        if marker:
            markers.add(marker)
    return markers


def _module_markers(tree: ast.Module) -> set[str]:
    """Extract module-level pytestmark markers."""
    markers = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            continue
        markers |= _extract_markers_from_node(node.value)
    return markers


def check_file(
    filepath: Path,
) -> tuple[list[MarkerIssue], list[MarkerIssue], list[MarkerIssue]]:
    """Check a single file for marker issues."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except SyntaxError:
        return [], [], []

    module_markers = _module_markers(tree)
    visitor = TestMarkerVisitor(filepath, module_markers)
    visitor.visit(tree)
    return visitor.unmarked, visitor.unknown, visitor.conflicts


def main() -> int:
    strict = "--strict" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--strict"]
    if len(args) < 1:
        print("Usage: python scripts/verify_test_markers.py [--strict] <path>")
        return 1

    path = Path(args[0])
    unmarked: list[MarkerIssue] = []
    unknown: list[MarkerIssue] = []
    conflicts: list[MarkerIssue] = []

    if path.is_file():
        unmarked, unknown, conflicts = check_file(path)
    elif path.is_dir():
        for filepath in path.rglob("test_*.py"):
            file_unmarked, file_unknown, file_conflicts = check_file(filepath)
            unmarked.extend(file_unmarked)
            unknown.extend(file_unknown)
            conflicts.extend(file_conflicts)

    if unknown:
        print(f"Found {len(unknown)} tests with unknown markers:\n")
        for issue in unknown[:20]:
            print(f"  {issue.file}:{issue.line}: {issue.name} ({issue.issue})")

    if conflicts:
        print(f"\nFound {len(conflicts)} tests with marker conflicts:\n")
        for issue in conflicts[:20]:
            print(f"  {issue.file}:{issue.line}: {issue.name} ({issue.issue})")

    if unmarked:
        print(
            f"\nFound {len(unmarked)} tests without risk markers (defaulting to standard):\n"
        )
        for issue in unmarked[:20]:
            print(f"  {issue.file}:{issue.line}: {issue.name} ({issue.issue})")

    if any(len(items) > 20 for items in (unknown, conflicts, unmarked)):
        print("  ... and more")

    if unknown or conflicts or (strict and unmarked):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
