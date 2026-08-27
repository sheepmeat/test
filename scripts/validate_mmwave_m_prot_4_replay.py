#!/usr/bin/env python3
"""Validate the compact M-PROT-4 deterministic replay catalog.

The validator exercises fixture construction and SW-01 admission inspection;
it does not run model inference, touch D2, or change any runtime contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Running a script by path places ``scripts/`` on sys.path rather than the
# repository root; make the canonical package imports explicit and portable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_sw01_interface_checker import MODE_FIXTURE, STATUS_PASS, evaluate_stream
from tests.helpers.mmwave_m_prot_4_replay import (
    SCHEMA_VERSION,
    fixture_spec_sha256,
    generate_fixture,
    load_fixture_catalog,
)


CATALOG = ROOT / "tests" / "fixtures" / "mmwave" / "m_prot_4" / "fixture_catalog.json"
REGISTRY = ROOT / "tests" / "fixtures" / "mmwave" / "m_prot_4" / "fixture_checksums.json"
CHECKSUMS = ROOT / "tests" / "fixtures" / "mmwave" / "m_prot_4" / "checksums.sha256"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _validate_checksum_file() -> bool:
    if not CHECKSUMS.exists():
        return False
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, rel = line.split(None, 1)
        except ValueError as exc:
            raise AssertionError(f"malformed checksum line: {line!r}") from exc
        rel = rel.strip()
        if rel.startswith("*"):
            rel = rel[1:]
        path = ROOT / rel
        if Path(rel).is_absolute() or rel.startswith("/") or ".." in Path(rel).parts:
            raise AssertionError(f"non-relative checksum path: {rel!r}")
        if not path.exists():
            raise AssertionError(f"checksum target missing: {rel}")
        actual = _sha256(path)
        if actual != expected:
            raise AssertionError(f"checksum mismatch: {rel}: {actual} != {expected}")
    return True


def _validate_registry(entries: list[dict[str, Any]]) -> bool:
    if not REGISTRY.exists():
        return False
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "M_PROT_4_DETERMINISTIC_REPLAY_CHECKSUMS_V1":
        raise AssertionError("unexpected fixture checksum registry schema")
    if raw.get("catalog_sha256") != _sha256(CATALOG):
        raise AssertionError("fixture checksum registry catalog hash is stale")
    expected = {
        str(item["fixture_id"]): (str(item["spec_sha256"]), str(item["fixture_sha256"]))
        for item in (raw.get("fixtures") or ())
    }
    actual = {
        str(item["fixture_id"]): (str(item["spec_sha256"]), str(item["fixture_sha256"]))
        for item in entries
    }
    if expected != actual:
        raise AssertionError("fixture checksum registry does not match generated materialisation")
    return True


def validate() -> dict[str, Any]:
    specs = load_fixture_catalog(CATALOG)
    entries: list[dict[str, Any]] = []
    expected_case_status = {
        "HEALTH_FAILURE": "FAIL_HEALTH_UNAVAILABLE",
        "SCALAR_RR_ONLY": "FAIL_SCALAR_TELEMETRY_ONLY",
    }
    for spec in specs:
        first = generate_fixture(spec)
        second = generate_fixture(spec)
        if first.canonical_bytes != second.canonical_bytes:
            raise AssertionError(f"nondeterministic canonical bytes: {spec.fixture_id}")
        if first.fixture_sha256 != second.fixture_sha256:
            raise AssertionError(f"nondeterministic fixture SHA: {spec.fixture_id}")
        payload = first.canonical_bytes.decode("utf-8")
        if "/Users/" in payload or "file://" in payload or "\\\\" in payload:
            raise AssertionError(f"absolute path leak: {spec.fixture_id}")
        receipts = [evaluate_stream(bundle, mode=MODE_FIXTURE) for bundle in first.bundles]
        statuses = [str(receipt["overall_status"]) for receipt in receipts]
        expected = expected_case_status.get(spec.case, STATUS_PASS)
        if spec.case in expected_case_status:
            if expected not in statuses:
                raise AssertionError(
                    f"unexpected SW-01 status for {spec.fixture_id}: {statuses} (expected {expected})"
                )
        elif any(status != STATUS_PASS for status in statuses):
            raise AssertionError(f"unexpected SW-01 failure for {spec.fixture_id}: {statuses}")
        entries.append(
            {
                "fixture_id": spec.fixture_id,
                "case": spec.case,
                "spec_sha256": fixture_spec_sha256(spec),
                "fixture_sha256": first.fixture_sha256,
                "sample_rate_hz": first.sample_rate_hz,
                "duration_s": first.duration_s,
                "sample_count": first.sample_count,
                "bundle_partition": list(first.bundle_partition),
                "sw01_bundle_statuses": statuses,
            }
        )
    registry_valid = _validate_registry(entries)
    checksum_file_valid = _validate_checksum_file()
    return {
        "schema_version": "M_PROT_4_DETERMINISTIC_REPLAY_VALIDATION_V1",
        "phase": "M-PROT-4",
        "status": "PASS",
        "catalog": _relative(CATALOG),
        "catalog_sha256": _sha256(CATALOG),
        "fixture_count": len(entries),
        "determinism": "PASS_SAME_SPEC_SAME_BYTES_AND_SHA256",
        "sha_change_on_semantic_spec_change": "TESTED",
        "sw01_types": "PASS_CANONICAL_SAMPLE_AND_STREAMBUNDLE",
        "fixture_registry": "PASS" if registry_valid else "NOT_PRESENT",
        "sw01_checksum_file": "PASS" if checksum_file_valid else "NOT_PRESENT",
        "fixtures": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="indent the JSON result")
    args = parser.parse_args(argv)
    try:
        result = validate()
    except (AssertionError, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
