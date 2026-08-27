#!/usr/bin/env python3
"""Standalone M-PROT-2 B23 reference harness. Not the integrated application runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_m_prot_2_b23_runtime import (  # noqa: E402
    run_prototype_inference,
    valid_fixture_from_scaler,
    verify_scaler,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="JSON fixture with trace/mask/scale/quality")
    parser.add_argument("--positive-path", action="store_true", help="run the built-in valid synthetic fixture")
    parser.add_argument("--output", type=Path, help="write inference receipt JSON")
    args = parser.parse_args()
    # Authoritative path always verifies scaler + B23 identities internally.
    if args.positive_path:
        scaler = verify_scaler(ROOT)
        fixture = valid_fixture_from_scaler(scaler)
    elif args.fixture is not None:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    else:
        parser.error("provide --fixture or --positive-path")
        return 2
    receipt = run_prototype_inference(
        fixture,
        root=ROOT,
        lineage_class=fixture.get("lineage_class", "FIXTURE_NON_CAMPAIGN"),
    )
    payload = receipt.to_json()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
