"""Fail CI if Settings/fields are missing good descriptions.

Checks all Pydantic BaseModel fields reachable from Settings for:
- Non-empty description
- Minimum description length (configurable)

Exit code 1 when violations are found.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from pydantic import BaseModel

from fapilog.core.settings import Settings


def iter_models(model: BaseModel) -> Iterable[BaseModel]:
    yield model
    for field_name, _unused_field in type(model).model_fields.items():
        value = getattr(model, field_name, None)
        if isinstance(value, BaseModel):
            yield from iter_models(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-length", type=int, default=15)
    args = parser.parse_args()

    cfg = Settings()
    failures: list[str] = []

    for m in iter_models(cfg):
        model_name = type(m).__name__
        for field_name, field in type(m).model_fields.items():
            desc = getattr(field, "description", None) or ""
            if not desc or len(desc.strip()) < args.min_length:
                failures.append(f"{model_name}.{field_name}: missing/short description")

    if failures:
        print(
            "Missing or too-short descriptions (set via Field(..., description=...)):"
        )
        for f in failures:
            print(f" - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
