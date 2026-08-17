"""Offline MI48 device-domain preparation tools.

This module deliberately separates future raw capture intake from model
selection.  It never writes to a capture directory and never assigns labels
from model output.  The command-line wrappers in this phase use it to build
derived canonical evidence, compare temperature domains, and evaluate the
already-frozen Float TFLite artifact when a future labelled capture exists.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import numpy as np


CONTRACT_PHASE = "T-C0"
CAPTURE_CONTRACT_ID = "safenest.thermal.mi48.capture.v1"
SAMPLE_SCHEMA = "safenest.thermal.mi48.sample.v1"
DATASET_SCHEMA = "safenest.thermal.mi48.dataset.v1"
NATIVE_SHAPE = (62, 80)
NATIVE_DTYPE = "uint16"
RAW_UNIT = "0.1_K"
P1_PROFILE_ID = "P1_TRAIN_FITTED_GLOBAL_ZSCORE"
P1_MEAN = 22.769290618485442
P1_STD = 2.8684523405441222
FLOAT_TFLITE_LOGICAL_PATH = "models/thermal/candidates/SMALL_CNN_BASELINE_V1_P1_float32.tflite"
FLOAT_TFLITE_SHA256 = "fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779"
FLOAT_INPUT_SHAPE = [1, 62, 80, 1]
FLOAT_OUTPUT_SHAPE = [1, 3]
CLASS_ORDER = ("NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL")
SOURCE_LABELS = ("EMPTY", "STANDING", "SITTING", "CROUCHING", "LYING", "OTHER_CONTROLLED", "UNKNOWN", "NOT_ANNOTATED")
TARGET_MAP = {
    "EMPTY": "NOT_HUMAN",
    "STANDING": "HUMAN_NORMAL",
    "SITTING": "HUMAN_NORMAL",
    "CROUCHING": "HUMAN_NORMAL",
    "LYING": "HUMAN_FALL",
}
SPLITS = ("TRAIN", "VALIDATION", "LOCKED_TEST", "REAL_EVAL_DEVELOPMENT", "UNASSIGNED")
POSTURE_LABELS = ("NONE", "STANDING", "SITTING", "CROUCHING", "LYING", "OTHER_CONTROLLED", "UNKNOWN")
PRESENCE_LABELS = ("ABSENT", "PRESENT", "UNKNOWN")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def canonical_jsonl(value: Any) -> str:
    """Serialize one deterministic JSON object on exactly one JSONL line."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "~", "file://")):
        return False
    if "\\" in value or "\x00" in value:
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def compute_sample_id(collection_id: str, session_id: str, frame_id: str) -> str:
    """Return a stable identity independent of array order or file name."""

    material = f"{SAMPLE_SCHEMA}|{collection_id}|{session_id}|{frame_id}".encode("utf-8")
    return "MI48S1_" + hashlib.sha256(material).hexdigest()


def raw_uint16_to_celsius(raw: np.ndarray) -> np.ndarray:
    values = np.asarray(raw)
    if values.dtype.kind not in "ui" or values.dtype.itemsize != 2:
        raise ValueError("MI48 raw frame must be uint16")
    if values.shape[-2:] != NATIVE_SHAPE:
        raise ValueError(f"MI48 raw frame shape must end in {NATIVE_SHAPE}, got {values.shape}")
    celsius = values.astype(np.float32) / np.float32(10.0) - np.float32(273.15)
    if not np.isfinite(celsius).all():
        raise ValueError("MI48 Celsius conversion produced non-finite values")
    return celsius


def p1_from_celsius(celsius: np.ndarray) -> np.ndarray:
    values = np.asarray(celsius, dtype=np.float32)
    return (values - np.float32(P1_MEAN)) / np.float32(P1_STD)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record {path}:{line_number} is not an object")
        records.append(value)
    return records


def _session_paths(collection_root: Path) -> list[Path]:
    return sorted(collection_root.glob("subjects/*/sessions/*/session.json"), key=lambda p: p.as_posix())


def _load_split_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    document = _read_json(path)
    if document.get("schema_version") != "safenest.thermal.mi48.split.v1":
        raise ValueError("split map schema_version must be safenest.thermal.mi48.split.v1")
    assignments = document.get("assignments")
    if not isinstance(assignments, dict):
        raise ValueError("split map assignments must be an object")
    result: dict[str, str] = {}
    for group_id, split in assignments.items():
        if not isinstance(group_id, str) or split not in SPLITS[:-1]:
            raise ValueError(f"invalid split assignment {group_id!r}: {split!r}")
        result[group_id] = split
    return result


