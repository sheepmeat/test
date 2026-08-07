#!/usr/bin/env python3
"""Cross-validate Phase A1 pilot artifacts against the authoritative A0 index."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(
    *,
    a0_dir: Path,
    a1_dir: Path,
    archive_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    required = {
        "pilot_selection.json",
        "pilot_decode_results.jsonl",
        "decoder_profiles.json",
        "exceptions.json",
        "a1_summary.json",
    }
    for name in sorted(required):
        if not (a1_dir / name).is_file():
            errors.append(f"missing A1 artifact: {name}")
    if errors:
        return errors

    a0_records = _jsonl(a0_dir / "recording_index.jsonl")
    a0_by_id = {item["recording_id"]: item for item in a0_records}
    selection_doc = _json(a1_dir / "pilot_selection.json")
    selections = selection_doc.get("recordings", [])
    results = _jsonl(a1_dir / "pilot_decode_results.jsonl")
    profiles_doc = _json(a1_dir / "decoder_profiles.json")
    profiles = profiles_doc.get("profiles", [])
    exceptions_doc = _json(a1_dir / "exceptions.json")
    exceptions = exceptions_doc.get("exceptions", [])
    summary = _json(a1_dir / "a1_summary.json")

    selection_ids = [item.get("recording_id") for item in selections]
    result_ids = [item.get("recording_id") for item in results]
    if len(selection_ids) != len(set(selection_ids)):
        errors.append("pilot selection contains duplicate recording IDs")
    if len(result_ids) != len(set(result_ids)):
        errors.append("decode results contain duplicate recording IDs")
    if set(selection_ids) != set(result_ids):
        errors.append("every and only selected pilot recording must have a decode result")
    if selection_ids != sorted(selection_ids):
        errors.append("pilot selection ordering is not deterministic recording-ID order")
    if result_ids != sorted(result_ids):
        errors.append("decode result ordering is not deterministic recording-ID order")

    required_selection_fields = {
        "recording_id",
        "subject_id",
        "source_recording_path",
        "posture",
        "activity_or_test",
        "a0_schema_profile",
        "annotation_present",
        "selection_reason",
    }
    for item in selections:
        missing = required_selection_fields - set(item)
        if missing:
            errors.append(
                f"selection {item.get('recording_id')} missing fields: {sorted(missing)}"
            )
        source = a0_by_id.get(item.get("recording_id"))
        if source is None:
            errors.append(f"selection references unknown A0 recording: {item.get('recording_id')}")
            continue
        comparisons = {
            "subject_id": source["subject_id"],
            "source_recording_path": source["source_recording_path"],
            "posture": source["posture"]["value"],
            "activity_or_test": source["activity_or_test"]["value"],
            "a0_schema_profile": source["schema_profile"],
            "annotation_present": bool(source.get("annotation_files")),
        }
        for key, expected in comparisons.items():
            if item.get(key) != expected:
                errors.append(
                    f"selection {item['recording_id']} {key} differs from A0: "
                    f"{item.get(key)!r} != {expected!r}"
                )

    profile_ids = [profile.get("decoder_profile_id") for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        errors.append("decoder profile IDs are not unique")
    profile_id_set = set(profile_ids)
    valid_alignment = {
        "EXACT_ALIGNMENT",
        "OFF_BY_ONE",
        "FRAME_COUNT_MISMATCH",
        "TIMESTAMP_PARSE_FAILURE",
        "DECODE_FAILURE",
    }
    successful: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for result in results:
        record_id = result.get("recording_id")
        source = a0_by_id.get(record_id)
        if source is None:
            errors.append(f"decode result references unknown A0 recording: {record_id}")
            continue
        expected_members = {
            "radar_member": source["radar_files"][0],
            "timestamp_member": source["timestamp_files"][0],
            "chirp_config_member": source["chirp_config_files"][0],
        }
        for key, expected in expected_members.items():
            if result.get(key) != expected:
                errors.append(f"{record_id} {key} does not match A0 linkage")
        status = result.get("payload_decode_status", "")
        if status.startswith("SUCCESS") and not result.get("errors"):
            successful.append(result)
            numeric_nonnegative = (
                "compressed_size_bytes",
                "decompressed_size_bytes",
                "compression_ratio",
                "frame_count",
                "timestamp_count",
                "duplicate_timestamp_count",
                "backward_timestamp_count",
                "large_gap_count",
            )
            for key in numeric_nonnegative:
                value = result.get(key)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                    errors.append(f"{record_id} has invalid numeric {key}: {value!r}")
            for key in ("frame_axis", "antenna_axis", "range_bin_axis"):
                if not isinstance(result.get(key), int):
                    errors.append(f"{record_id} unresolved axis is not explicit integer: {key}")
            shape = result.get("shape")
            if not (
                isinstance(shape, list)
                and len(shape) == 3
                and all(isinstance(value, int) and value > 0 for value in shape)
            ):
                errors.append(f"{record_id} has invalid shape: {shape!r}")
            else:
                if result["frame_count"] != shape[result["frame_axis"]]:
                    errors.append(f"{record_id} frame count does not match decoded shape")
            expected_difference = result["frame_count"] - result["timestamp_count"]
            if result.get("frame_timestamp_difference") != expected_difference:
                errors.append(f"{record_id} frame/timestamp difference is inconsistent")
            if result.get("decoder_profile_id") not in profile_id_set:
                errors.append(f"{record_id} references missing decoder profile")
            if result.get("arbitrary_object_execution") is not False:
                errors.append(f"{record_id} does not explicitly prohibit object execution")
        else:
            failures.append(result)
            if not result.get("errors"):
                errors.append(f"failed result {record_id} has no preserved error")
        if result.get("alignment_status") not in valid_alignment:
            errors.append(f"{record_id} has invalid alignment status")

    profile_counts = Counter(
        result.get("decoder_profile_id") for result in successful
    )
    for profile in profiles:
        profile_id = profile["decoder_profile_id"]
        if profile.get("recording_count") != profile_counts[profile_id]:
            errors.append(f"profile {profile_id} recording count mismatch")
        supported = sorted(
            {
                result["a0_schema_profile"]
                for result in successful
                if result["decoder_profile_id"] == profile_id
            }
        )
        if profile.get("supported_a0_schema_profiles") != supported:
            errors.append(f"profile {profile_id} A0-profile mapping mismatch")
        if profile.get("safe_decoder") is not True:
            errors.append(f"profile {profile_id} is not explicitly safe")
        if "remaining_unknowns" not in profile:
            errors.append(f"profile {profile_id} omits remaining_unknowns")

    expected_counts = {
        "pilot_recording_count": len(selections),
        "pilot_subject_count": len({item["subject_id"] for item in selections}),
        "decode_success_count": len(successful),
        "decode_warning_count": sum(bool(item.get("warnings")) for item in successful),
        "decode_failure_count": len(failures),
        "decoder_profile_count": len(profiles),
        "exact_frame_timestamp_alignment_count": sum(
            item.get("alignment_status") == "EXACT_ALIGNMENT" for item in successful
        ),
        "alignment_mismatch_count": sum(
            item.get("alignment_status") != "EXACT_ALIGNMENT" for item in successful
        ),
        "blocker_count": sum(item.get("severity") == "BLOCKER" for item in exceptions),
        "error_count": sum(item.get("severity") == "ERROR" for item in exceptions),
        "warning_count": sum(item.get("severity") == "WARNING" for item in exceptions),
        "info_count": sum(item.get("severity") == "INFO" for item in exceptions),
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            errors.append(f"summary {key} mismatch: {summary.get(key)!r} != {expected!r}")

    selected_profiles = {item["a0_schema_profile"] for item in selections}
    if selected_profiles != {"SCHEMA_PROFILE_001", "SCHEMA_PROFILE_002"}:
        errors.append("pilot does not cover both A0 schema profiles")
    if {item["posture"] for item in selections} != {"Lying", "Sitting"}:
        errors.append("pilot does not cover both postures")
    if {item["activity_or_test"] for item in selections} != {"Rest", "Post-exercise"}:
        errors.append("pilot does not cover rest and post-exercise")
    if {item["annotation_present"] for item in selections} != {False, True}:
        errors.append("pilot does not cover annotation presence and absence")

    if summary.get("archive_unchanged_after_a1") is not True:
        errors.append("summary does not confirm archive immutability")
    if summary.get("arbitrary_object_execution_performed") is not False:
        errors.append("summary does not confirm zero arbitrary object execution")
    if summary.get("unsafe_deserialization_required") is not False:
        errors.append("summary claims unsafe deserialization is required")
    if archive_path is not None:
        measured = _sha256(archive_path)
        if measured != summary.get("archive_sha256_before_a1"):
            errors.append("live archive hash differs from A1 pre-hash")
        if measured != summary.get("archive_sha256_after_a1"):
            errors.append("live archive hash differs from A1 post-hash")

    valid_severity = {"INFO", "WARNING", "ERROR", "BLOCKER"}
    valid_category = {
        "DECOMPRESSION",
        "SERIALIZATION",
        "UNSAFE_SERIALIZATION",
        "ARRAY_SHAPE",
        "DTYPE",
        "COMPLEX_ENCODING",
        "AXIS_SEMANTICS",
        "CHIRP_CONFIG",
        "FRAME_COUNT",
        "TIMESTAMP_ALIGNMENT",
        "SCHEMA_VARIANT",
        "A0_CONTRADICTION",
        "UNKNOWN",
    }
    exception_ids = [item.get("exception_id") for item in exceptions]
    if len(exception_ids) != len(set(exception_ids)):
        errors.append("exception IDs are not unique")
    for item in exceptions:
        if item.get("severity") not in valid_severity:
            errors.append(f"invalid exception severity: {item.get('severity')}")
        if item.get("category") not in valid_category:
            errors.append(f"invalid exception category: {item.get('category')}")
        unknown = set(item.get("affected_recording_ids", [])) - set(result_ids)
        if unknown:
            errors.append(f"exception {item.get('exception_id')} references unknown pilots")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--a0-dir",
        type=Path,
        default=root / "datasets/mmwave/manifests/a0_raw_inventory",
    )
    parser.add_argument(
        "--a1-dir",
        type=Path,
        default=root / "datasets/mmwave/manifests/a1_rfft_pilot",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=root / "datasets/raw_archives/external_datasets/db_records.zip",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    problems = validate(
        a0_dir=args.a0_dir.resolve(),
        a1_dir=args.a1_dir.resolve(),
        archive_path=args.archive.resolve(),
    )
    if problems:
        print("A1 manifest validation: FAIL")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("A1 manifest validation: PASS")
