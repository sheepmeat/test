#!/usr/bin/env python3
"""SW-01 CLI: non-campaign mmWave interface checker.

Modes:
  --fixture PATH       offline fixture validation (NOT a live source)
  --stream-jsonl PATH  external versioned JSONL through source abstraction
  --stdin-jsonl        same schema via stdin
  --live [--port]      hardware probe (UART parser pluggable / unproven)

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
    MODE_EXTERNAL_STREAM,
    MODE_FIXTURE,
    MODE_LIVE_HARDWARE,
    annotate_receipt,
    evaluate_stream,
    inventory_serial_ports,
    live_target_unavailable_receipt,
    load_fixture,
    run_source_pipeline,
)
from adapters.mmwave_sw01_source import (  # noqa: E402
    BACKEND_JSONL,
    BACKEND_STDIN,
    BACKEND_UART,
    PARSER_UNAVAILABLE,
    TRANSPORT_ABSENT,
    TRANSPORT_NA,
    TRANSPORT_PRESENT,
    UART_PROTOCOL,
    backend_registry,
    open_source,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-backends",
        action="store_true",
        help="Print backend registry and exit",
    )
    g = parser.add_mutually_exclusive_group(required=False)
    g.add_argument("--fixture", type=Path, help="Fixture JSON path (offline only)")
    g.add_argument("--stream-jsonl", type=Path, help="External versioned JSONL source stream")
    g.add_argument("--stdin-jsonl", action="store_true", help="External JSONL on stdin")
    g.add_argument("--live", action="store_true", help="Live hardware non-campaign probe")
    parser.add_argument("--port", type=str, default=None, help="Optional UART port hint for --live")
    parser.add_argument("--out", type=Path, default=None, help="Write receipt JSON")
    args = parser.parse_args()

    if args.list_backends:
        sys.stdout.write(json.dumps(backend_registry(), indent=2) + "\n")
        return 0

    if not any([args.fixture, args.stream_jsonl, args.stdin_jsonl, args.live]):
        parser.error("one of --fixture / --stream-jsonl / --stdin-jsonl / --live is required")

    if args.fixture:
        bundle = load_fixture(args.fixture)
        receipt = evaluate_stream(
            bundle,
            mode=MODE_FIXTURE,
            check_source=args.fixture.as_posix(),
        )
        receipt = annotate_receipt(
            receipt,
            mode=MODE_FIXTURE,
            transport_status=TRANSPORT_NA,
            source_backend_status="FIXTURE",
            parser_status="FIXTURE_LOADER",
            pipeline_semantics={
                "software_pipeline_validated": False,
                "live_hardware_verified": False,
                "note": "Fixture mode is offline validation only",
            },
        )
    elif args.stream_jsonl:
        src = open_source(BACKEND_JSONL, path=args.stream_jsonl)
        receipt = run_source_pipeline(
            src,
            mode=MODE_EXTERNAL_STREAM,
            check_source=args.stream_jsonl.as_posix(),
        )
        receipt = annotate_receipt(
            receipt,
            mode=MODE_EXTERNAL_STREAM,
            transport_status=TRANSPORT_NA,
            pipeline_semantics={
                **(receipt.get("pipeline_semantics") or {}),
                "software_pipeline_validated": receipt.get("overall_status")
                == "PASS_NON_CAMPAIGN_INTERFACE_CHECK",
                "live_hardware_verified": False,
                "live_hardware_not_verified": True,
            },
        )
    elif args.stdin_jsonl:
        src = open_source(BACKEND_STDIN, stdin=sys.stdin)
        receipt = run_source_pipeline(
            src,
            mode=MODE_EXTERNAL_STREAM,
            check_source="stdin",
        )
        receipt = annotate_receipt(
            receipt,
            mode=MODE_EXTERNAL_STREAM,
            transport_status=TRANSPORT_NA,
            pipeline_semantics={
                **(receipt.get("pipeline_semantics") or {}),
                "software_pipeline_validated": receipt.get("overall_status")
                == "PASS_NON_CAMPAIGN_INTERFACE_CHECK",
                "live_hardware_verified": False,
                "live_hardware_not_verified": True,
            },
        )
    else:
        ports = inventory_serial_ports()
        if args.port:
            port_exists = args.port in ports or Path(args.port).exists()
            if not port_exists:
                receipt = live_target_unavailable_receipt(
                    reason=f"requested_port_not_found:{args.port}",
                    serial_candidates=ports,
                )
                receipt = annotate_receipt(
                    receipt,
                    mode=MODE_LIVE_HARDWARE,
                    transport_status=TRANSPORT_ABSENT,
                    source_backend_status=UART_PROTOCOL,
                    parser_status=PARSER_UNAVAILABLE,
                    pipeline_semantics={
                        "software_pipeline_validated": False,
                        "live_hardware_verified": False,
                    },
                )
            else:
                src = open_source(BACKEND_UART, port=args.port)
                receipt = run_source_pipeline(
                    src,
                    mode=MODE_LIVE_HARDWARE,
                    check_source=args.port,
                )
                receipt = annotate_receipt(
                    receipt,
                    mode=MODE_LIVE_HARDWARE,
                    transport_status=TRANSPORT_PRESENT,
                    source_backend_status=UART_PROTOCOL,
                    parser_status=PARSER_UNAVAILABLE,
                    pipeline_semantics={
                        "software_pipeline_validated": False,
                        "live_hardware_verified": False,
                        "serial_transport_present": True,
                        "parser_backend_unavailable": True,
                    },
                )
        elif not ports:
            receipt = live_target_unavailable_receipt(
                reason="no_candidate_mmwave_serial_port",
                serial_candidates=ports,
            )
            receipt = annotate_receipt(
                receipt,
                mode=MODE_LIVE_HARDWARE,
                transport_status=TRANSPORT_ABSENT,
                source_backend_status=UART_PROTOCOL,
                parser_status=PARSER_UNAVAILABLE,
                pipeline_semantics={
                    "software_pipeline_validated": False,
                    "live_hardware_verified": False,
                },
            )
        else:
            receipt = live_target_unavailable_receipt(
                reason="candidate_ports_present_but_uart_parser_unproven",
                serial_candidates=ports,
            )
            receipt = annotate_receipt(
                receipt,
                mode=MODE_LIVE_HARDWARE,
                transport_status=TRANSPORT_PRESENT,
                source_backend_status=UART_PROTOCOL,
                parser_status=PARSER_UNAVAILABLE,
                pipeline_semantics={
                    "software_pipeline_validated": False,
                    "live_hardware_verified": False,
                    "serial_transport_present": True,
                    "parser_backend_unavailable": True,
                },
            )

    receipt["campaign_data_created"] = False
    receipt["d1_admissible"] = False
    receipt["campaign_slot_consumed"] = False
    receipt["model_inference"] = False
    receipt["role_l_loaded"] = False
    receipt = annotate_receipt(receipt)

    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