def _resolve_split(session: Mapping[str, Any], split_map: Mapping[str, str]) -> str:
    subject_id = str(session.get("subject_id", ""))
    session_id = str(session.get("session_id", ""))
    values = {split_map[key] for key in (subject_id, session_id) if key in split_map}
    if len(values) > 1:
        raise ValueError(f"subject/session split assignment conflict for {session_id}")
    return next(iter(values), "UNASSIGNED")


def _native_byte_order(session: Mapping[str, Any], frame: Mapping[str, Any]) -> str:
    value = frame.get("native_byte_order")
    if value is None and isinstance(session.get("sensor"), Mapping):
        value = session["sensor"].get("native_byte_order")
    if value not in {"little", "big"}:
        raise ValueError("native byte order is required and must be T-C-verified as 'little' or 'big'")
    return str(value)


def _read_native_frame(path: Path, session: Mapping[str, Any], frame: Mapping[str, Any]) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".npy":
        raw = np.load(path, allow_pickle=False)
        if raw.dtype != np.dtype("uint16") or tuple(raw.shape) != NATIVE_SHAPE:
            raise ValueError(f"native .npy must be uint16 {NATIVE_SHAPE}, got {raw.dtype} {raw.shape}")
        return np.asarray(raw, dtype=np.uint16)
    byte_order = _native_byte_order(session, frame)
    expected_bytes = int(np.prod(NATIVE_SHAPE)) * 2
    payload = path.read_bytes()
    if len(payload) != expected_bytes:
        raise ValueError(f"native frame byte length {len(payload)} != {expected_bytes}")
    dtype = np.dtype("<u2" if byte_order == "little" else ">u2")
    return np.frombuffer(payload, dtype=dtype).reshape(NATIVE_SHAPE).astype(np.uint16)


def _annotation_index(session_dir: Path) -> dict[str, dict[str, Any]]:
    path = session_dir / "annotations.jsonl"
    if not path.is_file():
        raise FileNotFoundError(path)
    latest: dict[str, dict[str, Any]] = {}
    for record in _read_jsonl(path):
        frame_id = record.get("frame_id")
        source = record.get("source_annotation")
        if not isinstance(frame_id, str) or not isinstance(source, Mapping):
            continue
        previous = latest.get(frame_id)
        if previous is None or int(record.get("revision", 1)) >= int(previous.get("revision", 1)):
            latest[frame_id] = record
    return latest


def _label_semantics(source_label: Any, source: Mapping[str, Any]) -> tuple[str, str] | None:
    """Return independent presence/posture labels, rejecting contradictions."""

    expected = {
        "EMPTY": ("ABSENT", "NONE"),
        "STANDING": ("PRESENT", "STANDING"),
        "SITTING": ("PRESENT", "SITTING"),
        "CROUCHING": ("PRESENT", "CROUCHING"),
        "LYING": ("PRESENT", "LYING"),
    }.get(source_label)
    if expected is None:
        return None
    presence = source.get("presence_label", expected[0])
    posture = source.get("posture_label", expected[1])
    if presence not in PRESENCE_LABELS or posture not in POSTURE_LABELS:
        raise ValueError(f"invalid independent label fields for {source_label!r}: {presence!r}/{posture!r}")
    if (presence, posture) != expected:
        raise ValueError(f"inconsistent presence/posture fields for {source_label!r}: {presence!r}/{posture!r}")
    return str(presence), str(posture)


def _timestamp_pair(frame: Mapping[str, Any]) -> tuple[float, float]:
    """Resolve required wall-clock and monotonic timestamps from a frame."""

    wall = frame.get("wall_timestamp", frame.get("host_wall_time"))
    monotonic = frame.get("monotonic_timestamp", frame.get("host_receive_monotonic_timestamp_ns"))
    if not isinstance(wall, (str, int, float)) or wall == "":
        raise ValueError("valid frame is missing wall_timestamp/host_wall_time")
    if not isinstance(monotonic, (int, float)) or isinstance(monotonic, bool):
        raise ValueError("valid frame is missing numeric monotonic_timestamp/host_receive_monotonic_timestamp_ns")
    if isinstance(wall, str):
        try:
            wall_value = datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp()
        except ValueError as exc:
            raise ValueError(f"invalid wall timestamp {wall!r}") from exc
    else:
        wall_value = float(wall)
    monotonic_value = float(monotonic)
    if not np.isfinite(wall_value) or not np.isfinite(monotonic_value):
        raise ValueError("frame timestamps must be finite")
    return wall_value, monotonic_value


