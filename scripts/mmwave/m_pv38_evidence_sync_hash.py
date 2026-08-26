#!/usr/bin/env python3
"""Deterministic SW-03 synchronization records and SHA-256 receipts.

This module deliberately records evidence plumbing only.  It does not acquire
sensor data, infer physiology, authorize a campaign, or construct D1
membership.  The two synchronization methods here mirror the locked M-N10
clock policy: a shared host clock or an explicit marker observed on both
timelines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/MMWAVE_V2_D1_sw03_sw04_evidence_tooling_01"

SUPPORTED_SYNC_METHODS = {"SHARED_CLOCK", "EXPLICIT_SYNC_MARKER"}
SUPPORTED_EVIDENCE_TYPES = {
    "SENSOR_OBSERVATION",
    "OCCUPANCY_REFERENCE",
    "ACCESS_CONTROL_EVIDENCE",
    "SENSOR_HEALTH",
    "TIMING_ALIGNMENT",
    "RECORDING_PROVENANCE",
    "REJECTION_EVIDENCE",
}
FIXTURE_SEMANTICS = [
    "FIXTURE_ONLY",
    "NON_CAMPAIGN",
    "NOT_D1_MEMBERSHIP",
    "NOT_DATASET_ADMISSIBLE",
]
FORBIDDEN_TIMING_KEYS = {
    "tolerance_ms",
    "timing_tolerance_ms",
    "max_allowed_clock_error_ms",
    "maximum_allowed_clock_error_ms",
    "pass_threshold_ms",
    "alignment_pass_threshold_ms",
    "max_clock_error_ms",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_portable_reference(value: Any) -> bool:
    """Return whether a persisted reference is repository-portable."""

    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    if value.startswith(("/", "file://", "\\\\")):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return False
    parts = value.replace("\\", "/").split("/")
    return ".." not in parts


def find_absolute_paths(value: Any, location: str = "root") -> list[str]:
    """Find non-portable absolute or local-file references in a value."""

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(find_absolute_paths(child, f"{location}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(find_absolute_paths(child, f"{location}[{index}]"))
    elif isinstance(value, str) and not _is_portable_reference(value):
        found.append(location)
    return found


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 digest for bytes."""

    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_fixture_semantics(record: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    semantics = record.get("fixture_semantics")
    if semantics != FIXTURE_SEMANTICS:
        errors.append(f"{label}: fixture_semantics must be exactly {FIXTURE_SEMANTICS}")
    return errors


def _find_forbidden_keys(value: Any, location: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_TIMING_KEYS:
                found.append(f"{location}.{key}")
            found.extend(_find_forbidden_keys(child, f"{location}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_keys(child, f"{location}[{index}]"))
    return found


def create_hash_receipt(
    evidence_id: str,
    evidence_type: str,
    source_identity: str,
    reference_identity: str,
    *,
    payload: bytes | None = None,
    digest: str | None = None,
    file_reference: str | None = None,
    size_bytes: int | None = None,
    time_coverage: Mapping[str, Any] | None = None,
    fixture_semantics: Sequence[str] = FIXTURE_SEMANTICS,
) -> dict[str, Any]:
    """Create an immutable SHA-256 receipt.

    ``payload`` is accepted for deterministic tests and synthetic fixtures;
    callers handling sensitive evidence can supply only its digest and a
    portable reference.  The receipt never contains the payload.
    """

    if not evidence_id or not isinstance(evidence_id, str):
        raise ValueError("evidence_id must be a non-empty string")
    if evidence_type not in SUPPORTED_EVIDENCE_TYPES:
        raise ValueError(f"unsupported evidence_type: {evidence_type}")
    if not source_identity or not reference_identity:
        raise ValueError("source_identity and reference_identity are required")
    if file_reference is not None and not _is_portable_reference(file_reference):
        raise ValueError("file_reference must be repository-portable")
    if payload is not None:
        computed = sha256_bytes(payload)
        if digest is not None and digest != computed:
            raise ValueError("provided digest does not match payload")
        digest = computed
    if digest is None or not SHA256_RE.fullmatch(digest):
        raise ValueError("digest must be a lowercase 64-character SHA-256 value")
    if size_bytes is not None and (not isinstance(size_bytes, int) or size_bytes < 0):
        raise ValueError("size_bytes must be a non-negative integer")
    if list(fixture_semantics) != FIXTURE_SEMANTICS:
        raise ValueError("fixture_semantics must identify this as a non-campaign fixture")

    receipt: dict[str, Any] = {
        "schema_version": "MMWAVE-V2-D1-SW03-HASH-RECEIPT-V1",
        "evidence_id": evidence_id,
        "immutable_evidence_id": evidence_id,
        "identifier_semantics": "IMMUTABLE",
        "evidence_type": evidence_type,
        "source_identity": source_identity,
        "reference_identity": reference_identity,
        "hash_algorithm": "SHA-256",
        "sha256": digest,
        "fixture_semantics": list(fixture_semantics),
    }
    if file_reference is not None:
        receipt["file_reference"] = file_reference
    if size_bytes is not None:
        receipt["size_bytes"] = size_bytes
    if time_coverage is not None:
        receipt["time_coverage"] = dict(time_coverage)
    return receipt


def verify_hash_receipt(
    receipt: Mapping[str, Any],
    *,
    payload: bytes | None = None,
    actual_sha256: str | None = None,
) -> bool:
    """Verify a receipt against bytes or an independently computed digest."""

    expected = receipt.get("sha256")
    if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
        return False
    if payload is not None:
        actual_sha256 = sha256_bytes(payload)
    if actual_sha256 is None or SHA256_RE.fullmatch(actual_sha256) is None:
        return False
    return actual_sha256 == expected


def validate_hash_receipt(receipt: Mapping[str, Any], label: str = "receipt") -> list[str]:
    """Validate one receipt without accessing the referenced payload."""

    errors: list[str] = []
    required = (
        "schema_version",
        "evidence_id",
        "immutable_evidence_id",
        "identifier_semantics",
        "evidence_type",
        "source_identity",
        "reference_identity",
        "hash_algorithm",
        "sha256",
        "fixture_semantics",
    )
    if not isinstance(receipt, Mapping):
        return [f"{label}: record must be an object"]
    for key in required:
        if key not in receipt:
            errors.append(f"{label}: missing {key}")
    if receipt.get("schema_version") != "MMWAVE-V2-D1-SW03-HASH-RECEIPT-V1":
        errors.append(f"{label}: unsupported schema_version")
    evidence_id = receipt.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        errors.append(f"{label}: evidence_id must be non-empty")
    if receipt.get("immutable_evidence_id") != evidence_id:
        errors.append(f"{label}: immutable_evidence_id must equal evidence_id")
    if receipt.get("identifier_semantics") != "IMMUTABLE":
        errors.append(f"{label}: identifier_semantics must be IMMUTABLE")
    if receipt.get("evidence_type") not in SUPPORTED_EVIDENCE_TYPES:
        errors.append(f"{label}: unsupported evidence_type")
    for key in ("source_identity", "reference_identity"):
        if not isinstance(receipt.get(key), str) or not receipt.get(key):
            errors.append(f"{label}: {key} must be non-empty")
    if receipt.get("hash_algorithm") != "SHA-256":
        errors.append(f"{label}: hash_algorithm must be SHA-256")
    if not isinstance(receipt.get("sha256"), str) or SHA256_RE.fullmatch(receipt.get("sha256", "")) is None:
        errors.append(f"{label}: sha256 is malformed")
    if "file_reference" in receipt and not _is_portable_reference(receipt["file_reference"]):
        errors.append(f"{label}: file_reference is not portable")
    if "size_bytes" in receipt and (not isinstance(receipt["size_bytes"], int) or receipt["size_bytes"] < 0):
        errors.append(f"{label}: size_bytes is invalid")
    errors.extend(_require_fixture_semantics(receipt, label))
    errors.extend(f"{label}: forbidden timing key at {path}" for path in _find_forbidden_keys(receipt))
    errors.extend(f"{label}: absolute/local path at {path}" for path in find_absolute_paths(receipt))
    return errors


def validate_hash_receipts(
    receipts: Sequence[Mapping[str, Any]],
    *,
    actual_digests: Mapping[str, str] | None = None,
) -> list[str]:
    """Validate receipts, duplicate immutable IDs, and optional verification."""

    errors: list[str] = []
    seen: set[str] = set()
    actual_digests = actual_digests or {}
    for index, receipt in enumerate(receipts):
        label = f"hash_receipts[{index}]"
        errors.extend(validate_hash_receipt(receipt, label))
        evidence_id = receipt.get("evidence_id") if isinstance(receipt, Mapping) else None
        if isinstance(evidence_id, str):
            if evidence_id in seen:
                errors.append(f"{label}: duplicate immutable evidence_id {evidence_id}")
            seen.add(evidence_id)
            if evidence_id in actual_digests and not verify_hash_receipt(receipt, actual_sha256=actual_digests[evidence_id]):
                errors.append(f"{label}: hash mismatch for {evidence_id}")
    unknown_actuals = sorted(set(actual_digests) - seen)
    errors.extend(f"actual digest supplied for unknown evidence_id {evidence_id}" for evidence_id in unknown_actuals)
    return errors


def validate_sync_record(record: Mapping[str, Any], label: str = "sync_record") -> list[str]:
    """Validate one shared-clock or explicit-marker synchronization record."""

    errors: list[str] = []
    if not isinstance(record, Mapping):
        return [f"{label}: record must be an object"]
    required = (
        "schema_version",
        "sync_record_id",
        "method",
        "source_identity",
        "clock_identity",
        "source_timestamp",
        "alignment_method",
        "measured_offset_delta_ms",
        "alignment_status",
        "validation_status",
        "threshold_status",
        "live_evidence_status",
        "fixture_semantics",
    )
    errors.extend(f"{label}: missing {key}" for key in required if key not in record)
    if record.get("schema_version") != "MMWAVE-V2-D1-SW03-SYNC-RECORD-V1":
        errors.append(f"{label}: unsupported schema_version")
    if not isinstance(record.get("sync_record_id"), str) or not record.get("sync_record_id"):
        errors.append(f"{label}: sync_record_id must be non-empty")
    method = record.get("method")
    if method not in SUPPORTED_SYNC_METHODS:
        errors.append(f"{label}: method must be SHARED_CLOCK or EXPLICIT_SYNC_MARKER")
    for key in ("source_identity", "clock_identity", "source_timestamp", "alignment_method"):
        if not isinstance(record.get(key), str) or not record.get(key):
            errors.append(f"{label}: {key} must be non-empty")
    if not isinstance(record.get("measured_offset_delta_ms"), (int, float)) or isinstance(record.get("measured_offset_delta_ms"), bool):
        errors.append(f"{label}: measured_offset_delta_ms must be numeric")
    if "uncertainty_ms" in record and (not isinstance(record["uncertainty_ms"], (int, float)) or isinstance(record["uncertainty_ms"], bool) or record["uncertainty_ms"] < 0):
        errors.append(f"{label}: uncertainty_ms must be a non-negative number")
    if record.get("alignment_status") != "ALIGNMENT_MEASURABLE":
        errors.append(f"{label}: alignment_status must be ALIGNMENT_MEASURABLE")
    if record.get("validation_status") not in {"FIXTURE_ONLY_ALIGNMENT_RECORDED", "ALIGNMENT_MEASURABLE"}:
        errors.append(f"{label}: validation_status must not claim live PASS")
    if record.get("threshold_status") != "THRESHOLD_NOT_GOVERNED":
        errors.append(f"{label}: threshold_status must be THRESHOLD_NOT_GOVERNED")
    if record.get("live_evidence_status") != "NOT_LIVE_EVIDENCE":
        errors.append(f"{label}: fixture sync cannot be live evidence")
    errors.extend(_require_fixture_semantics(record, label))
    if method == "SHARED_CLOCK":
        if record.get("sync_marker_id") is not None:
            errors.append(f"{label}: SHARED_CLOCK must not carry a sync marker")
        if record.get("host_timestamp") is not None and not isinstance(record.get("host_timestamp"), str):
            errors.append(f"{label}: host_timestamp must be a string when present")
    if method == "EXPLICIT_SYNC_MARKER":
        if not isinstance(record.get("sync_marker_id"), str) or not record.get("sync_marker_id"):
            errors.append(f"{label}: explicit marker method requires sync_marker_id")
        if record.get("host_timestamp") is None or not isinstance(record.get("host_timestamp"), str):
            errors.append(f"{label}: explicit marker method requires host_timestamp")
        if record.get("source_marker_observed") is not True or record.get("host_marker_observed") is not True:
            errors.append(f"{label}: explicit marker must be observed on both timelines")
    errors.extend(f"{label}: forbidden timing key at {path}" for path in _find_forbidden_keys(record))
    errors.extend(f"{label}: absolute/local path at {path}" for path in find_absolute_paths(record))
    return errors


def validate_sync_records(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Validate sync records and reject duplicate immutable record IDs."""

    errors: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        label = f"sync_records[{index}]"
        errors.extend(validate_sync_record(record, label))
        record_id = record.get("sync_record_id") if isinstance(record, Mapping) else None
        if isinstance(record_id, str):
            if record_id in seen:
                errors.append(f"{label}: duplicate sync_record_id {record_id}")
            seen.add(record_id)
    return errors


def sync_record_schema_document() -> dict[str, Any]:
    """Return the versioned machine-readable SW-03 sync schema."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "MMWAVE-V2-D1-SW03-SYNC-RECORD-V1",
        "title": "SafeNest mmWave V2 SW-03 synchronization record",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "sync_record_id",
            "method",
            "source_identity",
            "clock_identity",
            "source_timestamp",
            "alignment_method",
            "measured_offset_delta_ms",
            "alignment_status",
            "validation_status",
            "threshold_status",
            "live_evidence_status",
            "fixture_semantics",
        ],
        "properties": {
            "schema_version": {"const": "MMWAVE-V2-D1-SW03-SYNC-RECORD-V1"},
            "sync_record_id": {"type": "string", "minLength": 1},
            "method": {"enum": sorted(SUPPORTED_SYNC_METHODS)},
            "source_identity": {"type": "string", "minLength": 1},
            "clock_identity": {"type": "string", "minLength": 1},
            "source_timestamp": {"type": "string", "minLength": 1},
            "host_timestamp": {"type": ["string", "null"]},
            "sync_marker_id": {"type": ["string", "null"]},
            "source_marker_observed": {"type": "boolean"},
            "host_marker_observed": {"type": "boolean"},
            "alignment_method": {"type": "string", "minLength": 1},
            "measured_offset_delta_ms": {"type": "number"},
            "uncertainty_ms": {"type": "number", "minimum": 0},
            "alignment_status": {"const": "ALIGNMENT_MEASURABLE"},
            "validation_status": {"enum": ["FIXTURE_ONLY_ALIGNMENT_RECORDED", "ALIGNMENT_MEASURABLE"]},
            "threshold_status": {"const": "THRESHOLD_NOT_GOVERNED"},
            "live_evidence_status": {"const": "NOT_LIVE_EVIDENCE"},
            "fixture_semantics": {"type": "array", "const": FIXTURE_SEMANTICS},
        },
    }


def hash_receipt_schema_document() -> dict[str, Any]:
    """Return the versioned machine-readable SW-03 hash receipt schema."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "MMWAVE-V2-D1-SW03-HASH-RECEIPT-V1",
        "title": "SafeNest mmWave V2 SW-03 immutable SHA-256 evidence receipt",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "evidence_id",
            "immutable_evidence_id",
            "identifier_semantics",
            "evidence_type",
            "source_identity",
            "reference_identity",
            "hash_algorithm",
            "sha256",
            "fixture_semantics",
        ],
        "properties": {
            "schema_version": {"const": "MMWAVE-V2-D1-SW03-HASH-RECEIPT-V1"},
            "evidence_id": {"type": "string", "minLength": 1},
            "immutable_evidence_id": {"type": "string", "minLength": 1},
            "identifier_semantics": {"const": "IMMUTABLE"},
            "evidence_type": {"enum": sorted(SUPPORTED_EVIDENCE_TYPES)},
            "source_identity": {"type": "string", "minLength": 1},
            "reference_identity": {"type": "string", "minLength": 1},
            "file_reference": {"type": "string", "minLength": 1},
            "hash_algorithm": {"const": "SHA-256"},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "size_bytes": {"type": "integer", "minimum": 0},
            "time_coverage": {"type": "object"},
            "fixture_semantics": {"type": "array", "const": FIXTURE_SEMANTICS},
        },
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest_directory(manifest_dir: Path = DEFAULT_MANIFEST_DIR) -> dict[str, Any]:
    """Validate the SW-03 files in a manifest directory."""

    sync_path = manifest_dir / "sync_records.json"
    hash_path = manifest_dir / "hash_receipts.json"
    missing = [path.name for path in (sync_path, hash_path) if not path.is_file()]
    if missing:
        return {"ok": False, "failed_checks": ["required_sync_hash_artifacts_present"], "errors": missing}
    try:
        sync_records = _read_json(sync_path)["records"]
        hash_receipts = _read_json(hash_path)["receipts"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"ok": False, "failed_checks": ["sync_hash_json_shape"], "errors": [str(exc)]}
    errors = validate_sync_records(sync_records)
    errors.extend(validate_hash_receipts(hash_receipts))
    return {
        "ok": not errors,
        "failed_checks": [] if not errors else ["sync_hash_semantics"],
        "errors": errors,
        "sync_record_count": len(sync_records),
        "hash_receipt_count": len(hash_receipts),
    }


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="validate sync records and hash receipts")
    validate_parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    args = parser.parse_args(argv)
    if args.command == "validate":
        result = validate_manifest_directory(args.manifest_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
