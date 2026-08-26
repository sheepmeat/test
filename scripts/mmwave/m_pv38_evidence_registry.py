#!/usr/bin/env python3
"""SW-04 evidence registries and the fixture-only SW-03/SW-04 validator.

The bundle produced by this module is intentionally non-campaign evidence
plumbing.  Recording provenance, occupancy evidence, sensor health, timing,
and rejection are separate channels.  No registry entry is a D1 membership
entry and no field is a physiological label derived from sensor quality.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave.m_pv38_evidence_sync_hash import (  # noqa: E402
    DEFAULT_MANIFEST_DIR,
    FIXTURE_SEMANTICS,
    create_hash_receipt,
    find_absolute_paths,
    hash_receipt_schema_document,
    sha256_bytes,
    sha256_file,
    sync_record_schema_document,
    validate_hash_receipts,
    validate_sync_records,
    verify_hash_receipt,
)


MANIFEST_ID = "MMWAVE_V2_D1_SW03_SW04_EVIDENCE_TOOLING_V1"
BASE_SHA = "13a56b7e41e9519ad61238a74861ef4ad6ea16ab"
TERMINAL_VERDICTS = {
    "SW03_SW04_IMPLEMENTED_FIXTURE_VALIDATED",
    "SW03_SW04_CORRECTIVE_REQUIRED",
    "SW03_SW04_BLOCKED_CONTRACT_AMBIGUITY",
}
PASS_VERDICT = "SW03_SW04_IMPLEMENTED_FIXTURE_VALIDATED"
CANONICAL_D1_STATE = "datasets/mmwave/manifests/MMWAVE_V2_post_pubabs_critical_path/critical_path_state.json"
CANONICAL_D1_SNAPSHOT = "datasets/mmwave/manifests/MMWAVE_V2_D1_physical_resource_recovery_01/d1_membership_unchanged.json"
CANONICAL_LIFECYCLE_STATE = "datasets/mmwave/manifests/M-PV3_8_lifecycle_closure/lifecycle_closure_state.json"

SCHEMA_FILES = {
    "sync": "schemas/sync_record_schema.json",
    "hash": "schemas/hash_receipt_schema.json",
    "provenance": "schemas/recording_provenance_registry_schema.json",
    "occupancy": "schemas/occupancy_evidence_registry_schema.json",
    "health": "schemas/sensor_health_registry_schema.json",
    "rejection": "schemas/rejection_registry_schema.json",
}
REGISTRY_FILES = {
    "provenance": "recording_provenance_registry.json",
    "occupancy": "occupancy_evidence_registry.json",
    "health": "sensor_health_registry.json",
    "rejection": "rejection_registry.json",
}
FIXTURE_FILES = {
    "valid_sync": "fixtures/valid_synchronized_evidence_set.json",
    "explicit_marker": "fixtures/explicit_sync_marker_evidence_set.json",
    "hash_verification": "fixtures/hash_verification.json",
    "health_fault": "fixtures/sensor_health_fault.json",
    "occupancy_missing": "fixtures/occupancy_evidence_missing.json",
    "rejection_retained": "fixtures/rejected_observation_retained.json",
    "duplicate_id": "fixtures/duplicate_evidence_id_rejected.json",
    "hash_mismatch": "fixtures/hash_mismatch_rejected.json",
}
CORE_FILES = (
    "bundle_metadata.json",
    "sync_records.json",
    "hash_receipts.json",
    *SCHEMA_FILES.values(),
    *REGISTRY_FILES.values(),
    *FIXTURE_FILES.values(),
)
FINAL_FILES = (*CORE_FILES, "validation_result.json", "checksums.json", "checksums.sha256")

REGISTRY_SCHEMA_VERSIONS = {
    "provenance": "MMWAVE-V2-D1-SW04-RECORDING-PROVENANCE-REGISTRY-V1",
    "occupancy": "MMWAVE-V2-D1-SW04-OCCUPANCY-EVIDENCE-REGISTRY-V1",
    "health": "MMWAVE-V2-D1-SW04-SENSOR-HEALTH-REGISTRY-V1",
    "rejection": "MMWAVE-V2-D1-SW04-REJECTION-REGISTRY-V1",
}
REGISTRY_REQUIRED_FIELDS = {
    "provenance": (
        "schema_version",
        "registry_record_id",
        "recording_identity",
        "sensor_identity",
        "configuration_identity",
        "placement_zone",
        "evidence_references",
        "time_coverage",
        "health_registry_record_id",
        "acceptance_state",
        "fixture_semantics",
    ),
    "occupancy": (
        "schema_version",
        "registry_record_id",
        "authoritative_occupancy_reference",
        "target_zone_coverage",
        "no_human_evidence_reference",
        "sealed_access_evidence_reference",
        "time_interval",
        "sync_evidence_ids",
        "hash_receipt_ids",
        "occupancy_state",
        "review_status",
        "absent_eligibility",
        "physiology_label",
        "fixture_semantics",
    ),
    "health": (
        "schema_version",
        "registry_record_id",
        "sensor_identity",
        "device_connected",
        "stream_valid",
        "timestamp_valid",
        "continuity_status",
        "reported_device_health",
        "reset_restart_observed",
        "fault_code",
        "evidence_ids",
        "health_state",
        "physiology_interpretation",
        "review_status",
        "fixture_semantics",
    ),
    "rejection": (
        "schema_version",
        "rejection_record_id",
        "immutable_candidate_recording_reference",
        "reason_code",
        "reason_detail",
        "evidence_references",
        "time_coverage",
        "decision_source",
        "retained",
        "acceptance_state",
        "eligible_for_absent",
        "physiology_label",
        "fixture_semantics",
    ),
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _portable_reference(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    if value.startswith(("/", "file://", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return False
    return ".." not in value.replace("\\", "/").split("/")


def _fixture_semantics() -> list[str]:
    return list(FIXTURE_SEMANTICS)


def _time_coverage(start: str = "2026-08-27T00:00:00Z", end: str = "2026-08-27T00:00:15Z") -> dict[str, str]:
    return {"start": start, "end": end, "clock": "SYNTHETIC_UTC_FIXTURE_CLOCK"}


def _synthetic_payloads() -> dict[str, bytes]:
    """Return deterministic in-memory payloads used only for fixture hashing."""

    return {
        "EVIDENCE-SENSOR-001": b"SafeNest|fixture|sensor-observation|001|v1\n",
        "EVIDENCE-OCCUPANCY-001": b"SafeNest|fixture|occupancy-reference|001|v1\n",
        "EVIDENCE-ACCESS-001": b"SafeNest|fixture|sealed-access-evidence|001|v1\n",
        "EVIDENCE-HEALTH-001": b"SafeNest|fixture|sensor-health|001|v1\n",
        "EVIDENCE-TIMING-001": b"SafeNest|fixture|timing-alignment|001|v1\n",
        "EVIDENCE-PROVENANCE-001": b"SafeNest|fixture|recording-provenance|001|v1\n",
        "EVIDENCE-REJECTION-001": b"SafeNest|fixture|rejection-evidence|001|v1\n",
    }


def _hash_receipts() -> tuple[list[dict[str, Any]], dict[str, str]]:
    payloads = _synthetic_payloads()
    definitions = [
        ("EVIDENCE-SENSOR-001", "SENSOR_OBSERVATION", "SYNTHETIC_SENSOR_SOURCE_001", "SYNTHETIC_SENSOR_REF_001", "fixtures/non_campaign/evidence/sensor_observation_001.bin"),
        ("EVIDENCE-OCCUPANCY-001", "OCCUPANCY_REFERENCE", "SYNTHETIC_OCCUPANCY_SOURCE_001", "SYNTHETIC_OCCUPANCY_REF_001", "fixtures/non_campaign/evidence/occupancy_reference_001.bin"),
        ("EVIDENCE-ACCESS-001", "ACCESS_CONTROL_EVIDENCE", "SYNTHETIC_ACCESS_SOURCE_001", "SYNTHETIC_ACCESS_REF_001", "fixtures/non_campaign/evidence/sealed_access_001.bin"),
        ("EVIDENCE-HEALTH-001", "SENSOR_HEALTH", "SYNTHETIC_HEALTH_SOURCE_001", "SYNTHETIC_HEALTH_REF_001", "fixtures/non_campaign/evidence/sensor_health_001.bin"),
        ("EVIDENCE-TIMING-001", "TIMING_ALIGNMENT", "SYNTHETIC_TIMING_SOURCE_001", "SYNTHETIC_TIMING_REF_001", "fixtures/non_campaign/evidence/timing_alignment_001.bin"),
        ("EVIDENCE-PROVENANCE-001", "RECORDING_PROVENANCE", "SYNTHETIC_PROVENANCE_SOURCE_001", "SYNTHETIC_PROVENANCE_REF_001", "fixtures/non_campaign/evidence/recording_provenance_001.bin"),
        ("EVIDENCE-REJECTION-001", "REJECTION_EVIDENCE", "SYNTHETIC_REJECTION_SOURCE_001", "SYNTHETIC_REJECTION_REF_001", "fixtures/non_campaign/evidence/rejection_001.bin"),
    ]
    receipts: list[dict[str, Any]] = []
    actual_digests: dict[str, str] = {}
    for evidence_id, evidence_type, source, reference, file_reference in definitions:
        payload = payloads[evidence_id]
        receipt = create_hash_receipt(
            evidence_id,
            evidence_type,
            source,
            reference,
            payload=payload,
            file_reference=file_reference,
            size_bytes=len(payload),
            time_coverage=_time_coverage(),
        )
        receipts.append(receipt)
        actual_digests[evidence_id] = sha256_bytes(payload)
    return receipts, actual_digests


def _sync_records() -> list[dict[str, Any]]:
    semantics = _fixture_semantics()
    return [
        {
            "schema_version": "MMWAVE-V2-D1-SW03-SYNC-RECORD-V1",
            "sync_record_id": "SYNC-FIXTURE-SHARED-CLOCK-001",
            "method": "SHARED_CLOCK",
            "source_identity": "SYNTHETIC_SENSOR_SOURCE_001",
            "clock_identity": "SYNTHETIC_HOST_COMMON_CLOCK_V1",
            "source_timestamp": "2026-08-27T00:00:00.000Z",
            "host_timestamp": "2026-08-27T00:00:00.000Z",
            "sync_marker_id": None,
            "alignment_method": "SAME_HOST_COMMON_CLOCK",
            "measured_offset_delta_ms": 0.0,
            "uncertainty_ms": 0.5,
            "alignment_status": "ALIGNMENT_MEASURABLE",
            "validation_status": "FIXTURE_ONLY_ALIGNMENT_RECORDED",
            "threshold_status": "THRESHOLD_NOT_GOVERNED",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "fixture_semantics": semantics,
        },
        {
            "schema_version": "MMWAVE-V2-D1-SW03-SYNC-RECORD-V1",
            "sync_record_id": "SYNC-FIXTURE-EXPLICIT-MARKER-001",
            "method": "EXPLICIT_SYNC_MARKER",
            "source_identity": "SYNTHETIC_OCCUPANCY_SOURCE_001",
            "clock_identity": "SYNTHETIC_INDEPENDENT_CLOCK_PAIR_V1",
            "source_timestamp": "2026-08-27T00:00:05.000Z",
            "host_timestamp": "2026-08-27T00:00:05.012Z",
            "sync_marker_id": "SYNC-MARKER-FIXTURE-001",
            "source_marker_observed": True,
            "host_marker_observed": True,
            "alignment_method": "EXPLICIT_MARKER_ON_BOTH_TIMELINES",
            "measured_offset_delta_ms": 12.0,
            "uncertainty_ms": 1.5,
            "alignment_status": "ALIGNMENT_MEASURABLE",
            "validation_status": "FIXTURE_ONLY_ALIGNMENT_RECORDED",
            "threshold_status": "THRESHOLD_NOT_GOVERNED",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "fixture_semantics": semantics,
        },
    ]


def _provenance_records() -> list[dict[str, Any]]:
    return [
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["provenance"],
            "registry_record_id": "PROVENANCE-FIXTURE-001",
            "recording_identity": {
                "planned_recording_id": "PLANNED-FIXTURE-RECORDING-001",
                "actual_recording_id": "ACTUAL-FIXTURE-RECORDING-001",
                "actual_recording_reference": "fixtures/non_campaign/recordings/actual_recording_001",
            },
            "sensor_identity": {
                "sensor_id": "SYNTHETIC_SENSOR_001",
                "source_identity": "SYNTHETIC_SENSOR_SOURCE_001",
                "device_family": "SYNTHETIC_MMWAVE_FIXTURE",
            },
            "configuration_identity": {
                "config_id": "SYNTHETIC_CONFIG_001",
                "config_hash_receipt_id": "EVIDENCE-PROVENANCE-001",
            },
            "placement_zone": {
                "placement_id": "SYNTHETIC_PLACEMENT_001",
                "zone_id": "SYNTHETIC_TARGET_ZONE_001",
                "coverage_status": "FIXTURE_DECLARED_ONLY",
            },
            "evidence_references": {
                "sensor_observation": ["EVIDENCE-SENSOR-001"],
                "occupancy_reference": ["EVIDENCE-OCCUPANCY-001"],
                "access_control": ["EVIDENCE-ACCESS-001"],
                "health": ["EVIDENCE-HEALTH-001"],
                "timing_alignment": ["SYNC-FIXTURE-SHARED-CLOCK-001", "SYNC-FIXTURE-EXPLICIT-MARKER-001"],
                "recording_provenance": ["EVIDENCE-PROVENANCE-001"],
                "rejection": [],
            },
            "time_coverage": _time_coverage(),
            "health_registry_record_id": "HEALTH-FIXTURE-VALID-001",
            "acceptance_state": "RETAINED_FIXTURE_ONLY",
            "rejection_registry_record_id": None,
            "fixture_semantics": _fixture_semantics(),
        }
    ]


def _occupancy_records() -> list[dict[str, Any]]:
    semantics = _fixture_semantics()
    return [
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["occupancy"],
            "registry_record_id": "OCCUPANCY-FIXTURE-VALID-001",
            "authoritative_occupancy_reference": {
                "identity": "SYNTHETIC_OCCUPANCY_REF_001",
                "source_identity": "SYNTHETIC_OCCUPANCY_SOURCE_001",
                "status": "FIXTURE_REFERENCE_PRESENT",
            },
            "target_zone_coverage": {
                "zone_id": "SYNTHETIC_TARGET_ZONE_001",
                "coverage_status": "FIXTURE_DECLARED_ONLY",
                "authoritative": True,
            },
            "no_human_evidence_reference": "EVIDENCE-OCCUPANCY-001",
            "sealed_access_evidence_reference": "EVIDENCE-ACCESS-001",
            "time_interval": _time_coverage(),
            "sync_evidence_ids": ["SYNC-FIXTURE-EXPLICIT-MARKER-001"],
            "hash_receipt_ids": ["EVIDENCE-OCCUPANCY-001", "EVIDENCE-ACCESS-001", "EVIDENCE-TIMING-001"],
            "occupancy_state": "OCCUPANCY_REFERENCE_PRESENT_SYNTHETIC",
            "review_status": "FIXTURE_REVIEWED_ONLY",
            "absent_eligibility": "NOT_ELIGIBLE_FROM_FIXTURE",
            "physiology_label": None,
            "fixture_semantics": semantics,
        },
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["occupancy"],
            "registry_record_id": "OCCUPANCY-FIXTURE-MISSING-001",
            "authoritative_occupancy_reference": None,
            "target_zone_coverage": {
                "zone_id": "SYNTHETIC_TARGET_ZONE_002",
                "coverage_status": "MISSING_AUTHORITATIVE_REFERENCE",
                "authoritative": False,
            },
            "no_human_evidence_reference": None,
            "sealed_access_evidence_reference": None,
            "time_interval": _time_coverage("2026-08-27T00:01:00Z", "2026-08-27T00:01:15Z"),
            "sync_evidence_ids": ["SYNC-FIXTURE-SHARED-CLOCK-001"],
            "hash_receipt_ids": [],
            "occupancy_state": "UNKNOWN_REFERENCE_MISSING",
            "review_status": "INCOMPLETE_REVIEW_REQUIRED",
            "absent_eligibility": "NOT_ELIGIBLE",
            "physiology_label": None,
            "fixture_semantics": semantics,
        },
    ]


def _health_records() -> list[dict[str, Any]]:
    semantics = _fixture_semantics()
    return [
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["health"],
            "registry_record_id": "HEALTH-FIXTURE-VALID-001",
            "sensor_identity": "SYNTHETIC_SENSOR_001",
            "device_connected": True,
            "stream_valid": True,
            "timestamp_valid": True,
            "continuity_status": "CONTINUOUS_FIXTURE_STREAM",
            "reported_device_health": "REPORTED_OK_FIXTURE_ONLY",
            "reset_restart_observed": False,
            "fault_code": None,
            "evidence_ids": ["EVIDENCE-HEALTH-001"],
            "health_state": "HEALTH_OBSERVED_FIXTURE_ONLY",
            "physiology_interpretation": "NOT_PROVIDED",
            "review_status": "FIXTURE_REVIEWED_ONLY",
            "fixture_semantics": semantics,
        },
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["health"],
            "registry_record_id": "HEALTH-FIXTURE-FAULT-001",
            "sensor_identity": "SYNTHETIC_SENSOR_002",
            "device_connected": True,
            "stream_valid": False,
            "timestamp_valid": True,
            "continuity_status": "FREEZE_DETECTED",
            "reported_device_health": "FAULT_REPORTED_FIXTURE_ONLY",
            "reset_restart_observed": True,
            "fault_code": "SYNTHETIC_STREAM_FREEZE",
            "evidence_ids": ["EVIDENCE-HEALTH-001"],
            "health_state": "FAULT_RETAINED",
            "physiology_interpretation": "NOT_PROVIDED",
            "review_status": "FIXTURE_FAULT_RETAINED",
            "fixture_semantics": semantics,
        },
    ]


def _rejection_records() -> list[dict[str, Any]]:
    return [
        {
            "schema_version": REGISTRY_SCHEMA_VERSIONS["rejection"],
            "rejection_record_id": "REJECTION-FIXTURE-001",
            "immutable_candidate_recording_reference": {
                "candidate_id": "SYNTHETIC-CANDIDATE-001",
                "recording_id": "ACTUAL-FIXTURE-RECORDING-002",
                "reference": "fixtures/non_campaign/recordings/rejected_recording_002",
            },
            "reason_code": "OCCUPANCY_EVIDENCE_MISSING",
            "reason_detail": "Authoritative occupancy and sealed-access references are missing; retain the observation for audit.",
            "evidence_references": ["EVIDENCE-SENSOR-001", "EVIDENCE-REJECTION-001"],
            "time_coverage": _time_coverage("2026-08-27T00:02:00Z", "2026-08-27T00:02:15Z"),
            "decision_source": "SW04_FIXTURE_VALIDATOR",
            "retained": True,
            "acceptance_state": "REJECTED",
            "eligible_for_absent": False,
            "physiology_label": None,
            "fixture_semantics": _fixture_semantics(),
        }
    ]


def _schema_common(required: Sequence[str], schema_version: str, title: str, properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_version,
        "title": title,
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": dict(properties),
    }


def _string() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _registry_schema_document(kind: str) -> dict[str, Any]:
    version = REGISTRY_SCHEMA_VERSIONS[kind]
    common = {
        "schema_version": {"const": version},
        "registry_record_id": _string(),
        "fixture_semantics": {"type": "array", "const": FIXTURE_SEMANTICS},
    }
    if kind == "provenance":
        properties = {
            **common,
            "recording_identity": {"type": "object"},
            "sensor_identity": {"type": "object"},
            "configuration_identity": {"type": "object"},
            "placement_zone": {"type": "object"},
            "evidence_references": {"type": "object"},
            "time_coverage": {"type": "object"},
            "health_registry_record_id": _string(),
            "acceptance_state": _string(),
            "rejection_registry_record_id": _nullable_string(),
        }
        title = "SafeNest mmWave V2 SW-04 recording provenance registry record"
    elif kind == "occupancy":
        properties = {
            **common,
            "authoritative_occupancy_reference": {"type": ["object", "null"]},
            "target_zone_coverage": {"type": "object"},
            "no_human_evidence_reference": _nullable_string(),
            "sealed_access_evidence_reference": _nullable_string(),
            "time_interval": {"type": "object"},
            "sync_evidence_ids": {"type": "array"},
            "hash_receipt_ids": {"type": "array"},
            "occupancy_state": _string(),
            "review_status": _string(),
            "absent_eligibility": _string(),
            "physiology_label": {"type": ["string", "null"]},
        }
        title = "SafeNest mmWave V2 SW-04 occupancy evidence registry record"
    elif kind == "health":
        properties = {
            **common,
            "sensor_identity": _string(),
            "device_connected": {"type": "boolean"},
            "stream_valid": {"type": "boolean"},
            "timestamp_valid": {"type": "boolean"},
            "continuity_status": _string(),
            "reported_device_health": _string(),
            "reset_restart_observed": {"type": "boolean"},
            "fault_code": _nullable_string(),
            "evidence_ids": {"type": "array"},
            "health_state": _string(),
            "physiology_interpretation": {"const": "NOT_PROVIDED"},
            "review_status": _string(),
        }
        title = "SafeNest mmWave V2 SW-04 sensor health registry record"
    elif kind == "rejection":
        properties = {
            **common,
            "rejection_record_id": _string(),
            "immutable_candidate_recording_reference": {"type": "object"},
            "reason_code": _string(),
            "reason_detail": _string(),
            "evidence_references": {"type": "array"},
            "time_coverage": {"type": "object"},
            "decision_source": _string(),
            "retained": {"const": True},
            "acceptance_state": {"const": "REJECTED"},
            "eligible_for_absent": {"const": False},
            "physiology_label": {"type": ["string", "null"]},
        }
        title = "SafeNest mmWave V2 SW-04 rejection registry record"
    else:
        raise KeyError(kind)
    return _schema_common(REGISTRY_REQUIRED_FIELDS[kind], version, title, properties)


def registry_schema_documents() -> dict[str, dict[str, Any]]:
    return {kind: _registry_schema_document(kind) for kind in REGISTRY_SCHEMA_VERSIONS}


def _all_referenced_evidence(record: Mapping[str, Any], kind: str) -> list[str]:
    refs: list[str] = []
    if kind == "provenance":
        evidence = record.get("evidence_references", {})
        if isinstance(evidence, Mapping):
            for values in evidence.values():
                if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
                    refs.extend(str(value) for value in values)
        config = record.get("configuration_identity", {})
        if isinstance(config, Mapping) and config.get("config_hash_receipt_id"):
            refs.append(str(config["config_hash_receipt_id"]))
    elif kind == "occupancy":
        for key in ("no_human_evidence_reference", "sealed_access_evidence_reference"):
            if record.get(key):
                refs.append(str(record[key]))
        refs.extend(str(value) for value in record.get("hash_receipt_ids", []) if isinstance(value, str))
    elif kind == "health":
        refs.extend(str(value) for value in record.get("evidence_ids", []) if isinstance(value, str))
    elif kind == "rejection":
        refs.extend(str(value) for value in record.get("evidence_references", []) if isinstance(value, str))
    return refs


def validate_registry_records(
    kind: str,
    records: Sequence[Mapping[str, Any]],
    *,
    known_evidence_ids: set[str] | None = None,
    known_sync_ids: set[str] | None = None,
) -> list[str]:
    """Validate one logically distinct SW-04 registry."""

    if kind not in REGISTRY_SCHEMA_VERSIONS:
        return [f"unsupported registry kind: {kind}"]
    errors: list[str] = []
    seen: set[str] = set()
    known_evidence_ids = known_evidence_ids or set()
    known_sync_ids = known_sync_ids or set()
    for index, record in enumerate(records):
        label = f"{kind}[{index}]"
        if not isinstance(record, Mapping):
            errors.append(f"{label}: record must be an object")
            continue
        errors.extend(f"{label}: missing {key}" for key in REGISTRY_REQUIRED_FIELDS[kind] if key not in record)
        if record.get("schema_version") != REGISTRY_SCHEMA_VERSIONS[kind]:
            errors.append(f"{label}: unsupported schema_version")
        record_id_key = "rejection_record_id" if kind == "rejection" else "registry_record_id"
        record_id = record.get(record_id_key)
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"{label}: {record_id_key} must be non-empty")
        elif record_id in seen:
            errors.append(f"{label}: duplicate registry_record_id {record_id}")
        else:
            seen.add(record_id)
        if record.get("fixture_semantics") != FIXTURE_SEMANTICS:
            errors.append(f"{label}: fixture semantics are not fixture-only")
        errors.extend(f"{label}: absolute/local path at {path}" for path in find_absolute_paths(record))
        if kind == "provenance":
            recording = record.get("recording_identity")
            if not isinstance(recording, Mapping) or not recording.get("planned_recording_id") or not recording.get("actual_recording_id") or not _portable_reference(recording.get("actual_recording_reference")):
                errors.append(f"{label}: planned-to-actual recording lineage is incomplete")
            if not isinstance(record.get("evidence_references"), Mapping):
                errors.append(f"{label}: evidence_references must preserve separate channels")
            if not isinstance(record.get("health_registry_record_id"), str) or not record.get("health_registry_record_id"):
                errors.append(f"{label}: health registry linkage is required")
        elif kind == "occupancy":
            state = record.get("occupancy_state")
            if state == "UNKNOWN_REFERENCE_MISSING":
                missing_fields = ("authoritative_occupancy_reference", "no_human_evidence_reference", "sealed_access_evidence_reference")
                if any(record.get(field) is not None for field in missing_fields):
                    errors.append(f"{label}: missing occupancy fixture must retain explicit missing references")
                if record.get("review_status") != "INCOMPLETE_REVIEW_REQUIRED" or record.get("absent_eligibility") == "ELIGIBLE":
                    errors.append(f"{label}: missing occupancy must remain incomplete and ineligible")
                if record.get("physiology_label") is not None:
                    errors.append(f"{label}: missing occupancy cannot carry a physiology label")
            elif state == "OCCUPANCY_REFERENCE_PRESENT_SYNTHETIC":
                if not isinstance(record.get("authoritative_occupancy_reference"), Mapping) or not record["authoritative_occupancy_reference"].get("identity"):
                    errors.append(f"{label}: authoritative occupancy identity is required when present")
                if not record.get("no_human_evidence_reference") or not record.get("sealed_access_evidence_reference"):
                    errors.append(f"{label}: synthetic complete occupancy fixture is missing evidence references")
            else:
                errors.append(f"{label}: unsupported occupancy_state")
            if not isinstance(record.get("sync_evidence_ids"), Sequence) or isinstance(record.get("sync_evidence_ids"), (str, bytes, bytearray)) or not set(record.get("sync_evidence_ids", [])) <= known_sync_ids:
                errors.append(f"{label}: sync evidence references are invalid")
        elif kind == "health":
            fault = record.get("fault_code")
            if fault is not None and (record.get("health_state") != "FAULT_RETAINED" or record.get("review_status") != "FIXTURE_FAULT_RETAINED"):
                errors.append(f"{label}: health fault must be retained separately")
            if record.get("physiology_interpretation") != "NOT_PROVIDED":
                errors.append(f"{label}: health must not provide physiology semantics")
        elif kind == "rejection":
            if record.get("retained") is not True or record.get("acceptance_state") != "REJECTED":
                errors.append(f"{label}: rejection must be retained with REJECTED state")
            if record.get("eligible_for_absent") is not False or record.get("physiology_label") is not None:
                errors.append(f"{label}: rejected observation must not become eligible ABSENT or physiological")
            reference = record.get("immutable_candidate_recording_reference")
            if not isinstance(reference, Mapping) or not reference.get("candidate_id") or not reference.get("recording_id") or not _portable_reference(reference.get("reference")):
                errors.append(f"{label}: immutable candidate/recording reference is incomplete")
        refs = _all_referenced_evidence(record, kind)
        errors.extend(f"{label}: unknown evidence reference {ref}" for ref in refs if ref not in known_evidence_ids and not ref.startswith("SYNC-"))
        errors.extend(f"{label}: unknown sync reference {ref}" for ref in refs if ref.startswith("SYNC-") and ref not in known_sync_ids)
    return errors


def _bundle_metadata() -> dict[str, Any]:
    return {
        "schema_version": "MMWAVE-V2-D1-SW03-SW04-EVIDENCE-TOOLING-V1",
        "manifest_id": MANIFEST_ID,
        "phase": "MMWAVE-V2-D1-SWPREP-03-04",
        "base_commit": BASE_SHA,
        "scope": "SOFTWARE_AND_SYNTHETIC_FIXTURE_ONLY",
        "capture_executed": False,
        "d1_membership_created": False,
        "d2_accessed": False,
        "mr60_supervised_physiology_used": False,
        "model_training": False,
        "model_evaluation": False,
        "sw01_implemented": False,
        "sw02_implemented": False,
        "live_occupancy_evidence": "NOT_PRODUCED",
        "live_sensor_health_evidence": "NOT_PRODUCED",
        "timing_threshold_status": "THRESHOLD_NOT_GOVERNED",
        "fixture_semantics": _fixture_semantics(),
        "provenance_channels": [
            "sensor_observation",
            "occupancy_reference",
            "sealed_access_evidence",
            "sensor_health",
            "timing_alignment",
            "recording_identity",
            "rejection_reason",
        ],
        "physiology_label_generation": "FORBIDDEN_FROM_SENSOR_QUALITY_OR_OCCUPANCY_GAPS",
        "d1_membership_source_read_only": [CANONICAL_D1_STATE, CANONICAL_D1_SNAPSHOT],
    }


def _fixture_documents(sync_records: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    semantics = _fixture_semantics()
    shared_id = sync_records[0]["sync_record_id"]
    marker_id = sync_records[1]["sync_record_id"]
    sensor_id = receipts[0]["evidence_id"]
    return {
        "valid_sync": {
            "fixture_id": "FIXTURE-SW0304-VALID-SHARED-CLOCK-001",
            "scenario": "VALID_SYNCHRONIZED_EVIDENCE_SET",
            "fixture_semantics": semantics,
            "sync_record_ids": [shared_id],
            "hash_receipt_ids": [sensor_id, "EVIDENCE-TIMING-001"],
            "alignment_status": "ALIGNMENT_MEASURABLE",
            "threshold_status": "THRESHOLD_NOT_GOVERNED",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "explicit_marker": {
            "fixture_id": "FIXTURE-SW0304-EXPLICIT-MARKER-001",
            "scenario": "EXPLICIT_SYNC_MARKER_EVIDENCE_SET",
            "fixture_semantics": semantics,
            "sync_record_ids": [marker_id],
            "marker_observed_on_both_timelines": True,
            "alignment_status": "ALIGNMENT_MEASURABLE",
            "threshold_status": "THRESHOLD_NOT_GOVERNED",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "hash_verification": {
            "fixture_id": "FIXTURE-SW0304-HASH-VERIFICATION-001",
            "scenario": "HASH_VERIFICATION",
            "fixture_semantics": semantics,
            "evidence_id": "EVIDENCE-SENSOR-001",
            "expected_sha256": receipts[0]["sha256"],
            "actual_sha256": receipts[0]["sha256"],
            "verification_status": "VERIFIED_FIXTURE_PAYLOAD_ONLY",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "health_fault": {
            "fixture_id": "FIXTURE-SW0304-HEALTH-FAULT-001",
            "scenario": "SENSOR_HEALTH_FAULT",
            "fixture_semantics": semantics,
            "health_registry_record_id": "HEALTH-FIXTURE-FAULT-001",
            "fault_code": "SYNTHETIC_STREAM_FREEZE",
            "retained": True,
            "physiology_interpretation": "NOT_PROVIDED",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "occupancy_missing": {
            "fixture_id": "FIXTURE-SW0304-OCCUPANCY-MISSING-001",
            "scenario": "OCCUPANCY_EVIDENCE_MISSING",
            "fixture_semantics": semantics,
            "occupancy_registry_record_id": "OCCUPANCY-FIXTURE-MISSING-001",
            "status": "INCOMPLETE",
            "absent_eligibility": "NOT_ELIGIBLE",
            "physiology_label": None,
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "rejection_retained": {
            "fixture_id": "FIXTURE-SW0304-REJECTION-RETAINED-001",
            "scenario": "REJECTED_OBSERVATION_RETAINED",
            "fixture_semantics": semantics,
            "rejection_record_id": "REJECTION-FIXTURE-001",
            "retained": True,
            "acceptance_state": "REJECTED",
            "eligible_for_absent": False,
            "physiology_label": None,
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "duplicate_id": {
            "fixture_id": "FIXTURE-SW0304-DUPLICATE-ID-001",
            "scenario": "DUPLICATE_IMMUTABLE_EVIDENCE_ID",
            "fixture_semantics": semantics,
            "duplicate_evidence_ids": ["EVIDENCE-SENSOR-001", "EVIDENCE-SENSOR-001"],
            "expected_validation": "REJECTED_DUPLICATE_IMMUTABLE_ID",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
        "hash_mismatch": {
            "fixture_id": "FIXTURE-SW0304-HASH-MISMATCH-001",
            "scenario": "HASH_MISMATCH",
            "fixture_semantics": semantics,
            "evidence_id": "EVIDENCE-SENSOR-001",
            "expected_sha256": receipts[0]["sha256"],
            "actual_sha256": "f" * 64,
            "expected_validation": "REJECTED_HASH_MISMATCH",
            "live_evidence_status": "NOT_LIVE_EVIDENCE",
            "campaign_status": "NON_CAMPAIGN",
            "d1_membership_status": "NOT_D1_MEMBERSHIP",
            "dataset_admissibility": "NOT_DATASET_ADMISSIBLE",
        },
    }


def _read_d1_state() -> dict[str, Any]:
    state_path = ROOT / CANONICAL_D1_STATE
    snapshot_path = ROOT / CANONICAL_D1_SNAPSHOT
    lifecycle_path = ROOT / CANONICAL_LIFECYCLE_STATE
    state = read_json(state_path)
    snapshot = read_json(snapshot_path)
    lifecycle = read_json(lifecycle_path)
    expected = state.get("d1", {}).get("expected", {})
    observed = state.get("d1", {}).get("observed_governed", {})
    counts = {
        "expected_present": expected.get("PRESENT"),
        "expected_absent": expected.get("ABSENT"),
        "observed_present": observed.get("PRESENT"),
        "observed_absent": observed.get("ABSENT"),
        "snapshot_present_expected": snapshot.get("present_expected"),
        "snapshot_absent_expected": snapshot.get("absent_expected"),
        "absent_sessions_created_this_phase": snapshot.get("absent_sessions_created_this_phase"),
        "d1_campaign_dir_exists": snapshot.get("d1_campaign_dir_exists"),
    }
    unchanged = (
        counts == {
            "expected_present": 57,
            "expected_absent": 57,
            "observed_present": 57,
            "observed_absent": 0,
            "snapshot_present_expected": 57,
            "snapshot_absent_expected": 0,
            "absent_sessions_created_this_phase": 0,
            "d1_campaign_dir_exists": False,
        }
        and state.get("d1", {}).get("status") == "UNCHANGED"
        and snapshot.get("membership_status") == "BLOCKED_INVALID_FINAL_MEMBERSHIP"
        and lifecycle.get("closure_status") == "RESOURCE_BLOCKED_CLOSED"
    )
    return {
        "source": CANONICAL_D1_STATE,
        "resource_recovery_snapshot": CANONICAL_D1_SNAPSHOT,
        "counts": counts,
        "membership_created": False,
        "unchanged": unchanged,
        "m_pv38_status": lifecycle.get("closure_status"),
        "m_pv4": state.get("m_pv4"),
        "d2": state.get("d2"),
    }


def _load_records(manifest_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    sync_records = read_json(manifest_dir / "sync_records.json")["records"]
    hash_receipts = read_json(manifest_dir / "hash_receipts.json")["receipts"]
    registries = {
        kind: read_json(manifest_dir / filename)["records"] for kind, filename in REGISTRY_FILES.items()
    }
    return sync_records, hash_receipts, registries


def _check(name: str, ok: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _validate_schema_documents(manifest_dir: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected: dict[str, dict[str, Any]] = {"sync": sync_record_schema_document(), "hash": hash_receipt_schema_document()}
    expected.update(registry_schema_documents())
    for key, filename in SCHEMA_FILES.items():
        path = manifest_dir / filename
        try:
            document = read_json(path)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            errors.append(f"schema {key}: {exc}")
            continue
        if document != expected[key]:
            errors.append(f"schema {key}: generated document differs from implementation")
        if document.get("type") != "object" or not isinstance(document.get("required"), list) or not isinstance(document.get("properties"), Mapping):
            errors.append(f"schema {key}: invalid object-schema shape")
    return errors, expected


def _validate_fixture_documents(manifest_dir: Path, sync_records: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    documents: dict[str, Any] = {}
    for key, filename in FIXTURE_FILES.items():
        try:
            documents[key] = read_json(manifest_dir / filename)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            errors.append(f"fixture {key}: {exc}")
    for key, document in documents.items():
        if document.get("fixture_semantics") != FIXTURE_SEMANTICS:
            errors.append(f"fixture {key}: missing required fixture semantics")
        if document.get("live_evidence_status") != "NOT_LIVE_EVIDENCE":
            errors.append(f"fixture {key}: cannot claim live evidence")
        if document.get("campaign_status") != "NON_CAMPAIGN" or document.get("d1_membership_status") != "NOT_D1_MEMBERSHIP" or document.get("dataset_admissibility") != "NOT_DATASET_ADMISSIBLE":
            errors.append(f"fixture {key}: campaign/membership/admissibility semantics are incomplete")
        errors.extend(f"fixture {key}: absolute/local path at {path}" for path in find_absolute_paths(document))
    sync_ids = {str(record.get("sync_record_id")) for record in sync_records}
    receipt_by_id = {str(receipt.get("evidence_id")): receipt for receipt in receipts}
    valid_sync = documents.get("valid_sync", {})
    if valid_sync.get("scenario") != "VALID_SYNCHRONIZED_EVIDENCE_SET" or not set(valid_sync.get("sync_record_ids", [])) <= sync_ids:
        errors.append("valid synchronized evidence fixture is incomplete")
    marker = documents.get("explicit_marker", {})
    marker_ids = {str(record.get("sync_record_id")) for record in sync_records if record.get("method") == "EXPLICIT_SYNC_MARKER"}
    if marker.get("scenario") != "EXPLICIT_SYNC_MARKER_EVIDENCE_SET" or not marker.get("marker_observed_on_both_timelines") or not set(marker.get("sync_record_ids", [])) <= marker_ids:
        errors.append("explicit sync-marker fixture is incomplete")
    verification = documents.get("hash_verification", {})
    if verification.get("verification_status") != "VERIFIED_FIXTURE_PAYLOAD_ONLY" or verification.get("expected_sha256") != verification.get("actual_sha256") or verification.get("evidence_id") not in receipt_by_id:
        errors.append("hash verification fixture is incomplete")
    fault = documents.get("health_fault", {})
    if fault.get("fault_code") is None or fault.get("retained") is not True or fault.get("physiology_interpretation") != "NOT_PROVIDED":
        errors.append("health fault fixture is not retained separately")
    missing = documents.get("occupancy_missing", {})
    if missing.get("status") != "INCOMPLETE" or missing.get("absent_eligibility") == "ELIGIBLE" or missing.get("physiology_label") is not None:
        errors.append("missing occupancy fixture was converted into a physiological outcome")
    rejected = documents.get("rejection_retained", {})
    if rejected.get("retained") is not True or rejected.get("acceptance_state") != "REJECTED" or rejected.get("eligible_for_absent") is not False:
        errors.append("rejection retention fixture is incomplete")
    duplicate = documents.get("duplicate_id", {})
    duplicate_ids = duplicate.get("duplicate_evidence_ids", [])
    if duplicate.get("expected_validation") != "REJECTED_DUPLICATE_IMMUTABLE_ID" or len(duplicate_ids) != 2 or duplicate_ids[0] != duplicate_ids[1]:
        errors.append("duplicate evidence-id rejection fixture is incomplete")
    mismatch = documents.get("hash_mismatch", {})
    if mismatch.get("expected_validation") != "REJECTED_HASH_MISMATCH" or mismatch.get("expected_sha256") == mismatch.get("actual_sha256") or verify_hash_receipt(mismatch, actual_sha256=mismatch.get("actual_sha256")):
        errors.append("hash mismatch rejection fixture is incomplete")
    return errors


def _checksum_map(manifest_dir: Path) -> dict[str, str]:
    excluded = {"checksums.json", "checksums.sha256"}
    paths = sorted(
        path for path in manifest_dir.rglob("*") if path.is_file() and path.name not in excluded
    )
    artifacts: dict[str, str] = {}
    for path in paths:
        try:
            name = path.relative_to(ROOT).as_posix()
        except ValueError:
            # Temporary directories are useful for deterministic tests.  The
            # active bundle still uses repository-relative paths above.
            name = (Path(manifest_dir.name) / path.relative_to(manifest_dir)).as_posix()
        artifacts[name] = sha256_file(path)
    return artifacts


def _validate_checksum_receipts(manifest_dir: Path, *, require_final_artifacts: bool) -> tuple[bool, dict[str, Any]]:
    checksum_json = manifest_dir / "checksums.json"
    checksum_list = manifest_dir / "checksums.sha256"
    if not checksum_json.is_file() or not checksum_list.is_file():
        return (not require_final_artifacts), {"missing": [path.name for path in (checksum_json, checksum_list) if not path.is_file()]}
    try:
        declared = read_json(checksum_json).get("files", {})
    except (json.JSONDecodeError, AttributeError) as exc:
        return False, {"error": str(exc)}
    listed: dict[str, str] = {}
    malformed: list[str] = []
    for line in checksum_list.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, path = line.split("  ", 1)
        except ValueError:
            malformed.append(line)
            continue
        listed[path] = digest
    expected = _checksum_map(manifest_dir)
    mismatches = {
        path: {"expected": digest, "actual": expected.get(path)}
        for path, digest in listed.items()
        if expected.get(path) != digest
    }
    ok = not malformed and declared == listed and listed == expected
    return ok, {
        "malformed": malformed,
        "declared_count": len(declared),
        "listed_count": len(listed),
        "expected_count": len(expected),
        "mismatches": mismatches,
    }


def validate_bundle(manifest_dir: Path = DEFAULT_MANIFEST_DIR, *, require_final_artifacts: bool = True) -> dict[str, Any]:
    """Validate the complete SW-03/SW-04 fixture bundle fail-closed."""

    checks: list[dict[str, Any]] = []
    required = FINAL_FILES if require_final_artifacts else CORE_FILES
    missing = [name for name in required if not (manifest_dir / name).is_file()]
    checks.append(_check("required_artifacts_present", not missing, missing))
    if missing:
        return {
            "schema_version": "MMWAVE-V2-D1-SW03-SW04-VALIDATION-V1",
            "ok": False,
            "failed_checks": ["required_artifacts_present"],
            "checks": checks,
            "terminal_verdict": "SW03_SW04_CORRECTIVE_REQUIRED",
        }
    try:
        metadata = read_json(manifest_dir / "bundle_metadata.json")
        sync_records, receipts, registries = _load_records(manifest_dir)
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
        return {
            "schema_version": "MMWAVE-V2-D1-SW03-SW04-VALIDATION-V1",
            "ok": False,
            "failed_checks": ["machine_readable_bundle"],
            "checks": checks + [_check("machine_readable_bundle", False, str(exc))],
            "terminal_verdict": "SW03_SW04_CORRECTIVE_REQUIRED",
        }
    checks.append(_check("fixture_only_scope", metadata.get("scope") == "SOFTWARE_AND_SYNTHETIC_FIXTURE_ONLY" and metadata.get("capture_executed") is False and metadata.get("d1_membership_created") is False, {"scope": metadata.get("scope"), "capture_executed": metadata.get("capture_executed"), "d1_membership_created": metadata.get("d1_membership_created")}))
    checks.append(_check("safety_prohibitions_preserved", all(metadata.get(key) is False for key in ("d2_accessed", "mr60_supervised_physiology_used", "model_training", "model_evaluation", "sw01_implemented", "sw02_implemented")), {key: metadata.get(key) for key in ("d2_accessed", "mr60_supervised_physiology_used", "model_training", "model_evaluation", "sw01_implemented", "sw02_implemented")}))
    schema_errors, _ = _validate_schema_documents(manifest_dir)
    checks.append(_check("versioned_schema_documents", not schema_errors, schema_errors))
    sync_errors = validate_sync_records(sync_records)
    checks.append(_check("sync_records_semantics", not sync_errors, sync_errors))
    payload_digests = {evidence_id: sha256_bytes(payload) for evidence_id, payload in _synthetic_payloads().items()}
    hash_errors = validate_hash_receipts(receipts, actual_digests=payload_digests)
    checks.append(_check("hash_receipts_semantics_and_verification", not hash_errors, hash_errors))
    known_evidence_ids = {str(receipt.get("evidence_id")) for receipt in receipts}
    known_sync_ids = {str(record.get("sync_record_id")) for record in sync_records}
    registry_errors: list[str] = []
    for kind, records in registries.items():
        registry_errors.extend(validate_registry_records(kind, records, known_evidence_ids=known_evidence_ids, known_sync_ids=known_sync_ids))
    checks.append(_check("separate_registry_semantics", not registry_errors, registry_errors))
    fixture_errors = _validate_fixture_documents(manifest_dir, sync_records, receipts)
    checks.append(_check("synthetic_fixture_demonstrations", not fixture_errors, fixture_errors))
    try:
        d1_state = _read_d1_state()
        d1_ok = d1_state["unchanged"] and d1_state["membership_created"] is False
        d1_detail: Any = d1_state
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
        d1_ok = False
        d1_detail = str(exc)
        d1_state = {"unchanged": False, "membership_created": None}
    checks.append(_check("d1_membership_count_unchanged", d1_ok, d1_detail))
    portability_errors: list[str] = []
    for path in manifest_dir.rglob("*.json"):
        try:
            value = read_json(path)
        except json.JSONDecodeError as exc:
            portability_errors.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
            continue
        portability_errors.extend(f"{path.relative_to(ROOT).as_posix()}: absolute/local path at {location}" for location in find_absolute_paths(value))
    checks.append(_check("machine_readable_artifacts_are_portable", not portability_errors, portability_errors))
    if require_final_artifacts:
        checksum_ok, checksum_detail = _validate_checksum_receipts(manifest_dir, require_final_artifacts=True)
        checks.append(_check("checksum_receipts_complete", checksum_ok, checksum_detail))
        try:
            persisted_result = read_json(manifest_dir / "validation_result.json")
            verdict_ok = persisted_result.get("terminal_verdict") in TERMINAL_VERDICTS and persisted_result.get("ok") is True
        except (json.JSONDecodeError, OSError, AttributeError) as exc:
            verdict_ok = False
            persisted_result = {"error": str(exc)}
        checks.append(_check("validation_result_has_one_governed_verdict", verdict_ok, {"terminal_verdict": persisted_result.get("terminal_verdict"), "ok": persisted_result.get("ok")}))
    failures = [check["name"] for check in checks if not check["ok"]]
    verdict = PASS_VERDICT if not failures else "SW03_SW04_CORRECTIVE_REQUIRED"
    return {
        "schema_version": "MMWAVE-V2-D1-SW03-SW04-VALIDATION-V1",
        "manifest_id": MANIFEST_ID,
        "phase": "MMWAVE-V2-D1-SWPREP-03-04",
        "base_commit": BASE_SHA,
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
        "terminal_verdict": verdict,
        "d1_membership_snapshot": d1_state,
        "live_execution": {
            "capture_executed": False,
            "live_occupancy_evidence": "NOT_PRODUCED",
            "live_sensor_health_evidence": "NOT_PRODUCED",
        },
    }


def build_synthetic_bundle(manifest_dir: Path = DEFAULT_MANIFEST_DIR) -> dict[str, Any]:
    """Write the deterministic synthetic bundle and return final validation."""

    manifest_dir.mkdir(parents=True, exist_ok=True)
    sync_records = _sync_records()
    receipts, _ = _hash_receipts()
    registries = {
        "provenance": _provenance_records(),
        "occupancy": _occupancy_records(),
        "health": _health_records(),
        "rejection": _rejection_records(),
    }
    write_json(manifest_dir / "bundle_metadata.json", _bundle_metadata())
    write_json(manifest_dir / "sync_records.json", {"schema_version": "MMWAVE-V2-D1-SW03-SYNC-RECORDS-BUNDLE-V1", "records": sync_records})
    write_json(manifest_dir / "hash_receipts.json", {"schema_version": "MMWAVE-V2-D1-SW03-HASH-RECEIPTS-BUNDLE-V1", "receipts": receipts})
    write_json(manifest_dir / SCHEMA_FILES["sync"], sync_record_schema_document())
    write_json(manifest_dir / SCHEMA_FILES["hash"], hash_receipt_schema_document())
    for kind, filename in SCHEMA_FILES.items():
        if kind in ("sync", "hash"):
            continue
        write_json(manifest_dir / filename, _registry_schema_document(kind))
    for kind, records in registries.items():
        write_json(manifest_dir / REGISTRY_FILES[kind], {"schema_version": f"{REGISTRY_SCHEMA_VERSIONS[kind]}-BUNDLE", "registry_kind": kind, "records": records})
    fixtures = _fixture_documents(sync_records, receipts)
    for key, filename in FIXTURE_FILES.items():
        write_json(manifest_dir / filename, fixtures[key])

    semantic_result = validate_bundle(manifest_dir, require_final_artifacts=False)
    write_json(manifest_dir / "validation_result.json", semantic_result)
    checksum_map = _checksum_map(manifest_dir)
    write_json(manifest_dir / "checksums.json", {"schema_version": "MMWAVE-V2-D1-SW03-SW04-CHECKSUMS-V1", "algorithm": "SHA-256", "files": checksum_map})
    checksum_lines = "".join(f"{digest}  {path}\n" for path, digest in checksum_map.items())
    (manifest_dir / "checksums.sha256").write_text(checksum_lines, encoding="utf-8")
    return validate_bundle(manifest_dir, require_final_artifacts=True)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="write deterministic synthetic SW-03/SW-04 bundle")
    build_parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    validate_parser = subparsers.add_parser("validate", help="validate an existing SW-03/SW-04 bundle")
    validate_parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_synthetic_bundle(args.manifest_dir)
    else:
        result = validate_bundle(args.manifest_dir)
    print(json.dumps({key: result[key] for key in ("ok", "failed_checks", "terminal_verdict")}, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(_main())
