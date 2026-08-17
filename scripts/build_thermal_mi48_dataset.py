#!/usr/bin/env python3
"""Build a derived MI48 canonical dataset from an approved capture contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thermal_mi48_device_domain import build_canonical_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--split-map", type=Path)
    parser.add_argument("--derive-p1", action="store_true")
    parser.add_argument("--require-split", action="store_true")
    parser.add_argument("--sample-stride", type=int, default=1)
    args = parser.parse_args()
    result = build_canonical_dataset(
        args.capture_root,
        args.output_root,
        split_map_path=args.split_map,
        derive_p1=args.derive_p1,
        require_split=args.require_split,
        sample_stride=args.sample_stride,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