def _write_checksums(root: Path) -> None:
    rows = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    (root / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_canonical_dataset(
    capture_root: Path,
    output_root: Path,
    *,
    split_map_path: Path | None = None,
    derive_p1: bool = False,
    require_split: bool = False,
    sample_stride: int = 1,
) -> dict[str, Any]:
    """Build derived Celsius/P1 arrays without modifying the capture root."""

    capture_root = Path(capture_root).resolve()
    output_root = Path(output_root).resolve()
    collection_path = capture_root / "collection.json"
    if not collection_path.is_file():
        raise FileNotFoundError(collection_path)
    collection = _read_json(collection_path)
    if collection.get("schema_version") != "safenest.thermal.real_capture.collection.v1":
        raise ValueError("capture collection schema is not the approved real-capture v1 contract")
    collection_id = str(collection.get("collection_id", ""))
    if not collection_id:
        raise ValueError("collection_id is required")
    split_map = _load_split_map(split_map_path)
    if output_root == capture_root or capture_root in output_root.parents:
        raise ValueError("derived output must be outside the read-only capture root")
    if not isinstance(sample_stride, int) or isinstance(sample_stride, bool) or sample_stride < 1:
        raise ValueError("sample_stride must be a positive integer")

    samples: list[dict[str, Any]] = []
    celsius_by_sample: dict[str, np.ndarray] = {}
    p1_by_sample: dict[str, np.ndarray] = {}
    excluded: Counter[str] = Counter()
    sessions = _session_paths(capture_root)
    if not sessions:
        raise ValueError("capture contains no session manifests")
    for session_path in sessions:
        session = _read_json(session_path)
        session_dir = session_path.parent
        if session.get("collection_id") != collection_id:
            raise ValueError(f"session collection_id mismatch: {session_path}")
        if not isinstance(session.get("session_id"), str) or not session.get("session_id"):
            raise ValueError(f"session_id is required: {session_path}")
        if not isinstance(session.get("subject_id"), str) or not session.get("subject_id"):
            raise ValueError(f"subject_id or NONE is required: {session_path}")
        sensor = session.get("sensor")
        if not isinstance(sensor, Mapping):
            raise ValueError(f"sensor identity is required: {session_path}")
        declared_shape = sensor.get("native_shape", list(NATIVE_SHAPE))
        declared_dtype = sensor.get("native_dtype", NATIVE_DTYPE)
        if list(declared_shape) != list(NATIVE_SHAPE) or declared_dtype != NATIVE_DTYPE:
            raise ValueError(f"session native contract mismatch: {session_path}")
        frames_path = session_dir / "frames.jsonl"
        if not frames_path.is_file():
            raise FileNotFoundError(frames_path)
        annotations = _annotation_index(session_dir)
        split = _resolve_split(session, split_map)
        if require_split and split == "UNASSIGNED":
            raise ValueError(f"no frozen split assignment for {session.get('session_id')}")
        frames = _read_jsonl(frames_path)
        frames = sorted(frames, key=lambda row: (int(row.get("sequence_index", 0)), str(row.get("frame_id", ""))))
        seen_frame_ids: set[str] = set()
        previous_wall: float | None = None
        previous_monotonic: float | None = None
        for frame in frames:
            frame_id = frame.get("frame_id")
            if not isinstance(frame_id, str) or not frame_id:
                raise ValueError(f"frame_id is required: {frames_path}")
            if frame_id in seen_frame_ids:
                raise ValueError(f"duplicate frame identity: {frame_id}")
            seen_frame_ids.add(frame_id)
            if frame.get("validity_status") != "VALID":
                excluded["INVALID_FRAME"] += 1
                continue
            wall_timestamp, monotonic_timestamp = _timestamp_pair(frame)
            if previous_wall is not None and wall_timestamp < previous_wall:
                raise ValueError(f"wall timestamps are not monotonic in {session.get('session_id')}")
            if previous_monotonic is not None and monotonic_timestamp < previous_monotonic:
                raise ValueError(f"monotonic timestamps are not ordered in {session.get('session_id')}")
            previous_wall = wall_timestamp
            previous_monotonic = monotonic_timestamp
            sequence_index = int(frame.get("sequence_index", len(seen_frame_ids) - 1))
            if sequence_index % sample_stride != 0:
                excluded["DETERMINISTIC_SAMPLE_STRIDE"] += 1
                continue
            annotation = annotations.get(frame_id)
            source = annotation.get("source_annotation", {}) if annotation else {}
            source_label = source.get("label")
            target_label = TARGET_MAP.get(source_label)
            if target_label is None:
                excluded["MISSING_OR_UNSUPPORTED_LABEL"] += 1
                continue
            semantics = _label_semantics(source_label, source)
            if semantics is None:
                excluded["MISSING_OR_UNSUPPORTED_LABEL"] += 1
                continue
            presence_label, posture_label = semantics
            decoded = frame.get("decoded_native_file")
            if not isinstance(decoded, str) or not portable_relative_path(decoded):
                raise ValueError(f"valid frame {frame_id} has no portable decoded_native_file")
            decoded_path = (session_dir / PurePosixPath(decoded)).resolve()
            try:
                decoded_path.relative_to(session_dir.resolve())
            except ValueError as exc:
                raise ValueError(f"decoded native path escapes session: {decoded}") from exc
            raw = _read_native_frame(decoded_path, session, frame)
            celsius = raw_uint16_to_celsius(raw)
            sample_id = compute_sample_id(collection_id, str(session.get("session_id")), str(frame_id))
            if sample_id in celsius_by_sample:
                raise ValueError(f"duplicate deterministic sample identity: {sample_id}")
            rel_decoded = decoded_path.relative_to(capture_root).as_posix()
            record = {
                "schema_version": SAMPLE_SCHEMA,
                "sample_id": sample_id,
                "collection_id": collection_id,
                "subject_id": session.get("subject_id"),
                "session_id": session.get("session_id"),
                "recording_id": session.get("recording_id"),
                "frame_id": frame_id,
                "sequence_index": frame.get("sequence_index"),
                "event_id": frame.get("event_id"),
                "timestamps": {
                    "wall_timestamp": frame.get("wall_timestamp", frame.get("host_wall_time")),
                    "monotonic_timestamp": frame.get("monotonic_timestamp", frame.get("host_receive_monotonic_timestamp_ns")),
                },
                "source_label": source_label,
                "human_presence_label": presence_label,
                "posture_label": posture_label,
                "event_phase": annotation.get("event_phase", "NOT_APPLICABLE") if annotation else "UNKNOWN",
                "model_target": target_label,
                "label_provenance": {
                    "annotation_id": annotation.get("annotation_id") if annotation else None,
                    "ground_truth_method": source.get("ground_truth_method"),
                    "annotator_code": (annotation.get("provenance") or {}).get("annotator_code") if annotation else None,
                    "revision": annotation.get("revision") if annotation else None,
                    "human_fall_semantics": "LYING_DERIVED_POSTURE_PROXY_NOT_TEMPORAL_EVENT_GROUND_TRUTH" if source_label == "LYING" else "POSTURE_OR_PRESENCE_SOURCE_LABEL",
                },
                "split": split,
                "raw_lineage": {
                    "capture_root_role": "READ_ONLY_INPUT",
                    "decoded_native_logical_path": rel_decoded,
                    "decoded_native_sha256": sha256_file(decoded_path),
                    "native_shape": list(NATIVE_SHAPE),
                    "native_dtype": NATIVE_DTYPE,
                    "raw_unit": RAW_UNIT,
                    "conversion": "celsius = raw_uint16 / 10.0 - 273.15",
                },
                "preprocessing": {
                    "geometry": "NATIVE_62x80_UNCHANGED",
                    "p1_profile_id": P1_PROFILE_ID if derive_p1 else "NOT_DERIVED",
                    "p1_refit": False,
                },
            }
            samples.append(record)
            celsius_by_sample[sample_id] = celsius
            if derive_p1:
                p1_by_sample[sample_id] = p1_from_celsius(celsius)

    if not samples:
        raise ValueError("no valid labelled uint16 frames were eligible for canonical build")
    samples.sort(key=lambda row: row["sample_id"])
    # The arrays are reordered to the deterministic sample order, rather than
    # inheriting filesystem or glob order.
    celsius = np.stack([celsius_by_sample[row["sample_id"]] for row in samples]).astype(np.float32)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "samples.jsonl").write_text("".join(canonical_jsonl(row) for row in samples), encoding="utf-8")
    np.save(output_root / "celsius.npy", celsius, allow_pickle=False)
    if derive_p1:
        p1 = np.stack([p1_by_sample[row["sample_id"]] for row in samples]).astype(np.float32)
        np.save(output_root / "p1.npy", p1, allow_pickle=False)
    summary = {
        "schema_version": DATASET_SCHEMA,
        "contract_phase": CONTRACT_PHASE,
        "dataset_role": "DERIVED_MI48_DEVICE_DOMAIN_EVIDENCE",
        "collection_id": collection_id,
        "source_capture_read_only": True,
        "source_capture_modified": False,
        "sample_count": len(samples),
        "excluded_counts": dict(sorted(excluded.items())),
        "split_counts": dict(sorted(Counter(row["split"] for row in samples).items())),
        "source_label_counts": dict(sorted(Counter(row["source_label"] for row in samples).items())),
        "model_target_counts": dict(sorted(Counter(row["model_target"] for row in samples).items())),
        "array_shape": list(celsius.shape),
        "array_dtype": "float32",
        "raw_dtype": NATIVE_DTYPE,
        "raw_unit": RAW_UNIT,
        "p1_profile_id": P1_PROFILE_ID if derive_p1 else "NOT_DERIVED",
        "sampling_policy": {"method": "SEQUENCE_INDEX_MODULO", "sample_stride": sample_stride, "random_sampling": False},
        "split_map_supplied": split_map_path is not None,
        "split_policy_frozen_before_model_evaluation": split_map_path is not None,
        "raw_to_canonical_lineage_complete": True,
        "derived_output_only": True,
        "next_authority": "T-C/T-D_REVIEW_REQUIRED",
    }
    (output_root / "dataset_build_summary.json").write_text(canonical_json(summary), encoding="utf-8")
    _write_checksums(output_root)
    return summary


