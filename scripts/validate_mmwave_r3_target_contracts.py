#!/usr/bin/env python3
"""Validate the deterministic SafeNest mmWave V2 R3 target evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_mmwave_r3_target_contracts import (
    D0_SPLIT,
    OUTPUT_FILES,
    OUTPUT_RELATIVE_ROOT,
    ROOT,
    R1_CONTRACT_ID,
    R2_CANDIDATE_SET_ID,
    Q2_CONTRACT_ID,
    R3_SCHEMA_VERSION,
    _load_jsonl,
)


REQUIRED_CHECKS = (
    "R2_CONTRACT_INHERITED",
    "D0_TRAIN_ONLY",
    "D0_VAL_USED_FOR_TARGET_TUNING",
    "D0_SUBJECT_HELDOUT_USED",
    "M_N6_EXCLUDED_HELDOUT_USED",
    "D1_REFERENCE_SUPPORTED",
    "D2_USED",
    "MR60_SUPERVISED_USE",
    "BREATHING_EVIDENCE_TARGET_VERSIONED",
    "RR_TARGET_VERSIONED",
    "TEMPORAL_HOLD_TARGET_VERSIONED",
    "BREATHING_AND_RR_SEPARATE",
    "RR_UNAVAILABLE_ENCODED_AS_ZERO",
    "DIRECT_THREE_CLASS_PRIMARY_TARGET",
    "WHOLE_WINDOW_APNEA_DEFAULT",
    "LOW_RADAR_AMPLITUDE_DEFINES_APNEA",
    "RADAR_AMPLITUDE_USED_AS_REFERENCE_LABEL",
    "TEMPORAL_BASELINE_EXPLICIT",
    "TEMPORAL_RECOVERY_EXPLICIT",
    "TRANSITION_STATE_EXPLICIT",
    "D1_PROTOCOL_APNEA_AUTO_MAPPED_TO_SAFENEST_APNEA",
    "Q2_THRESHOLDS_REDEFINED",
    "INVALID_RADAR_INPUT_MODEL_SUPERVISION_ELIGIBLE",
    "F1_F2_F3_WINNER_SELECTED",
    "MODEL_TRAINING",
    "MODEL_ARCHITECTURE_SELECTED",
    "PROBABILITY_THRESHOLD_SELECTED",
    "APNEA_PERSISTENCE_THRESHOLD_FINALIZED",
    "PARALLEL_TRACK_BRANCH_CONTAMINATION",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk_strings(value: Any, trail: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(trail, value)]
    if isinstance(value, Mapping):
        items: list[tuple[str, str]] = []
        for key, child in value.items():
            child_trail = f"{trail}.{key}" if trail else str(key)
            items.extend(_walk_strings(child, child_trail))
        return items
    if isinstance(value, list):
        items = []
        for index, child in enumerate(value):
            items.extend(_walk_strings(child, f"{trail}[{index}]"))
        return items
    return []


def _finite_positive(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _validate_row_shape(row: Mapping[str, Any], source_id: str, errors: list[str], index: int) -> None:
    required = {
        "schema_version",
        "source_id",
        "dataset_id",
        "subject_id",
        "recording_id",
        "split",
        "breathing_evidence",
        "rr_target",
        "temporal_hold",
        "supervision_eligibility",
        "source_label_provenance",
        "provenance",
    }
    missing = sorted(required - set(row))
    if missing:
        errors.append(f"{source_id}[{index}] missing fields: {missing}")
        return
    if row.get("schema_version") != "MMWAVE_V2_R3_TARGET_ROW_V1":
        errors.append(f"{source_id}[{index}] row schema mismatch")
    if row.get("source_id") != source_id:
        errors.append(f"{source_id}[{index}] source_id mismatch")
    for key in ("breathing_evidence", "rr_target", "temporal_hold", "supervision_eligibility"):
        if not isinstance(row.get(key), Mapping):
            errors.append(f"{source_id}[{index}] {key} is not an object")
    provenance = row.get("provenance")
    if not isinstance(provenance, Mapping):
        errors.append(f"{source_id}[{index}] provenance is not an object")


def _validate_d0(rows: list[dict[str, Any]], split_doc: Mapping[str, Any], errors: list[str]) -> None:
    if len(rows) != 318:
        errors.append(f"D0 TRAIN row count: {len(rows)}")
    if len({row.get("window_id") for row in rows}) != len(rows):
        errors.append("D0 duplicate window_id")
    train_subjects = set(split_doc.get("subject_ids", {}).get("TRAIN", []))
    val_subjects = set(split_doc.get("subject_ids", {}).get("VAL", []))
    heldout_subjects = set(split_doc.get("subject_ids", {}).get("D0_SUBJECT_HELDOUT", []))
    excluded_subjects = set(split_doc.get("excluded_subject_ids", []))
    if len({row.get("subject_id") for row in rows}) != 66:
        errors.append("D0 TRAIN subject count is not 66")
    if len({row.get("recording_id") for row in rows}) != 264:
        errors.append("D0 TRAIN recording count is not 264")
    for index, row in enumerate(rows):
        _validate_row_shape(row, "D0", errors, index)
        if row.get("split") != "TRAIN":
            errors.append(f"D0[{index}] non-TRAIN row")
        subject_id = row.get("subject_id")
        if subject_id not in train_subjects:
            errors.append(f"D0[{index}] subject not in frozen TRAIN: {subject_id}")
        if subject_id in val_subjects or subject_id in heldout_subjects or subject_id in excluded_subjects:
            errors.append(f"D0[{index}] leaked subject: {subject_id}")
        breathing = row.get("breathing_evidence", {})
        rr = row.get("rr_target", {})
        temporal = row.get("temporal_hold", {})
        eligibility = row.get("supervision_eligibility", {})
        if breathing.get("target_contract") != "MMWAVE_V2_R3_BREATHING_EVIDENCE_TARGET_V1":
            errors.append(f"D0[{index}] breathing contract mismatch")
        if rr.get("target_contract") != "MMWAVE_V2_R3_RR_TARGET_V1":
            errors.append(f"D0[{index}] RR contract mismatch")
        if temporal.get("target_contract") != "MMWAVE_V2_R3_TEMPORAL_HOLD_TARGET_V1":
            errors.append(f"D0[{index}] temporal contract mismatch")
        if rr.get("target_status") == "TARGET_UNAVAILABLE":
            if rr.get("rr_bpm") is not None:
                errors.append(f"D0[{index}] unavailable RR must be null")
            if rr.get("unavailable_reason") in (None, ""):
                errors.append(f"D0[{index}] unavailable RR reason missing")
        elif not _finite_positive(rr.get("rr_bpm")):
            errors.append(f"D0[{index}] available RR is not finite positive")
        if rr.get("rr_bpm") == 0:
            errors.append(f"D0[{index}] zero RR used")
        for key in ("baseline_state", "event_state", "recovery_state", "transition_ambiguity"):
            if key not in temporal:
                errors.append(f"D0[{index}] temporal field missing: {key}")
        if eligibility.get("radar_input_available") is False and eligibility.get("model_supervision_eligible") is True:
            errors.append(f"D0[{index}] invalid radar input became supervision eligible")
        if temporal.get("event_state") != "NO_HOLD_EVENT_IN_WINDOW" and row.get("source_label_provenance", {}).get("a4_label") == "APNEA":
            if breathing.get("breathing_reference_state") == "BREATHING_REFERENCE_ABSENT":
                errors.append(f"D0[{index}] partial/annotated APNEA row became whole-window absence")
    if not all(row.get("temporal_hold", {}).get("persistence_threshold") == "DEFERRED_TO_M_PV1" for row in rows):
        errors.append("D0 persistence threshold was finalized")


def _validate_d1(rows: list[dict[str, Any]], errors: list[str]) -> None:
    if len(rows) != 265:
        errors.append(f"D1 row count: {len(rows)}")
    if len({row.get("recording_id") for row in rows}) != len(rows):
        errors.append("D1 duplicate recording_id")
    for index, row in enumerate(rows):
        _validate_row_shape(row, "D1", errors, index)
        breathing = row.get("breathing_evidence", {})
        rr = row.get("rr_target", {})
        temporal = row.get("temporal_hold", {})
        provenance = row.get("provenance", {})
        source = row.get("source_label_provenance", {})
        if breathing.get("target_status") != "TARGET_UNAVAILABLE":
            errors.append(f"D1[{index}] compact evidence unexpectedly created breathing target")
        if rr.get("target_status") != "TARGET_UNAVAILABLE" or rr.get("rr_bpm") is not None:
            errors.append(f"D1[{index}] compact evidence unexpectedly created RR target")
        if temporal.get("target_status") != "TARGET_UNAVAILABLE":
            errors.append(f"D1[{index}] temporal target unexpectedly available")
        if provenance.get("reference_waveform_materialized_in_compact_input") is not False:
            errors.append(f"D1[{index}] reference materialization flag changed")
        if source.get("source_apnea_string_auto_mapped_to_safenest_apnea") is not False:
            errors.append(f"D1[{index}] source apnea was auto-mapped")
        if source.get("source_breath_hold_protocol_present") is True and temporal.get("event_id") is not None:
            errors.append(f"D1[{index}] source apnea has guessed event_id")


def _validate_checksums(root: Path, evidence_root: Path, checksums: Mapping[str, Any], errors: list[str]) -> None:
    expected = {name for name in OUTPUT_FILES if name != "checksums.json"}
    files = checksums.get("files")
    if not isinstance(files, Mapping) or set(files) != expected:
        errors.append("R3 output checksum coverage is incomplete")
    else:
        for name in sorted(expected):
            path = evidence_root / name
            if not path.is_file():
                errors.append(f"checksum target missing: {name}")
            elif files.get(name) != _sha256(path):
                errors.append(f"checksum mismatch: {name}")
    if checksums.get("checksum_self_included") is not False:
        errors.append("checksum self-inclusion policy changed")
    for section in ("input_lineage", "code"):
        values = checksums.get(section)
        if not isinstance(values, Mapping):
            errors.append(f"checksum section missing: {section}")
            continue
        for relative, digest in values.items():
            path = root / relative
            if not path.is_file():
                errors.append(f"checksum path missing: {relative}")
            elif digest != _sha256(path):
                errors.append(f"checksum mismatch: {relative}")


def validate(root: Path = ROOT, evidence_root: Path = ROOT / OUTPUT_RELATIVE_ROOT) -> dict[str, Any]:
    errors: list[str] = []
    missing = [name for name in OUTPUT_FILES if not (evidence_root / name).is_file()]
    if missing:
        return {
            "schema_version": R3_SCHEMA_VERSION,
            "phase": "R3",
            "ok": False,
            "gate": "BLOCKED",
            "errors": [f"missing evidence file: {name}" for name in missing],
        }

    docs = {name: _read_json(evidence_root / name) for name in OUTPUT_FILES if name.endswith(".json") and name != "checksums.json"}
    checksums = _read_json(evidence_root / "checksums.json")
    d0_rows = _read_jsonl(evidence_root / "d0_target_rows.jsonl")
    d1_rows = _read_jsonl(evidence_root / "d1_target_rows.jsonl")
    for name, value in {**docs, "checksums.json": checksums}.items():
        for trail, string in _walk_strings(value, name):
            if "/Users/" in string or string.startswith("file://") or string.startswith("/private/") or string.startswith("/home/"):
                errors.append(f"absolute path in {trail}")

    target_set = docs["target_contract_set.json"]
    breathing = docs["breathing_evidence_contract.json"]
    rr = docs["rr_target_contract.json"]
    temporal = docs["temporal_hold_contract.json"]
    eligibility = docs["supervision_eligibility_contract.json"]
    d0_audit = docs["d0_target_audit.json"]
    d1_audit = docs["d1_target_audit.json"]
    cross = docs["cross_domain_target_compatibility.json"]
    transition = docs["transition_audit.json"]
    exceptions = docs["exception_registry.json"]
    recorded = docs["validation_result.json"]
    split_doc = _read_json(root / D0_SPLIT)

    if target_set.get("contract_set_id") != "MMWAVE_V2_R3_TARGET_CONTRACT_SET_V1":
        errors.append("target contract set identity mismatch")
    if target_set.get("r2_handoff", {}).get("head") != "37ea18d43780393b3f5c28deed655343ade59cd9":
        errors.append("R2 handoff head mismatch")
    if target_set.get("r2_handoff", {}).get("candidate_set_id") != R2_CANDIDATE_SET_ID:
        errors.append("R2 candidate set identity mismatch")
    if target_set.get("selection", {}).get("selected_candidate") is not None:
        errors.append("R3 candidate selection occurred")
    if target_set.get("upstream_contracts", {}).get("r1") != R1_CONTRACT_ID:
        errors.append("R1 contract inheritance mismatch")
    if target_set.get("upstream_contracts", {}).get("q2") != Q2_CONTRACT_ID:
        errors.append("Q2 contract inheritance mismatch")
    if breathing.get("contract_id") != "MMWAVE_V2_R3_BREATHING_EVIDENCE_TARGET_V1":
        errors.append("breathing contract identity mismatch")
    if rr.get("contract_id") != "MMWAVE_V2_R3_RR_TARGET_V1":
        errors.append("RR contract identity mismatch")
    if temporal.get("contract_id") != "MMWAVE_V2_R3_TEMPORAL_HOLD_TARGET_V1":
        errors.append("temporal contract identity mismatch")
    if eligibility.get("contract_id") != "MMWAVE_V2_R3_MODEL_SUPERVISION_ELIGIBILITY_V1":
        errors.append("eligibility contract identity mismatch")
    if target_set.get("safety_boundaries", {}).get("direct_three_class_primary_target") is not False:
        errors.append("direct three-class target was reinstated")
    if target_set.get("safety_boundaries", {}).get("whole_window_apnea_default") is not False:
        errors.append("whole-window APNEA default was reinstated")
    if target_set.get("safety_boundaries", {}).get("apnea_persistence_threshold_finalized") is not False:
        errors.append("persistence threshold was finalized")
    if exceptions.get("total_blockers") != 0:
        errors.append("R3 exception registry contains blockers")
    if d0_audit.get("d0_train_only") is not True or d0_audit.get("d0_val_used_for_target_tuning") is not False:
        errors.append("D0 governance flags are not fail-closed")
    if d1_audit.get("source_apnea_metadata_auto_mapped_to_safenest_apnea") is not False:
        errors.append("D1 source apnea auto-mapping flag is unsafe")
    if cross.get("model_score_used_to_define_targets") is not False:
        errors.append("target semantics depend on model score")
    if transition.get("d0_train", {}).get("partial_event_rows_are_not_whole_window_apnea") is not True:
        errors.append("transition policy missing")

    _validate_d0(d0_rows, split_doc, errors)
    _validate_d1(d1_rows, errors)
    _validate_checksums(root, evidence_root, checksums, errors)

    checks = recorded.get("checks", {}) if isinstance(recorded, Mapping) else {}
    for key in REQUIRED_CHECKS:
        if key not in checks:
            errors.append(f"validation check missing: {key}")
    if checks.get("D0_TRAIN_ONLY") != "YES":
        errors.append("D0_TRAIN_ONLY check is not YES")
    for key in (
        "D0_VAL_USED_FOR_TARGET_TUNING",
        "D0_SUBJECT_HELDOUT_USED",
        "M_N6_EXCLUDED_HELDOUT_USED",
        "D2_USED",
        "MR60_SUPERVISED_USE",
        "DIRECT_THREE_CLASS_PRIMARY_TARGET",
        "WHOLE_WINDOW_APNEA_DEFAULT",
        "LOW_RADAR_AMPLITUDE_DEFINES_APNEA",
        "RADAR_AMPLITUDE_USED_AS_REFERENCE_LABEL",
        "D1_PROTOCOL_APNEA_AUTO_MAPPED_TO_SAFENEST_APNEA",
        "Q2_THRESHOLDS_REDEFINED",
        "INVALID_RADAR_INPUT_MODEL_SUPERVISION_ELIGIBLE",
        "F1_F2_F3_WINNER_SELECTED",
        "MODEL_TRAINING",
        "MODEL_ARCHITECTURE_SELECTED",
        "PROBABILITY_THRESHOLD_SELECTED",
        "APNEA_PERSISTENCE_THRESHOLD_FINALIZED",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION",
    ):
        if checks.get(key) != "NO":
            errors.append(f"safety check is not NO: {key}")
    if recorded.get("ok") is not True or recorded.get("gate") != "PASS_WITH_LIMITATIONS":
        errors.append("recorded R3 validation result is not PASS_WITH_LIMITATIONS")

    result = {
        "schema_version": R3_SCHEMA_VERSION,
        "phase": "R3",
        "audit_date": "2026-08-23",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "checks": checks,
        "r3_ready_for_m_pv1": "YES" if not errors else "NO",
        "validated_files": list(OUTPUT_FILES),
        "d0_train_windows": len(d0_rows),
        "d1_recordings": len(d1_rows),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence-root", type=Path, default=ROOT / OUTPUT_RELATIVE_ROOT)
    args = parser.parse_args()
    try:
        result = validate(args.root.resolve(), args.evidence_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": R3_SCHEMA_VERSION, "phase": "R3", "ok": False, "gate": "BLOCKED", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
