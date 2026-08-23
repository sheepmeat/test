#!/usr/bin/env python3
"""Validate the compact SafeNest mmWave M-PV1 contract evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVIDENCE = ROOT / "datasets/mmwave/manifests/M-PV1_public_multidomain_contract"
CONFIG = ROOT / "config/mmwave/m_pv1_public_multidomain_contract.json"
REQUIRED = (
    "prerequisite_audit.json",
    "dataset_role_contract.json",
    "d0_model_ready_audit.json",
    "d1_reference_materialization_audit.json",
    "d1_subject_split.json",
    "representation_freeze.json",
    "model_input_contract.json",
    "target_mapping_profile.json",
    "temporal_context_contract.json",
    "quality_abstention_contract.json",
    "source_balancing_contract.json",
    "m_pv2_example_manifest.json",
    "target_coverage_audit.json",
    "cross_domain_compatibility.json",
    "d2_lock_audit.json",
    "exception_registry.json",
    "validation_result.json",
    "checksums.json",
)
ABSOLUTE_RE = re.compile(r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)")


def load(name: str) -> Any:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contains_absolute(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_absolute(k) or contains_absolute(v) for k, v in value.items())
    if isinstance(value, list):
        return any(contains_absolute(v) for v in value)
    return isinstance(value, str) and bool(ABSOLUTE_RE.search(value))


def validate() -> Dict[str, Any]:
    errors: List[str] = []
    missing = [name for name in REQUIRED if not (EVIDENCE / name).is_file()]
    if not CONFIG.is_file():
        errors.append("MISSING_CONFIG")
    if missing:
        errors.extend("MISSING_EVIDENCE:" + name for name in missing)
        return {"phase": "M-PV1", "ok": False, "gate": "BLOCKED", "errors": errors}
    docs = {name: load(name) for name in REQUIRED}
    for name, document in docs.items():
        if contains_absolute(document):
            errors.append("ABSOLUTE_PATH:" + name)

    prereq = docs["prerequisite_audit.json"]
    checks = prereq.get("checks", {})
    for key in ("D0_ACCEPTED", "D1_ACCEPTED", "R3_ACCEPTED", "Q2_ACCEPTED", "I1_ACCEPTED", "R1_CONTRACT_PRESENT", "R2_CONTRACT_PRESENT"):
        if checks.get(key) != "YES":
            errors.append("PREREQUISITE:" + key)
    if checks.get("DIRECT_PREREQUISITES_ACCEPTED") != "YES":
        errors.append("DIRECT_PREREQUISITES_GATE")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("contract_id") != "MMWAVE_V2_M_PV1_PUBLIC_MULTIDOMAIN_CONTRACT_V1":
        errors.append("CONFIG_ID")
    if config.get("model_training_performed") is not False or config.get("d2_used") is not False:
        errors.append("CONFIG_SCOPE")

    d0 = docs["d0_model_ready_audit.json"]
    if d0.get("inherited_split_identity") != "MMWAVE_V2_D0_SUBJECT_SPLIT_V1":
        errors.append("D0_SPLIT_ID")
    if d0.get("split_changed") is not False or d0.get("m_n6_excluded_subjects_used") is not False:
        errors.append("D0_SPLIT_POLICY")
    if d0.get("base_present_count") != 162 or d0.get("base_ambiguous_count") != 156:
        errors.append("D0_R3_COUNTS")
    if d0.get("base_absent_count") != 0 or d0.get("corrected_event_interval_absent_count") != 116:
        errors.append("D0_ABSENT_REBINDING")
    if d0.get("corrected_event_interval_audit_only_count") != 40:
        errors.append("D0_CORRECTIVE_AUDIT_COUNT")

    d1 = docs["d1_reference_materialization_audit.json"]
    if d1.get("recording_count") != 265 or d1.get("adapted_recording_count") != 265:
        errors.append("D1_RECORDING_COUNT")
    if d1.get("checksum_verified") is not True or d1.get("raw_waveforms_committed") is not False:
        errors.append("D1_CHECKSUM_OR_RAW_POLICY")
    if d1.get("waveforms_accessed") is not True or d1.get("waveforms_persisted") is not False:
        errors.append("D1_MATERIALIZATION_POLICY")
    if d1.get("temporal_hold_supervision") != "UNAVAILABLE":
        errors.append("D1_HOLD_POLICY")

    d1_split = docs["d1_subject_split.json"]
    if d1_split.get("counts") != {"D1_DEV_TRAIN": 8, "D1_DEV_VAL": 3}:
        errors.append("D1_SPLIT_COUNTS")
    train = set(d1_split.get("subject_ids", {}).get("D1_DEV_TRAIN", []))
    val = set(d1_split.get("subject_ids", {}).get("D1_DEV_VAL", []))
    if not train.isdisjoint(val) or len(train | val) != 11:
        errors.append("D1_SPLIT_DISJOINT")
    if d1_split.get("recording_level_leakage") != "NO":
        errors.append("D1_RECORDING_LEAKAGE")

    representation = docs["representation_freeze.json"]
    if representation.get("common_rate_hz") != 10.0:
        errors.append("COMMON_RATE")
    for key in ("window_local_MAD_divide_only", "source_specific_gain_matching", "low_amplitude_auto_normalization"):
        if representation.get(key) is not False:
            errors.append("REPRESENTATION_SAFETY:" + key)
    if representation.get("original_scale_information_preserved") is not True:
        errors.append("SCALE_PRESERVATION")
    if representation.get("F2_role") != "ACTIVE_SCALAR_CANDIDATE" or representation.get("F3_role") != "ACTIVE_TRACE_QUALITY_CANDIDATE":
        errors.append("REPRESENTATION_ROLES")
    compatibility_matrix = representation.get("task_compatibility_matrix", {})
    if compatibility_matrix.get("PROFILE_A_FEATURE_F2_V1", {}).get("breathing_evidence") is not False:
        errors.append("F2_BREATHING_MUST_BE_UNSUPPORTED")
    if compatibility_matrix.get("PROFILE_B_TRACE_F3_R1_V1", {}).get("breathing_evidence") is not True:
        errors.append("TRACE_BREATHING_COMPATIBILITY")
    if compatibility_matrix.get("PROFILE_C_HYBRID_TRACE_PLUS_F2_V1", {}).get("breathing_evidence") is not True:
        errors.append("HYBRID_BREATHING_COMPATIBILITY")

    temporal = docs["temporal_context_contract.json"]
    if temporal.get("model_context_duration_s") != 30.0 or temporal.get("model_context_samples") != 300 or temporal.get("model_evaluation_stride_s") != 5.0:
        errors.append("TEMPORAL_CONTEXT")
    if temporal.get("causal_context") is not True:
        errors.append("CAUSAL_CONTEXT")
    target_interval = temporal.get("target_interval", {})
    if target_interval.get("breathing_target_duration_s") != 5.0 or target_interval.get("breathing_target_anchor") != "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT":
        errors.append("BREATHING_TARGET_CONTRACT")
    if target_interval.get("arbitrary_internal_target_interval") is not False or target_interval.get("future_information_allowed") is not False:
        errors.append("TARGET_LOCATION_POLICY")
    rr_interval = temporal.get("rr_reference_interval", {})
    if rr_interval.get("duration_s") != 30.0 or rr_interval.get("anchor") != "FULL_CAUSAL_CONTEXT_REFERENCE_INTERVAL" or rr_interval.get("separate_from_breathing_target") is not True:
        errors.append("RR_INTERVAL_SEPARATION")
    if temporal.get("padding_policy", "").lower().find("fake") >= 0:
        errors.append("FAKE_PADDING")
    if temporal.get("gap_policy", "").lower().find("no interpolation") < 0:
        errors.append("GAP_POLICY")

    target = docs["target_mapping_profile.json"]
    if target.get("DIRECT_THREE_CLASS_PRIMARY_TARGET") is not False:
        errors.append("DIRECT_THREE_CLASS")
    breathing = target.get("breathing_evidence", {})
    if breathing.get("states") != ["PRESENT", "ABSENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"]:
        errors.append("BREATHING_STATES")
    if breathing.get("source_apnea_term_auto_target") is not False or breathing.get("whole_window_apnea_default") is not False:
        errors.append("APNEA_SOURCE_POLICY")
    if target.get("rr", {}).get("zero_is_not_unavailable") is not True:
        errors.append("RR_ZERO_POLICY")
    if breathing.get("target_duration_s") != 5.0 or breathing.get("target_anchor") != "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT":
        errors.append("BREATHING_TARGET_ANCHOR")
    if breathing.get("causal_context") is not True or breathing.get("arbitrary_internal_target_interval") is not False:
        errors.append("BREATHING_CAUSALITY")
    if breathing.get("present_absent_same_target_duration") is not True or breathing.get("present_absent_same_target_semantics") is not True:
        errors.append("BREATHING_SEMANTIC_ALIGNMENT")
    if target.get("rr", {}).get("separate_from_breathing_interval") is not True:
        errors.append("RR_BREATHING_COLLAPSED")
    temporal_target = target.get("temporal_hold", {})
    if temporal_target.get("learning_boundary") != "DETERMINISTIC_POST_BREATHING_COMPOSITION_ONLY" or temporal_target.get("direct_neural_supervision") is not False:
        errors.append("TEMPORAL_LEARNING_BOUNDARY")

    coverage = docs["target_coverage_audit.json"]
    if coverage.get("zero_counts_are_visible") is not True:
        errors.append("COVERAGE_ZERO_VISIBILITY")
    if coverage.get("by_domain", {}).get("D0", {}).get("breathing", {}).get("PRESENT") != 162:
        errors.append("COVERAGE_D0_PRESENT")
    if coverage.get("by_domain", {}).get("D0", {}).get("breathing", {}).get("ABSENT") != 116:
        errors.append("COVERAGE_D0_ABSENT")
    if coverage.get("by_domain", {}).get("D0", {}).get("breathing", {}).get("AMBIGUOUS") != 40:
        errors.append("COVERAGE_D0_AMBIGUOUS")
    if coverage.get("by_domain", {}).get("D1", {}).get("breathing", {}).get("PRESENT") != 236:
        errors.append("COVERAGE_D1_PRESENT")
    if coverage.get("by_domain", {}).get("D1", {}).get("breathing", {}).get("ABSENT") != 0 or coverage.get("by_domain", {}).get("D1", {}).get("breathing", {}).get("AMBIGUOUS") != 8:
        errors.append("COVERAGE_D1_STATES")
    if coverage.get("by_domain", {}).get("D1", {}).get("breathing_audit_only", {}).get("TARGET_UNAVAILABLE") != 21:
        errors.append("COVERAGE_D1_AUDIT_UNAVAILABLE")
    if coverage.get("unique_model_input_contexts") != 562 or coverage.get("duplicate_target_overlay_count") != 0:
        errors.append("UNIQUE_INPUT_ACCOUNTING")
    if coverage.get("quality_clean_unique_model_input_count") != 562:
        errors.append("QUALITY_UNIQUE_INPUT_ACCOUNTING")

    examples = docs["m_pv2_example_manifest.json"].get("examples", [])
    ids = [row.get("example_id") for row in examples]
    if len(ids) != len(set(ids)) or len(ids) != docs["m_pv2_example_manifest.json"].get("example_count"):
        errors.append("EXAMPLE_ID_DETERMINISM")
    model_ready = [row for row in examples if row.get("model_ready") is True]
    model_input_ids = [row.get("model_input_id") for row in model_ready]
    if len(model_input_ids) != len(set(model_input_ids)):
        errors.append("DUPLICATE_MODEL_INPUT_ID")
    if docs["m_pv2_example_manifest.json"].get("unique_model_input_contexts") != len(model_ready):
        errors.append("MANIFEST_UNIQUE_INPUT_COUNT")
    breathing_durations = set()
    breathing_anchors = set()
    breathing_semantics = set()
    for row in model_ready:
        required = (
            "model_input_id", "source_id", "subject_id", "recording_id", "split",
            "context_start_s", "context_end_s", "context_duration_s", "target_task",
            "target_start_s", "target_end_s", "target_duration_s", "target_anchor",
            "causal_context", "representation_profile_compatibility", "supervision_eligibility",
            "provenance", "target_records", "model_input_tensor_status",
        )
        for field in required:
            if field not in row:
                errors.append("MODEL_READY_MISSING_FIELD:" + field)
        if row.get("model_input_tensor_status") != "VALID_DECLARED_REGENERABLE_FROM_ACCEPTED_CONTRACTS":
            errors.append("MODEL_READY_INVALID_TENSOR:" + str(row.get("example_id")))
        cstart = float(row.get("context_start_s"))
        cend = float(row.get("context_end_s"))
        tstart = float(row.get("target_start_s"))
        tend = float(row.get("target_end_s"))
        if row.get("causal_context") is not True or cend - cstart != 30.0:
            errors.append("MODEL_CONTEXT_NOT_FIXED_CAUSAL:" + str(row.get("example_id")))
        if row.get("target_task") != "breathing_evidence":
            errors.append("TOP_LEVEL_TARGET_TASK:" + str(row.get("example_id")))
        if row.get("target_anchor") != "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT":
            errors.append("TARGET_ANCHOR:" + str(row.get("example_id")))
        if row.get("target_duration_s") != 5.0 or tend - tstart != 5.0 or abs(tstart - (cend - 5.0)) > 1e-9 or abs(tend - cend) > 1e-9:
            errors.append("TARGET_INTERVAL_ALIGNMENT:" + str(row.get("example_id")))
        if tstart < cstart or tend > cend:
            errors.append("TARGET_OUTSIDE_CONTEXT:" + str(row.get("example_id")))
        breathing_state = row.get("breathing_reference_state")
        if row.get("breathing_supervision_eligible") and breathing_state not in {"BREATHING_REFERENCE_PRESENT", "BREATHING_REFERENCE_ABSENT"}:
            errors.append("BREATHING_ELIGIBILITY_STATE:" + str(row.get("example_id")))
        breathing_durations.add(row.get("target_duration_s"))
        breathing_anchors.add(row.get("target_anchor"))
        breathing_semantics.add((row.get("target_task"), row.get("target_anchor"), row.get("target_duration_s")))
        target_records = row.get("target_records", [])
        if len(target_records) != 4:
            errors.append("TARGET_RECORD_COUNT:" + str(row.get("example_id")))
        record_by_task = {record.get("target_task"): record for record in target_records}
        for task in ("breathing_evidence", "rr", "temporal_hold", "quality"):
            if task not in record_by_task:
                errors.append("TARGET_RECORD_MISSING:" + task + ":" + str(row.get("example_id")))
        breathing_record = record_by_task.get("breathing_evidence", {})
        if breathing_record.get("target_anchor") != "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT" or breathing_record.get("target_duration_s") != 5.0:
            errors.append("BREATHING_RECORD_ALIGNMENT:" + str(row.get("example_id")))
        rr_record = record_by_task.get("rr", {})
        if rr_record.get("target_anchor") != "FULL_CAUSAL_CONTEXT_REFERENCE_INTERVAL" or rr_record.get("target_duration_s") != 30.0:
            errors.append("RR_RECORD_INTERVAL:" + str(row.get("example_id")))
        temporal_record = record_by_task.get("temporal_hold", {})
        if temporal_record.get("learning_boundary") != "DETERMINISTIC_POST_BREATHING_COMPOSITION_ONLY" or temporal_record.get("supervision_eligible") is not False:
            errors.append("TEMPORAL_RECORD_BOUNDARY:" + str(row.get("example_id")))
    if breathing_durations != {5.0} or breathing_anchors != {"FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT"}:
        errors.append("BREATHING_TARGET_FIXED_SEMANTICS")
    if len(breathing_semantics) != 1:
        errors.append("BREATHING_PRESENT_ABSENT_SEMANTICS")
    if any(row.get("example_role") == "EVENT_RELATIVE_HOLD_INTERVAL" and row.get("model_ready") is True for row in examples):
        errors.append("EVENT_OVERLAY_MODEL_INPUT_ROW")
    if any(row.get("model_ready") is True and row.get("target_start_s") < row.get("context_start_s") for row in examples):
        errors.append("FUTURE_OR_PRECONTEXT_TARGET")
    clean_inputs = {row.get("model_input_id") for row in model_ready if row.get("quality_status") == "CLEAN"}
    if docs["target_coverage_audit.json"].get("quality_clean_unique_model_input_count") != len(clean_inputs):
        errors.append("QUALITY_DUPLICATE_COUNTING")
    for row in model_ready:
        matrix = row.get("representation_profile_compatibility", {})
        if matrix.get("PROFILE_A_FEATURE_F2_V1", {}).get("breathing_evidence") is not False:
            errors.append("ROW_F2_BREATHING_COMPATIBILITY")
    forbidden_subjects = set(load("../M-PV0_D0_v2_split_label_audit/v2_subject_split.json").get("excluded_subject_ids", [])) if False else set()
    # The accepted split is outside the M-PV1 directory; use the repository
    # copy directly rather than manufacturing a second split manifest.
    split_path = ROOT / "datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit/v2_subject_split.json"
    if split_path.is_file():
        forbidden_subjects = set(json.loads(split_path.read_text(encoding="utf-8")).get("excluded_subject_ids", []))
    if any(row.get("subject_id") in forbidden_subjects for row in examples if row.get("source_id") == "D0"):
        errors.append("M_N6_EXCLUDED_SUBJECT_USED")
    if any(row.get("source_id") == "D0" and row.get("split") != "TRAIN" for row in examples):
        errors.append("D0_NONTRAIN_EXAMPLE")

    d2 = docs["d2_lock_audit.json"]
    for key, expected in (("semantic_access", "NO"), ("feature_extraction", "NO"), ("target_use", "NO"), ("selection_use", "NO")):
        if d2.get(key) != expected:
            errors.append("D2_" + key.upper())
    if d2.get("model_inference_count") != 0:
        errors.append("D2_INFERENCE")

    result = docs["validation_result.json"]
    if result.get("schema_version") != "M-PV1.2_CORRECTIVE_ALIGNMENT" or result.get("gate") != "PASS_WITH_LIMITATIONS" or result.get("ok") is not True or result.get("deterministic_generation") is not True:
        errors.append("RECORDED_VALIDATION")
    safety = result.get("checks", {})
    for key, expected in (("MODEL_TRAINING", "NO"), ("MODEL_SELECTION", "NO"), ("INT8_WORK", "NO"), ("MR60_SUPERVISED_USE", "NO"), ("D2_USED_FOR_SELECTION", "NO"), ("INVALID_INPUT_PHYSIOLOGY_SUPERVISION", "NO"), ("BREATHING_TARGET_FIXED_ANCHOR", "YES"), ("BREATHING_PRESENT_ABSENT_SAME_TARGET_DURATION", "YES"), ("BREATHING_PRESENT_ABSENT_SAME_TARGET_SEMANTICS", "YES"), ("EVENT_TARGET_CONTEXT_CAUSAL", "YES"), ("ARBITRARY_INTERNAL_TARGET_INTERVAL", "NO"), ("MODEL_READY_TARGET_WITHOUT_VALID_INPUT_TENSOR", "NO"), ("FEATURE_PROFILE_TARGET_LOCATION_AMBIGUOUS", "NO"), ("DUPLICATE_INPUT_CONTRADICTORY_BREATHING_LABELS", "NO"), ("QUALITY_CONTEXT_DUPLICATE_COUNTING", "NO"), ("SYNTHETIC_RATIO_USES_UNIQUE_CLEAN_INPUT_COUNT", "YES"), ("TEMPORAL_HOLD_LEARNING_BOUNDARY_FROZEN", "YES"), ("MODEL_FAMILY_TASK_COMPATIBILITY_FROZEN", "YES"), ("RR_INTERVAL_SEPARATE_FROM_BREATHING_INTERVAL", "YES")):
        if safety.get(key) != expected:
            errors.append("SAFETY_" + key)

    checksums = docs["checksums.json"]
    for name, recorded in checksums.get("files", {}).items():
        path = EVIDENCE / name
        if not path.is_file() or sha256_file(path) != recorded:
            errors.append("CHECKSUM:" + name)
    config_record = checksums.get("config", {})
    if config_record.get("sha256") != sha256_file(CONFIG):
        errors.append("CHECKSUM:config")
    generator = ROOT / "scripts/mmwave_m_pv1_public_multidomain_contract.py"
    if checksums.get("generator", {}).get("sha256") != sha256_file(generator):
        errors.append("CHECKSUM:generator")

    tracked_raw = subprocess.run(["git", "ls-files", "--", "*.zip", "*.mat", "datasets/raw_archives"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    if tracked_raw:
        errors.append("RAW_PAYLOAD_TRACKED")

    return {
        "phase": "M-PV1",
        "schema_version": "M-PV1.2_CORRECTIVE_ALIGNMENT",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "example_count": len(examples),
        "unique_model_input_contexts": len(model_input_ids),
        "d1_model_ready_contexts": d1.get("model_ready_context_count"),
        "d0_corrected_absent": d0.get("corrected_event_interval_absent_count"),
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