def validate_built_dataset(dataset_root: Path) -> dict[str, Any]:
    root = Path(dataset_root).resolve()
    errors: list[dict[str, str]] = []
    summary_path = root / "dataset_build_summary.json"
    samples_path = root / "samples.jsonl"
    celsius_path = root / "celsius.npy"
    for path in (summary_path, samples_path, celsius_path):
        if not path.is_file():
            errors.append({"code": "REQUIRED_BUILT_ARTIFACT_MISSING", "path": path.name, "message": "Required derived artifact is missing."})
    if errors:
        return {"status": "FAIL", "errors": errors, "sample_count": 0}
    summary = _read_json(summary_path)
    samples = _read_jsonl(samples_path)
    arrays = np.load(celsius_path, allow_pickle=False)
    if arrays.dtype != np.dtype("float32") or arrays.shape != (len(samples), *NATIVE_SHAPE):
        errors.append({"code": "CANONICAL_ARRAY_CONTRACT_INVALID", "path": "celsius.npy", "message": f"Expected float32 ({len(samples)}, 62, 80), got {arrays.dtype} {arrays.shape}."})
    if not np.isfinite(arrays).all():
        errors.append({"code": "CANONICAL_NONFINITE", "path": "celsius.npy", "message": "Celsius array contains non-finite values."})
    ids: set[str] = set()
    groups: dict[str, str] = {}
    session_timestamps: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for index, row in enumerate(samples):
        path = f"samples.jsonl:{index}"
        expected_id = compute_sample_id(str(row.get("collection_id")), str(row.get("session_id")), str(row.get("frame_id")))
        if row.get("sample_id") != expected_id:
            errors.append({"code": "SAMPLE_ID_INVALID", "path": path, "message": "sample_id is not derived from the immutable identity tuple."})
        if row.get("sample_id") in ids:
            errors.append({"code": "DUPLICATE_SAMPLE_ID", "path": path, "message": "sample_id is duplicated."})
        ids.add(row.get("sample_id"))
        source_label = row.get("source_label")
        try:
            semantics = _label_semantics(source_label, {"presence_label": row.get("human_presence_label"), "posture_label": row.get("posture_label")})
        except ValueError:
            semantics = None
        if row.get("schema_version") != SAMPLE_SCHEMA or source_label not in TARGET_MAP or row.get("model_target") != TARGET_MAP.get(source_label) or semantics is None or row.get("event_phase") not in {"PRE_EVENT", "FALL_TRANSITION", "POST_FALL_LYING", "RECOVERY", "NORMAL_ACTIVITY", "NOT_APPLICABLE", "UNKNOWN"}:
            errors.append({"code": "LABEL_CONTRACT_INVALID", "path": path, "message": "Source label or explicit model mapping is invalid."})
        split = row.get("split")
        if split not in SPLITS:
            errors.append({"code": "SPLIT_INVALID", "path": path, "message": "Unknown split role."})
        subject = str(row.get("subject_id"))
        previous = groups.get(subject)
        if previous is not None and previous != split:
            errors.append({"code": "SUBJECT_SPLIT_LEAKAGE", "path": path, "message": "One subject appears in multiple split roles."})
        groups[subject] = split
        if not isinstance(row.get("raw_lineage"), Mapping) or not row["raw_lineage"].get("decoded_native_logical_path"):
            errors.append({"code": "LINEAGE_INCOMPLETE", "path": path, "message": "Raw-to-canonical lineage is incomplete."})
        timestamps = row.get("timestamps")
        if not isinstance(timestamps, Mapping):
            errors.append({"code": "TIMESTAMP_MISSING", "path": path, "message": "Wall and monotonic timestamps are required for canonical samples."})
        else:
            try:
                wall = timestamps.get("wall_timestamp")
                monotonic = float(timestamps.get("monotonic_timestamp"))
                if isinstance(wall, str):
                    wall_value = datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp()
                else:
                    wall_value = float(wall)
                if not np.isfinite(wall_value) or not np.isfinite(monotonic):
                    raise ValueError
                sequence_index = int(row.get("sequence_index", len(session_timestamps[str(row.get("session_id"))])))
                session_timestamps[str(row.get("session_id"))].append((sequence_index, wall_value, monotonic))
            except (TypeError, ValueError, OverflowError):
                errors.append({"code": "TIMESTAMP_INVALID", "path": path, "message": "Wall and monotonic timestamps must be finite and parseable."})
    for session_id, values in sorted(session_timestamps.items()):
        ordered = [item[1:] for item in sorted(values, key=lambda item: (item[0], item[1], item[2]))]
        if any(current[0] < previous[0] for previous, current in zip(ordered, ordered[1:])):
            errors.append({"code": "WALL_TIMESTAMP_ORDER_INVALID", "path": f"session:{session_id}", "message": "Wall timestamps are not monotonic."})
        if any(current[1] < previous[1] for previous, current in zip(ordered, ordered[1:])):
            errors.append({"code": "MONOTONIC_TIMESTAMP_ORDER_INVALID", "path": f"session:{session_id}", "message": "Monotonic timestamps are not ordered."})
    if summary.get("raw_to_canonical_lineage_complete") is not True or summary.get("source_capture_modified") is not False:
        errors.append({"code": "LINEAGE_SUMMARY_INVALID", "path": "dataset_build_summary.json", "message": "Derived dataset must retain complete lineage and immutable input status."})
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": sorted(errors, key=lambda item: (item["code"], item["path"])),
        "sample_count": len(samples),
        "subject_count": len(groups),
        "split_counts": dict(sorted(Counter(row.get("split") for row in samples).items())),
    }


