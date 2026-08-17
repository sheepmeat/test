"""Focused T-C0 contract and offline-tool tests using synthetic metadata only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import types

import numpy as np
import pytest

from scripts.thermal_mi48_device_domain import (
    CLASS_ORDER,
    P1_MEAN,
    P1_STD,
    TARGET_MAP,
    build_canonical_dataset,
    compare_domains,
    compute_sample_id,
    dry_run_legacy_snapshot,
    p1_from_celsius,
    raw_uint16_to_celsius,
    validate_built_dataset,
    evaluate_float_tflite,
)
from scripts.validate_thermal_t_c0 import validate_evidence


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "datasets/thermal/manifests/T-C0_mi48_device_domain_acquisition"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_fixture(root: Path, *, labels: tuple[str, ...] = ("STANDING", "LYING"), bad_bytes: bool = False) -> Path:
    collection = root / "collection"
    session_dir = collection / "subjects/SUBJ-001/sessions/SESSION-001"
    (session_dir / "decoded_native").mkdir(parents=True)
    _write_json(collection / "collection.json", {"schema_version": "safenest.thermal.real_capture.collection.v1", "collection_id": "COLL-001"})
    _write_json(
        session_dir / "session.json",
        {
            "schema_version": "safenest.thermal.real_capture.session.v1",
            "collection_id": "COLL-001",
            "subject_id": "SUBJ-001",
            "session_id": "SESSION-001",
            "recording_id": "REC-001",
            "sensor": {"native_byte_order": "little", "native_shape": [62, 80], "native_dtype": "uint16"},
        },
    )
    frames = []
    annotations = []
    for index, label in enumerate(labels):
        frame_id = f"FRAME-{index:03d}"
        relative = f"decoded_native/{frame_id}.bin"
        values = np.full((62, 80), 2731 + index * 10, dtype="<u2")
        payload = values.tobytes()
        if bad_bytes and index == 0:
            payload = payload[:-2]
        (session_dir / relative).write_bytes(payload)
        frames.append({"frame_id": frame_id, "sequence_index": index, "validity_status": "VALID", "decoded_native_file": relative, "event_id": None, "host_wall_time": f"2026-08-18T10:00:0{index}+00:00", "host_receive_monotonic_timestamp_ns": 1_000_000_000 + index * 1_000_000})
        annotations.append({"annotation_id": f"ANN-{index}", "frame_id": frame_id, "revision": 1, "source_annotation": {"label": label, "ground_truth_method": "CONTROLLED_SCENARIO_MANIFEST", "confidence": 1.0}, "provenance": {"annotator_code": "OP-001"}})
    (session_dir / "frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in frames), encoding="utf-8")
    (session_dir / "annotations.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in annotations), encoding="utf-8")
    split = root / "split.json"
    _write_json(split, {"schema_version": "safenest.thermal.mi48.split.v1", "assignments": {"SUBJ-001": "VALIDATION"}})
    return collection


def test_raw_conversion_and_frozen_p1() -> None:
    raw = np.array([[2731, 2741]], dtype=np.uint16).reshape(1, 1, 2)
    # Conversion helper requires the native geometry, so use a full frame.
    frame = np.full((62, 80), 2731, dtype=np.uint16)
    celsius = raw_uint16_to_celsius(frame)
    assert celsius.shape == (62, 80)
    assert float(celsius[0, 0]) == pytest.approx(-0.04998779, abs=1e-6)
    p1 = p1_from_celsius(np.full((62, 80), P1_MEAN, dtype=np.float32))
    assert np.allclose(p1, 0.0)


def test_deterministic_sample_id_is_not_array_index() -> None:
    first = compute_sample_id("COLL-001", "SESSION-001", "FRAME-001")
    second = compute_sample_id("COLL-001", "SESSION-001", "FRAME-001")
    assert first == second
    assert first.startswith("MI48S1_")
    assert len(first) == len("MI48S1_") + 64


def test_builder_is_deterministic_and_preserves_lineage(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path)
    first = tmp_path / "derived-a"
    second = tmp_path / "derived-b"
    split = tmp_path / "split.json"
    build_canonical_dataset(capture, first, split_map_path=split, derive_p1=True, require_split=True)
    build_canonical_dataset(capture, second, split_map_path=split, derive_p1=True, require_split=True)
    for name in ("samples.jsonl", "celsius.npy", "p1.npy", "dataset_build_summary.json"):
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == hashlib.sha256((second / name).read_bytes()).hexdigest()
    result = validate_built_dataset(first)
    assert result["status"] == "PASS"
    assert result["sample_count"] == 2
    assert result["split_counts"] == {"VALIDATION": 2}


def test_builder_rejects_bad_native_shape_or_dtype(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path, bad_bytes=True)
    with pytest.raises(ValueError, match="byte length"):
        build_canonical_dataset(capture, tmp_path / "derived", split_map_path=tmp_path / "split.json", require_split=True)


def test_builder_rejects_unknown_label_instead_of_fabricating_target(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path, labels=("UNKNOWN",))
    with pytest.raises(ValueError, match="no valid labelled"):
        build_canonical_dataset(capture, tmp_path / "derived", split_map_path=tmp_path / "split.json", require_split=True)


def test_builder_rejects_inconsistent_presence_posture_label(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path)
    annotation_path = capture / "subjects/SUBJ-001/sessions/SESSION-001/annotations.jsonl"
    rows = [json.loads(line) for line in annotation_path.read_text().splitlines()]
    rows[0]["source_annotation"]["presence_label"] = "ABSENT"
    annotation_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    with pytest.raises(ValueError, match="inconsistent presence/posture"):
        build_canonical_dataset(capture, tmp_path / "derived", split_map_path=tmp_path / "split.json", require_split=True)


def test_builder_rejects_timestamp_order_violation(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path)
    frames_path = capture / "subjects/SUBJ-001/sessions/SESSION-001/frames.jsonl"
    rows = [json.loads(line) for line in frames_path.read_text().splitlines()]
    rows[1]["host_receive_monotonic_timestamp_ns"] = 1
    frames_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    with pytest.raises(ValueError, match="monotonic timestamps are not ordered"):
        build_canonical_dataset(capture, tmp_path / "derived", split_map_path=tmp_path / "split.json", require_split=True)


def test_builder_sampling_is_deterministic_and_not_random(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path, labels=("STANDING", "LYING"))
    output = tmp_path / "derived"
    summary = build_canonical_dataset(capture, output, split_map_path=tmp_path / "split.json", require_split=True, sample_stride=2)
    assert summary["sample_count"] == 1
    assert summary["excluded_counts"] == {"DETERMINISTIC_SAMPLE_STRIDE": 1}
    assert summary["sampling_policy"] == {"method": "SEQUENCE_INDEX_MODULO", "random_sampling": False, "sample_stride": 2}


def test_built_dataset_rejects_subject_split_leakage(tmp_path: Path) -> None:
    capture = _write_fixture(tmp_path)
    output = tmp_path / "derived"
    build_canonical_dataset(capture, output, split_map_path=tmp_path / "split.json", require_split=True)
    rows = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
    rows[1]["split"] = "LOCKED_TEST"
    (output / "samples.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    assert any(item["code"] == "SUBJECT_SPLIT_LEAKAGE" for item in validate_built_dataset(output)["errors"])


def test_domain_comparator_reports_range_diagnostics(tmp_path: Path) -> None:
    historical = np.full((2, 62, 80), 2731, dtype=np.uint16)
    mi48 = np.full((2, 62, 80), 2500, dtype=np.uint16)
    historical_path = tmp_path / "historical.npy"
    mi48_path = tmp_path / "mi48.npy"
    np.save(historical_path, historical)
    np.save(mi48_path, mi48)
    result = compare_domains(historical_path, mi48_path)
    assert result["p1_contract"]["refit"] is False
    assert result["range_metrics"]["mi48_pixels_below_historical_min"] == 1.0
    assert result["thresholds_are_domain_diagnostics_not_quality_claims"] is True


def test_float_harness_uses_frozen_p1_and_fails_closed_on_locked_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture = _write_fixture(tmp_path)
    output = tmp_path / "derived"
    build_canonical_dataset(capture, output, split_map_path=tmp_path / "split.json", require_split=True)
    model = tmp_path / "model.tflite"
    model.write_bytes(b"synthetic-model")
    measured_sha = hashlib.sha256(model.read_bytes()).hexdigest()
    observed_inputs: list[np.ndarray] = []

    class FakeInterpreter:
        def __init__(self, **_: object) -> None:
            self.tensor = None

        def allocate_tensors(self) -> None:
            return None

        def get_input_details(self) -> list[dict[str, object]]:
            return [{"index": 0, "shape": np.array([1, 62, 80, 1]), "dtype": np.float32}]

        def get_output_details(self) -> list[dict[str, object]]:
            return [{"index": 1, "shape": np.array([1, 3]), "dtype": np.float32}]

        def set_tensor(self, _index: int, value: np.ndarray) -> None:
            observed_inputs.append(value.copy())

        def invoke(self) -> None:
            return None

        def get_tensor(self, _index: int) -> np.ndarray:
            return np.array([[0.1, 0.8, 0.1]], dtype=np.float32)

    fake_tf = types.SimpleNamespace(lite=types.SimpleNamespace(Interpreter=FakeInterpreter))
    monkeypatch.setitem(sys.modules, "tensorflow", fake_tf)
    result = evaluate_float_tflite(output, model, expected_sha256=measured_sha)
    assert result["preprocessing"]["refit"] is False
    assert result["model"]["sha256"] == measured_sha
    assert observed_inputs
    expected = p1_from_celsius(np.load(output / "celsius.npy", allow_pickle=False)[0])[None, ..., None]
    assert np.allclose(observed_inputs[0], expected, atol=1e-5)

    rows = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
    rows[0]["split"] = "LOCKED_TEST"
    (output / "samples.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    with pytest.raises(ValueError, match="LOCKED_TEST"):
        evaluate_float_tflite(output, model, expected_sha256=measured_sha)


def test_legacy_snapshot_dry_run_does_not_promote_or_mutate(tmp_path: Path) -> None:
    result = dry_run_legacy_snapshot(tmp_path / "missing-snapshot")
    assert result["used"] == "READ_ONLY_DRY_RUN"
    assert result["modified"] is False
    assert result["synthetic_labels_assigned"] is False
    assert result["model_evaluation_performed"] is False


def test_t_c0_readiness_passes() -> None:
    result = validate_evidence(repo_root=ROOT, evidence_dir=EVIDENCE, check_checksums=True)
    assert result["evidence_validation"] == "PASS"
    assert result["readiness_status"] == "PASS_WITH_LIMITATIONS"
    assert result["float_retraining_required"] == "UNRESOLVED"


def test_t_c0_rejects_frame_random_split(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, evidence)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text())
    contract["split_policy"]["frame_random_split_allowed"] = True
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    result = validate_evidence(repo_root=ROOT, evidence_dir=evidence, check_checksums=False)
    assert any(item["code"] == "SPLIT_POLICY_INVALID" for item in result["errors"])


def test_t_c0_rejects_fall_semantic_escalation(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, evidence)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text())
    contract["label_contract"]["human_fall_semantics"] = "TEMPORAL_FALL_GROUND_TRUTH"
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    result = validate_evidence(repo_root=ROOT, evidence_dir=evidence, check_checksums=False)
    assert any(item["code"] == "FALL_SEMANTICS_ESCALATED" for item in result["errors"])


def test_t_c0_rejects_abs_path_leak(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, evidence)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text())
    contract["debug_path"] = "/absolute/example/mi48"
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    result = validate_evidence(repo_root=ROOT, evidence_dir=evidence, check_checksums=False)
    assert any(item["code"] == "ABSOLUTE_PATH_LEAK" for item in result["errors"])


def test_target_mapping_does_not_add_unapproved_class() -> None:
    assert TARGET_MAP["LYING"] == "HUMAN_FALL"
    assert set(TARGET_MAP.values()) == set(CLASS_ORDER)
