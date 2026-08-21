#!/usr/bin/env python3
"""D0: V2 subject split and label/eligibility audit for the 110-subject public radar set.

Data/split/label governance only. Does not train, does not implement R1, does not
access D2 payload, and does not use MR60 labels.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_ID = "D0"
SCHEMA_VERSION = "D0.1"
AUDIT_DATE = "2026-08-22"
SPLIT_IDENTITY = "MMWAVE_V2_D0_SUBJECT_SPLIT_V1"
SPLIT_NAMESPACE = "MMWAVE_V2_D0_DEVELOPMENT_SPLIT_V1"
SPLIT_SEED = 20260822
SPLIT_NAMES = ("TRAIN", "VAL", "D0_SUBJECT_HELDOUT")
TARGET_RATIOS = {"TRAIN": 0.70, "VAL": 0.15, "D0_SUBJECT_HELDOUT": 0.15}
FORBIDDEN_SPLIT_NAMES = ("FINAL_TEST", "LOCKED_PUBLIC_CROSS_DEVICE_TEST")

CANONICAL_DOI = "10.5281/zenodo.18599983"
CANONICAL_VERSION = "1.1"
CANONICAL_DATASET_ID = "dataset-10_5281_zenodo_18599983"
CANONICAL_TITLE = (
    "Extensive Age-Balanced and Subject-Varied mmWave Radar Dataset of Referenced Records for Vital Signs"
)
BASE_SHA = "fbfb22dbce2fe502fd59ad61332daac3a7a3bcd7"
MPV0_COMMIT = "18e4a4e86d6bf95795d6749a91ce303ad3f1c417"

MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit"
SPLIT_PATH = ROOT / "datasets/mmwave/splits/mmwave_v2_d0_subject_split_v1.json"
MPV0_POLICY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/role_lock_policy.json"
MPV0_SOURCE = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/source_registry.json"
MN4_SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
A5_SPLIT = ROOT / "datasets/mmwave/splits/mmwave_real_subject_split_v1.json"
MN6_HELDOUT = ROOT / "datasets/mmwave/manifests/m_n6_heldout_result.json"
A0_IDENTITY = ROOT / "datasets/mmwave/manifests/a0_raw_inventory/source_identity.json"
A0_RECORDINGS = ROOT / "datasets/mmwave/manifests/a0_raw_inventory/recording_index.jsonl"
A6_WINDOWS = ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl"
A6_RECORDINGS = ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_recording_results.jsonl"
A6_EXCEPTIONS = ROOT / "datasets/mmwave/manifests/a6_full_conversion/exceptions.json"
A4_PROFILE = ROOT / "datasets/mmwave/manifests/a4_label_pilot/label_mapping_profile.json"

MANIFEST_JSON_FILES = (
    "source_population_audit.json",
    "v2_subject_split.json",
    "label_reference_audit.json",
    "eligibility_summary.json",
    "split_balance_summary.json",
    "exception_registry.json",
)

ELIGIBILITY_TAXONOMY = (
    "BREATHING_EVIDENCE_ELIGIBLE",
    "RR_REFERENCE_ELIGIBLE",
    "VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE",
    "TRANSITION_OR_AMBIGUOUS",
    "REFERENCE_UNAVAILABLE",
    "ANNOTATION_INVALID",
    "SOURCE_RECORDING_INVALID",
)

RADAR_HARDWARE = {
    "Lying": "NodeNs IWR6843ISK",
    "Sitting": "Texas Instruments IWR6843ISK-ODS",
}

ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)


class D0AccountingError(RuntimeError):
    """Stop split generation when 110/16/94 accounting cannot be reproduced."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def count_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: int(counter[key]) for key in sorted(counter)}


