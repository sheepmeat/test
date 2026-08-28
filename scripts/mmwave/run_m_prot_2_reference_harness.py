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
    GOVERNED_FIXTURE_DIR_REL,
    PrototypeFailClosed,
    capture_runtime_environment,
    resolve_fixture_document,
    run_prototype_inference,
    valid_fixture_from_scaler,
    verify_scaler,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="JSON fixture or overlay (base+overrides)")
    parser.add_argument("--positive-path", action="store_true", help="run the built-in valid synthetic fixture")
    parser.add_argument("--output", type=Path, help="write inference receipt JSON")
    parser.add_argument(
        "--include-environment",
        action="store_true",
        help="embed reference runtime environment in the receipt output",
    )
    args = parser.parse_args()
    # Authoritative path always verifies scaler + B23 identities internally.
    try:
        if args.positive_path:
            scaler = verify_scaler(ROOT)
            fixture = valid_fixture_from_scaler(scaler)
        elif args.fixture is not None:
            fixture_root = (ROOT / GOVERNED_FIXTURE_DIR_REL).resolve()
            fixture = resolve_fixture_document(args.fixture, fixture_root=fixture_root)
        else:
            parser.error("provide --fixture or --positive-path")
            return 2
    except PrototypeFailClosed as exc:
        payload = {
            "schema_version": "M-PROT-2-INFERENCE-RECEIPT-V1",
            "status": "UNAVAILABLE",
            "fail_closed_code": exc.code,
            "detail": exc.message,
            "PROTOTYPE_INTEGRATION_ONLY": True,
            "FINAL_GOVERNED_EVALUATION": False,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 0

    receipt = run_prototype_inference(
        fixture,
        root=ROOT,
        lineage_class=fixture.get("lineage_class", "FIXTURE_NON_CAMPAIGN"),
    )
    payload = receipt.to_json()
    if args.include_environment or args.positive_path:
        payload["reference_environment"] = capture_runtime_environment()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
