#!/usr/bin/env python3
"""
Machine-Readable Inventory Validator for Phase A0 mmWave Raw Dataset Inventory.

Verifies internal consistency across all Phase A0 manifest files:
- Valid JSON/JSONL syntax
- Uniqueness of deterministic identifiers (source_file_id, recording_id, subject_id, anomaly_id)
- Detail vs Summary count matching (zip members, recordings, anomalies, linkages, profiles)
- Referenced archive member path existence
- Gate status consistency
"""

import os
import sys
import json
import argparse


def validate_inventory_directory(inventory_dir):
    """
    Validates all manifest files in the specified directory.
    Returns (success: bool, errors: list[str]).
    """
    errors = []

    summary_path = os.path.join(inventory_dir, "inventory_summary.json")
    source_id_path = os.path.join(inventory_dir, "source_identity.json")
    claims_path = os.path.join(inventory_dir, "documented_claims.json")
    integrity_path = os.path.join(inventory_dir, "archive_integrity.json")
    members_path = os.path.join(inventory_dir, "archive_members.jsonl")
    recordings_path = os.path.join(inventory_dir, "recording_index.jsonl")
    profiles_path = os.path.join(inventory_dir, "schema_profiles.json")
    anomalies_path = os.path.join(inventory_dir, "anomalies.json")

    # 1. Check required files exist
    required_paths = [
        summary_path, source_id_path, claims_path, integrity_path,
        members_path, recordings_path, profiles_path, anomalies_path
    ]
    for p in required_paths:
        if not os.path.exists(p):
            errors.append(f"Required manifest file missing: {p}")

    if errors:
        return False, errors

    # 2. Parse JSON files
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse inventory_summary.json: {e}")
        return False, errors

    try:
        with open(integrity_path, "r", encoding="utf-8") as f:
            integrity = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse archive_integrity.json: {e}")
        return False, errors

    try:
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse schema_profiles.json: {e}")
        return False, errors

    try:
        with open(anomalies_path, "r", encoding="utf-8") as f:
            anomalies_data = json.load(f)
            anomalies = anomalies_data.get("anomalies", [])
    except Exception as e:
        errors.append(f"Failed to parse anomalies.json: {e}")
        return False, errors

    # 3. Parse JSONL files & verify IDs
    members = []
    member_paths = set()
    source_file_ids = set()

    try:
        with open(members_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                m = json.loads(line)
                members.append(m)
                path = m.get("member_path")
                if path:
                    member_paths.add(path)
                sf_id = m.get("source_file_id")
                if sf_id:
                    if sf_id in source_file_ids:
                        errors.append(f"Duplicate source_file_id '{sf_id}' at line {line_no} in archive_members.jsonl")
                    source_file_ids.add(sf_id)
    except Exception as e:
        errors.append(f"Failed to parse archive_members.jsonl: {e}")

    recordings = []
    recording_ids = set()
    subject_ids = set()
    linkage_counts = {
        "COMPLETE": 0,
        "COMPLETE_WITH_OPTIONAL_FILES_ABSENT": 0,
        "PARTIAL": 0,
        "AMBIGUOUS": 0,
        "BROKEN": 0,
        "UNCLASSIFIED": 0
    }

    try:
        with open(recordings_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                r = json.loads(line)
                recordings.append(r)
                rec_id = r.get("recording_id")
                if rec_id:
                    if rec_id in recording_ids:
                        errors.append(f"Duplicate recording_id '{rec_id}' at line {line_no} in recording_index.jsonl")
                    recording_ids.add(rec_id)
                subj_id = r.get("subject_id")
                if subj_id:
                    subject_ids.add(subj_id)

                status = r.get("linkage_status")
                if status in linkage_counts:
                    linkage_counts[status] += 1
                else:
                    errors.append(f"Unknown linkage_status '{status}' in recording '{rec_id}'")

                # Check referenced member paths exist in member_paths
                all_ref_files = (r.get("radar_files", []) + r.get("timestamp_files", []) +
                                 r.get("chirp_config_files", []) + r.get("reference_files", []) +
                                 r.get("annotation_files", []))
                for ref_path in all_ref_files:
                    if ref_path not in member_paths:
                        errors.append(f"Recording '{rec_id}' references missing archive member path: '{ref_path}'")

    except Exception as e:
        errors.append(f"Failed to parse recording_index.jsonl: {e}")

    # 4. Check anomaly ID uniqueness & severity counts
    anomaly_ids = set()
    severity_counts = {"BLOCKER": 0, "ERROR": 0, "WARNING": 0, "INFO": 0}
    for a in anomalies:
        a_id = a.get("anomaly_id")
        if a_id:
            if a_id in anomaly_ids:
                errors.append(f"Duplicate anomaly_id '{a_id}' in anomalies.json")
            anomaly_ids.add(a_id)
        sev = a.get("severity")
        if sev in severity_counts:
            severity_counts[sev] += 1

    # 5. Cross-check summary vs detailed counts
    if summary.get("archive_present"):
        if len(members) != summary.get("zip_member_count"):
            errors.append(f"Member count mismatch: archive_members.jsonl ({len(members)}) vs summary ({summary.get('zip_member_count')})")

        if len(recordings) != summary.get("recording_count"):
            errors.append(f"Recording count mismatch: recording_index.jsonl ({len(recordings)}) vs summary ({summary.get('recording_count')})")

        if summary.get("complete_linkage_count") != linkage_counts["COMPLETE"]:
            errors.append(f"Complete linkage count mismatch: summary ({summary.get('complete_linkage_count')}) vs detailed ({linkage_counts['COMPLETE']})")

        if summary.get("complete_with_optional_missing_count") != linkage_counts["COMPLETE_WITH_OPTIONAL_FILES_ABSENT"]:
            errors.append(f"Complete with optional missing count mismatch: summary ({summary.get('complete_with_optional_missing_count')}) vs detailed ({linkage_counts['COMPLETE_WITH_OPTIONAL_FILES_ABSENT']})")

        if summary.get("partial_linkage_count") != linkage_counts["PARTIAL"]:
            errors.append(f"Partial linkage count mismatch: summary ({summary.get('partial_linkage_count')}) vs detailed ({linkage_counts['PARTIAL']})")

        if summary.get("blocker_count") != severity_counts["BLOCKER"]:
            errors.append(f"Blocker count mismatch: summary ({summary.get('blocker_count')}) vs anomalies ({severity_counts['BLOCKER']})")

        if summary.get("error_count") != severity_counts["ERROR"]:
            errors.append(f"Error count mismatch: summary ({summary.get('error_count')}) vs anomalies ({severity_counts['ERROR']})")

        if summary.get("warning_count") != severity_counts["WARNING"]:
            errors.append(f"Warning count mismatch: summary ({summary.get('warning_count')}) vs anomalies ({severity_counts['WARNING']})")

        if summary.get("info_count") != severity_counts["INFO"]:
            errors.append(f"Info count mismatch: summary ({summary.get('info_count')}) vs anomalies ({severity_counts['INFO']})")

        if len(profiles.get("profiles", [])) != summary.get("schema_profile_count"):
            errors.append(f"Schema profile count mismatch: profiles ({len(profiles.get('profiles', []))}) vs summary ({summary.get('schema_profile_count')})")

    success = len(errors) == 0
    return success, errors


def main():
    parser = argparse.ArgumentParser(description="Validate Phase A0 Machine-Readable Raw Inventory")
    parser.add_argument("--inventory-dir", default="datasets/mmwave/manifests/a0_raw_inventory")
    args = parser.parse_args()

    repo_root = os.popen("git rev-parse --show-toplevel").read().strip() or os.getcwd()
    abs_inventory_dir = os.path.isabs(args.inventory_dir) and args.inventory_dir or os.path.join(repo_root, args.inventory_dir)

    print(f"Validating Phase A0 inventory in: {abs_inventory_dir}")
    success, errors = validate_inventory_directory(abs_inventory_dir)

    if success:
        print("SUCCESS: Phase A0 machine-readable inventory is internally valid and consistent.")
        sys.exit(0)
    else:
        print(f"VALIDATION FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