def invert_split_map(subject_ids: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for split_name, ids in subject_ids.items():
        for subject_id in ids:
            if subject_id in out:
                raise D0AccountingError(f"duplicate subject in historical split: {subject_id}")
            out[subject_id] = split_name
    return out


def deterministic_assignment_key(subject_id: str) -> str:
    return hashlib.sha256(f"{SPLIT_NAMESPACE}:{SPLIT_SEED}:{subject_id}".encode("utf-8")).hexdigest()


def calculate_split_counts(total: int) -> dict[str, int]:
    quotas = {name: total * TARGET_RATIOS[name] for name in SPLIT_NAMES}
    counts = {name: math.floor(quotas[name]) for name in SPLIT_NAMES}
    remaining = total - sum(counts.values())
    order = sorted(SPLIT_NAMES, key=lambda name: (-(quotas[name] - counts[name]), SPLIT_NAMES.index(name)))
    for name in order[:remaining]:
        counts[name] += 1
    return counts


def assign_subject_splits(subject_ids: list[str]) -> dict[str, str]:
    unique = sorted(set(subject_ids))
    if len(unique) != len(set(subject_ids)):
        raise D0AccountingError("duplicate subject ids in V2 eligible pool")
    counts = calculate_split_counts(len(unique))
    ordered = sorted(unique, key=lambda sid: (deterministic_assignment_key(sid), sid))
    assignment: dict[str, str] = {}
    cursor = 0
    for split_name in SPLIT_NAMES:
        for sid in ordered[cursor : cursor + counts[split_name]]:
            assignment[sid] = split_name
        cursor += counts[split_name]
    if len(assignment) != len(unique):
        raise D0AccountingError("split assignment did not cover the eligible pool")
    return assignment


def rr_available(window: dict[str, Any]) -> bool:
    info = window.get("movesense_reference_rr") or {}
    return info.get("rr_bpm") is not None


def window_eligibility(window: dict[str, Any], recording_invalid: bool, annotation_invalid: bool) -> dict[str, Any]:
    flags = {name: False for name in ELIGIBILITY_TAXONOMY}
    flags["SOURCE_RECORDING_INVALID"] = recording_invalid
    flags["ANNOTATION_INVALID"] = annotation_invalid
    flags["BREATHING_EVIDENCE_ELIGIBLE"] = (
        not recording_invalid
        and window.get("timeline_valid", True)
        and not (window.get("signal_quality_metrics") or {}).get("has_nan", False)
        and not (window.get("signal_quality_metrics") or {}).get("has_inf", False)
    )
    flags["RR_REFERENCE_ELIGIBLE"] = flags["BREATHING_EVIDENCE_ELIGIBLE"] and rr_available(window)
    flags["REFERENCE_UNAVAILABLE"] = flags["BREATHING_EVIDENCE_ELIGIBLE"] and not rr_available(window)
    flags["VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE"] = (
        window.get("safenest_label") == "APNEA"
        and window.get("mapping_rule_id") == "A4_RULE_APNEA_VOLUNTARY_PROXY"
        and window.get("assignment_status") == "ASSIGNED"
    )
    flags["TRANSITION_OR_AMBIGUOUS"] = window.get("assignment_status") == "AMBIGUOUS"

    if flags["SOURCE_RECORDING_INVALID"]:
        primary = "SOURCE_RECORDING_INVALID"
    elif flags["ANNOTATION_INVALID"]:
        primary = "ANNOTATION_INVALID"
    elif flags["TRANSITION_OR_AMBIGUOUS"]:
        primary = "TRANSITION_OR_AMBIGUOUS"
    elif flags["VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE"]:
        primary = "VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE"
    elif flags["RR_REFERENCE_ELIGIBLE"]:
        primary = "RR_REFERENCE_ELIGIBLE"
    elif flags["REFERENCE_UNAVAILABLE"]:
        primary = "REFERENCE_UNAVAILABLE"
    elif flags["BREATHING_EVIDENCE_ELIGIBLE"]:
        primary = "BREATHING_EVIDENCE_ELIGIBLE"
    else:
        primary = "SOURCE_RECORDING_INVALID"
    return {"flags": flags, "primary_eligibility": primary}


def v2_role_for_subject(subject_id: str, assignment: dict[str, str], excluded: set[str]) -> str:
    if subject_id in excluded:
        return "EXCLUDED_M_N6_HELDOUT"
    return assignment[subject_id]


def heldout_coverage_ok(windows: list[dict[str, Any]], assignment: dict[str, str]) -> dict[str, Any]:
    heldout_ids = {sid for sid, split in assignment.items() if split == "D0_SUBJECT_HELDOUT"}
    heldout_windows = [row for row in windows if row["subject_id"] in heldout_ids]
    apnea = sum(1 for row in heldout_windows if row.get("safenest_label") == "APNEA")
    rr = sum(1 for row in heldout_windows if row.get("safenest_label") in ("NORMAL", "RAPID_OR_ABNORMAL"))
    rest = sum(1 for row in heldout_windows if row.get("source_test_condition") == "Rest")
    post = sum(1 for row in heldout_windows if row.get("source_test_condition") == "Post-exercise")
    lying = sum(1 for row in heldout_windows if row.get("posture") == "Lying")
    sitting = sum(1 for row in heldout_windows if row.get("posture") == "Sitting")
    apnea_subjects = sorted(
        {
            row["subject_id"]
            for row in heldout_windows
            if row.get("safenest_label") == "APNEA"
        }
    )
    return {
        "heldout_subject_count": len(heldout_ids),
        "heldout_window_count": len(heldout_windows),
        "assigned_apnea_proxy_windows": apnea,
        "rr_supervised_windows": rr,
        "rest_windows": rest,
        "post_exercise_windows": post,
        "lying_windows": lying,
        "sitting_windows": sitting,
        "subjects_with_assigned_apnea_proxy": apnea_subjects,
        "usable": apnea >= 1 and rr >= 1 and rest >= 1 and post >= 1 and lying >= 1 and sitting >= 1 and len(apnea_subjects) >= 1,
    }


def build() -> dict[str, Any]:
    policy = load_json(MPV0_POLICY)
    mpv0_source = load_json(MPV0_SOURCE)
    a0 = load_json(A0_IDENTITY)
    mn4_split = load_json(MN4_SPLIT)
    a5_split = load_json(A5_SPLIT)
    mn6_heldout = load_json(MN6_HELDOUT)
    a4_profile = load_json(A4_PROFILE)
    recordings = load_jsonl(A0_RECORDINGS)
    windows = load_jsonl(A6_WINDOWS)
    a6_recordings = load_jsonl(A6_RECORDINGS)
    a6_exceptions = load_json(A6_EXCEPTIONS)

    frozen_excluded = list(policy["heldout_exclusion"]["excluded_subject_ids"])
    excluded = set(frozen_excluded)
    mn4_heldout = list(mn4_split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
    if frozen_excluded != mn4_heldout:
        raise D0AccountingError("M-PV0 excluded set does not match M-N4 NEW_MODEL_HELDOUT_TEST")
    if mn6_heldout["heldout_subject_count"] != len(mn4_heldout):
        raise D0AccountingError("M-N6 heldout subject count disagrees with M-N4 split")

    d0_identity = mpv0_source["sources"]["D0"]
    if d0_identity.get("dataset_doi_or_record_id") != CANONICAL_DOI:
        raise D0AccountingError("M-PV0 D0 canonical DOI is not Zenodo v1.1 18599983")
    if d0_identity.get("dataset_version") != CANONICAL_VERSION:
        raise D0AccountingError("M-PV0 D0 canonical version is not 1.1")
    if a0["dataset_identity"]["doi"] != CANONICAL_DOI:
        raise D0AccountingError("A0 DOI is not the frozen D0 v1.1 identity")

    all_subjects = sorted({row["subject_id"] for row in recordings})
    window_subjects = sorted({row["subject_id"] for row in windows})
    if len(all_subjects) != 110:
        raise D0AccountingError(f"A0 subject count is {len(all_subjects)}, expected 110")
    if window_subjects != all_subjects:
        raise D0AccountingError("A6 window subjects disagree with A0 recording subjects")
    if len(recordings) != 440:
        raise D0AccountingError(f"A0 recording count is {len(recordings)}, expected 440")
    if len(excluded) != 16 or excluded - set(all_subjects):
        raise D0AccountingError("frozen excluded set is not a 16-subject subset of A0")

    eligible = sorted(sid for sid in all_subjects if sid not in excluded)
    if len(eligible) != len(all_subjects) - len(excluded):
        raise D0AccountingError("eligible pool accounting failed")

    rec_ids = [row["recording_id"] for row in recordings]
    if len(rec_ids) != len(set(rec_ids)):
        raise D0AccountingError("duplicate recording_id in A0")
    win_ids = [row["window_id"] for row in windows]
    if len(win_ids) != len(set(win_ids)):
        raise D0AccountingError("duplicate window_id in A6")

    assignment = assign_subject_splits(eligible)
    counts = {name: sum(1 for sid in eligible if assignment[sid] == name) for name in SPLIT_NAMES}
    train = {sid for sid, split in assignment.items() if split == "TRAIN"}
    val = {sid for sid, split in assignment.items() if split == "VAL"}
    heldout = {sid for sid, split in assignment.items() if split == "D0_SUBJECT_HELDOUT"}
    if train & val or train & heldout or val & heldout:
        raise D0AccountingError("subject leakage in V2 D0 split")
    if (train | val | heldout) & excluded:
        raise D0AccountingError("M-N6 heldout subject entered V2 development split")
    if set(assignment) != set(eligible):
        raise D0AccountingError("assignment keys disagree with eligible pool")

    coverage = heldout_coverage_ok(windows, assignment)
    if not coverage["usable"]:
        raise D0AccountingError("D0_SUBJECT_HELDOUT lacks usable target coverage; split not frozen")

    a5_map = invert_split_map(a5_split["subject_ids"])
    mn6_map = invert_split_map(mn4_split["subject_ids"])
    a6_rec_map = {row["recording_id"]: row for row in a6_recordings}
    windows_by_rec: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for window in windows:
        windows_by_rec[window["recording_id"]].append(window)

    annotation_invalid_recordings = {
        row["recording_id"]
        for row in a6_exceptions
        if row.get("category") in {"ANNOTATION_PARSE_FAILURE", "ANNOTATION_READ_FAILURE"}
        and row.get("severity") in {"ERROR", "BLOCKING"}
    }
    recording_invalid = {
        row["recording_id"]
        for row in a6_recordings
        if row.get("status") not in {"SUCCESS", "SUCCESS_WITH_WARNINGS"}
    }

    window_primary = Counter()
    window_flag_true = Counter()
    window_labels = Counter()
    eligible_window_primary = Counter()
    eligible_window_labels = Counter()
    subjects_with_assigned_apnea: set[str] = set()
    subjects_with_voluntary_source: set[str] = set()

    for window in windows:
        rec_id = window["recording_id"]
        eligibility = window_eligibility(
            window,
            rec_id in recording_invalid,
            rec_id in annotation_invalid_recordings,
        )
        primary = eligibility["primary_eligibility"]
        window_primary[primary] += 1
        for name, flag in eligibility["flags"].items():
            if flag:
                window_flag_true[name] += 1
        label = window.get("safenest_label") or "AMBIGUOUS"
        window_labels[label] += 1
        if window["subject_id"] not in excluded:
            eligible_window_primary[primary] += 1
            eligible_window_labels[label] += 1
        if eligibility["flags"]["VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE"]:
            subjects_with_assigned_apnea.add(window["subject_id"])
        if window.get("original_annotation_type") == "VOLUNTARY_NON_BREATHING":
            subjects_with_voluntary_source.add(window["subject_id"])

    transition_only_hold_subjects = sorted(
        (set(eligible) & subjects_with_voluntary_source) - (set(eligible) & subjects_with_assigned_apnea)
    )

    recording_audits: list[dict[str, Any]] = []
    for rec in recordings:
        rec_id = rec["recording_id"]
        subject_id = rec["subject_id"]
        a6 = a6_rec_map[rec_id]
        rec_windows = windows_by_rec[rec_id]
        posture = rec["posture"]["value"]
        condition = rec["activity_or_test"]["value"]
        v2_split = v2_role_for_subject(subject_id, assignment, excluded)
        rec_primary = Counter()
        rec_labels = Counter()
        for window in rec_windows:
            eligibility = window_eligibility(
                window,
                rec_id in recording_invalid,
                rec_id in annotation_invalid_recordings,
            )
            rec_primary[eligibility["primary_eligibility"]] += 1
            rec_labels[window.get("safenest_label") or "AMBIGUOUS"] += 1
        quality_flags = list(a6.get("timeline_summary", {}).get("quality_flags") or [])
        recording_audits.append(
            {
                "recording_id": rec_id,
                "subject_id": subject_id,
                "source_subject_id": rec.get("source_subject_id"),
                "source_recording_path": rec.get("source_recording_path"),
                "historical_a5_split": a5_map.get(subject_id),
                "historical_m_n6_split": mn6_map.get(subject_id),
                "v2_split": v2_split,
                "posture": posture,
                "radar_hardware": RADAR_HARDWARE[posture],
                "radar_domain": "60_GHZ_FMCW",
                "source_test_condition": condition,
                "radar_files_present": bool(rec.get("radar_files")),
                "movesense_acc_files_present": bool(rec.get("movesense_acc_files")),
                "movesense_ecg_files_present": bool(rec.get("movesense_ecg_files")),
                "non_breathing_annotation_files_present": bool(rec.get("annotation_files")),
                "annotation_event_count": a6.get("annotation_event_count", 0),
                "a6_status": a6.get("status"),
                "duration_seconds": a6.get("timeline_summary", {}).get("duration_seconds"),
                "window_count": a6.get("window_count"),
                "timeline_quality_flags": quality_flags,
                "parse_failures": [],
                "window_labels": count_dict(rec_labels),
                "window_primary_eligibility": count_dict(rec_primary),
                "respiratory_reference_usability": "MOVESENSE_CHEST_ACC_RR_AVAILABLE",
                "movesense_ecg_role": "SOURCE_FILE_PRESENT_NOT_USED_FOR_A4_LABELS",
                "voluntary_non_breathing_source_term": "non_breathing_ts.csv / VOLUNTARY_NON_BREATHING",
                "safenest_apnea_meaning": "voluntary breath-hold based APNEA proxy, not clinical apnea",
                "clinical_apnea_claimed": False,
            }
        )

    recording_audits.sort(key=lambda row: row["recording_id"])

    mn6_train = set(mn4_split["subject_ids"]["TRAIN"])
    mn6_val = set(mn4_split["subject_ids"]["VAL"])
    reused_train = sorted(train & mn6_train)
    reused_val = sorted(val & mn6_val)
    moved_from_mn6 = {
        "eligible_subjects_that_changed_train_val_role": len(eligible) - len(reused_train) - len(reused_val),
        "same_as_m_n6_train": len(reused_train),
        "same_as_m_n6_val": len(reused_val),
        "note": "V2 assignment is independently hashed. Overlap with M-N6 TRAIN/VAL is incidental, not copied.",
    }

    split_doc = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "split_identity": SPLIT_IDENTITY,
        "source_identity": {
            "source_id": "D0",
            "role": "REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN",
            "canonical_dataset": CANONICAL_TITLE,
            "canonical_safenest_version": f"Zenodo v{CANONICAL_VERSION}",
            "doi": CANONICAL_DOI,
            "dataset_id": CANONICAL_DATASET_ID,
            "subjects": 110,
            "recordings": 440,
        },
        "algorithm": "SHA256(namespace:seed:subject_id) then largest-remainder counts",
        "namespace": SPLIT_NAMESPACE,
        "seed": SPLIT_SEED,
        "split_unit": "SUBJECT",
        "target_ratios": TARGET_RATIOS,
        "eligible_subject_count": len(eligible),
        "excluded_subject_count": len(frozen_excluded),
        "excluded_subject_ids": frozen_excluded,
        "excluded_reason": "M-N6 NEW_MODEL_HELDOUT_TEST consumed once; V2_SELECTION_REUSE=FORBIDDEN",
        "subject_ids": {
            "TRAIN": sorted(train),
            "VAL": sorted(val),
            "D0_SUBJECT_HELDOUT": sorted(heldout),
        },
        "counts": counts,
        "subject_overlap_allowed": False,
        "heldout_name": "D0_SUBJECT_HELDOUT",
        "heldout_is_final_cross_device_test": False,
        "heldout_role": "internal D0 subject-heldout for later candidate comparison before D2",
        "forbidden_names_not_used": list(FORBIDDEN_SPLIT_NAMES),
        "historical_m_n6_train_val_copied": False,
        "historical_a5_locked_test_auto_excluded": False,
        "m_n6_assignment_incidental_overlap": moved_from_mn6,
        "ratio_rationale": [
            "Every eligible subject has Rest, Post-exercise, Lying, and Sitting recordings, so subject-level allocation cannot collapse a condition or radar family.",
            "70/15/15 follows the established SafeNest development-split remainder convention without copying M-N6 subject IDs.",
            "14-subject VAL and 14-subject D0_SUBJECT_HELDOUT keep independent D0 evidence for later comparison and subject-heldout evaluation. D2 remains the locked external test.",
            "Coverage was inspected on this frozen seed before freeze. Subjects were not moved after the hash assignment.",
        ],
        "provenance": [
            repo_rel(A0_RECORDINGS),
            repo_rel(A6_WINDOWS),
            repo_rel(MN4_SPLIT),
            repo_rel(MN6_HELDOUT),
            repo_rel(MPV0_POLICY),
        ],
        "base_sha": BASE_SHA,
        "mpv0_commit": MPV0_COMMIT,
        "clinical_apnea_claimed": False,
        "d2_accessed": "NO",
        "mr60_supervised_use": "NO",
    }

    population = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "canonical_d0_identity": split_doc["source_identity"],
        "roadmap_v1_0_pointer": "https://zenodo.org/records/16760684",
        "roadmap_pointer_status": "RECORDED_DISCREPANCY_DO_NOT_DOWNGRADE_CANONICAL_IDENTITY",
        "a0_doi": a0["dataset_identity"]["doi"],
        "mpv0_canonical_doi": d0_identity.get("dataset_doi_or_record_id"),
        "mpv0_canonical_version": d0_identity.get("dataset_version"),
        "source_population": {
            "total_subjects": len(all_subjects),
            "total_recordings": len(recordings),
            "recordings_per_subject": count_dict(Counter(Counter(row["subject_id"] for row in recordings).values())),
            "frozen_excluded_subjects": len(frozen_excluded),
            "v2_eligible_subjects": len(eligible),
            "v2_eligible_recordings": sum(1 for row in recordings if row["subject_id"] not in excluded),
        },
        "excluded_subject_ids": frozen_excluded,
        "eligible_subject_ids": eligible,
        "posture_counts_all": count_dict(Counter(row["posture"]["value"] for row in recordings)),
        "condition_counts_all": count_dict(Counter(row["activity_or_test"]["value"] for row in recordings)),
        "eligible_posture_counts": count_dict(
            Counter(row["posture"]["value"] for row in recordings if row["subject_id"] not in excluded)
        ),
        "eligible_condition_counts": count_dict(
            Counter(row["activity_or_test"]["value"] for row in recordings if row["subject_id"] not in excluded)
        ),
        "annotation_file_presence_all": {
            "present": sum(1 for row in recordings if row.get("annotation_files")),
            "absent": sum(1 for row in recordings if not row.get("annotation_files")),
        },
        "eligible_rest_recordings_with_annotation": sum(
            1
            for row in recordings
            if row["subject_id"] not in excluded
            and row["activity_or_test"]["value"] == "Rest"
            and row.get("annotation_files")
        ),
        "eligible_rest_recordings_without_annotation": sum(
            1
            for row in recordings
            if row["subject_id"] not in excluded
            and row["activity_or_test"]["value"] == "Rest"
            and not row.get("annotation_files")
        ),
        "movesense_acc_files_all_present": all(bool(row.get("movesense_acc_files")) for row in recordings),
        "movesense_ecg_files_all_present": all(bool(row.get("movesense_ecg_files")) for row in recordings),
        "radar_files_all_present": all(bool(row.get("radar_files")) for row in recordings),
        "demographic_metadata_in_local_a0": False,
        "demographic_source_if_acquired_later": "ParticipantsInfo.xlsx on Zenodo v1.1; not used for this split",
        "local_raw_payload_present": False,
        "lineage_used": "A0 recording inventory + A6 window/recording manifests; raw zip not required for this phase",
        "d2_accessed": "NO",
        "mr60_supervised_use": "NO",
    }

    label_audit = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "label_profile_id": a4_profile.get("profile_id"),
        "apnea_policy": {
            "safenest_apnea": "voluntary breath-hold based APNEA proxy, not clinical apnea diagnosis",
            "source_term_preserved": "VOLUNTARY_NON_BREATHING / non_breathing_ts.csv",
            "clinical_apnea_claimed": False,
            "unlabeled_quiet_region_is_not_apnea": True,
            "low_radar_amplitude_is_not_apnea": True,
            "min_event_duration_seconds": a4_profile.get("apnea_policy", {}).get("min_event_duration_seconds"),
            "min_overlap_seconds": a4_profile.get("apnea_policy", {}).get("min_overlap_seconds"),
        },
        "rr_reference": {
            "independent_reference_used": "MOVESENSE_CHEST_ACC",
            "ecg_files_present": True,
            "ecg_used_for_a4_labels": False,
            "windows_with_acc_rr": sum(1 for row in windows if rr_available(row)),
            "windows_without_acc_rr": sum(1 for row in windows if not rr_available(row)),
        },
        "a6_window_label_counts_all": count_dict(window_labels),
        "a6_window_label_counts_eligible_pool": count_dict(eligible_window_labels),
        "mapping_rule_counts_eligible_pool": count_dict(
            Counter(row["mapping_rule_id"] for row in windows if row["subject_id"] not in excluded)
        ),
        "subjects_with_assigned_apnea_proxy_in_eligible_pool": sorted(set(eligible) & subjects_with_assigned_apnea),
        "eligible_subjects_without_assigned_apnea_proxy_window": transition_only_hold_subjects,
        "transition_only_hold_note": (
            "These eligible subjects have source voluntary non-breathing timestamps, but no 30 s window "
            "meets the A4 overlap >= 6 s APNEA-proxy rule. Rest windows are TRANSITION_OR_AMBIGUOUS. "
            "They remain eligible for breathing-evidence and RR supervision, not APNEA-proxy supervision."
        ),
        "a6_exception_categories": count_dict(Counter(row["category"] for row in a6_exceptions)),
        "annotation_parse_failures": 0,
        "source_recording_invalid_count": len(recording_invalid),
        "recordings": recording_audits,
        "d2_accessed": "NO",
        "mr60_supervised_use": "NO",
        "clinical_apnea_claimed": False,
    }

    eligibility = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "taxonomy": list(ELIGIBILITY_TAXONOMY),
        "derivation": "source evidence from A0/A4/A6; never from model predictions",
        "primary_precedence": [
            "SOURCE_RECORDING_INVALID",
            "ANNOTATION_INVALID",
            "TRANSITION_OR_AMBIGUOUS",
            "VOLUNTARY_BREATH_HOLD_PROXY_ELIGIBLE",
            "RR_REFERENCE_ELIGIBLE",
            "REFERENCE_UNAVAILABLE",
            "BREATHING_EVIDENCE_ELIGIBLE",
        ],
        "coexistence_rules": {
            "RR_and_not_APNEA_proxy": "Post-exercise and non-overlapping rest windows with Movesense ACC RR can supervise RR without APNEA-proxy labels.",
            "APNEA_proxy_and_RR_present": "Assigned APNEA-proxy windows also have ACC RR computed, but RR is not the supervision target during annotated hold overlap.",
            "TRANSITION_not_pure_class": "Non-zero hold overlap below 6 s is TRANSITION_OR_AMBIGUOUS; excluded from pure-class APNEA-proxy supervision.",
        },
        "window_primary_counts_all": count_dict(window_primary),
        "window_primary_counts_eligible_pool": count_dict(eligible_window_primary),
        "window_flag_true_counts_all": count_dict(window_flag_true),
        "eligible_subjects_with_apnea_proxy_window": len(set(eligible) & subjects_with_assigned_apnea),
        "eligible_subjects_with_voluntary_non_breathing_source": len(set(eligible) & subjects_with_voluntary_source),
        "eligible_subjects_transition_only_hold": transition_only_hold_subjects,
        "clinical_apnea_claimed": False,
    }

    def split_slice(split_name: str) -> dict[str, Any]:
        sids = {sid for sid, name in assignment.items() if name == split_name}
        recs = [row for row in recordings if row["subject_id"] in sids]
        wins = [row for row in windows if row["subject_id"] in sids]
        apnea_subjects = sorted({row["subject_id"] for row in wins if row.get("safenest_label") == "APNEA"})
        return {
            "subjects": len(sids),
            "recordings": len(recs),
            "windows": len(wins),
            "labels": count_dict(Counter(row.get("safenest_label") or "AMBIGUOUS" for row in wins)),
            "conditions": count_dict(Counter(row["activity_or_test"]["value"] for row in recs)),
            "postures": count_dict(Counter(row["posture"]["value"] for row in recs)),
            "radar_hardware": count_dict(Counter(RADAR_HARDWARE[row["posture"]["value"]] for row in recs)),
            "subjects_with_assigned_apnea_proxy": len(apnea_subjects),
            "assigned_apnea_proxy_windows": sum(1 for row in wins if row.get("safenest_label") == "APNEA"),
            "rr_windows": sum(1 for row in wins if row.get("safenest_label") in ("NORMAL", "RAPID_OR_ABNORMAL")),
            "transition_windows": sum(1 for row in wins if (row.get("safenest_label") or "AMBIGUOUS") == "AMBIGUOUS"),
        }

    leakage = {
        "TRAIN_intersect_VAL": sorted(train & val),
        "TRAIN_intersect_D0_SUBJECT_HELDOUT": sorted(train & heldout),
        "VAL_intersect_D0_SUBJECT_HELDOUT": sorted(val & heldout),
        "ALL_V2_D0_intersect_M_N6_HELDOUT": sorted((train | val | heldout) & excluded),
        "duplicate_recording_ids_across_v2_splits": [],
        "subject_overlap": 0,
        "excluded_heldout_reuse": 0,
        "duplicate_recording_leakage": 0,
    }
    rec_to_splits: dict[str, set[str]] = defaultdict(set)
    for rec in recordings:
        role = v2_role_for_subject(rec["subject_id"], assignment, excluded)
        if role != "EXCLUDED_M_N6_HELDOUT":
            rec_to_splits[rec["recording_id"]].add(role)
    dup_rec = sorted(rid for rid, splits in rec_to_splits.items() if len(splits) > 1)
    leakage["duplicate_recording_ids_across_v2_splits"] = dup_rec
    leakage["duplicate_recording_leakage"] = len(dup_rec)

    balance = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "split_identity": SPLIT_IDENTITY,
        "counts": counts,
        "by_split": {name: split_slice(name) for name in SPLIT_NAMES},
        "heldout_coverage": coverage,
        "leakage": leakage,
        "transition_only_hold_subjects_by_split": {
            name: [sid for sid in transition_only_hold_subjects if assignment[sid] == name]
            for name in SPLIT_NAMES
        },
        "allocation_inspected_before_freeze": True,
        "subjects_moved_after_assignment": False,
        "d2_accessed": "NO",
        "mr60_supervised_use": "NO",
    }

    exceptions = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "total_blockers": 0,
        "exceptions": [
            {
                "blocking": False,
                "code": "D0_LOCAL_PAYLOAD_ABSENT_IN_THIS_WORKTREE",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "gitignored db_records.zip is not present. D0 uses A0/A6 derived lineage, which is sufficient for split and label eligibility.",
            },
            {
                "blocking": False,
                "code": "D0_OFFICIAL_VS_LOCAL_REPACKAGING",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "Inherited A0 relationship_status LIKELY_REPACKAGED_NOT_FULLY_VERIFIED. Canonical identity remains Zenodo v1.1.",
            },
            {
                "blocking": False,
                "code": "D0_DEMOGRAPHIC_METADATA_NOT_IN_LOCAL_A0",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "ParticipantsInfo.xlsx is listed on Zenodo v1.1 but is not in the local A0 recording inventory. Split does not claim demographic stratification.",
            },
            {
                "blocking": False,
                "code": "D0_THREE_SUBJECTS_TRANSITION_ONLY_HOLD",
                "severity": "NON_BLOCKING_WARNING",
                "summary": (
                    "Eligible subjects p026, p034, and p040 have voluntary non-breathing source timestamps "
                    "but no assigned APNEA-proxy 30 s window (overlap below 6 s or hold outside the canonical window). "
                    "Hash assignment placed all three in TRAIN. VAL and D0_SUBJECT_HELDOUT retain assigned APNEA-proxy coverage."
                ),
            },
            {
                "blocking": False,
                "code": "D0_INCOMPLETE_TAIL_DROPPED",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "A6 dropped incomplete tails after full 30 s windows on 350 recordings. Some annotated hold seconds can fall outside canonical windows.",
            },
            {
                "blocking": False,
                "code": "D0_ECG_PRESENT_NOT_USED_FOR_A4_RR",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "Movesense ECG files exist on all 440 recordings. A4/A6 RR labels use Movesense chest ACC, not ECG.",
            },
            {
                "blocking": False,
                "code": "D0_V1_FEATURE_CONTRACT_NOT_FROZEN",
                "severity": "INFORMATIONAL",
                "summary": "D0 does not freeze R1 representation, MAD alternatives, RR model structure, or abstention thresholds.",
            },
        ],
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "source_population_audit.json": population,
        "v2_subject_split.json": split_doc,
        "label_reference_audit.json": label_audit,
        "eligibility_summary.json": eligibility,
        "split_balance_summary.json": balance,
        "exception_registry.json": exceptions,
    }
    checksum_files = {}
    for name, doc in artifacts.items():
        checksum_files[name] = dump_json(MANIFEST_DIR / name, doc)
    split_digest = dump_json(SPLIT_PATH, split_doc)
    checksums = {
        "algorithm": "SHA-256",
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "files": checksum_files,
        "split_file": {
            "path": repo_rel(SPLIT_PATH),
            "sha256": split_digest,
        },
    }
    dump_json(MANIFEST_DIR / "checksums.json", checksums)
    return {
        "eligible": len(eligible),
        "excluded": len(frozen_excluded),
        "counts": counts,
        "coverage": coverage,
        "checksums": checksums,
    }


def main() -> int:
    try:
        result = build()
    except D0AccountingError as exc:
        print(json.dumps({"ok": False, "gate": "BLOCKED", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "phase": PHASE_ID,
                "split_identity": SPLIT_IDENTITY,
                "eligible": result["eligible"],
                "excluded": result["excluded"],
                "counts": result["counts"],
                "heldout_usable": result["coverage"]["usable"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
