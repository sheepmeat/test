#!/usr/bin/env python3
"""Compare a historical Thermal domain with a future MI48 domain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thermal_mi48_device_domain import compare_domains


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historical", type=Path)
    parser.add_argument("mi48", type=Path)
    parser.add_argument("--historical-key")
    parser.add_argument("--mi48-key")
    args = parser.parse_args()
    result = compare_domains(args.historical, args.mi48, historical_key=args.historical_key, mi48_key=args.mi48_key)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
