#!/usr/bin/env python3
"""Focused M-PV0 gate checks. Metadata only. No D2 payload, training, or adapters."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_pv0_public_multidomain_registry import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    INT8_PATH,
    MN4_SPLIT,
    MN6_HELDOUT,
    MN9_LOCK,
    MN9_RESULT,
    REGISTRY_DIR,
    REGISTRY_JSON_FILES,
    dump_json,
    load_json,
    sha256_bytes,
    sha256_file,
)

REQUIRED_ROLES = {
    "D0": "REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN",
    "D1": "REQUIRED_AUXILIARY_DEVELOPMENT_DOMAIN",
    "D2": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
    "D3": "OPTIONAL_NON_BLOCKING_QUALITY_RR_DEVELOPMENT_DOMAIN",
}

D2_FORBIDDEN = (
    "representation_selection",
    "feature_selection",
    "model_family_selection",
    "seed_selection",
    "threshold_selection",
    "calibration_selection",
    "augmentation_selection",
    "candidate_inference",
)


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def check_absolute_paths(obj: object, trail: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            check_absolute_paths(value, f"{trail}.{key}", errors)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            check_absolute_paths(value, f"{trail}[{idx}]", errors)
    elif isinstance(obj, str) and ABSOLUTE_PATH_RE.search(obj):
        fail(errors, f"ABSOLUTE_PATH:{trail}")


def validate() -> dict:
    errors: list[str] = []
    if not REGISTRY_DIR.is_dir():
        return {
            "phase": "M-PV0",
            "gate": "BLOCKED",
            "ok": False,
            "errors": ["REGISTRY_DIR_MISSING"],
        }

    files = {name: load_json(REGISTRY_DIR / name) for name in (*REGISTRY_JSON_FILES, "checksums.json")}
    for name, doc in files.items():
        check_absolute_paths(doc, name, errors)

    source = files["source_registry.json"]
    policy = files["role_lock_policy.json"]
    license_audit = files["license_access_audit.json"]
    v1 = files["v1_failure_baseline.json"]
    exceptions = files["exception_registry.json"]
    checksums = files["checksums.json"]

    for source_id, role in REQUIRED_ROLES.items():
        actual = source["sources"].get(source_id, {}).get("intended_role")
        if actual != role:
            fail(errors, f"ROLE_MISMATCH:{source_id}:{actual}")
        if policy["roles"].get(source_id) != role:
            fail(errors, f"POLICY_ROLE_MISMATCH:{source_id}")

    if policy.get("D3_NON_BLOCKING") != "YES":
        fail(errors, "D3_NOT_MARKED_NON_BLOCKING")
    if source["sources"]["D3"]["lock_state"] != "OPTIONAL_NON_BLOCKING":
        fail(errors, "D3_LOCK_STATE")

    d2_lock = policy["d2_lock"]
    for field in D2_FORBIDDEN:
        if d2_lock.get(field) != "FORBIDDEN":
            fail(errors, f"D2_LOCK_FIELD:{field}")
    if d2_lock.get("candidate_inference_count") != 0:
        fail(errors, "D2_CANDIDATE_INFERENCE_COUNT")
    if d2_lock.get("MODEL_INFERENCE_COUNT") != 0:
        fail(errors, "D2_MODEL_INFERENCE_COUNT")
    if d2_lock.get("PUBLIC_METADATA_ACCESS") != "YES":
        fail(errors, "D2_METADATA_ACCESS")
    for field in (
        "PAYLOAD_ACQUISITION",
        "PAYLOAD_SEMANTIC_INSPECTION",
        "FEATURE_EXTRACTION",
        "MODEL_INFERENCE",
    ):
        if d2_lock.get(field) != "NO":
            fail(errors, f"D2_ACCESS:{field}")
    if license_audit["d2_access_audit"]["MODEL_INFERENCE_COUNT"] != 0:
        fail(errors, "LICENSE_D2_INFERENCE_COUNT")

    mr60 = policy["mr60_policy"]
    for field in (
        "supervised_TRAIN",
        "supervised_VAL",
        "supervised_TEST",
        "representation_selection",
        "model_family_selection",
        "threshold_tuning",
        "calibration",
        "augmentation_tuning",
        "label_construction",
    ):
        if mr60.get(field) != "FORBIDDEN":
            fail(errors, f"MR60_POLICY:{field}")

    split = load_json(MN4_SPLIT)
    expected_heldout = split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"]
    recorded = source["consumed_evidence"]["m_n6_new_model_heldout_test"]["subject_ids"]
    if recorded != expected_heldout:
        fail(errors, "HELDOUT_SUBJECTS_MISMATCH")
    if len(recorded) != 16:
        fail(errors, "HELDOUT_COUNT")
    if source["consumed_evidence"]["m_n6_new_model_heldout_test"]["V2_SELECTION_REUSE"] != "FORBIDDEN":
        fail(errors, "HELDOUT_REUSE_NOT_FORBIDDEN")
    if policy["heldout_exclusion"]["OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN"] != "YES":
        fail(errors, "HELDOUT_EXCLUSION_FLAG")
    if source["consumed_evidence"]["CONSUMED_SUBJECT_SET_UNRESOLVED"]:
        fail(errors, "CONSUMED_SUBJECT_SET_UNRESOLVED")
    mn6 = load_json(MN6_HELDOUT)
    if mn6["heldout_may_be_reused_for_future_model_selection"] is not False:
        fail(errors, "MN6_HELDOUT_REUSE_FLAG")
    mn9 = load_json(MN9_RESULT)
    if mn9["NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9"] != 0:
        fail(errors, "MN9_HELDOUT_INFERENCE")

    lock = load_json(MN9_LOCK)
    if v1["selected_int8"]["artifact_id"] != "MMWAVE_M_N9_FULL_INT8_V1":
        fail(errors, "V1_ARTIFACT_ID")
    if v1["role"] != "OBSERVE_ONLY_READ_ONLY_BASELINE":
        fail(errors, "V1_ROLE")
    if sha256_file(INT8_PATH) != v1["selected_int8"]["artifact_sha256"]:
        fail(errors, "V1_INT8_SHA")
    if v1["selected_int8"]["artifact_sha256"] != lock["artifact_sha256"]:
        fail(errors, "V1_INT8_LOCK_SHA")
    if v1["output_semantics"]["apnea_is_clinical_diagnosis"]:
        fail(errors, "CLINICAL_APNEA_CLAIM")
    if not v1["fail_closed_observed"]["v2_must_preserve_abstention_requirement"]:
        fail(errors, "ABSTENTION_POLICY_MISSING")

    required_source_fields = (
        "source_id",
        "canonical_name",
        "public_url",
        "publication_doi",
        "dataset_doi_or_record_id",
        "publisher_or_host",
        "dataset_version",
        "release_or_update_date",
        "license",
        "access_mode",
        "expected_download_size",
        "radar_frequency",
        "radar_hardware",
        "raw_signal_type",
        "processed_signal_type",
        "reference_modality",
        "subject_count_claims",
        "recording_count_claims",
        "conditions",
        "breath_hold_ground_truth_available",
        "intended_role",
        "allowed_uses",
        "forbidden_uses",
        "lock_state",
        "checksum_source",
        "local_payload_present",
        "provenance_evidence",
        "known_ambiguities",
    )
    for source_id, row in source["sources"].items():
        for field in required_source_fields:
            if field not in row:
                fail(errors, f"MISSING_FIELD:{source_id}:{field}")

    for name in REGISTRY_JSON_FILES:
        text = (REGISTRY_DIR / name).read_text(encoding="utf-8")
        digest = sha256_bytes(text.encode("utf-8"))
        if checksums["files"].get(name) != digest:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")

    rerun = json.dumps(load_json(REGISTRY_DIR / "source_registry.json"), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if sha256_bytes(rerun.encode("utf-8")) != checksums["files"]["source_registry.json"]:
        fail(errors, "JSON_NOT_DETERMINISTIC")

    d3_conflict = any(
        row["code"] == "D3_PARTICIPANT_RECORDING_COUNT_CONFLICT" for row in exceptions["exceptions"]
    )
    if not d3_conflict:
        fail(errors, "D3_COUNT_CONFLICT_NOT_RECORDED")

    flags = policy["gate_flags"]
    required_yes = (
        "D0_ROLE_UNAMBIGUOUS",
        "D1_ROLE_UNAMBIGUOUS",
        "D2_ROLE_LOCKED",
        "D3_NON_BLOCKING",
        "D2_PRELOCK_ACCESS_AUDIT_EXISTS",
        "MR60_SUPERVISED_USE_FORBIDDEN",
        "OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN",
    )
    for key in required_yes:
        if flags.get(key) != "YES":
            fail(errors, f"GATE_FLAG:{key}")
    if flags.get("D2_MODEL_INFERENCE_COUNT") != 0:
        fail(errors, "GATE_FLAG:D2_MODEL_INFERENCE_COUNT")
    if flags.get("PARALLEL_TRACK_BRANCH_CONTAMINATION") != "NO":
        fail(errors, "GATE_FLAG:PARALLEL_TRACK_BRANCH_CONTAMINATION")

    gate = "BLOCKED" if errors else policy["gate"]
    if errors:
        gate = "BLOCKED"
    result = {
        "schema_version": "M-PV0.1",
        "phase": "M-PV0",
        "ok": not errors,
        "gate": gate if not errors else "BLOCKED",
        "errors": errors,
        "checks": {
            "D0_ROLE_UNAMBIGUOUS": flags.get("D0_ROLE_UNAMBIGUOUS"),
            "D1_ROLE_UNAMBIGUOUS": flags.get("D1_ROLE_UNAMBIGUOUS"),
            "D2_ROLE_LOCKED": flags.get("D2_ROLE_LOCKED"),
            "D3_NON_BLOCKING": flags.get("D3_NON_BLOCKING"),
            "D2_PRELOCK_ACCESS_AUDIT_EXISTS": flags.get("D2_PRELOCK_ACCESS_AUDIT_EXISTS"),
            "D2_MODEL_INFERENCE_COUNT": flags.get("D2_MODEL_INFERENCE_COUNT"),
            "MR60_SUPERVISED_USE_FORBIDDEN": flags.get("MR60_SUPERVISED_USE_FORBIDDEN"),
            "OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN": flags.get("OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN"),
            "PARALLEL_TRACK_BRANCH_CONTAMINATION": flags.get("PARALLEL_TRACK_BRANCH_CONTAMINATION"),
        },
        "heldout_subject_count": len(recorded),
        "v1_artifact_id": v1["selected_int8"]["artifact_id"],
        "v1_sha256": v1["selected_int8"]["artifact_sha256"],
    }
    dump_json(REGISTRY_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps({"ok": result["ok"], "gate": result["gate"], "errors": result["errors"]}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
