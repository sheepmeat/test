#!/usr/bin/env python3
"""SafeNest Phase A6 — Full mmWave Real-Data Conversion Validator.

Provides in-memory and standalone CLI validation for Phase A6 full conversion,
verifying A0-A5 contract compliance, timestamp provenance, zero cross-split leakage,
path provenance, checksum integrity, and Phase-A exit gate criteria.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))


class A6ValidationError(Exception):
    """Raised when Phase A6 full conversion validation fails."""


def validate_full_conversion_artifacts(
    root_dir: Path = ROOT_DIR,
    manifest_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate all Phase A6 full conversion manifest artifacts against contracts."""
    if manifest_dir is None:
        manifest_dir = root_dir / "datasets/mmwave/manifests/a6_full_conversion"

    if not manifest_dir.is_dir():
        raise A6ValidationError(f"Phase A6 manifest directory not found: {manifest_dir}")

    # 1. Check raw archive SHA-256 immutability
    archive_path = root_dir / "datasets/raw_archives/external_datasets/db_records.zip"
    if not archive_path.is_file():
        raise A6ValidationError(f"Raw dataset archive zip not found: {archive_path}")

    hasher = hashlib.sha256()
    with open(archive_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    current_archive_sha256 = hasher.hexdigest()

    expected_archive_sha256 = "f0bcfdac94f88b43bb34d3da8e8f071a787291f86c97798059b8dbf4d4be08b0"
    if current_archive_sha256 != expected_archive_sha256:
        raise A6ValidationError(
            f"Raw archive SHA-256 changed! Expected {expected_archive_sha256}, got {current_archive_sha256}"
        )

    # 2. Check checksums.sha256 in A6 manifest directory
    checksums_file = manifest_dir / "checksums.sha256"
    if not checksums_file.is_file():
        raise A6ValidationError(f"Checksums manifest missing: {checksums_file}")

    for line in checksums_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        exp_hash, rel_name = parts[0], parts[1]
        target_f = manifest_dir / rel_name
        if not target_f.is_file():
            raise A6ValidationError(f"Manifest file listed in checksums missing: {rel_name}")
        actual_hash = hashlib.sha256(target_f.read_bytes()).hexdigest()
        if actual_hash != exp_hash:
            raise A6ValidationError(f"Checksum mismatch for manifest file {rel_name}: expected {exp_hash}, got {actual_hash}")

    # 3. Load A0 inventory & A5 splits
    a0_manifest = root_dir / "datasets/mmwave/manifests/a0_raw_inventory/recording_index.jsonl"
    if not a0_manifest.is_file():
        raise A6ValidationError(f"Authoritative A0 inventory missing: {a0_manifest}")

    a0_recordings = []
    with open(a0_manifest, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a0_recordings.append(json.loads(line))

    a0_rec_ids = set(r["recording_id"] for r in a0_recordings)
    a0_subj_ids = set(r["subject_id"] for r in a0_recordings)

    a5_split_json = root_dir / "datasets/mmwave/splits/mmwave_real_subject_split_v1.json"
    if not a5_split_json.is_file():
        raise A6ValidationError(f"Authoritative A5 split JSON missing: {a5_split_json}")

    a5_split_data = json.loads(a5_split_json.read_text(encoding="utf-8"))
    a5_subject_split_map = a5_split_data.get("subject_split_map", {})

    # 4. Load A6 manifests
    rec_results = []
    with open(manifest_dir / "full_recording_results.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec_results.append(json.loads(line))

    windows = []
    with open(manifest_dir / "full_window_manifest.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                windows.append(json.loads(line))

    provenance = []
    with open(manifest_dir / "full_provenance_manifest.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                provenance.append(json.loads(line))

    summary = json.loads((manifest_dir / "a6_summary.json").read_text(encoding="utf-8"))

    # 5. Rule Validations
    # Rule 1: Every A0 recording has exactly 1 A6 terminal result
    a6_rec_ids = set(r["recording_id"] for r in rec_results)
    if len(a6_rec_ids) != len(rec_results):
        raise A6ValidationError(f"Duplicate recording entries in full_recording_results.jsonl! Total: {len(rec_results)}, Unique: {len(a6_rec_ids)}")

    missing_recs = a0_rec_ids - a6_rec_ids
    if missing_recs:
        raise A6ValidationError(f"A0 recordings missing from A6 full conversion results: {missing_recs}")

    unknown_recs = a6_rec_ids - a0_rec_ids
    if unknown_recs:
        raise A6ValidationError(f"Unknown recordings in A6 conversion results: {unknown_recs}")

    # Rule 2: Immutable Split Inheritance
    valid_splits = {"TRAIN", "VALIDATION", "LOCKED_TEST"}
    for r in rec_results:
        rec_id = r["recording_id"]
        subj_id = r["subject_id"]
        rec_split = r["split"]
        expected_split = a5_subject_split_map.get(subj_id)

        if expected_split not in valid_splits:
            raise A6ValidationError(f"Invalid split value for subject {subj_id}: {expected_split}")
        if rec_split != expected_split:
            raise A6ValidationError(f"Recording {rec_id} split '{rec_split}' != inherited subject split '{expected_split}'")

    for w in windows:
        win_id = w["window_id"]
        subj_id = w["subject_id"]
        win_split = w["split"]
        expected_split = a5_subject_split_map.get(subj_id)

        if win_split != expected_split:
            raise A6ValidationError(f"Window {win_id} split '{win_split}' != inherited subject split '{expected_split}'")

    # Rule 3: Eligibility Restrictions
    for w in windows:
        win_id = w["window_id"]
        split = w["split"]
        status = w["assignment_status"]

        # Hard failure: LOCKED_TEST training eligibility must be False
        if split == "LOCKED_TEST" and w.get("training_eligible", False):
            raise A6ValidationError(f"LOCKED_TEST window {win_id} has training_eligible=True!")

        # Hard failure: AMBIGUOUS pure-class eligibility must be False
        if status == "AMBIGUOUS":
            if w.get("training_eligible", False) or w.get("validation_eligible", False) or w.get("locked_test_evaluation_eligible", False):
                raise A6ValidationError(f"AMBIGUOUS window {win_id} has pure-class eligibility set to True!")

    # Rule 4: Timestamp Contract
    for p in provenance:
        if p.get("timestamp_reference") != "COMMON_ACQUISITION_COMPUTER_CLOCK":
            raise A6ValidationError(f"Invalid timestamp reference: {p.get('timestamp_reference')}")
        if p.get("source_timezone") != "UNVERIFIED":
            raise A6ValidationError(f"Invalid source timezone: {p.get('source_timezone')}")
        if p.get("utc_conversion_claimed") is not False:
            raise A6ValidationError("utc_conversion_claimed must be False!")

    # Rule 5: Path Provenance (No absolute local paths in machine-readable canonical fields)
    for p in provenance:
        for key in ("archive_identifier", "source_radar_member", "source_timestamp_member", "a1_decoder_profile"):
            val = str(p.get(key, ""))
            if val.startswith("/Users/") or val.startswith("file://") or val.startswith("C:\\"):
                raise A6ValidationError(f"Absolute local path found in canonical provenance field '{key}': {val}")

    # Rule 6: Zero Cross-Split Leakage
    leakage = summary.get("leakage_audit_summary", {})
    if leakage.get("cross_split_exact_signal_overlap", 0) > 0:
        raise A6ValidationError(f"CRITICAL LEAKAGE: cross_split_exact_signal_overlap = {leakage['cross_split_exact_signal_overlap']}")
    if leakage.get("cross_split_subject_overlap", 0) > 0:
        raise A6ValidationError(f"CRITICAL LEAKAGE: cross_split_subject_overlap = {leakage['cross_split_subject_overlap']}")
    if leakage.get("cross_split_recording_overlap", 0) > 0:
        raise A6ValidationError(f"CRITICAL LEAKAGE: cross_split_recording_overlap = {leakage['cross_split_recording_overlap']}")
    if leakage.get("cross_split_window_id_overlap", 0) > 0:
        raise A6ValidationError(f"CRITICAL LEAKAGE: cross_split_window_id_overlap = {leakage['cross_split_window_id_overlap']}")

    # Rule 7: Gate State Verification
    if not summary.get("validation_passed", False):
        raise A6ValidationError("Phase A6 summary validation_passed is False!")

    return {
        "validation_success": True,
        "a6_gate_status": summary.get("a6_gate_status", "PASS_WITH_WARNINGS"),
        "phase_b_entry_status": summary.get("phase_b_entry_status", "READY_WITH_CONDITIONS"),
        "total_recordings_validated": len(rec_results),
        "total_windows_validated": len(windows),
        "total_provenance_validated": len(provenance),
        "raw_archive_sha256": current_archive_sha256,
    }


def main() -> None:
    res = validate_full_conversion_artifacts()
    print("Standalone A6 Full Conversion Validation Result:")
    print(f"Validation Success: {res['validation_success']}")
    print(f"A6 Gate Status: {res['a6_gate_status']}")
    print(f"Phase-B Entry Status: {res['phase_b_entry_status']}")
    print(f"Validated Recordings: {res['total_recordings_validated']}")
    print(f"Validated Windows: {res['total_windows_validated']}")


if __name__ == "__main__":
    main()
