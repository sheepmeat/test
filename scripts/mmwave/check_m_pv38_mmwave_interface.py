#!/usr/bin/env python3
"""SW-01 CLI: non-campaign mmWave interface checker.

Modes:
  --fixture PATH   offline/fixture validation
  --live           live non-campaign probe (no campaign evidence)

Does not load ROLE_L models. Does not create D1 membership.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_sw01_interface_checker import (  # noqa: E402
    STATUS_BACKEND,
    StreamBundle,
    evaluate_stream,
    inventory_serial_ports,
    live_target_unavailable_receipt,
    load_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--fixture", type=Path, help="Fixture JSON path")
    g.add_argument("--live", action="store_true", help="Live non-campaign probe")
    parser.add_argument("--port", type=str, default=None, help="Optional UART port hint")
    parser.add_argument("--out", type=Path, default=None, help="Write receipt JSON")
    args = parser.parse_args()

    if args.fixture:
        bundle = load_fixture(args.fixture)
        receipt = evaluate_stream(
            bundle,
            mode="FIXTURE_OFFLINE_VALIDATION",
            check_source=args.fixture.as_posix(),
        )
        # Fixture mode must never be labeled as live/campaign pass
        assert receipt["mode"] == "FIXTURE_OFFLINE_VALIDATION"
        assert receipt["campaign_data_created"] is False
        assert receipt["d1_admissible"] is False
    else:
        ports = inventory_serial_ports()
        # No UART backend is installed in-repo (see sensors/mmwave/mmwave_adapter.py).
        # Do not import the production UART sensor adapter — it constructs a model interpreter.
        if args.port:
            if args.port not in ports and not Path(args.port).exists():
                receipt = live_target_unavailable_receipt(
                    reason=f"requested_port_not_found:{args.port}",
                    serial_candidates=ports,
                )
            else:
                # Port path exists but real MR60 UART backend is not installed.
                receipt = evaluate_stream(
                    StreamBundle(backend_error="Real MR60BHA2 UART backend is not installed"),
                    mode="LIVE_NON_CAMPAIGN_CHECK",
                    check_source=args.port,
                )
                receipt["overall_status"] = STATUS_BACKEND
                receipt["faults"] = list(dict.fromkeys(receipt["faults"] + ["BACKEND_UNAVAILABLE"]))
        elif not ports:
            receipt = live_target_unavailable_receipt(
                reason="no_candidate_mmwave_serial_port",
                serial_candidates=ports,
            )
        else:
            receipt = live_target_unavailable_receipt(
                reason="candidate_ports_present_but_uart_backend_not_installed",
                serial_candidates=ports,
            )
            receipt["overall_status"] = STATUS_BACKEND

        receipt["mode"] = "LIVE_NON_CAMPAIGN_CHECK"
        receipt["probe_class"] = "NON_CAMPAIGN_INTERFACE_PROBE"
        receipt["campaign_data_created"] = False
        receipt["d1_admissible"] = False
        receipt["campaign_slot_consumed"] = False
        # Recompute hash after live-mode mutations
        receipt.pop("receipt_sha256", None)
        import hashlib as _hashlib
        receipt["receipt_sha256"] = _hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    sys.stdout.write(text)
    # Non-zero only for unexpected internal errors; expected fail-closed statuses still exit 0
    # so CI can collect receipts. Callers inspect overall_status.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
