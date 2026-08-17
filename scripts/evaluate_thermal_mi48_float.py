#!/usr/bin/env python3
"""Evaluate the frozen Float TFLite artifact on a future labelled MI48 build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thermal_mi48_device_domain import evaluate_float_tflite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--expected-sha256", default=None)
    args = parser.parse_args()
    kwargs = {} if args.expected_sha256 is None else {"expected_sha256": args.expected_sha256}
    result = evaluate_float_tflite(args.dataset_root, args.model_path, **kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
