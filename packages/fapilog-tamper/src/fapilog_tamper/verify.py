"""
Verification API placeholder (Story 4.17).
"""

from __future__ import annotations

from typing import Any, NamedTuple


class VerifyReport(NamedTuple):
    valid: bool
    checked: int
    error: str | None = None


def verify_records(_records: list[dict[str, Any]]) -> VerifyReport:
    """Bootstrap verification stub; will be expanded in later stories."""
    return VerifyReport(valid=True, checked=len(_records))
