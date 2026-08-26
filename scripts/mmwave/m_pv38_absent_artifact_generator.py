#!/usr/bin/env python3
"""Deterministic SW-02 artifact generator for the mmWave V2 D1 gate.

This module implements the two-stage identity lifecycle described by the
authoritative M-PV3.8 acquisition gate.  It can structurally generate and
validate a future predeclaration/receipt set, but the checked-in execution
bundle is fixture-only and never creates a governed campaign artifact.

The validator is deliberately fail-closed: a malformed Stage-1 identity lock
prevents receipt validation, and a receipt set must bind every planned ID to
exactly one actual recording identifier and SHA-256 value.
"""

from __future__ import annotations

import argparse
import copy
import datetime as _datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACT_REL = Path("config/mmwave/m_pv38_absent_membership_acquisition_gate.json")
PLAN_REL = Path("datasets/mmwave/manifests/M-PV3_8_absent_acquisition_planning/acquisition_plan.json")
TOOL_REL = Path("scripts/mmwave/m_pv38_absent_artifact_generator.py")
VALIDATOR_REL = Path("scripts/validate_mmwave_d1_sw02_artifact_generator.py")

CONTRACT_ID = "MMWAVE_V2_M_PV38_ABSENT_MEMBERSHIP_ACQUISITION_GATE_V1"
CONTRACT_VERSION = "M-PV3.8.4_CHECKSUM_LIFECYCLE_CLARIFICATION"
TOOL_VERSION = "SW-02_ARTIFACT_GENERATOR_V1"
PHASE_ID = "MMWAVE-V2-D1-SWPREP-02"
PREDECLARATION_SCHEMA = "MMWAVE_V2_D1_SW02_PREDECLARATION_V1"
RECEIPTS_SCHEMA = "MMWAVE_V2_D1_SW02_POST_CAPTURE_RECEIPTS_V1"
FIXTURE_EXECUTION_SCHEMA = "MMWAVE_V2_D1_SW02_FIXTURE_EXECUTION_V1"
EVIDENCE_MANIFEST_SCHEMA = "MMWAVE_V2_D1_SW02_EVIDENCE_MANIFEST_V1"
VALIDATION_SCHEMA = "MMWAVE_V2_D1_SW02_VALIDATION_V1"
FIXTURE_SEMANTICS = [
    "FIXTURE_ONLY",
    "NON_CAMPAIGN",
    "NOT_D1_MEMBERSHIP",
    "NOT_DATASET_ADMISSIBLE",
]
FIXTURE_BASE_SHA = "13a56b7e41e9519ad61238a74861ef4ad6ea16ab"
NOT_APPLICABLE_BEFORE_CAPTURE = "NOT_APPLICABLE_BEFORE_CAPTURE"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")


class ArtifactValidationError(ValueError):
    """Structured fail-closed validation error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else "%s: %s" % (code, detail)
        super().__init__(message)


def canonical_json(value: Any) -> str:
    """Return the byte-stable JSON representation used by all artifacts."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactValidationError("JSON_READ_FAILED", "%s: %s" % (path, exc)) from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ArtifactValidationError("PATH_OUTSIDE_REPOSITORY", str(path)) from exc


def _load_contract(root: Path) -> Dict[str, Any]:
    contract_path = root / CONTRACT_REL
    contract = load_json(contract_path)
    if not isinstance(contract, dict):
        raise ArtifactValidationError("CONTRACT_NOT_OBJECT", str(CONTRACT_REL))
    if contract.get("contract_id") != CONTRACT_ID:
        raise ArtifactValidationError("CONTRACT_ID_MISMATCH", str(contract.get("contract_id")))
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise ArtifactValidationError("CONTRACT_VERSION_MISMATCH", str(contract.get("schema_version")))
    return contract


def _load_plan(root: Path) -> Dict[str, Any]:
    plan = load_json(root / PLAN_REL)
    if not isinstance(plan, dict):
        raise ArtifactValidationError("PLAN_NOT_OBJECT", str(PLAN_REL))
    return plan