def _load_numeric_array(path: Path, key: str | None = None) -> np.ndarray:
    loaded = np.load(path, allow_pickle=False)
    if isinstance(loaded, np.lib.npyio.NpzFile):
        selected = key or ("celsius" if "celsius" in loaded.files else loaded.files[0])
        if selected not in loaded.files:
            raise ValueError(f"array key {selected!r} is not present in {path}")
        array = loaded[selected]
        loaded.close()
        return np.asarray(array)
    return np.asarray(loaded)


def distribution_summary(celsius: np.ndarray, *, p1: bool = True) -> dict[str, Any]:
    values = np.asarray(celsius, dtype=np.float32)
    if values.ndim == 2:
        values = values[None, ...]
    if values.ndim != 3 or tuple(values.shape[-2:]) != NATIVE_SHAPE:
        raise ValueError(f"expected [N,62,80], got {values.shape}")
    flat = values.astype(np.float64).reshape(-1)
    stats = {name: float(np.percentile(flat, quantile)) for name, quantile in (("min", 0), ("p0.1", 0.1), ("p1", 1), ("p5", 5), ("median", 50), ("p95", 95), ("p99", 99), ("p99.9", 99.9), ("max", 100))}
    result: dict[str, Any] = {"celsius": stats, "pixel_count": int(flat.size), "frame_count": int(values.shape[0])}
    if p1:
        result["p1"] = {name: float(np.percentile(((flat - P1_MEAN) / P1_STD), quantile)) for name, quantile in (("min", 0), ("p0.1", 0.1), ("p1", 1), ("p5", 5), ("median", 50), ("p95", 95), ("p99", 99), ("p99.9", 99.9), ("max", 100))}
    return result


