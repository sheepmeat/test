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
    if d0.get("base_absent_count") != 0 or d0.get("event_relative_absent_contexts", 0) <= 0:
        errors.append("D0_ABSENT_REBINDING")

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

    temporal = docs["temporal_context_contract.json"]
    if temporal.get("model_context_duration_s") != 30.0 or temporal.get("model_context_samples") != 300 or temporal.get("model_evaluation_stride_s") != 5.0:
        errors.append("TEMPORAL_CONTEXT")
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

    coverage = docs["target_coverage_audit.json"]
    if coverage.get("zero_counts_are_visible") is not True:
        errors.append("COVERAGE_ZERO_VISIBILITY")
    if coverage.get("by_domain", {}).get("D0", {}).get("breathing", {}).get("ABSENT") != 133:
        errors.append("COVERAGE_D0_ABSENT")
    if coverage.get("by_domain", {}).get("D1", {}).get("breathing", {}).get("PRESENT") != 236:
        errors.append("COVERAGE_D1_PRESENT")

    examples = docs["m_pv2_example_manifest.json"].get("examples", [])
    ids = [row.get("example_id") for row in examples]
    if len(ids) != len(set(ids)) or len(ids) != docs["m_pv2_example_manifest.json"].get("example_count"):
        errors.append("EXAMPLE_ID_DETERMINISM")
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
    if result.get("gate") != "PASS_WITH_LIMITATIONS" or result.get("ok") is not True or result.get("deterministic_generation") is not True:
        errors.append("RECORDED_VALIDATION")
    safety = result.get("checks", {})
    for key, expected in (("MODEL_TRAINING", "NO"), ("MODEL_SELECTION", "NO"), ("INT8_WORK", "NO"), ("MR60_SUPERVISED_USE", "NO"), ("D2_USED_FOR_SELECTION", "NO"), ("INVALID_INPUT_PHYSIOLOGY_SUPERVISION", "NO")):
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
        "schema_version": "M-PV1.1",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "example_count": len(examples),
        "d1_model_ready_contexts": d1.get("model_ready_context_count"),
        "d0_event_relative_absent": d0.get("event_relative_absent_contexts"),
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
