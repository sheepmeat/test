"""Focused tests for fixture and operational non-campaign SW-03/SW-04 tooling."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mmwave.m_pv38_evidence_registry import (
    DEFAULT_MANIFEST_DIR,
    FIXTURE_FILES,
    OPERATIONAL_EXAMPLES_FILE,
    REGISTRY_FILES,
    SCHEMA_FILES,
    _hash_receipts,
    _read_d1_state,
    _synthetic_payloads,
    build_synthetic_bundle,
    read_json,
    registry_schema_documents,
    validate_bundle,
    validate_registry_records,
)
from scripts.mmwave.m_pv38_evidence_sync_hash import (
    FIXTURE_SEMANTICS,
    LIVE_DEBUG_NON_CAMPAIGN,
    OPERATIONAL_SEMANTICS,
    _find_forbidden_keys,
    create_hash_receipt,
    create_hash_receipt_from_file,
    create_sync_record,
    evidence_scope_schema_document,
    hash_receipt_schema_document,
    sha256_bytes,
    sync_record_schema_document,
    validate_hash_receipt,
    validate_hash_receipts,
    validate_sync_records,
    verify_hash_receipt,
    verify_hash_receipt_from_file,
    _main as sync_cli_main,
)


ROOT = Path(__file__).resolve().parents[1]


def _bundle_records() -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    sync_records = read_json(DEFAULT_MANIFEST_DIR / "sync_records.json")["records"]
    receipts = read_json(DEFAULT_MANIFEST_DIR / "hash_receipts.json")["receipts"]
    registries = {
        kind: read_json(DEFAULT_MANIFEST_DIR / filename)["records"] for kind, filename in REGISTRY_FILES.items()
    }
    return sync_records, receipts, registries


def test_bundle_schema_validation_is_green() -> None:
    result = validate_bundle(DEFAULT_MANIFEST_DIR)
    assert result["ok"] is True
    assert result["terminal_verdict"] == "SW03_SW04_SOFTWARE_COMPLETE_LIVE_EVIDENCE_PENDING"
    assert result["fixture_pipeline_status"] == "COMPLETE"
    assert result["operational_non_campaign_pipeline_status"] == "COMPLETE"
    assert result["actual_file_hash_pipeline_status"] == "COMPLETE"
    assert result["cross_registry_integrity_status"] == "COMPLETE"
    assert result["live_hardware_evidence_status"] == "NOT_EXECUTED"
    assert set(SCHEMA_FILES) == set(registry_schema_documents()) | {"scope", "sync", "hash"}
    assert read_json(DEFAULT_MANIFEST_DIR / SCHEMA_FILES["scope"]) == evidence_scope_schema_document()
    assert read_json(DEFAULT_MANIFEST_DIR / SCHEMA_FILES["sync"]) == sync_record_schema_document()
    assert read_json(DEFAULT_MANIFEST_DIR / SCHEMA_FILES["hash"]) == hash_receipt_schema_document()


def test_hashing_is_deterministic_and_does_not_store_payload() -> None:
    payload = b"deterministic-fixture-payload"
    receipt = create_hash_receipt(
        "TEST-EVIDENCE-001",
        "SENSOR_OBSERVATION",
        "TEST-SOURCE-001",
        "TEST-REFERENCE-001",
        payload=payload,
        file_reference="fixtures/non_campaign/test_payload.bin",
        fixture_semantics=FIXTURE_SEMANTICS,
    )
    assert receipt["sha256"] == sha256_bytes(payload)
    assert verify_hash_receipt(receipt, payload=payload) is True
    assert "payload" not in receipt
    assert create_hash_receipt(
        "TEST-EVIDENCE-001",
        "SENSOR_OBSERVATION",
        "TEST-SOURCE-001",
        "TEST-REFERENCE-001",
        payload=payload,
        file_reference="fixtures/non_campaign/test_payload.bin",
        fixture_semantics=FIXTURE_SEMANTICS,
    ) == receipt


def test_live_debug_hash_receipt_is_non_campaign_without_fixture_lock() -> None:
    payload = b"live-debug-operational-shape"
    receipt = create_hash_receipt(
        "DEBUG-TEST-EVIDENCE-001",
        "SENSOR_OBSERVATION",
        "DEBUG-TEST-SOURCE-001",
        "DEBUG-TEST-REFERENCE-001",
        payload=payload,
        file_reference="operational/non_campaign/evidence/debug_001.bin",
        scope=LIVE_DEBUG_NON_CAMPAIGN,
    )
    assert receipt["evidence_scope"] == LIVE_DEBUG_NON_CAMPAIGN
    assert receipt["scope_semantics"] == OPERATIONAL_SEMANTICS
    assert "fixture_semantics" not in receipt
    assert receipt["live_evidence_status"] == "LIVE_DEBUG_NON_CAMPAIGN_OBSERVED"
    assert validate_hash_receipt(receipt) == []
    assert validate_hash_receipts([receipt], actual_digests={receipt["evidence_id"]: sha256_bytes(payload)}) == []


def test_real_temporary_file_hash_path_is_complete_without_payload_copy() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "debug_evidence.bin"
        source.write_bytes(b"temporary operational evidence")
        receipt = create_hash_receipt_from_file(
            source,
            "DEBUG-TEST-FILE-EVIDENCE-001",
            "SENSOR_OBSERVATION",
            "DEBUG-TEST-FILE-SOURCE-001",
            scope=LIVE_DEBUG_NON_CAMPAIGN,
        )
        assert receipt["sha256"] == sha256_bytes(source.read_bytes())
        assert receipt["size_bytes"] == source.stat().st_size
        assert str(source) not in json.dumps(receipt)
        assert verify_hash_receipt_from_file(receipt, source) is True
        source.write_bytes(b"changed")
        assert verify_hash_receipt_from_file(receipt, source) is False


def test_caller_supplied_live_debug_sync_records_validate() -> None:
    shared = create_sync_record(
        "SYNC-DEBUG-TEST-SHARED-001",
        "SHARED_CLOCK",
        "DEBUG-TEST-SENSOR",
        "DEBUG-TEST-CLOCK",
        "2026-08-27T00:20:00.000Z",
        2.0,
        host_timestamp="2026-08-27T00:20:00.002Z",
        uncertainty_ms=1.0,
        scope=LIVE_DEBUG_NON_CAMPAIGN,
    )
    marker = create_sync_record(
        "SYNC-DEBUG-TEST-MARKER-001",
        "EXPLICIT_SYNC_MARKER",
        "DEBUG-TEST-REFERENCE",
        "DEBUG-TEST-CLOCK-PAIR",
        "2026-08-27T00:20:05.000Z",
        4.0,
        host_timestamp="2026-08-27T00:20:05.004Z",
        sync_marker_id="DEBUG-TEST-MARKER-001",
        source_marker_observed=True,
        host_marker_observed=True,
        uncertainty_ms=1.0,
        scope=LIVE_DEBUG_NON_CAMPAIGN,
    )
    assert validate_sync_records([shared, marker]) == []
    assert shared["validation_status"] == "LIVE_NON_CAMPAIGN_ALIGNMENT_OBSERVED"
    assert marker["method"] == "EXPLICIT_SYNC_MARKER"
    assert marker["scope_semantics"] == OPERATIONAL_SEMANTICS


def test_operational_hash_and_sync_cli_paths_are_usable() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source = temp / "debug_payload.bin"
        receipt_file = temp / "receipt.json"
        sync_file = temp / "sync.json"
        source.write_bytes(b"cli operational evidence")
        assert sync_cli_main([
            "hash-file",
            "--scope",
            LIVE_DEBUG_NON_CAMPAIGN,
            "--evidence-id",
            "CLI-DEBUG-EVIDENCE-001",
            "--evidence-type",
            "SENSOR_OBSERVATION",
            "--source-id",
            "CLI-SOURCE-001",
            "--file",
            str(source),
            "--output",
            str(receipt_file),
        ]) == 0
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        assert receipt["evidence_scope"] == LIVE_DEBUG_NON_CAMPAIGN
        assert str(source) not in receipt_file.read_text(encoding="utf-8")
        assert sync_cli_main(["verify-hash-receipt", "--receipt-file", str(receipt_file), "--file", str(source)]) == 0
        assert sync_cli_main([
            "create-sync-record",
            "--scope",
            LIVE_DEBUG_NON_CAMPAIGN,
            "--sync-record-id",
            "CLI-DEBUG-SYNC-001",
            "--method",
            "EXPLICIT_SYNC_MARKER",
            "--source-id",
            "CLI-SOURCE-001",
            "--clock-identity",
            "CLI-CLOCK-001",
            "--source-timestamp",
            "2026-08-27T00:30:00.000Z",
            "--host-timestamp",
            "2026-08-27T00:30:00.005Z",
            "--sync-marker-id",
            "CLI-MARKER-001",
            "--source-marker-observed",
            "--host-marker-observed",
            "--measured-offset-delta-ms",
            "5",
            "--uncertainty-ms",
            "1",
            "--output",
            str(sync_file),
        ]) == 0
        assert validate_sync_records([json.loads(sync_file.read_text(encoding="utf-8"))]) == []


def _operational_examples() -> dict:
    return read_json(DEFAULT_MANIFEST_DIR / OPERATIONAL_EXAMPLES_FILE)


def test_operational_registries_validate_and_keep_non_final_states() -> None:
    examples = _operational_examples()
    known_types = {record["evidence_id"]: record["evidence_type"] for record in examples["hash_receipts"]}
    known_ids = set(known_types)
    sync_ids = {record["sync_record_id"] for record in examples["sync_records"]}
    health_ids = {record["registry_record_id"] for record in examples["registries"]["health"]}
    rejection_ids = {record["rejection_record_id"] for record in examples["registries"]["rejection"]}
    for kind, records in examples["registries"].items():
        assert validate_registry_records(
            kind,
            records,
            known_evidence_ids=known_ids,
            known_sync_ids=sync_ids,
            known_evidence_types=known_types,
            known_health_registry_ids=health_ids,
            known_rejection_registry_ids=rejection_ids,
        ) == []
    assert all(record["evidence_scope"] == LIVE_DEBUG_NON_CAMPAIGN for records in examples["registries"].values() for record in records)
    assert next(record for record in examples["registries"]["occupancy"] if record["occupancy_state"] == "REFERENCE_MISSING")["absent_eligibility"] == "NOT_ELIGIBLE"


def test_dangling_health_and_rejection_registry_links_are_rejected() -> None:
    examples = _operational_examples()
    known_types = {record["evidence_id"]: record["evidence_type"] for record in examples["hash_receipts"]}
    common = {
        "known_evidence_ids": set(known_types),
        "known_sync_ids": {record["sync_record_id"] for record in examples["sync_records"]},
        "known_evidence_types": known_types,
        "known_health_registry_ids": {record["registry_record_id"] for record in examples["registries"]["health"]},
        "known_rejection_registry_ids": {record["rejection_record_id"] for record in examples["registries"]["rejection"]},
    }
    provenance = copy.deepcopy(examples["registries"]["provenance"][0])
    provenance["health_registry_record_id"] = "HEALTH-DEBUG-MISSING"
    assert any("dangling health registry reference" in error for error in validate_registry_records("provenance", [provenance], **common))
    provenance = copy.deepcopy(examples["registries"]["provenance"][0])
    provenance["rejection_registry_record_id"] = "REJECTION-DEBUG-MISSING"
    assert any("dangling rejection registry reference" in error for error in validate_registry_records("provenance", [provenance], **common))


def test_unknown_hash_and_sync_references_are_rejected() -> None:
    examples = _operational_examples()
    known_types = {record["evidence_id"]: record["evidence_type"] for record in examples["hash_receipts"]}
    common = {
        "known_evidence_ids": set(known_types),
        "known_sync_ids": {record["sync_record_id"] for record in examples["sync_records"]},
        "known_evidence_types": known_types,
        "known_health_registry_ids": {record["registry_record_id"] for record in examples["registries"]["health"]},
        "known_rejection_registry_ids": {record["rejection_record_id"] for record in examples["registries"]["rejection"]},
    }
    occupancy = copy.deepcopy(next(record for record in examples["registries"]["occupancy"] if record["occupancy_state"] == "REFERENCE_PRESENT_UNREVIEWED"))
    occupancy["hash_receipt_ids"].append("DEBUG-EVIDENCE-UNKNOWN")
    assert any("unknown evidence reference DEBUG-EVIDENCE-UNKNOWN" in error for error in validate_registry_records("occupancy", [occupancy], **common))
    occupancy = copy.deepcopy(next(record for record in examples["registries"]["occupancy"] if record["occupancy_state"] == "REFERENCE_PRESENT_UNREVIEWED"))
    occupancy["sync_evidence_ids"].append("SYNC-DEBUG-UNKNOWN")
    assert any("sync evidence references are invalid" in error for error in validate_registry_records("occupancy", [occupancy], **common))


def test_duplicate_immutable_evidence_id_is_rejected() -> None:
    _, receipts, _ = _bundle_records()
    errors = validate_hash_receipts([receipts[0], copy.deepcopy(receipts[0])])
    assert any("duplicate immutable evidence_id" in error for error in errors)


def test_malformed_and_mismatched_sha_are_rejected() -> None:
    _, receipts, _ = _bundle_records()
    malformed = copy.deepcopy(receipts[0])
    malformed["sha256"] = "not-a-sha256"
    assert validate_hash_receipts([malformed])
    mismatch = copy.deepcopy(receipts[0])
    mismatch["sha256"] = "f" * 64
    assert verify_hash_receipt(mismatch, actual_sha256=receipts[0]["sha256"]) is False
    errors = validate_hash_receipts([mismatch], actual_digests={mismatch["evidence_id"]: receipts[0]["sha256"]})
    assert any("hash mismatch" in error for error in errors)


def test_missing_occupancy_is_incomplete_not_absent() -> None:
    sync_records, receipts, registries = _bundle_records()
    missing = next(record for record in registries["occupancy"] if record["occupancy_state"] == "UNKNOWN_REFERENCE_MISSING")
    errors = validate_registry_records(
        "occupancy",
        [missing],
        known_evidence_ids={record["evidence_id"] for record in receipts},
        known_sync_ids={record["sync_record_id"] for record in sync_records},
    )
    assert errors == []
    assert missing["review_status"] == "INCOMPLETE_REVIEW_REQUIRED"
    assert missing["absent_eligibility"] == "NOT_ELIGIBLE"
    assert missing["physiology_label"] is None


def test_health_fault_is_retained_without_physiology_semantics() -> None:
    sync_records, receipts, registries = _bundle_records()
    fault = next(record for record in registries["health"] if record["fault_code"] is not None)
    errors = validate_registry_records(
        "health",
        [fault],
        known_evidence_ids={record["evidence_id"] for record in receipts},
        known_sync_ids={record["sync_record_id"] for record in sync_records},
    )
    assert errors == []
    assert fault["health_state"] == "FAULT_RETAINED"
    assert fault["physiology_interpretation"] == "NOT_PROVIDED"


def test_rejection_is_retained_and_not_eligible_absent() -> None:
    sync_records, receipts, registries = _bundle_records()
    rejection = registries["rejection"][0]
    errors = validate_registry_records(
        "rejection",
        [rejection],
        known_evidence_ids={record["evidence_id"] for record in receipts},
        known_sync_ids={record["sync_record_id"] for record in sync_records},
    )
    assert errors == []
    assert rejection["retained"] is True
    assert rejection["acceptance_state"] == "REJECTED"
    assert rejection["eligible_for_absent"] is False
    assert rejection["physiology_label"] is None


def test_sync_methods_are_distinguishable_and_both_auditable() -> None:
    sync_records, _, _ = _bundle_records()
    assert {record["method"] for record in sync_records} == {"SHARED_CLOCK", "EXPLICIT_SYNC_MARKER"}
    assert validate_sync_records(sync_records) == []
    marker = next(record for record in sync_records if record["method"] == "EXPLICIT_SYNC_MARKER")
    assert marker["source_marker_observed"] is True
    assert marker["host_marker_observed"] is True
    shared = next(record for record in sync_records if record["method"] == "SHARED_CLOCK")
    assert shared["sync_marker_id"] is None


def test_no_timing_tolerance_is_invented() -> None:
    sync_records, _, _ = _bundle_records()
    assert all(record["threshold_status"] == "THRESHOLD_NOT_GOVERNED" for record in sync_records)
    assert all(record["alignment_status"] == "ALIGNMENT_MEASURABLE" for record in sync_records)
    assert _find_forbidden_keys(sync_records) == []


def test_every_fixture_is_explicitly_non_campaign() -> None:
    for filename in FIXTURE_FILES.values():
        fixture = read_json(DEFAULT_MANIFEST_DIR / filename)
        assert fixture["fixture_semantics"] == FIXTURE_SEMANTICS
        assert fixture["live_evidence_status"] == "NOT_LIVE_EVIDENCE"
        assert fixture["campaign_status"] == "NON_CAMPAIGN"
        assert fixture["d1_membership_status"] == "NOT_D1_MEMBERSHIP"
        assert fixture["dataset_admissibility"] == "NOT_DATASET_ADMISSIBLE"


def test_d1_membership_counts_unchanged_and_upstream_state_is_read_only() -> None:
    source_paths = [
        ROOT / "datasets/mmwave/manifests/MMWAVE_V2_post_pubabs_critical_path/critical_path_state.json",
        ROOT / "datasets/mmwave/manifests/MMWAVE_V2_D1_physical_resource_recovery_01/d1_membership_unchanged.json",
    ]
    before = {path: path.read_bytes() for path in source_paths}
    result = build_synthetic_bundle(DEFAULT_MANIFEST_DIR)
    after = {path: path.read_bytes() for path in source_paths}
    assert before == after
    snapshot = _read_d1_state()
    assert result["ok"] is True
    assert snapshot["unchanged"] is True
    assert snapshot["membership_created"] is False
    assert snapshot["counts"]["observed_present"] == 57
    assert snapshot["counts"]["observed_absent"] == 0


def test_bundle_generation_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
        first = Path(first_dir) / "bundle"
        second = Path(second_dir) / "bundle"
        first_result = build_synthetic_bundle(first)
        second_result = build_synthetic_bundle(second)
        assert first_result["ok"] is True
        assert second_result["ok"] is True
        first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
        second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
        assert first_files == second_files
        assert all((first / relative).read_bytes() == (second / relative).read_bytes() for relative in first_files)


def test_synthetic_hash_payloads_are_internal_only() -> None:
    receipts, _ = _hash_receipts()
    payloads = _synthetic_payloads()
    assert set(payloads) == {receipt["evidence_id"] for receipt in receipts}
    assert all("payload" not in receipt for receipt in receipts)


class TestMmwaveD1Sw0304EvidenceTooling(unittest.TestCase):
    """Keep the focused tests runnable with either pytest or unittest."""

    def test_bundle_schema_validation_is_green(self) -> None:
        test_bundle_schema_validation_is_green()

    def test_hashing_is_deterministic_and_does_not_store_payload(self) -> None:
        test_hashing_is_deterministic_and_does_not_store_payload()

    def test_live_debug_hash_receipt_is_non_campaign_without_fixture_lock(self) -> None:
        test_live_debug_hash_receipt_is_non_campaign_without_fixture_lock()

    def test_real_temporary_file_hash_path_is_complete_without_payload_copy(self) -> None:
        test_real_temporary_file_hash_path_is_complete_without_payload_copy()

    def test_caller_supplied_live_debug_sync_records_validate(self) -> None:
        test_caller_supplied_live_debug_sync_records_validate()

    def test_operational_hash_and_sync_cli_paths_are_usable(self) -> None:
        test_operational_hash_and_sync_cli_paths_are_usable()

    def test_operational_registries_validate_and_keep_non_final_states(self) -> None:
        test_operational_registries_validate_and_keep_non_final_states()

    def test_dangling_health_and_rejection_registry_links_are_rejected(self) -> None:
        test_dangling_health_and_rejection_registry_links_are_rejected()

    def test_unknown_hash_and_sync_references_are_rejected(self) -> None:
        test_unknown_hash_and_sync_references_are_rejected()

    def test_duplicate_immutable_evidence_id_is_rejected(self) -> None:
        test_duplicate_immutable_evidence_id_is_rejected()

    def test_malformed_and_mismatched_sha_are_rejected(self) -> None:
        test_malformed_and_mismatched_sha_are_rejected()

    def test_missing_occupancy_is_incomplete_not_absent(self) -> None:
        test_missing_occupancy_is_incomplete_not_absent()

    def test_health_fault_is_retained_without_physiology_semantics(self) -> None:
        test_health_fault_is_retained_without_physiology_semantics()

    def test_rejection_is_retained_and_not_eligible_absent(self) -> None:
        test_rejection_is_retained_and_not_eligible_absent()

    def test_sync_methods_are_distinguishable_and_both_auditable(self) -> None:
        test_sync_methods_are_distinguishable_and_both_auditable()

    def test_no_timing_tolerance_is_invented(self) -> None:
        test_no_timing_tolerance_is_invented()

    def test_every_fixture_is_explicitly_non_campaign(self) -> None:
        test_every_fixture_is_explicitly_non_campaign()

    def test_d1_membership_counts_unchanged_and_upstream_state_is_read_only(self) -> None:
        test_d1_membership_counts_unchanged_and_upstream_state_is_read_only()

    def test_synthetic_hash_payloads_are_internal_only(self) -> None:
        test_synthetic_hash_payloads_are_internal_only()

    def test_bundle_generation_is_deterministic(self) -> None:
        test_bundle_generation_is_deterministic()