def compare_domains(historical_path: Path, mi48_path: Path, *, historical_key: str | None = None, mi48_key: str | None = None) -> dict[str, Any]:
    historical = _load_numeric_array(Path(historical_path), historical_key)
    mi48 = _load_numeric_array(Path(mi48_path), mi48_key)
    h = distribution_summary(historical)
    m = distribution_summary(mi48)
    h_values = np.asarray(historical, dtype=np.float32).reshape(-1)
    m_values = np.asarray(mi48, dtype=np.float32).reshape(-1)
    historical_p1 = (h_values.astype(np.float64) - P1_MEAN) / P1_STD
    mi48_p1 = (m_values.astype(np.float64) - P1_MEAN) / P1_STD
    lower, upper = float(np.min(historical_p1)), float(np.max(historical_p1))
    lower_pct, upper_pct = float(np.percentile(historical_p1, 0.1)), float(np.percentile(historical_p1, 99.9))
    return {
        "schema_version": "safenest.thermal.mi48.domain_comparison.v1",
        "historical": h,
        "mi48": m,
        "range_metrics": {
            "mi48_pixels_below_historical_min": float(np.mean(mi48_p1 < lower)),
            "mi48_pixels_above_historical_max": float(np.mean(mi48_p1 > upper)),
            "mi48_pixels_outside_historical_range": float(np.mean((mi48_p1 < lower) | (mi48_p1 > upper))),
            "mi48_pixels_outside_historical_p0_1_p99_9_envelope": float(np.mean((mi48_p1 < lower_pct) | (mi48_p1 > upper_pct))),
            "mi48_pixels_below_historical_min_count": int(np.sum(mi48_p1 < lower)),
            "mi48_pixels_above_historical_max_count": int(np.sum(mi48_p1 > upper)),
        },
        "p1_contract": {"profile_id": P1_PROFILE_ID, "mean": P1_MEAN, "std": P1_STD, "refit": False},
        "thresholds_are_domain_diagnostics_not_quality_claims": True,
    }


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    matrix = np.zeros((len(CLASS_ORDER), len(CLASS_ORDER)), dtype=np.int64)
    for truth, prediction in zip(y_true, y_pred):
        if 0 <= truth < len(CLASS_ORDER) and 0 <= prediction < len(CLASS_ORDER):
            matrix[truth, prediction] += 1
    per_class = {}
    recalls = []
    f1s = []
    for index, name in enumerate(CLASS_ORDER):
        tp = int(matrix[index, index])
        fp = int(matrix[:, index].sum() - tp)
        fn = int(matrix[index, :].sum() - tp)
        support = int(matrix[index, :].sum())
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / support if support else None
        f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None
        per_class[name] = {"support": support, "precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
        if recall is not None:
            recalls.append(recall)
        if f1 is not None:
            f1s.append(f1)
    return {
        "sample_count": int(y_true.size),
        "accuracy": float(np.mean(y_true == y_pred)) if y_true.size else None,
        "balanced_accuracy": float(np.mean(recalls)) if recalls else None,
        "macro_f1": float(np.mean(f1s)) if f1s else None,
        "class_order": list(CLASS_ORDER),
        "confusion_matrix": matrix.tolist(),
        "per_class": per_class,
        "prediction_distribution": dict(sorted(Counter(CLASS_ORDER[int(index)] for index in y_pred if 0 <= index < len(CLASS_ORDER)).items())),
    }


def evaluate_float_tflite(dataset_root: Path, model_path: Path, *, expected_sha256: str = FLOAT_TFLITE_SHA256) -> dict[str, Any]:
    """Evaluate the frozen Float artifact; never fit or alter model state."""

    root = Path(dataset_root).resolve()
    model_path = Path(model_path).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    measured_sha = sha256_file(model_path)
    if measured_sha != expected_sha256:
        raise ValueError(f"Float TFLite SHA mismatch: {measured_sha} != {expected_sha256}")
    arrays = np.load(root / "celsius.npy", allow_pickle=False).astype(np.float32)
    samples = _read_jsonl(root / "samples.jsonl")
    if arrays.shape != (len(samples), *NATIVE_SHAPE):
        raise ValueError("celsius.npy and samples.jsonl have different row counts")
    if any(row.get("split") == "UNASSIGNED" for row in samples):
        raise ValueError("evaluation requires a frozen group-aware split")
    if any(row.get("split") == "LOCKED_TEST" for row in samples):
        raise ValueError("LOCKED_TEST evaluation requires a separate authorized access step")
    labels = np.asarray([CLASS_ORDER.index(row["model_target"]) for row in samples], dtype=np.int64)
    try:
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("TensorFlow/Lite runtime is required for Float evaluation") from exc
    interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=1)
    interpreter.allocate_tensors()
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError("frozen Float artifact must expose one input and one output")
    if list(inputs[0]["shape"]) != FLOAT_INPUT_SHAPE or list(outputs[0]["shape"]) != FLOAT_OUTPUT_SHAPE:
        raise ValueError("frozen Float artifact tensor contract mismatch")
    if inputs[0]["dtype"] != np.float32 or outputs[0]["dtype"] != np.float32:
        raise ValueError("frozen Float artifact must have float32 input/output")
    predictions: list[np.ndarray] = []
    for frame in arrays:
        prepared = p1_from_celsius(frame)[None, ..., None].astype(np.float32)
        interpreter.set_tensor(inputs[0]["index"], prepared)
        interpreter.invoke()
        predictions.append(np.asarray(interpreter.get_tensor(outputs[0]["index"])[0], dtype=np.float32))
    probabilities = np.stack(predictions)
    predicted_labels = np.argmax(probabilities, axis=1)

    def grouped_metrics(field: str) -> dict[str, Any]:
        groups: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(samples):
            value = row.get(field)
            if value is not None:
                groups[str(value)].append(index)
        return {
            group: _classification_metrics(labels[indexes], predicted_labels[indexes])
            for group, indexes in sorted(groups.items())
        }

    return {
        "schema_version": "safenest.thermal.mi48.float_evaluation.v1",
        "model": {"logical_path": FLOAT_TFLITE_LOGICAL_PATH, "sha256": measured_sha, "input_shape": FLOAT_INPUT_SHAPE, "output_shape": FLOAT_OUTPUT_SHAPE, "input_dtype": "float32", "output_dtype": "float32"},
        "dataset": {"sample_count": len(samples), "split_counts": dict(sorted(Counter(row["split"] for row in samples).items())), "ground_truth_source": "independent_annotation_manifest"},
        "preprocessing": {"input_unit": "CELSIUS", "p1_profile_id": P1_PROFILE_ID, "mean": P1_MEAN, "std": P1_STD, "refit": False},
        "metrics": _classification_metrics(labels, predicted_labels),
        "breakdowns": {"by_session": grouped_metrics("session_id"), "by_subject": grouped_metrics("subject_id")},
        "prediction_output_summary": {"probability_min": float(np.min(probabilities)), "probability_max": float(np.max(probabilities)), "probability_mean": float(np.mean(probabilities))},
        "accuracy_claim_scope": "LABELED_MI48_DEVICE_DOMAIN_ONLY",
        "locked_test_access": False,
        "retraining_decision": "NOT_DECIDED_BY_HARNESS",
    }


