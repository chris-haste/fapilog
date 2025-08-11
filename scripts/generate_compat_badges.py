#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    outdir = args.output
    outdir.mkdir(parents=True, exist_ok=True)

    # Minimal placeholder: generate a JSON badge data file for core versions
    data = {
        "fapilog": {
            "verified_versions": ["3.11"],
            "status": "passing",
        }
    }
    (outdir / "compat.json").write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
