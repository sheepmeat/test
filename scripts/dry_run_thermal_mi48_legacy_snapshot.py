#!/usr/bin/env python3
"""Inspect the legacy RP-X0 snapshot without copying or evaluating it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thermal_mi48_device_domain import dry_run_legacy_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(dry_run_legacy_snapshot(args.snapshot_root), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
