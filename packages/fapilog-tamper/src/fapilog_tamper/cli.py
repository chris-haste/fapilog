"""
CLI entry point for fapilog-tamper.
"""

from __future__ import annotations

from .verify import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