def dry_run_legacy_snapshot(snapshot_root: Path) -> dict[str, Any]:
    """Inventory the legacy snapshot without copying, labeling, or evaluating it."""

    root = Path(snapshot_root).resolve()
    if not root.is_dir():
        return {"schema_version": "safenest.thermal.mi48.legacy_snapshot_dry_run.v1", "used": "READ_ONLY_DRY_RUN", "exists": False, "modified": False, "compatibility": "NOT_AVAILABLE", "new_data_collected": False, "synthetic_labels_assigned": False, "model_evaluation_performed": False}
    candidates: list[str] = []
    thermal_terms = ("thermal", "mi48", "frame")
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file() or any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if any(term in relative.lower() for term in thermal_terms):
            candidates.append(relative)
    return {
        "schema_version": "safenest.thermal.mi48.legacy_snapshot_dry_run.v1",
        "used": "READ_ONLY_DRY_RUN",
        "exists": True,
        "modified": False,
        "compatibility": "PARTIAL",
        "capture_contract_detected": False,
        "thermal_related_file_count": len(candidates),
        "sample_observed_paths": candidates[:10],
        "observation_truncated": len(candidates) > 10,
        "reason": "Legacy Pi snapshot lacks the new collection/session/sample contract; it is infrastructure evidence only.",
        "new_data_collected": False,
        "synthetic_labels_assigned": False,
        "used_as_training": False,
        "model_evaluation_performed": False,
        "model_outputs_used_as_labels": False,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Offline SafeNest Thermal MI48 device-domain tools")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("capture_root", type=Path)
    build.add_argument("output_root", type=Path)
    build.add_argument("--split-map", type=Path)
    build.add_argument("--derive-p1", action="store_true")
    build.add_argument("--require-split", action="store_true")
    build.add_argument("--sample-stride", type=int, default=1)
    validate = sub.add_parser("validate")
    validate.add_argument("dataset_root", type=Path)
    domain = sub.add_parser("domain")
    domain.add_argument("historical", type=Path)
    domain.add_argument("mi48", type=Path)
    domain.add_argument("--historical-key")
    domain.add_argument("--mi48-key")
    evaluate = sub.add_parser("evaluate-float")
    evaluate.add_argument("dataset_root", type=Path)
    evaluate.add_argument("model_path", type=Path)
    dry = sub.add_parser("legacy-dry-run")
    dry.add_argument("snapshot_root", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        result = build_canonical_dataset(args.capture_root, args.output_root, split_map_path=args.split_map, derive_p1=args.derive_p1, require_split=args.require_split, sample_stride=args.sample_stride)
    elif args.command == "validate":
        result = validate_built_dataset(args.dataset_root)
    elif args.command == "domain":
        result = compare_domains(args.historical, args.mi48, historical_key=args.historical_key, mi48_key=args.mi48_key)
    elif args.command == "evaluate-float":
        result = evaluate_float_tflite(args.dataset_root, args.model_path)
    else:
        result = dry_run_legacy_snapshot(args.snapshot_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status", "PASS") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