def _reject_unsafe_paths(value: Any, location: str = "root") -> None:
    """Reject machine-readable local paths and traversal fragments."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_unsafe_paths(child, "%s.%s" % (location, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unsafe_paths(child, "%s[%d]" % (location, index))
    elif isinstance(value, str):
        if value.startswith(("/Users/", "/private/", "file://")):
            raise ArtifactValidationError("UNSAFE_PATH", "%s=%s" % (location, value))
        if "\\" in value or ".." in value.split("/"):
            raise ArtifactValidationError("UNSAFE_PATH", "%s=%s" % (location, value))


def _require_mapping(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError("FIELD_TYPE", "%s must be an object" % location)
    return value


def _require_nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactValidationError("FIELD_REQUIRED", location)
    return value


def _require_sha256(value: Any, location: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ArtifactValidationError("INVALID_SHA256", location)
    return value


def _require_git_sha(value: Any, location: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise ArtifactValidationError("INVALID_REPOSITORY_SHA", location)
    return value


def _parse_timestamp(value: Any, location: str) -> _datetime.datetime:
    text = _require_nonempty_string(value, location)
    try:
        parsed = _datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactValidationError("INVALID_TIMESTAMP", location) from exc
    if parsed.tzinfo is None:
        raise ArtifactValidationError("TIMESTAMP_MUST_HAVE_TIMEZONE", location)
    return parsed


def _require_integer(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactValidationError("FIELD_TYPE", "%s must be an integer" % location)
    return value


def _contract_expectations(root: Path) -> Dict[str, Any]:
    contract = _load_contract(root)
    plan = _load_plan(root)
    bounded = contract["bounded_acquisition_campaign"]
    preselection = contract["pre_acquisition_deterministic_selection"]
    stage1 = contract["recording_identity_lifecycle"]["stage_1_pre_capture_identity_lock"]
    selection_fields = list(preselection["required_predeclared_fields"])
    stage1_fields = list(stage1["required"])
    # The contract's predeclaration list mixes artifact-level identity with
    # per-slot identity.  Stage-1 is the authoritative per-slot list; only
    # the two fields that Stage-1 does not repeat are added here.  In
    # particular, contract_id and generator_tool_version remain artifact
    # metadata rather than invented slot fields.
    slot_fields = sorted(
        set(stage1_fields + ["recording_checksum"])
        | (set(selection_fields) - {"contract_id", "generator_tool_version"})
    )
    capture = plan.get("capture_protocol", {})
    return {
        "contract": contract,
        "plan": plan,
        "slot_fields": slot_fields,
        "groups": list(bounded["predeclared_lineage_groups"]),
        "slots_per_group": int(bounded["required_predeclared_recording_slots_per_lineage_group"]),
        "quotas": list(bounded["eligible_absent_context_quota_per_recording"]),
        "selection_rule": str(preselection["selection_rule_version"]),
        "window_seconds": int(capture.get("candidate_context_seconds", 30)),
        "target_seconds": int(capture.get("target_seconds", 5)),
    }


def _validate_fixture_semantics(document: Mapping[str, Any]) -> None:
    semantics = document.get("semantics")
    if not isinstance(semantics, list) or semantics != FIXTURE_SEMANTICS:
        raise ArtifactValidationError("FIXTURE_SEMANTICS_INVALID")
    if document.get("campaign_id") != "FIXTURE_NON_CAMPAIGN_DEMO_V1":
        raise ArtifactValidationError("FIXTURE_CAMPAIGN_ID_INVALID")


def validate_predeclaration(
    document: Mapping[str, Any],
    root: Path = ROOT_DIR,
    require_fixture: bool = False,
) -> Dict[str, Any]:
    """Validate the complete Stage-1 identity lock and fixed 3x3 structure."""

    doc = _require_mapping(document, "predeclaration")
    _reject_unsafe_paths(doc)
    expectations = _contract_expectations(root)
    if doc.get("schema_version") != PREDECLARATION_SCHEMA:
        raise ArtifactValidationError("PREDECLARATION_SCHEMA_MISMATCH")

    for key in (
        "contract_id",
        "contract_version",
        "campaign_id",
        "generator_tool_version",
        "repository_commit_sha",
        "creation_timestamp",
    ):
        _require_nonempty_string(doc.get(key), "predeclaration.%s" % key)
    if doc.get("contract_id") != CONTRACT_ID:
        raise ArtifactValidationError("CONTRACT_ID_MISMATCH", "predeclaration.contract_id")
    if doc.get("contract_version") != CONTRACT_VERSION:
        raise ArtifactValidationError("CONTRACT_VERSION_MISMATCH", "predeclaration.contract_version")
    if doc.get("generator_tool_version") != TOOL_VERSION:
        raise ArtifactValidationError("TOOL_VERSION_MISMATCH", "predeclaration.generator_tool_version")
    _require_git_sha(doc.get("repository_commit_sha"), "predeclaration.repository_commit_sha")
    creation_time = _parse_timestamp(doc.get("creation_timestamp"), "predeclaration.creation_timestamp")

    if require_fixture:
        _validate_fixture_semantics(doc)

    slots = doc.get("slots")
    if not isinstance(slots, list):
        raise ArtifactValidationError("SLOTS_NOT_LIST")
    expected_count = len(expectations["groups"]) * expectations["slots_per_group"]
    if len(slots) != expected_count:
        raise ArtifactValidationError("SLOT_COUNT_MISMATCH", "%d != %d" % (len(slots), expected_count))

    seen_slot_ids = set()
    seen_planned_ids = set()
    grouped: Dict[str, List[Mapping[str, Any]]] = {group: [] for group in expectations["groups"]}
    observed_order: List[Tuple[str, int]] = []
    for index, raw_slot in enumerate(slots):
        slot = _require_mapping(raw_slot, "predeclaration.slots[%d]" % index)
        location = "predeclaration.slots[%d]" % index
        for key in expectations["slot_fields"]:
            if key not in slot:
                raise ArtifactValidationError("SLOT_FIELD_REQUIRED", "%s.%s" % (location, key))
            _require_nonempty_string(slot.get(key), "%s.%s" % (location, key)) if key in {
                "campaign_id",
                "contract_version",
                "repository_commit_sha",
                "creation_timestamp",
                "acquisition_lineage_group_id",
                "recording_slot_id",
                "planned_recording_id",
                "sensor_identity",
                "placement",
                "target_zone",
                "selection_rule_version",
            } else None
        if slot.get("campaign_id") != doc.get("campaign_id"):
            raise ArtifactValidationError("SLOT_CAMPAIGN_MISMATCH", location)
        if slot.get("contract_version") != doc.get("contract_version"):
            raise ArtifactValidationError("SLOT_CONTRACT_VERSION_MISMATCH", location)
        if slot.get("generator_tool_version", doc.get("generator_tool_version")) != doc.get("generator_tool_version"):
            raise ArtifactValidationError("SLOT_TOOL_VERSION_MISMATCH", location)
        if slot.get("repository_commit_sha") != doc.get("repository_commit_sha"):
            raise ArtifactValidationError("SLOT_REPOSITORY_SHA_MISMATCH", location)
        slot_creation = _parse_timestamp(slot.get("creation_timestamp"), "%s.creation_timestamp" % location)
        if slot_creation != creation_time:
            raise ArtifactValidationError("SLOT_CREATION_TIMESTAMP_MISMATCH", location)
        if slot.get("recording_checksum") != NOT_APPLICABLE_BEFORE_CAPTURE:
            raise ArtifactValidationError("PRE_CAPTURE_CHECKSUM_NOT_APPLICABLE", location)
        _require_git_sha(slot.get("repository_commit_sha"), "%s.repository_commit_sha" % location)
        slot_id = str(slot["recording_slot_id"])
        planned_id = str(slot["planned_recording_id"])
        if slot_id in seen_slot_ids:
            raise ArtifactValidationError("DUPLICATE_RECORDING_SLOT_ID", slot_id)
        if planned_id in seen_planned_ids:
            raise ArtifactValidationError("DUPLICATE_PLANNED_RECORDING_ID", planned_id)
        seen_slot_ids.add(slot_id)
        seen_planned_ids.add(planned_id)

        group = str(slot["acquisition_lineage_group_id"])
        if group not in grouped:
            raise ArtifactValidationError("UNKNOWN_LINEAGE_GROUP", group)
        grouped[group].append(slot)
        order = _require_integer(slot.get("recording_order"), "%s.recording_order" % location)
        if order < 1 or order > expectations["slots_per_group"]:
            raise ArtifactValidationError("RECORDING_ORDER_INVALID", location)
        quota = _require_integer(slot.get("context_quota"), "%s.context_quota" % location)
        expected_quota = expectations["quotas"][order - 1]
        if quota != expected_quota:
            raise ArtifactValidationError("CONTEXT_QUOTA_MISMATCH", "%s=%d expected %d" % (location, quota, expected_quota))
        if slot.get("selection_rule_version") != expectations["selection_rule"]:
            raise ArtifactValidationError("SELECTION_RULE_MISMATCH", location)
        if _require_integer(slot.get("window_length_seconds"), "%s.window_length_seconds" % location) != expectations["window_seconds"]:
            raise ArtifactValidationError("WINDOW_LENGTH_MISMATCH", location)
        if _require_integer(slot.get("target_length_seconds"), "%s.target_length_seconds" % location) != expectations["target_seconds"]:
            raise ArtifactValidationError("TARGET_LENGTH_MISMATCH", location)
        start = _parse_timestamp(slot.get("scan_start_time"), "%s.scan_start_time" % location)
        end = _parse_timestamp(slot.get("scan_end_time"), "%s.scan_end_time" % location)
        if end <= start:
            raise ArtifactValidationError("SCAN_INTERVAL_INVALID", location)
        if (end - start).total_seconds() < expectations["window_seconds"]:
            raise ArtifactValidationError("SCAN_INTERVAL_TOO_SHORT", location)
        observed_order.append((group, order))

    orders_by_group: Dict[str, List[int]] = {}
    for group, group_slots in grouped.items():
        if len(group_slots) != expectations["slots_per_group"]:
            raise ArtifactValidationError("LINEAGE_SLOT_COUNT_MISMATCH", "%s=%d" % (group, len(group_slots)))
        orders = [int(slot["recording_order"]) for slot in group_slots]
        if sorted(orders) != list(range(1, expectations["slots_per_group"] + 1)):
            raise ArtifactValidationError("LINEAGE_ORDER_MISMATCH", group)
        orders_by_group[group] = sorted(orders)

    expected_order = [
        (group, order)
        for group in expectations["groups"]
        for order in range(1, expectations["slots_per_group"] + 1)
    ]
    if observed_order != expected_order:
        raise ArtifactValidationError("SLOT_ORDER_NOT_CANONICAL")

    if doc.get("selection_rule_version") is not None and doc.get("selection_rule_version") != expectations["selection_rule"]:
        raise ArtifactValidationError("TOP_LEVEL_SELECTION_RULE_MISMATCH")
    return {
        "status": "PASS",
        "schema_version": PREDECLARATION_SCHEMA,
        "slot_count": len(slots),
        "lineage_group_count": len(grouped),
        "lineage_groups": list(expectations["groups"]),
        "orders_by_group": orders_by_group,
        "total_context_quota": sum(int(slot["context_quota"]) for slot in slots),
        "planned_recording_ids": [str(slot["planned_recording_id"]) for slot in slots],
        "identity_lock": "VALIDATED",
    }


def generate_predeclaration(document: Mapping[str, Any], root: Path = ROOT_DIR) -> Dict[str, Any]:
    """Canonicalize and validate a caller-provided future predeclaration."""

    candidate = copy.deepcopy(dict(document))
    candidate.setdefault("schema_version", PREDECLARATION_SCHEMA)
    if isinstance(candidate.get("slots"), list):
        expectations = _contract_expectations(root)
        group_order = {group: index for index, group in enumerate(expectations["groups"])}

        def slot_sort_key(slot: Any) -> Tuple[int, int, str]:
            if not isinstance(slot, Mapping):
                return (len(group_order), 0, "")
            group = str(slot.get("acquisition_lineage_group_id", ""))
            order = slot.get("recording_order")
            numeric_order = order if isinstance(order, int) and not isinstance(order, bool) else 0
            return (group_order.get(group, len(group_order)), numeric_order, str(slot.get("recording_slot_id", "")))

        candidate["slots"] = sorted(candidate["slots"], key=slot_sort_key)
    validate_predeclaration(candidate, root=root)
    return json.loads(canonical_json(candidate))


def _fixture_timestamp(index: int) -> Tuple[str, str]:
    base = _datetime.datetime(2026, 8, 27, 0, 0, 0, tzinfo=_datetime.timezone.utc)
    start = base + _datetime.timedelta(seconds=index * 600)
    end = start + _datetime.timedelta(seconds=300)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def generate_fixture_predeclaration(root: Path = ROOT_DIR) -> Dict[str, Any]:
    expectations = _contract_expectations(root)
    slots: List[Dict[str, Any]] = []
    slot_number = 0
    for group in expectations["groups"]:
        for order in range(1, expectations["slots_per_group"] + 1):
            scan_start, scan_end = _fixture_timestamp(slot_number)
            slot_number += 1
            slots.append(
                {
                    "acquisition_lineage_group_id": group,
                    "campaign_id": "FIXTURE_NON_CAMPAIGN_DEMO_V1",
                    "context_quota": expectations["quotas"][order - 1],
                    "contract_version": CONTRACT_VERSION,
                    "creation_timestamp": "2026-08-27T00:00:00Z",
                    "generator_tool_version": TOOL_VERSION,
                    "placement": "FIXTURE_RIGID_MOUNT",
                    "planned_recording_id": "FIXTURE_PLANNED_%02d" % slot_number,
                    "recording_checksum": NOT_APPLICABLE_BEFORE_CAPTURE,
                    "recording_order": order,
                    "recording_slot_id": "FIXTURE_SLOT_%02d" % slot_number,
                    "repository_commit_sha": FIXTURE_BASE_SHA,
                    "scan_end_time": scan_end,
                    "scan_start_time": scan_start,
                    "selection_rule_version": expectations["selection_rule"],
                    "sensor_identity": "FIXTURE_SENSOR_ID_V1",
                    "target_length_seconds": expectations["target_seconds"],
                    "target_zone": "FIXTURE_EMPTY_TARGET_ZONE",
                    "window_length_seconds": expectations["window_seconds"],
                }
            )
    document = {
        "campaign_id": "FIXTURE_NON_CAMPAIGN_DEMO_V1",
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "creation_timestamp": "2026-08-27T00:00:00Z",
        "generator_tool_version": TOOL_VERSION,
        "note": "Synthetic metadata only; no governed campaign slot is consumed.",
        "repository_commit_sha": FIXTURE_BASE_SHA,
        "schema_version": PREDECLARATION_SCHEMA,
        "selection_rule_version": expectations["selection_rule"],
        "semantics": list(FIXTURE_SEMANTICS),
        "slots": slots,
    }
    validate_predeclaration(document, root=root, require_fixture=True)
    return json.loads(canonical_json(document))


def _validate_binding_evidence(receipt: Mapping[str, Any], location: str) -> None:
    source = receipt.get("source_provenance")
    if isinstance(source, Mapping):
        if source.get("planned_recording_id") is not None and source.get("planned_recording_id") != receipt.get("planned_recording_id"):
            raise ArtifactValidationError("WRONG_PLANNED_ACTUAL_BINDING", location)
        if source.get("actual_recording_identifier") is not None and source.get("actual_recording_identifier") != receipt.get("actual_recording_identifier"):
            raise ArtifactValidationError("WRONG_ACTUAL_ID_BINDING", location)
    metadata = receipt.get("file_metadata")
    if isinstance(metadata, Mapping):
        if metadata.get("planned_recording_id") is not None and metadata.get("planned_recording_id") != receipt.get("planned_recording_id"):
            raise ArtifactValidationError("WRONG_PLANNED_ACTUAL_BINDING", location)
        if metadata.get("actual_recording_identifier") is not None and metadata.get("actual_recording_identifier") != receipt.get("actual_recording_identifier"):
            raise ArtifactValidationError("WRONG_ACTUAL_ID_BINDING", location)


def _validate_receipt_fields(
    receipt: Mapping[str, Any],
    location: str,
    generator_tool_version: str,
) -> None:
    for key in (
        "planned_recording_id",
        "actual_recording_identifier",
        "sha256",
        "file_metadata",
        "capture_timestamp",
        "source_provenance",
        "generator_tool_version",
    ):
        if key not in receipt:
            raise ArtifactValidationError("RECEIPT_FIELD_REQUIRED", "%s.%s" % (location, key))
    _require_nonempty_string(receipt.get("planned_recording_id"), "%s.planned_recording_id" % location)
    _require_nonempty_string(receipt.get("actual_recording_identifier"), "%s.actual_recording_identifier" % location)
    _require_sha256(receipt.get("sha256"), "%s.sha256" % location)
    metadata = _require_mapping(receipt.get("file_metadata"), "%s.file_metadata" % location)
    if not metadata:
        raise ArtifactValidationError("FILE_METADATA_EMPTY", location)
    source = receipt.get("source_provenance")
    if not isinstance(source, (Mapping, str)) or (isinstance(source, str) and not source.strip()):
        raise ArtifactValidationError("SOURCE_PROVENANCE_INVALID", location)
    _parse_timestamp(receipt.get("capture_timestamp"), "%s.capture_timestamp" % location)
    if receipt.get("generator_tool_version") != generator_tool_version:
        raise ArtifactValidationError("RECEIPT_TOOL_VERSION_MISMATCH", location)
    _validate_binding_evidence(receipt, location)


def validate_receipts(
    predeclaration: Mapping[str, Any],
    receipts_document: Mapping[str, Any],
    root: Path = ROOT_DIR,
    require_complete: bool = True,
) -> Dict[str, Any]:
    """Validate Stage-2 receipts and exact one-to-one planned/actual binding."""

    try:
        predecl_result = validate_predeclaration(predeclaration, root=root)
    except ArtifactValidationError as exc:
        raise ArtifactValidationError("PREDECLARATION_IDENTITY_LOCK_REQUIRED", str(exc)) from exc
    receipts = _require_mapping(receipts_document, "receipts")
    _reject_unsafe_paths(receipts)
    if receipts.get("schema_version") != RECEIPTS_SCHEMA:
        raise ArtifactValidationError("RECEIPTS_SCHEMA_MISMATCH")
    if receipts.get("generator_tool_version") != predeclaration.get("generator_tool_version"):
        raise ArtifactValidationError("RECEIPTS_TOOL_VERSION_MISMATCH")
    if "semantics" in predeclaration:
        if receipts.get("semantics") != predeclaration.get("semantics"):
            raise ArtifactValidationError("RECEIPTS_SEMANTICS_MISMATCH")
    raw_receipts = receipts.get("receipts")
    if not isinstance(raw_receipts, list):
        raise ArtifactValidationError("RECEIPTS_NOT_LIST")
    planned_ids = set(predecl_result["planned_recording_ids"])
    seen_planned = set()
    seen_actual = set()
    normalized: List[Mapping[str, Any]] = []
    for index, raw_receipt in enumerate(raw_receipts):
        receipt = _require_mapping(raw_receipt, "receipts.receipts[%d]" % index)
        location = "receipts.receipts[%d]" % index
        _validate_receipt_fields(receipt, location, str(predeclaration.get("generator_tool_version")))
        planned_id = str(receipt["planned_recording_id"])
        actual_id = str(receipt["actual_recording_identifier"])
        if planned_id not in planned_ids:
            raise ArtifactValidationError("EXTRA_UNPLANNED_ACTUAL_RECORDING", planned_id)
        if planned_id in seen_planned:
            raise ArtifactValidationError("DUPLICATE_PLANNED_RECEIPT", planned_id)
        if actual_id in seen_actual:
            raise ArtifactValidationError("DUPLICATE_ACTUAL_RECORDING_ID", actual_id)
        seen_planned.add(planned_id)
        seen_actual.add(actual_id)
        normalized.append(receipt)
    missing = sorted(planned_ids - seen_planned)
    if require_complete and missing:
        raise ArtifactValidationError("MISSING_PLANNED_RECEIPT", ",".join(missing))
    if require_complete and len(seen_planned) != len(planned_ids):
        raise ArtifactValidationError("RECEIPT_BINDING_INCOMPLETE")
    expected_order = {planned_id: index for index, planned_id in enumerate(predecl_result["planned_recording_ids"])}
    ordered_ids = [str(item["planned_recording_id"]) for item in normalized]
    if require_complete and ordered_ids != [planned_id for planned_id in predecl_result["planned_recording_ids"]]:
        raise ArtifactValidationError("RECEIPT_ORDER_NOT_CANONICAL")
    return {
        "status": "PASS",
        "schema_version": RECEIPTS_SCHEMA,
        "receipt_count": len(normalized),
        "planned_count": len(planned_ids),
        "actual_count": len(seen_actual),
        "complete_binding": len(seen_planned) == len(planned_ids),
        "binding_order": [planned_id for planned_id in predecl_result["planned_recording_ids"] if planned_id in expected_order],
    }


def generate_receipts(
    predeclaration: Mapping[str, Any],
    actual_records: Sequence[Mapping[str, Any]],
    root: Path = ROOT_DIR,
) -> Dict[str, Any]:
    """Generate canonical receipts from caller-supplied actual metadata."""

    predecl_result = validate_predeclaration(predeclaration, root=root)
    if len(actual_records) != predecl_result["slot_count"]:
        raise ArtifactValidationError("ACTUAL_RECORD_COUNT_MISMATCH")
    records_by_planned: Dict[str, Dict[str, Any]] = {}
    for index, raw_record in enumerate(actual_records):
        record = dict(_require_mapping(raw_record, "actual_records[%d]" % index))
        if "sha256" not in record and "payload" in record:
            payload = record.pop("payload")
            if not isinstance(payload, (bytes, bytearray)):
                raise ArtifactValidationError("PAYLOAD_MUST_BE_BYTES", "actual_records[%d]" % index)
            record["sha256"] = sha256_bytes(bytes(payload))
            metadata = dict(record.get("file_metadata") or {})
            metadata.setdefault("size_bytes", len(payload))
            record["file_metadata"] = metadata
        record.setdefault("generator_tool_version", predeclaration.get("generator_tool_version"))
        _validate_receipt_fields(record, "actual_records[%d]" % index, str(predeclaration.get("generator_tool_version")))
        planned_id = str(record["planned_recording_id"])
        if planned_id not in set(predecl_result["planned_recording_ids"]):
            raise ArtifactValidationError("EXTRA_UNPLANNED_ACTUAL_RECORDING", planned_id)
        if planned_id in records_by_planned:
            raise ArtifactValidationError("DUPLICATE_PLANNED_RECEIPT", planned_id)
        records_by_planned[planned_id] = record
    missing = [planned_id for planned_id in predecl_result["planned_recording_ids"] if planned_id not in records_by_planned]
    if missing:
        raise ArtifactValidationError("MISSING_PLANNED_RECEIPT", ",".join(missing))
    receipts = [records_by_planned[planned_id] for planned_id in predecl_result["planned_recording_ids"]]
    output: Dict[str, Any] = {
        "generator_tool_version": str(predeclaration["generator_tool_version"]),
        "receipts": receipts,
        "schema_version": RECEIPTS_SCHEMA,
    }
    if "semantics" in predeclaration:
        output["semantics"] = copy.deepcopy(predeclaration["semantics"])
    validate_receipts(predeclaration, output, root=root)
    return json.loads(canonical_json(output))


def generate_fixture_receipts(predeclaration: Mapping[str, Any], root: Path = ROOT_DIR) -> Dict[str, Any]:
    slots = list(predeclaration.get("slots", []))
    actual_records: List[Dict[str, Any]] = []
    for index, slot in enumerate(slots, start=1):
        payload = ("SW02_FIXTURE_RECORDING_%02d\n" % index).encode("ascii")
        planned_id = str(slot["planned_recording_id"])
        actual_id = "FIXTURE_ACTUAL_%02d" % index
        actual_records.append(
            {
                "actual_recording_identifier": actual_id,
                "capture_timestamp": "2026-08-27T01:%02d:00Z" % (index - 1),
                "file_metadata": {
                    "actual_recording_identifier": actual_id,
                    "artifact_name": "fixture_actual_%02d.bin" % index,
                    "size_bytes": len(payload),
                },
                "generator_tool_version": TOOL_VERSION,
                "payload": payload,
                "planned_recording_id": planned_id,
                "source_provenance": {
                    "actual_recording_identifier": actual_id,
                    "fixture": True,
                    "planned_recording_id": planned_id,
                    "recording_slot_id": str(slot["recording_slot_id"]),
                },
            }
        )
    return generate_receipts(predeclaration, actual_records, root=root)


def _fixture_execution_receipt(predecl: Mapping[str, Any], receipts: Mapping[str, Any]) -> Dict[str, Any]:
    predecl_result = validate_predeclaration(predecl, require_fixture=True)
    receipt_result = validate_receipts(predecl, receipts)
    return {
        "complete_nine_slot_binding": receipt_result["complete_binding"],
        "d1_membership_entries_created": 0,
        "generator_tool_version": TOOL_VERSION,
        "identity_lock_validation": predecl_result["identity_lock"],
        "lineage_group_count": predecl_result["lineage_group_count"],
        "planned_actual_binding_validation": receipt_result["status"],
        "real_campaign_predeclaration_created": False,
        "real_slot_consumed": False,
        "schema_version": FIXTURE_EXECUTION_SCHEMA,
        "semantics": list(FIXTURE_SEMANTICS),
        "slot_count": predecl_result["slot_count"],
        "terminal_scope": "FIXTURE_ONLY_NON_CAMPAIGN",
    }


def _write_checksums(paths: Iterable[Path], root: Path, out_dir: Path) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    for path in sorted(paths, key=lambda item: _repo_relative(item, root)):
        entries[_repo_relative(path, root)] = sha256_file(path)
    checksums_json = out_dir / "checksums.json"
    checksums_sha = out_dir / "checksums.sha256"
    write_json(checksums_json, {"algorithm": "sha256", "files": entries})
    checksums_sha.write_text(
        "".join("%s  %s\n" % (digest, name) for name, digest in entries.items()),
        encoding="utf-8",
    )
    return entries


def build_fixture_bundle(output_dir: Path, root: Path = ROOT_DIR) -> Dict[str, Any]:
    """Generate and validate the non-campaign fixture evidence bundle."""

    output_dir = output_dir.resolve()
    _repo_relative(output_dir, root)
    fixtures_dir = output_dir / "fixtures"
    predecl_path = fixtures_dir / "fixture_predeclaration.json"
    receipts_path = fixtures_dir / "fixture_post_capture_checksum_receipts.json"
    execution_path = output_dir / "fixture_execution_receipt.json"
    validation_path = output_dir / "validation_result.json"
    evidence_path = output_dir / "evidence_manifest.json"
    predecl = generate_fixture_predeclaration(root=root)
    receipts = generate_fixture_receipts(predecl, root=root)
    write_json(predecl_path, predecl)
    write_json(receipts_path, receipts)
    predecl_result = validate_predeclaration(predecl, root=root, require_fixture=True)
    receipts_result = validate_receipts(predecl, receipts, root=root)
    execution = _fixture_execution_receipt(predecl, receipts)
    write_json(execution_path, execution)
    validation = {
        "deterministic_predeclaration": canonical_json_bytes(generate_fixture_predeclaration(root=root)) == predecl_path.read_bytes(),
        "deterministic_receipts": canonical_json_bytes(generate_fixture_receipts(predecl, root=root)) == receipts_path.read_bytes(),
        "predeclaration": predecl_result,
        "receipts": receipts_result,
        "schema_version": VALIDATION_SCHEMA,
        "status": "PASS",
    }
    write_json(validation_path, validation)
    checksums = _write_checksums([predecl_path, receipts_path, execution_path, validation_path], root, output_dir)
    contract_path = root / CONTRACT_REL
    tool_path = root / TOOL_REL
    validator_path = root / VALIDATOR_REL
    evidence: Dict[str, Any] = {
        "base": {
            "origin_main_sha": FIXTURE_BASE_SHA,
            "pr170_merged": True,
            "pr170_merge_commit": FIXTURE_BASE_SHA,
        },
        "contract": {
            "contract_id": CONTRACT_ID,
            "contract_version": CONTRACT_VERSION,
            "path": CONTRACT_REL.as_posix(),
            "sha256": sha256_file(contract_path),
        },
        "fixture": {
            "d1_membership_entries_created": 0,
            "groups": predecl_result["lineage_group_count"],
            "nine_slots": predecl_result["slot_count"],
            "planned_actual_binding": "PASS",
            "predeclaration": {
                "path": _repo_relative(predecl_path, root),
                "sha256": sha256_file(predecl_path),
            },
            "receipts": {
                "path": _repo_relative(receipts_path, root),
                "sha256": sha256_file(receipts_path),
            },
            "real_campaign_predeclaration_created": False,
            "real_slot_consumed": False,
            "semantics": list(FIXTURE_SEMANTICS),
            "slots_per_group": 3,
            "total_context_quota": predecl_result["total_context_quota"],
        },
        "generator": {
            "path": TOOL_REL.as_posix(),
            "sha256": sha256_file(tool_path),
            "tool_version": TOOL_VERSION,
        },
        "manifest_scope": "FIXTURE_ONLY_NON_CAMPAIGN",
        "phase": PHASE_ID,
        "schema_version": EVIDENCE_MANIFEST_SCHEMA,
        "terminal_verdict": "SW02_IMPLEMENTED_FIXTURE_VALIDATED",
        "validation": {
            "checksums": _repo_relative(output_dir / "checksums.sha256", root),
            "result": _repo_relative(validation_path, root),
            "status": "PASS",
        },
    }
    if validator_path.is_file():
        evidence["validator"] = {
            "path": VALIDATOR_REL.as_posix(),
            "sha256": sha256_file(validator_path),
        }
    write_json(evidence_path, evidence)
    # Re-read and validate the generated bundle, including byte-stable output.
    result = validate_fixture_bundle(root=root, manifest_dir=output_dir)
    result["evidence_manifest"] = _repo_relative(evidence_path, root)
    result["checksums"] = checksums
    return result


def _validate_checksums(root: Path, manifest_dir: Path) -> Dict[str, str]:
    checksums_json_path = manifest_dir / "checksums.json"
    checksums_sha_path = manifest_dir / "checksums.sha256"
    checksums_doc = _require_mapping(load_json(checksums_json_path), "checksums.json")
    files = _require_mapping(checksums_doc.get("files"), "checksums.json.files")
    listed: Dict[str, str] = {}
    for line in checksums_sha_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        pieces = line.split("  ", 1)
        if len(pieces) != 2 or not SHA256_RE.fullmatch(pieces[0]):
            raise ArtifactValidationError("CHECKSUM_LINE_INVALID", line)
        listed[pieces[1]] = pieces[0]
    if dict(files) != listed:
        raise ArtifactValidationError("CHECKSUM_JSON_LIST_MISMATCH")
    for relative, digest in listed.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ArtifactValidationError("CHECKSUM_MISMATCH", relative)
    return dict(listed)


def validate_fixture_bundle(root: Path = ROOT_DIR, manifest_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Validate only the checked-in SW-02 fixture evidence."""

    if manifest_dir is None:
        manifest_dir = root / "datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01"
    manifest_dir = manifest_dir.resolve()
    required = [
        manifest_dir / "fixtures/fixture_predeclaration.json",
        manifest_dir / "fixtures/fixture_post_capture_checksum_receipts.json",
        manifest_dir / "fixture_execution_receipt.json",
        manifest_dir / "validation_result.json",
        manifest_dir / "evidence_manifest.json",
        manifest_dir / "checksums.json",
        manifest_dir / "checksums.sha256",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ArtifactValidationError("FIXTURE_ARTIFACT_MISSING", ",".join(missing))
    predecl_path = manifest_dir / "fixtures/fixture_predeclaration.json"
    receipts_path = manifest_dir / "fixtures/fixture_post_capture_checksum_receipts.json"
    predecl = _require_mapping(load_json(predecl_path), "fixture_predeclaration")
    receipts = _require_mapping(load_json(receipts_path), "fixture_receipts")
    predecl_result = validate_predeclaration(predecl, root=root, require_fixture=True)
    receipt_result = validate_receipts(predecl, receipts, root=root)
    execution = _require_mapping(load_json(manifest_dir / "fixture_execution_receipt.json"), "fixture_execution_receipt")
    if execution.get("schema_version") != FIXTURE_EXECUTION_SCHEMA:
        raise ArtifactValidationError("EXECUTION_SCHEMA_MISMATCH")
    if execution.get("real_campaign_predeclaration_created") is not False or execution.get("real_slot_consumed") is not False or execution.get("d1_membership_entries_created") != 0:
        raise ArtifactValidationError("REAL_CAMPAIGN_SEMANTICS_VIOLATION")
    if execution.get("complete_nine_slot_binding") is not True:
        raise ArtifactValidationError("COMPLETE_BINDING_NOT_CONFIRMED")
    validation = _require_mapping(load_json(manifest_dir / "validation_result.json"), "validation_result")
    if validation.get("status") != "PASS" or validation.get("deterministic_predeclaration") is not True or validation.get("deterministic_receipts") is not True:
        raise ArtifactValidationError("VALIDATION_RESULT_NOT_PASS")
    evidence = _require_mapping(load_json(manifest_dir / "evidence_manifest.json"), "evidence_manifest")
    _reject_unsafe_paths(evidence)
    if evidence.get("schema_version") != EVIDENCE_MANIFEST_SCHEMA or evidence.get("terminal_verdict") != "SW02_IMPLEMENTED_FIXTURE_VALIDATED":
        raise ArtifactValidationError("EVIDENCE_MANIFEST_STATUS_INVALID")
    fixture = _require_mapping(evidence.get("fixture"), "evidence_manifest.fixture")
    if fixture.get("nine_slots") != 9 or fixture.get("groups") != 3 or fixture.get("slots_per_group") != 3 or fixture.get("total_context_quota") != 57:
        raise ArtifactValidationError("FIXTURE_STRUCTURE_INVALID")
    if fixture.get("real_campaign_predeclaration_created") is not False or fixture.get("real_slot_consumed") is not False or fixture.get("d1_membership_entries_created") != 0:
        raise ArtifactValidationError("EVIDENCE_REAL_CAMPAIGN_VIOLATION")
    if fixture.get("planned_actual_binding") != "PASS":
        raise ArtifactValidationError("FIXTURE_BINDING_NOT_PASS")
    checksums = _validate_checksums(root, manifest_dir)
    if checksums.get(_repo_relative(predecl_path, root)) != sha256_file(predecl_path):
        raise ArtifactValidationError("PREDECLARATION_CHECKSUM_MISSING")
    if checksums.get(_repo_relative(receipts_path, root)) != sha256_file(receipts_path):
        raise ArtifactValidationError("RECEIPTS_CHECKSUM_MISSING")
    if canonical_json_bytes(generate_fixture_predeclaration(root=root)) != predecl_path.read_bytes():
        raise ArtifactValidationError("PREDECLARATION_NON_DETERMINISTIC")
    if canonical_json_bytes(generate_fixture_receipts(predecl, root=root)) != receipts_path.read_bytes():
        raise ArtifactValidationError("RECEIPTS_NON_DETERMINISTIC")
    return {
        "status": "PASS",
        "phase": PHASE_ID,
        "terminal_verdict": "SW02_IMPLEMENTED_FIXTURE_VALIDATED",
        "predeclaration": predecl_result,
        "receipts": receipt_result,
        "real_campaign_predeclaration_created": False,
        "real_slot_consumed": False,
        "d1_membership_entries_created": 0,
        "manifest_dir": _repo_relative(manifest_dir, root),
    }


def _load_actual_records(path: Path) -> List[Mapping[str, Any]]:
    document = load_json(path)
    if isinstance(document, list):
        return [_require_mapping(item, "actual_records") for item in document]
    if isinstance(document, Mapping) and isinstance(document.get("records"), list):
        return [_require_mapping(item, "actual_records") for item in document["records"]]
    raise ArtifactValidationError("ACTUAL_RECORDS_NOT_LIST")


def _result_or_error(function: Any) -> int:
    try:
        result = function()
    except ArtifactValidationError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "detail": exc.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    fixture = sub.add_parser("generate-fixture-bundle", help="generate only the deterministic non-campaign fixture bundle")
    fixture.add_argument("--output-dir", type=Path, required=True)

    gen_pre = sub.add_parser("generate-predeclaration", help="canonicalize a future predeclaration JSON")
    gen_pre.add_argument("--input", type=Path, required=True)
    gen_pre.add_argument("--output", type=Path, required=True)

    gen_receipts = sub.add_parser("generate-receipts", help="generate a canonical receipt set from actual metadata JSON")
    gen_receipts.add_argument("--predeclaration", type=Path, required=True)
    gen_receipts.add_argument("--actual-records", type=Path, required=True)
    gen_receipts.add_argument("--output", type=Path, required=True)

    val_pre = sub.add_parser("validate-predeclaration", help="validate a Stage-1 identity lock")
    val_pre.add_argument("--input", type=Path, required=True)

    val_receipts = sub.add_parser("validate-receipts", help="validate complete Stage-2 receipts")
    val_receipts.add_argument("--predeclaration", type=Path, required=True)
    val_receipts.add_argument("--receipts", type=Path, required=True)

    verify = sub.add_parser("verify-binding", help="verify complete nine-slot binding")
    verify.add_argument("--predeclaration", type=Path, required=True)
    verify.add_argument("--receipts", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    if args.command == "generate-fixture-bundle":
        return _result_or_error(lambda: build_fixture_bundle(args.output_dir, root=ROOT_DIR))
    if args.command == "generate-predeclaration":
        def generate_pre() -> Dict[str, Any]:
            output = generate_predeclaration(_require_mapping(load_json(args.input), "predeclaration"), root=ROOT_DIR)
            write_json(args.output, output)
            return {"status": "PASS", "output": _repo_relative(args.output, ROOT_DIR), "tool_version": TOOL_VERSION}
        return _result_or_error(generate_pre)
    if args.command == "generate-receipts":
        def generate_rec() -> Dict[str, Any]:
            predecl = _require_mapping(load_json(args.predeclaration), "predeclaration")
            output = generate_receipts(predecl, _load_actual_records(args.actual_records), root=ROOT_DIR)
            write_json(args.output, output)
            return {"status": "PASS", "output": _repo_relative(args.output, ROOT_DIR), "receipt_count": len(output["receipts"]), "tool_version": TOOL_VERSION}
        return _result_or_error(generate_rec)
    if args.command == "validate-predeclaration":
        return _result_or_error(lambda: validate_predeclaration(_require_mapping(load_json(args.input), "predeclaration"), root=ROOT_DIR))
    if args.command in ("validate-receipts", "verify-binding"):
        def validate_rec() -> Dict[str, Any]:
            predecl = _require_mapping(load_json(args.predeclaration), "predeclaration")
            receipts = _require_mapping(load_json(args.receipts), "receipts")
            return validate_receipts(predecl, receipts, root=ROOT_DIR)
        return _result_or_error(validate_rec)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
