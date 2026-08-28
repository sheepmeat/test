#!/usr/bin/env python3
"""Validate the checked-in SW-02 fixture evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.mmwave.m_pv38_absent_artifact_generator import (
    ArtifactValidationError,
    ROOT_DIR,
    validate_fixture_bundle,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=ROOT_DIR / "datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01",
    )
    args = parser.parse_args(argv)
    try:
        result = validate_fixture_bundle(root=ROOT_DIR, manifest_dir=args.manifest_dir)
    except ArtifactValidationError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "detail": exc.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
