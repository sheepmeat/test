"""Focused tests for the Thermal real-capture contract and validator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_thermal_real_capture import validate_capture  # noqa: E402


CONTRACT_ROOT = ROOT / "datasets/thermal/manifests/real_capture_contract_v1"
STATIC_EXAMPLE = CONTRACT_ROOT / "examples/valid_static"
TEMPORAL_EXAMPLE = CONTRACT_ROOT / "examples/valid_temporal"


def _copy_example(tmp_path: Path, source: Path = STATIC_EXAMPLE) -> Path:
    target = tmp_path / source.name
    shutil.copytree(source, target)
    return target


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def _refresh_checksums(session_dir: Path) -> None:
    rows = []
    for path in sorted(session_dir.rglob("*")):
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        relative = path.relative_to(session_dir).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {relative}")
    (session_dir / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _codes(result: dict) -> set[str]:
    return {item["code"] for item in result.get("errors", []) + result.get("warnings", [])}


def test_valid_minimal_static_session() -> None:
    result = validate_capture(STATIC_EXAMPLE)
    assert result["capture_status"] == "CAPTURE_STRUCTURE_VALID_WITH_LIMITATIONS"
    assert result["raw_evidence_classification"] == "FULL_FRAME_RAW"
    assert result["temporal_provenance_status"] == "TEMPORAL_ORDER_ONLY"
    assert result["errors"] == []


def test_valid_temporal_capable_session() -> None:
    result = validate_capture(TEMPORAL_EXAMPLE)
    assert result["capture_status"] == "CAPTURE_STRUCTURE_VALID_WITH_LIMITATIONS"
    assert result["temporal_provenance_status"] == "TEMPORAL_PROVENANCE_VERIFIED"
    assert result["annotation_coverage"]["sessions"][0]["event_ids"] == ["event_S002_001_001"]
    assert result["errors"] == []


def test_duplicate_frame_id_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    records[1]["frame_id"] = records[0]["frame_id"]
    _write_jsonl(frames_path, records)
    result = validate_capture(root)
    assert "DUPLICATE_FRAME_ID" in _codes(result)


def test_missing_raw_frame_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    session = next(root.rglob("session.json")).parent
    (session / "raw/frame_S001_001_000001.bin").unlink()
    result = validate_capture(root)
    assert "MISSING_RAW_FRAME" in _codes(result)
    assert result["raw_integrity_status"] == "FAIL"


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    session = next(root.rglob("session.json")).parent
    (session / "raw/frame_S001_001_000000.bin").write_text("TAMPERED\n", encoding="utf-8")
    result = validate_capture(root)
    assert "CHECKSUM_MISMATCH" in _codes(result)


def test_non_monotonic_sequence_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    records[1]["sequence_index"] = 0
    _write_jsonl(frames_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "DUPLICATE_SEQUENCE_INDEX" in _codes(result)


def test_timestamp_reversal_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    records[1]["host_receive_monotonic_timestamp_ns"] = 900000000
    records[1]["host_wall_time"] = "2026-08-14T09:59:59.900+09:00"
    _write_jsonl(frames_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "TIMESTAMP_REVERSAL" in _codes(result)


def test_sequence_gap_is_reported_without_silent_repair(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    records[1]["sequence_index"] = 3
    records[1]["sensor_frame_counter"] = 103
    _write_jsonl(frames_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "SEQUENCE_GAP" in _codes(result)
    assert result["packet_loss_summary"]["sequence_gap_count"] == 2


@pytest.mark.parametrize("field", ["session_id", "subject_id"])
def test_missing_session_or_subject_id_is_rejected(tmp_path: Path, field: str) -> None:
    root = _copy_example(tmp_path)
    session_path = next(root.rglob("session.json"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session[field] = None
    _write_json(session_path, session)
    _refresh_checksums(session_path.parent)
    result = validate_capture(root)
    assert ("MISSING_SESSION_ID" if field == "session_id" else "MISSING_SUBJECT_ID") in _codes(result)


def test_bad_annotation_frame_reference_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    annotations_path = next(root.rglob("annotations.jsonl"))
    records = _read_jsonl(annotations_path)
    records[0]["frame_id"] = "frame_unknown"
    _write_jsonl(annotations_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "ANNOTATION_FRAME_REFERENCE_MISSING" in _codes(result)


def test_bad_event_ordering_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path, TEMPORAL_EXAMPLE)
    annotations_path = next(root.rglob("annotations.jsonl"))
    records = _read_jsonl(annotations_path)
    records[0]["phase_ranges"][0]["start_frame_id"] = "frame_S002_001_000002"
    records[0]["phase_ranges"][0]["end_frame_id"] = "frame_S002_001_000001"
    _write_jsonl(annotations_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "EVENT_RANGE_REVERSED" in _codes(result)


def test_unsupported_source_label_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    annotations_path = next(root.rglob("annotations.jsonl"))
    records = _read_jsonl(annotations_path)
    records[0]["source_annotation"]["label"] = "FALL"
    _write_jsonl(annotations_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "UNSUPPORTED_SOURCE_LABEL" in _codes(result)


def test_unknown_label_is_accepted(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    annotations_path = next(root.rglob("annotations.jsonl"))
    records = _read_jsonl(annotations_path)
    records[0]["source_annotation"]["label"] = "UNKNOWN"
    _write_jsonl(annotations_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert "UNSUPPORTED_SOURCE_LABEL" not in _codes(result)
    assert result["capture_status"] != "CAPTURE_INVALID"


def test_preprocessed_only_collection_is_rejected_as_raw_evidence(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    for record in records:
        record["raw_representation"] = "PREPROCESSED_ONLY"
    _write_jsonl(frames_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert result["raw_evidence_classification"] == "PREPROCESSED_ONLY_INSUFFICIENT"
    assert "PREPROCESSED_ONLY_COLLECTION" in _codes(result)


def test_scalar_only_collection_has_limited_classification(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    frames_path = next(root.rglob("frames.jsonl"))
    records = _read_jsonl(frames_path)
    for record in records:
        record["raw_representation"] = "SCALAR_ONLY"
        record["decoded_native_file"] = None
        record["scalar_thermal_max_c"] = None
    _write_jsonl(frames_path, records)
    _refresh_checksums(next(root.rglob("session.json")).parent)
    result = validate_capture(root)
    assert result["raw_evidence_classification"] == "SCALAR_ONLY_LIMITED"
    assert "SCALAR_ONLY_FULL_FRAME_UNAVAILABLE" in _codes(result)
    assert "PREPROCESSED_ONLY_COLLECTION" not in _codes(result)


def test_frame_random_split_metadata_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    collection_path = root / "collection.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    collection["split_policy"]["frame_random_split_allowed"] = True
    collection["split_policy"]["assignment_method"] = "FRAME_RANDOM_SEED_1"
    _write_json(collection_path, collection)
    result = validate_capture(root)
    assert "FRAME_RANDOM_SPLIT_REJECTED" in _codes(result)


def test_subject_role_leakage_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    original_session = next(root.rglob("session.json")).parent
    second_session = original_session.parent / "session_S001_002"
    shutil.copytree(original_session, second_session)
    session_path = second_session / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["session_id"] = "session_S001_002"
    session["recording_id"] = "recording_S001_002"
    session["role_governance"]["role"] = "REAL_DEVELOPMENT"
    _write_json(session_path, session)
    frames_path = second_session / "frames.jsonl"
    records = _read_jsonl(frames_path)
    for record in records:
        record["session_id"] = "session_S001_002"
        record["recording_id"] = "recording_S001_002"
        record["frame_id"] = record["frame_id"].replace("S001_001", "S001_002")
    _write_jsonl(frames_path, records)
    annotations_path = second_session / "annotations.jsonl"
    annotations = _read_jsonl(annotations_path)
    for record in annotations:
        record["session_id"] = "session_S001_002"
        record["annotation_id"] = record["annotation_id"].replace("S001_001", "S001_002")
        if record.get("frame_id"):
            record["frame_id"] = record["frame_id"].replace("S001_001", "S001_002")
    _write_jsonl(annotations_path, annotations)
    collection_path = root / "collection.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    collection["session_ids"].append("session_S001_002")
    _write_json(collection_path, collection)
    _refresh_checksums(second_session)
    result = validate_capture(root)
    assert "SUBJECT_ROLE_LEAKAGE" in _codes(result)


def test_locked_test_used_as_train_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    collection_path = root / "collection.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    collection["collection_role"] = "REAL_LOCKED_TEST"
    collection["split_policy"]["locked_test_access"] = "UNTOUCHED"
    _write_json(collection_path, collection)
    session_path = next(root.rglob("session.json"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["role_governance"]["role"] = "TRAIN"
    _write_json(session_path, session)
    _refresh_checksums(session_path.parent)
    result = validate_capture(root)
    assert "LOCKED_TEST_USED_AS_TRAIN" in _codes(result)


def test_filename_order_only_temporal_claim_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    session_path = next(root.rglob("session.json"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["temporal_evidence_claim"] = {
        "claimed_status": "TEMPORAL_PROVENANCE_VERIFIED",
        "filename_order_used_as_time": True,
        "source": "FILENAME_ORDER",
    }
    _write_json(session_path, session)
    _refresh_checksums(session_path.parent)
    result = validate_capture(root)
    assert "FILENAME_ORDER_NOT_TEMPORAL" in _codes(result)
    assert "TEMPORAL_CLAIM_NOT_SUPPORTED" in _codes(result)


def test_extra_unregistered_raw_file_is_rejected(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    session = next(root.rglob("session.json")).parent
    (session / "raw/extra.bin").write_text("EXTRA\n", encoding="utf-8")
    result = validate_capture(root)
    assert "EXTRA_UNREGISTERED_RAW_FILE" in _codes(result)


def test_schema_files_are_valid_json_and_portable() -> None:
    schema_paths = sorted(CONTRACT_ROOT.glob("*.schema.json"))
    assert len(schema_paths) == 5
    for path in schema_paths:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        assert parsed["$schema"].startswith("https://json-schema.org/")
        assert "/Users/" not in path.read_text(encoding="utf-8")
        assert "file://" not in path.read_text(encoding="utf-8")


def test_validator_has_no_model_coupling() -> None:
    source = (ROOT / "scripts/validate_thermal_real_capture.py").read_text(encoding="utf-8").lower()
    assert "thermalinterpreter" not in source
    assert "tflite" not in source
    assert "tensorflow" not in source
