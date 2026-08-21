"""Deterministic, read-only B6R-1 MI48 snapshot inventory and profiler.

The profiler deliberately treats source files as evidence.  It does not
convert, label, split, normalize, or write to a snapshot.  Only numeric arrays
whose final geometry is the contract's native 62x80 geometry are profiled as
thermal-frame candidates.  Other containers remain accounted for, but their
semantics are not guessed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import numpy as np


ARTIFACT_ID = "B6R-1_mi48_inventory"
ARTIFACT_SCHEMA = "safenest.thermal.b6r1.mi48.inventory.v1"
PROFILER_VERSION = "1.0.0"
NATIVE_SHAPE = (62, 80)
ACCOUNTING_CLASSES = (
    "READABLE",
    "CORRUPT",
    "EXCLUDED_WITH_EXPLICIT_REASON",
)
READABLE_STATUSES = ("READABLE", "UNREADABLE")
SCHEMA_STATUSES = ("KNOWN", "PARTIALLY_KNOWN", "UNKNOWN", "CORRUPT")
IDENTITY_STATUSES = ("RESOLVED", "UNRESOLVED")
REPEAT_FRACTION_THRESHOLD = 0.01
REPEAT_COUNT_FLOOR = 2
COORDINATE_CRITERIA = (
    "EXACT_ZERO_REPEAT",
    "EXACT_65535_REPEAT",
    "FRAME_MIN_REPEAT",
    "FRAME_MAX_REPEAT",
    "NONFINITE_REPEAT",
)
REQUIRED_METADATA_FIELDS = (
    "subject_id",
    "session_id",
    "recording_id",
    "timestamp",
    "scenario_id",
    "source_label",
    "posture_label",
    "presence_label",
    "split_role",
    "native_shape",
    "native_dtype",
    "native_byte_order",
    "physical_unit",
)
TEXT_EXTENSIONS = {".json", ".jsonl", ".csv", ".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
RAW_EXTENSIONS = {".bin", ".raw", ".dat"}
ARCHIVE_PART_RE = re.compile(r"\.zip\.\d+$", re.IGNORECASE)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_pretty(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_float(value: Any) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if math.isfinite(converted) else None


def _percentile_summary(values: Iterable[float]) -> dict[str, float | None]:
    material = np.asarray(list(values), dtype=np.float64)
    if material.size == 0:
        return {
            "min": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "min": float(np.min(material)),
        "median": float(np.percentile(material, 50)),
        "p90": float(np.percentile(material, 90)),
        "p95": float(np.percentile(material, 95)),
        "p99": float(np.percentile(material, 99)),
        "max": float(np.max(material)),
    }


def _dtype_name(dtype: np.dtype[Any]) -> str:
    return dtype.str


def _is_numeric(dtype: np.dtype[Any]) -> bool:
    return np.issubdtype(dtype, np.number)


def _frame_count_for_shape(shape: tuple[int, ...]) -> int:
    if shape == NATIVE_SHAPE:
        return 1
    if len(shape) == 3 and tuple(shape[-2:]) == NATIVE_SHAPE:
        return int(shape[0])
    return 0


def _is_frame_shape(shape: tuple[int, ...]) -> bool:
    return shape == NATIVE_SHAPE or (len(shape) == 3 and tuple(shape[-2:]) == NATIVE_SHAPE)


def _schema_for_array(dtype: np.dtype[Any], shape: tuple[int, ...]) -> tuple[str, str]:
    if not _is_numeric(dtype):
        return "OBJECT_OR_UNSUPPORTED_ARRAY", "UNKNOWN"
    if not _is_frame_shape(shape):
        return "NUMERIC_ARRAY_NON_MI48_GEOMETRY", "UNKNOWN"
    if dtype == np.dtype("uint16"):
        return "MI48_NATIVE_UINT16_62x80_FRAME", "KNOWN"
    return "THERMAL_GEOMETRY_62x80_NON_UINT16", "PARTIALLY_KNOWN"


def _base_record(root: Path, path: Path, logical_source_id: str, *, source_sha256: str | None = None) -> dict[str, Any]:
    stat = path.stat()
    relative = _relative_path(root, path)
    suffix = path.suffix.lower()
    return {
        "relative_path": relative,
        "logical_source_identifier": f"{logical_source_id}/{relative}",
        "extension": suffix or "<none>",
        "file_type": "UNKNOWN",
        "byte_size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": source_sha256 if source_sha256 is not None else sha256_file(path),
        "readability_status": "UNREADABLE",
        "accounting_class": "CORRUPT",
        "exception": None,
        "npz_keys": [],
        "key_schemas": {},
        "thermal_frame_count": 0,
        "schema_family": "UNKNOWN",
        "schema_status": "UNKNOWN",
        "metadata_fields": [],
        "exclusion_reason": None,
        "archive_summary": {},
    }


def _exception(
    relative_path: str,
    code: str,
    message: str,
    *,
    severity: str = "INFO",
) -> dict[str, str]:
    return {
        "relative_path": relative_path,
        "code": code,
        "severity": severity,
        "message": message,
    }


class _ProfileState:
    def __init__(self) -> None:
        self.frame_rows: list[dict[str, Any]] = []
        self.exceptions: list[dict[str, str]] = []
        self.schema_records: list[dict[str, Any]] = []
        self.metadata_sources: list[dict[str, Any]] = []
        self.observed_metadata_fields: defaultdict[str, list[str]] = defaultdict(list)
        self.filename_patterns: Counter[str] = Counter()
        self.directory_patterns: Counter[str] = Counter()
        self.dtype_counts: Counter[str] = Counter()
        self.shape_counts: Counter[str] = Counter()
        self.frame_metric_values: defaultdict[str, list[float]] = defaultdict(list)
        self.global_pixel_min: float | None = None
        self.global_pixel_max: float | None = None
        self.global_pixel_count = 0
        self.global_finite_count = 0
        self.global_nonfinite_count = 0
        self.global_zero_count = 0
        self.global_65535_count = 0
        self.global_dtype_min_count = 0
        self.global_dtype_max_count = 0
        self.coordinate_counts = {
            criterion: np.zeros(NATIVE_SHAPE, dtype=np.int64)
            for criterion in COORDINATE_CRITERIA
        }
        self.eligible_frame_count = 0

    def observe_frame(
        self,
        *,
        relative_path: str,
        key: str,
        frame_index: int,
        frame: np.ndarray,
        dtype: np.dtype[Any],
        source_shape: tuple[int, ...],
    ) -> None:
        values = np.asarray(frame)
        flat = values.reshape(-1)
        numeric = flat.astype(np.float64, copy=False)
        finite_mask = np.isfinite(numeric)
        finite = numeric[finite_mask]
        finite_count = int(finite.size)
        nonfinite_count = int(numeric.size - finite_count)
        zero_count = int(np.count_nonzero(numeric == 0))
        sentinel_count = int(np.count_nonzero(numeric == 65535))
        dtype_min_count = 0
        dtype_max_count = 0
        if np.issubdtype(dtype, np.integer):
            limits = np.iinfo(dtype)
            dtype_min_count = int(np.count_nonzero(numeric == limits.min))
            dtype_max_count = int(np.count_nonzero(numeric == limits.max))

        row: dict[str, Any] = {
            "frame_id": f"{relative_path}::{key}::{frame_index}",
            "relative_path": relative_path,
            "array_key": key,
            "frame_index": int(frame_index),
            "source_shape": list(source_shape),
            "frame_shape": list(values.shape),
            "dtype": _dtype_name(dtype),
            "pixel_count": int(numeric.size),
            "finite_count": finite_count,
            "nonfinite_count": nonfinite_count,
            "min": float(np.min(finite)) if finite_count else None,
            "max": float(np.max(finite)) if finite_count else None,
            "p2": float(np.percentile(finite, 2)) if finite_count else None,
            "p98": float(np.percentile(finite, 98)) if finite_count else None,
            "p98_minus_p2": (
                float(np.percentile(finite, 98) - np.percentile(finite, 2))
                if finite_count
                else None
            ),
            "exact_zero_count": zero_count,
            "exact_65535_count": sentinel_count,
            "dtype_min_count": dtype_min_count,
            "dtype_max_count": dtype_max_count,
            "nan_count": int(np.count_nonzero(np.isnan(numeric))) if np.issubdtype(dtype, np.floating) else 0,
            "negative_inf_count": int(np.count_nonzero(np.isneginf(numeric))) if np.issubdtype(dtype, np.floating) else 0,
            "positive_inf_count": int(np.count_nonzero(np.isposinf(numeric))) if np.issubdtype(dtype, np.floating) else 0,
        }
        self.frame_rows.append(row)
        self.dtype_counts[_dtype_name(dtype)] += 1
        self.shape_counts["x".join(str(part) for part in values.shape)] += 1
        for metric in ("min", "max", "p2", "p98", "p98_minus_p2"):
            if row[metric] is not None:
                self.frame_metric_values[metric].append(float(row[metric]))
        self.global_pixel_count += int(numeric.size)
        self.global_finite_count += finite_count
        self.global_nonfinite_count += nonfinite_count
        self.global_zero_count += zero_count
        self.global_65535_count += sentinel_count
        self.global_dtype_min_count += dtype_min_count
        self.global_dtype_max_count += dtype_max_count
        if finite_count:
            frame_min = float(np.min(finite))
            frame_max = float(np.max(finite))
            self.global_pixel_min = frame_min if self.global_pixel_min is None else min(self.global_pixel_min, frame_min)
            self.global_pixel_max = frame_max if self.global_pixel_max is None else max(self.global_pixel_max, frame_max)

            coordinate_view = values.astype(np.float64, copy=False)
            finite_view = np.isfinite(coordinate_view)
            zero_mask = coordinate_view == 0
            sentinel_mask = coordinate_view == 65535
            self.coordinate_counts["EXACT_ZERO_REPEAT"] += zero_mask.astype(np.int64)
            self.coordinate_counts["EXACT_65535_REPEAT"] += sentinel_mask.astype(np.int64)
            self.coordinate_counts["NONFINITE_REPEAT"] += (~finite_view).astype(np.int64)
            min_mask = finite_view & (coordinate_view == frame_min)
            max_mask = finite_view & (coordinate_view == frame_max)
            self.coordinate_counts["FRAME_MIN_REPEAT"] += min_mask.astype(np.int64)
            self.coordinate_counts["FRAME_MAX_REPEAT"] += max_mask.astype(np.int64)
        else:
            self.coordinate_counts["NONFINITE_REPEAT"] += np.ones(NATIVE_SHAPE, dtype=np.int64)
        self.eligible_frame_count += 1


def _record_schema(
    state: _ProfileState,
    *,
    relative_path: str,
    key: str,
    dtype: str,
    shape: tuple[int, ...],
    family: str,
    status: str,
    frame_count: int,
    error: str | None = None,
) -> None:
    state.schema_records.append(
        {
            "relative_path": relative_path,
            "array_key": key,
            "dtype": dtype,
            "shape": list(shape),
            "schema_family": family,
            "schema_status": status,
            "thermal_frame_count": int(frame_count),
            "error": error,
        }
    )


def _profile_array(
    state: _ProfileState,
    record: dict[str, Any],
    *,
    relative_path: str,
    key: str,
    array: np.ndarray,
) -> None:
    values = np.asarray(array)
    dtype = values.dtype
    shape = tuple(int(part) for part in values.shape)
    family, status = _schema_for_array(dtype, shape)
    frame_count = _frame_count_for_shape(shape) if _is_numeric(dtype) else 0
    _record_schema(
        state,
        relative_path=relative_path,
        key=key,
        dtype=_dtype_name(dtype),
        shape=shape,
        family=family,
        status=status,
        frame_count=frame_count,
    )
    record["key_schemas"][key] = {
        "dtype": _dtype_name(dtype),
        "shape": list(shape),
        "schema_family": family,
        "schema_status": status,
        "thermal_frame_count": frame_count,
    }
    if frame_count:
        record["thermal_frame_count"] += frame_count
        frames = values[None, ...] if values.ndim == 2 else values
        for index, frame in enumerate(frames):
            state.observe_frame(
                relative_path=relative_path,
                key=key,
                frame_index=index,
                frame=np.asarray(frame),
                dtype=dtype,
                source_shape=shape,
            )


def _read_json_keys(value: Any, prefix: str = "") -> set[str]:
    fields: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                continue
            path = f"{prefix}.{key}" if prefix else key
            fields.add(key)
            fields.update(_read_json_keys(nested, path))
    elif isinstance(value, list):
        for nested in value[:100]:
            fields.update(_read_json_keys(nested, prefix))
    return fields


def _observe_metadata_fields(state: _ProfileState, relative_path: str, fields: Iterable[str], source_kind: str) -> None:
    unique = sorted({field for field in fields if field})
    if not unique:
        return
    state.metadata_sources.append(
        {
            "relative_path": relative_path,
            "source_kind": source_kind,
            "observed_fields": unique,
            "provenance_confidence": "DIRECTLY_OBSERVED_FIELD_NAMES_ONLY",
        }
    )
    for field in unique:
        state.observed_metadata_fields[field].append(relative_path)


def _filename_pattern(relative_path: str) -> str:
    name = PurePosixPath(relative_path).name
    return re.sub(r"\d+", "<index>", name)


def _observe_path_tokens(state: _ProfileState, relative_path: str) -> None:
    path = PurePosixPath(relative_path)
    state.filename_patterns[_filename_pattern(relative_path)] += 1
    for part in path.parts[:-1]:
        if part:
            state.directory_patterns[part] += 1


def _inspect_npz(path: Path, record: dict[str, Any], state: _ProfileState) -> None:
    record["file_type"] = "NPZ"
    try:
        with np.load(path, allow_pickle=False) as archive:
            keys = sorted(str(key) for key in archive.files)
            record["npz_keys"] = keys
            record["readability_status"] = "READABLE"
            record["accounting_class"] = "READABLE"
            key_errors: dict[str, str] = {}
            for key in keys:
                try:
                    _profile_array(state, record, relative_path=record["relative_path"], key=key, array=archive[key])
                except Exception as exc:  # pragma: no cover - defensive for unusual NPZ members
                    message = f"{type(exc).__name__}: {exc}"
                    key_errors[key] = message
                    state.exceptions.append(_exception(record["relative_path"], "NPZ_KEY_READ_ERROR", message, severity="ERROR"))
            if key_errors:
                record["schema_status"] = "PARTIALLY_KNOWN" if record["key_schemas"] else "CORRUPT"
                record["exception"] = _json(key_errors)
            else:
                statuses = {item["schema_status"] for item in record["key_schemas"].values()}
                record["schema_status"] = "KNOWN" if "KNOWN" in statuses else ("PARTIALLY_KNOWN" if statuses else "UNKNOWN")
            families = sorted({item["schema_family"] for item in record["key_schemas"].values()})
            record["schema_family"] = "+".join(families) if families else "NPZ_WITHOUT_ARRAY_KEYS"
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        record["file_type"] = "NPZ"
        record["readability_status"] = "UNREADABLE"
        record["accounting_class"] = "CORRUPT"
        record["schema_status"] = "CORRUPT"
        record["schema_family"] = "CORRUPT_NPZ"
        record["exception"] = message
        state.exceptions.append(_exception(record["relative_path"], "NPZ_READ_ERROR", message, severity="ERROR"))


def _inspect_npy(path: Path, record: dict[str, Any], state: _ProfileState) -> None:
    record["file_type"] = "NPY"
    try:
        array = np.load(path, allow_pickle=False)
        record["readability_status"] = "READABLE"
        record["accounting_class"] = "READABLE"
        _profile_array(state, record, relative_path=record["relative_path"], key="<npy>", array=array)
        record["schema_status"] = next(iter(record["key_schemas"].values()))["schema_status"]
        record["schema_family"] = next(iter(record["key_schemas"].values()))["schema_family"]
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        record["readability_status"] = "UNREADABLE"
        record["accounting_class"] = "CORRUPT"
        record["schema_status"] = "CORRUPT"
        record["schema_family"] = "CORRUPT_NPY"
        record["exception"] = message
        state.exceptions.append(_exception(record["relative_path"], "NPY_READ_ERROR", message, severity="ERROR"))


def _png_header(stream: Any) -> dict[str, Any] | None:
    header = stream.read(29)
    if len(header) < 29 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header[16:29]
    )
    return {
        "width": int(width),
        "height": int(height),
        "bit_depth": int(bit_depth),
        "color_type": int(color_type),
        "compression": int(compression),
        "filter_method": int(filter_method),
        "interlace": int(interlace),
    }


def _inspect_zip(path: Path, record: dict[str, Any], state: _ProfileState) -> None:
    record["file_type"] = "ZIP_ARCHIVE"
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = sorted(archive.infolist(), key=lambda info: info.filename)
            files = [info for info in infos if not info.is_dir()]
            suffix_counts: Counter[str] = Counter()
            for info in files:
                suffix = PurePosixPath(info.filename).suffix.lower() or "<none>"
                suffix_counts[suffix] += 1
                member_parts = PurePosixPath(info.filename).parts
                if len(member_parts) > 1:
                    state.directory_patterns[member_parts[0]] += 1
            png_headers: list[dict[str, Any]] = []
            first_image = next((info for info in files if PurePosixPath(info.filename).suffix.lower() == ".png"), None)
            if first_image is not None:
                with archive.open(first_image, "r") as member:
                    header = _png_header(member)
                if header is not None:
                    png_headers.append(header)
            label_members = [info.filename for info in files if PurePosixPath(info.filename).name.lower() in {"labels.txt", "labels.csv", "annotations.json", "annotations.jsonl"}]
            record["readability_status"] = "READABLE"
            record["accounting_class"] = "EXCLUDED_WITH_EXPLICIT_REASON"
            record["schema_status"] = "UNKNOWN"
            record["schema_family"] = "ARCHIVE_MEMBER_SEMANTICS_NOT_MI48_VERIFIED"
            record["exclusion_reason"] = "ARCHIVE_MEMBERS_REQUIRE_SOURCE_CONTRACT_AND_ARE_NOT_PROMOTED_TO_MI48"
            record["archive_summary"] = {
                "member_count": len(infos),
                "file_member_count": len(files),
                "suffix_counts": dict(sorted(suffix_counts.items())),
                "sample_members": [info.filename for info in files[:20]],
                "png_header_samples": png_headers,
                "label_like_members": sorted(label_members),
            }
            if label_members:
                _observe_metadata_fields(state, record["relative_path"], ["source_label"], "ARCHIVE_LABEL_FILENAME_ONLY_AMBIGUOUS")
                state.exceptions.append(
                    _exception(
                        record["relative_path"],
                        "ARCHIVE_LABEL_SEMANTICS_AMBIGUOUS",
                        "A label-like member exists, but its schema and provenance are not an authoritative MI48 contract.",
                    )
                )
            if png_headers:
                state.exceptions.append(
                    _exception(
                        record["relative_path"],
                        "ARCHIVE_IMAGE_GEOMETRY_NOT_MI48_VERIFIED",
                        "Archive image geometry was observed without treating image pixels as MI48 thermal frames.",
                    )
                )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        record["readability_status"] = "UNREADABLE"
        record["accounting_class"] = "CORRUPT"
        record["schema_status"] = "CORRUPT"
        record["schema_family"] = "CORRUPT_ZIP"
        record["exception"] = message
        state.exceptions.append(_exception(record["relative_path"], "ZIP_READ_ERROR", message, severity="ERROR"))


def _inspect_text(path: Path, record: dict[str, Any], state: _ProfileState) -> None:
    record["file_type"] = "TEXT_METADATA"
    try:
        content = path.read_text(encoding="utf-8")
        record["readability_status"] = "READABLE"
        record["accounting_class"] = "READABLE"
        record["schema_family"] = "TEXT_METADATA"
        record["schema_status"] = "PARTIALLY_KNOWN"
        fields: set[str] = set()
        if path.suffix.lower() == ".json":
            fields = _read_json_keys(json.loads(content))
        elif path.suffix.lower() == ".jsonl":
            for line in content.splitlines()[:100]:
                if line.strip():
                    fields.update(_read_json_keys(json.loads(line)))
        elif path.suffix.lower() == ".csv":
            rows = list(csv.reader(content.splitlines()))
            if rows:
                fields.update(item.strip() for item in rows[0] if item.strip())
        else:
            if path.name.lower() in {"labels.txt", "labels.csv", "annotations.txt"}:
                fields.add("source_label")
        record["metadata_fields"] = sorted(fields)
        _observe_metadata_fields(state, record["relative_path"], fields, "TEXT_FILE")
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        record["readability_status"] = "UNREADABLE"
        record["accounting_class"] = "CORRUPT"
        record["schema_status"] = "CORRUPT"
        record["schema_family"] = "CORRUPT_TEXT_METADATA"
        record["exception"] = message
        state.exceptions.append(_exception(record["relative_path"], "TEXT_METADATA_READ_ERROR", message, severity="ERROR"))


def _inspect_image(path: Path, record: dict[str, Any], state: _ProfileState) -> None:
    record["file_type"] = "IMAGE_CONTAINER"
    try:
        with path.open("rb") as stream:
            header = _png_header(stream) if path.suffix.lower() == ".png" else None
        record["readability_status"] = "READABLE"
        record["accounting_class"] = "EXCLUDED_WITH_EXPLICIT_REASON"
        record["schema_status"] = "UNKNOWN"
        record["schema_family"] = "IMAGE_PIXEL_SEMANTICS_NOT_MI48_VERIFIED"
        record["exclusion_reason"] = "IMAGE_FORMAT_AND_SOURCE_CONTRACT_DO_NOT_ESTABLISH_MI48_NATIVE_FRAME_MEANING"
        if header is not None:
            record["archive_summary"] = {"png_header": header}
        state.exceptions.append(
            _exception(
                record["relative_path"],
                "IMAGE_SEMANTICS_UNRESOLVED",
                "Image container is readable, but it was not promoted to a thermal frame without an authoritative source contract.",
            )
        )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        record["readability_status"] = "UNREADABLE"
        record["accounting_class"] = "CORRUPT"
        record["schema_status"] = "CORRUPT"
        record["schema_family"] = "CORRUPT_IMAGE_CONTAINER"
        record["exception"] = message
        state.exceptions.append(_exception(record["relative_path"], "IMAGE_READ_ERROR", message, severity="ERROR"))


def _inspect_path(
    path: Path,
    root: Path,
    logical_source_id: str,
    state: _ProfileState,
    *,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    record = _base_record(root, path, logical_source_id, source_sha256=source_sha256)
    relative = record["relative_path"]
    _observe_path_tokens(state, relative)
    suffix = path.suffix.lower()
    if suffix == ".npz":
        _inspect_npz(path, record, state)
    elif suffix == ".npy":
        _inspect_npy(path, record, state)
    elif suffix == ".zip":
        _inspect_zip(path, record, state)
    elif ARCHIVE_PART_RE.search(path.name):
        record["file_type"] = "MULTI_VOLUME_ARCHIVE_PART"
        record["readability_status"] = "READABLE" if path.stat().st_size >= 4 else "UNREADABLE"
        record["accounting_class"] = "EXCLUDED_WITH_EXPLICIT_REASON" if record["readability_status"] == "READABLE" else "CORRUPT"
        record["schema_status"] = "UNKNOWN"
        record["schema_family"] = "MULTI_VOLUME_ARCHIVE_COMPONENT"
        record["exclusion_reason"] = "ARCHIVE_COMPONENT_IS_NOT_A_STANDALONE_MI48_SOURCE_FILE"
        state.exceptions.append(
            _exception(
                relative,
                "MULTI_VOLUME_ARCHIVE_COMPONENT_EXCLUDED",
                "Archive volume was accounted for but not opened as an independent dataset.",
            )
        )
    elif suffix in TEXT_EXTENSIONS:
        _inspect_text(path, record, state)
    elif suffix in IMAGE_EXTENSIONS:
        _inspect_image(path, record, state)
    elif suffix in RAW_EXTENSIONS:
        record["file_type"] = "RAW_BINARY"
        record["readability_status"] = "READABLE"
        record["accounting_class"] = "EXCLUDED_WITH_EXPLICIT_REASON"
        record["schema_status"] = "UNKNOWN"
        record["schema_family"] = "RAW_BINARY_WITHOUT_NATIVE_SCHEMA"
        record["exclusion_reason"] = "BYTE_ORDER_AND_CAPTURE_CONTRACT_NOT_PROVEN"
        state.exceptions.append(
            _exception(
                relative,
                "RAW_BINARY_SCHEMA_UNRESOLVED",
                "Raw binary bytes were hashed and accounted for, but native shape, byte order, and unit were not guessed.",
            )
        )
    else:
        record["file_type"] = "UNCLASSIFIED_FILE"
        record["readability_status"] = "READABLE"
        record["accounting_class"] = "EXCLUDED_WITH_EXPLICIT_REASON"
        record["schema_status"] = "UNKNOWN"
        record["schema_family"] = "UNKNOWN_FILE_TYPE"
        record["exclusion_reason"] = "UNCLASSIFIED_FILE_EXPLICITLY_EXCLUDED_FROM_MI48_FRAME_PROFILE"
        state.exceptions.append(
            _exception(
                relative,
                "UNKNOWN_FILE_TYPE_EXCLUDED",
                "File was discovered but its semantics are not known to the B6R-1 profiler.",
            )
        )
    return record


def _source_snapshot(root: Path, logical_source_id: str) -> dict[str, Any]:
    if not root.is_dir():
        return {
            "root_status": "UNAVAILABLE",
            "logical_source_id": logical_source_id,
            "files": [],
        }
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        stat = path.stat()
        relative = _relative_path(root, path)
        files.append(
            {
                "relative_path": relative,
                "logical_source_identifier": f"{logical_source_id}/{relative}",
                "byte_size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "sha256": sha256_file(path),
            }
        )
    return {
        "root_status": "AVAILABLE",
        "logical_source_id": logical_source_id,
        "files": files,
    }


def _compare_source_snapshots(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_map = {item["relative_path"]: item for item in before.get("files", [])}
    after_map = {item["relative_path"]: item for item in after.get("files", [])}
    added = sorted(set(after_map) - set(before_map))
    removed = sorted(set(before_map) - set(after_map))
    changed = sorted(
        path
        for path in set(before_map) & set(after_map)
        if before_map[path] != after_map[path]
    )
    return {
        "status": "PASS" if not added and not removed and not changed and before.get("root_status") == after.get("root_status") else "FAIL",
        "added": added,
        "removed": removed,
        "changed": changed,
        "before_file_count": len(before_map),
        "after_file_count": len(after_map),
    }


def _metadata_discovery(state: _ProfileState) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    observed_lower = {field.lower(): field for field in state.observed_metadata_fields}
    for required in REQUIRED_METADATA_FIELDS:
        exact = observed_lower.get(required.lower())
        if exact is not None:
            status = "DIRECTLY_OBSERVED"
            confidence = "FIELD_NAME_OBSERVED_WITHOUT_VALUE_PROVENANCE"
            sources = sorted(state.observed_metadata_fields[exact])
        elif required == "source_label" and any("label" in path.lower() for path in state.filename_patterns):
            status = "AMBIGUOUS"
            confidence = "LABEL_LIKE_FILENAME_ONLY"
            sources = []
        elif required == "split_role" and any(part.lower() in {"train", "test", "validation", "development"} for part in state.directory_patterns):
            status = "AMBIGUOUS"
            confidence = "DIRECTORY_NAME_NOT_A_SAFE_NEST_ROLE_ASSIGNMENT"
            sources = []
        else:
            status = "ABSENT"
            confidence = "NO_OBSERVED_FIELD"
            sources = []
        fields.append(
            {
                "field": required,
                "status": status,
                "provenance_confidence": confidence,
                "observed_in": sources,
            }
        )
    return {
        "schema_version": "safenest.thermal.b6r1.metadata_discovery.v1",
        "field_status_definitions": {
            "DIRECTLY_OBSERVED": "Field name was observed in a source structure; value provenance is not thereby trusted.",
            "DERIVABLE_WITHOUT_AMBIGUITY": "Not assigned by this profiler unless the source contract proves the derivation.",
            "AMBIGUOUS": "A filename or directory clue exists but cannot safely define a SafeNest field.",
            "ABSENT": "No field evidence was observed.",
        },
        "required_field_registry": fields,
        "observed_text_and_archive_sources": sorted(state.metadata_sources, key=lambda item: item["relative_path"]),
        "filename_patterns": [
            {"pattern": pattern, "count": count}
            for pattern, count in sorted(state.filename_patterns.items())
        ],
        "directory_components": [
            {"component": component, "count": count}
            for component, count in sorted(state.directory_patterns.items())
        ],
        "split_roles_assigned": False,
        "labels_remapped": False,
        "subject_or_session_groups_created": False,
    }


def _coordinate_rows(state: _ProfileState) -> list[dict[str, Any]]:
    eligible = state.eligible_frame_count
    if eligible == 0:
        return []
    minimum_count = max(REPEAT_COUNT_FLOOR, int(math.ceil(REPEAT_FRACTION_THRESHOLD * eligible)))
    rows: list[dict[str, Any]] = []
    for criterion in COORDINATE_CRITERIA:
        counts = state.coordinate_counts[criterion]
        for row_index, column_index in zip(*np.where(counts >= minimum_count)):
            count = int(counts[row_index, column_index])
            rows.append(
                {
                    "row": int(row_index),
                    "column": int(column_index),
                    "criterion": criterion,
                    "count": count,
                    "eligible_frame_count": eligible,
                    "fraction": float(count / eligible),
                    "minimum_repeat_count": minimum_count,
                    "supporting_statistics": {
                        "repeat_fraction_threshold": REPEAT_FRACTION_THRESHOLD,
                        "candidate_status": "ANOMALY_CANDIDATE",
                        "interpretation": "Observed repeated coordinate behavior; not a dead/invalid pixel conclusion.",
                    },
                }
            )
    return sorted(rows, key=lambda item: (-item["count"], item["criterion"], item["row"], item["column"]))


def _decision(
    *,
    root_status: str,
    identity_status: str,
    total_frames: int,
    accounting: Mapping[str, int],
    source_immutability: str,
) -> tuple[str, str]:
    if source_immutability != "PASS":
        return "INCONCLUSIVE", "Source mutation was detected during profiling; no downstream use is permitted."
    if root_status != "AVAILABLE":
        return "INCONCLUSIVE", "The authoritative MI48 snapshot root is unavailable."
    if identity_status != "RESOLVED":
        return "INCONCLUSIVE", "Candidate files were observed, but MI48 dataset identity was not resolved from authoritative evidence."
    if total_frames == 0:
        if accounting.get("CORRUPT", 0) and not accounting.get("READABLE", 0):
            return "UNUSABLE", "All discovered source files were unreadable or corrupt."
        return "INCONCLUSIVE", "No MI48 thermal frame could be identified without guessing schema semantics."
    if accounting.get("CORRUPT", 0) or accounting.get("EXCLUDED_WITH_EXPLICIT_REASON", 0):
        return "PARTIALLY_USABLE", "A thermal frame subset is readable, but corrupt or explicitly excluded source files remain."
    return "USABLE", "All discovered source files with identified thermal frames are readable and their schema is understood."


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            prepared = dict(row)
            for key, value in prepared.items():
                if isinstance(value, (dict, list)):
                    prepared[key] = _json(value)
            writer.writerow(prepared)


def _write_utf8(path: Path, text: str) -> None:
    """Write deterministic UTF-8 bytes without platform newline translation."""

    path.write_bytes(text.encode("utf-8"))


def _write_checksums(output_root: Path) -> None:
    rows: list[str] = []
    excluded = {"checksums.sha256", "source_checksums.sha256"}
    for path in sorted((item for item in output_root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(output_root).as_posix()):
        relative = path.relative_to(output_root).as_posix()
        if relative in excluded:
            continue
        rows.append(f"{sha256_file(path)}  {relative}")
    _write_utf8(output_root / "checksums.sha256", "\n".join(rows) + "\n")


def _write_source_checksums(output_root: Path, records: list[dict[str, Any]]) -> None:
    rows = [
        f"{record['sha256']}  {record['logical_source_identifier']}"
        for record in sorted(records, key=lambda item: item["logical_source_identifier"])
    ]
    _write_utf8(output_root / "source_checksums.sha256", "\n".join(rows) + ("\n" if rows else ""))


def _ledger_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": record["relative_path"],
            "logical_source_identifier": record["logical_source_identifier"],
            "extension": record["extension"],
            "file_type": record["file_type"],
            "byte_size": record["byte_size"],
            "mtime_ns": record["mtime_ns"],
            "sha256": record["sha256"],
            "readability_status": record["readability_status"],
            "accounting_class": record["accounting_class"],
            "exception": record["exception"],
            "npz_keys": record["npz_keys"],
            "key_schemas": record["key_schemas"],
            "thermal_frame_count": record["thermal_frame_count"],
            "schema_family": record["schema_family"],
            "schema_status": record["schema_status"],
            "metadata_fields": record["metadata_fields"],
            "exclusion_reason": record["exclusion_reason"],
            "archive_summary": record["archive_summary"],
        }
        for record in sorted(records, key=lambda item: item["relative_path"])
    ]


def profile_snapshot(
    snapshot_root: Path,
    output_root: Path,
    *,
    logical_source_id: str,
    identity_status: str = "UNRESOLVED",
) -> dict[str, Any]:
    """Profile one explicitly selected source root into a separate output root."""

    root = Path(snapshot_root).resolve()
    output = Path(output_root).resolve()
    if identity_status not in IDENTITY_STATUSES:
        raise ValueError(f"identity_status must be one of {IDENTITY_STATUSES}")
    if output == root or root in output.parents:
        raise ValueError("output_root must be separate from the read-only snapshot root")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output_root must be empty: {output}")

    before = _source_snapshot(root, logical_source_id)
    state = _ProfileState()
    records: list[dict[str, Any]] = []
    if root.is_dir():
        before_hashes = {item["relative_path"]: item["sha256"] for item in before["files"]}
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            relative = _relative_path(root, path)
            records.append(
                _inspect_path(
                    path,
                    root,
                    logical_source_id,
                    state,
                    source_sha256=before_hashes.get(relative),
                )
            )
    else:
        state.exceptions.append(
            _exception(
                ".",
                "SNAPSHOT_ROOT_UNAVAILABLE",
                "The selected snapshot root does not exist as a directory.",
                severity="ERROR",
            )
        )
    after = _source_snapshot(root, logical_source_id)
    immutability = _compare_source_snapshots(before, after)

    accounting = Counter(record["accounting_class"] for record in records)
    for accounting_class in ACCOUNTING_CLASSES:
        accounting.setdefault(accounting_class, 0)
    total_discovered = len(records)
    accounting_invariant = total_discovered == sum(accounting[item] for item in ACCOUNTING_CLASSES)
    total_frames = len(state.frame_rows)
    decision, decision_reason = _decision(
        root_status=before["root_status"],
        identity_status=identity_status,
        total_frames=total_frames,
        accounting=accounting,
        source_immutability=immutability["status"],
    )
    if identity_status != "RESOLVED":
        state.exceptions.append(
            _exception(
                ".",
                "SOURCE_IDENTITY_UNRESOLVED",
                "The caller did not assert an authoritative MI48 identity; no source was promoted to MI48 evidence.",
                severity="ERROR",
            )
        )

    coordinate_rows = _coordinate_rows(state)
    distribution = {
        "eligible_frame_count": total_frames,
        "pixel_count": state.global_pixel_count,
        "finite_pixel_count": state.global_finite_count,
        "nonfinite_pixel_count": state.global_nonfinite_count,
        "global_pixel_min": state.global_pixel_min,
        "global_pixel_max": state.global_pixel_max,
        "exact_zero_count": state.global_zero_count,
        "exact_65535_count": state.global_65535_count,
        "dtype_min_count": state.global_dtype_min_count,
        "dtype_max_count": state.global_dtype_max_count,
        "dtype_counts_by_frame": dict(sorted(state.dtype_counts.items())),
        "shape_counts_by_frame": dict(sorted(state.shape_counts.items())),
        "per_frame_metric_summaries": {
            metric: _percentile_summary(values)
            for metric, values in sorted(state.frame_metric_values.items())
        },
        "percentile_semantics": "p2/p98/span are exact per-frame finite-pixel statistics; aggregate summaries describe the distribution of those frame statistics, not a guessed global pixel percentile.",
    }
    schema_families: dict[str, dict[str, Any]] = {}
    for item in sorted(state.schema_records, key=lambda row: (row["schema_family"], row["relative_path"], row["array_key"])):
        family = item["schema_family"]
        entry = schema_families.setdefault(
            family,
            {
                "schema_family": family,
                "schema_status": item["schema_status"],
                "array_count": 0,
                "file_count": 0,
                "thermal_frame_count": 0,
                "examples": [],
            },
        )
        entry["array_count"] += 1
        entry["thermal_frame_count"] += int(item["thermal_frame_count"])
        if item["schema_status"] == "CORRUPT":
            entry["schema_status"] = "CORRUPT"
        elif item["schema_status"] == "PARTIALLY_KNOWN" and entry["schema_status"] == "UNKNOWN":
            entry["schema_status"] = "PARTIALLY_KNOWN"
        if len(entry["examples"]) < 10:
            entry["examples"].append(
                {
                    "relative_path": item["relative_path"],
                    "array_key": item["array_key"],
                    "dtype": item["dtype"],
                    "shape": item["shape"],
                }
            )
    for record in sorted(records, key=lambda row: row["relative_path"]):
        family = record["schema_family"]
        entry = schema_families.setdefault(
            family,
            {
                "schema_family": family,
                "schema_status": record["schema_status"],
                "array_count": 0,
                "file_count": 0,
                "thermal_frame_count": 0,
                "examples": [],
            },
        )
        entry["file_count"] += 1
        if record["schema_status"] == "CORRUPT":
            entry["schema_status"] = "CORRUPT"
        elif record["schema_status"] == "PARTIALLY_KNOWN" and entry["schema_status"] == "UNKNOWN":
            entry["schema_status"] = "PARTIALLY_KNOWN"
        if len(entry["examples"]) < 10:
            archive_shape = record.get("archive_summary", {}).get("png_header")
            if archive_shape is None:
                png_samples = record.get("archive_summary", {}).get("png_header_samples", [])
                archive_shape = png_samples[0] if png_samples else None
            entry["examples"].append(
                {
                    "relative_path": record["relative_path"],
                    "array_key": None,
                    "dtype": None,
                    "shape": archive_shape,
                }
            )

    summary = {
        "schema_version": ARTIFACT_SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "profiler_version": PROFILER_VERSION,
        "source": {
            "logical_source_id": logical_source_id,
            "root_status": before["root_status"],
            "identity_status": identity_status,
            "raw_source_modified_by_profiler": False,
            "source_files_are_read_only_inputs": True,
        },
        "accounting": {
            "total_discovered": total_discovered,
            "readable": int(accounting["READABLE"]),
            "corrupt": int(accounting["CORRUPT"]),
            "excluded_with_explicit_reason": int(accounting["EXCLUDED_WITH_EXPLICIT_REASON"]),
            "readability_status_counts": {
                status: sum(1 for record in records if record["readability_status"] == status)
                for status in READABLE_STATUSES
            },
            "unknown_schema_file_count": sum(1 for record in records if record["schema_status"] == "UNKNOWN"),
            "invariant_total_equals_readable_plus_corrupt_plus_excluded": accounting_invariant,
        },
        "thermal_frames": {
            "identified_without_guessing": total_frames,
            "frame_statistics_file": "frame_statistics.csv",
            "coordinate_profile_file": "coordinate_frequency_profile.csv",
            "distribution": distribution,
        },
        "schema_families_file": "schema_families.json",
        "metadata_discovery_file": "metadata_discovery.json",
        "exceptions_file": "exception_registry.json",
        "source_immutability_file": "source_immutability.json",
        "decision": {
            "B6R_1_MI48_DATASET_STATUS": decision,
            "reason": decision_reason,
            "B6R_2_supportable_now": False,
            "B6R_2_was_executed": False,
        },
        "anomaly_candidate_policy": {
            "status_label": "ANOMALY_CANDIDATE",
            "criteria": list(COORDINATE_CRITERIA),
            "minimum_repeat_count": REPEAT_COUNT_FLOOR,
            "repeat_fraction_threshold": REPEAT_FRACTION_THRESHOLD,
            "effective_minimum_repeat_count": max(REPEAT_COUNT_FLOOR, int(math.ceil(REPEAT_FRACTION_THRESHOLD * total_frames))) if total_frames else None,
            "no_invalid_or_dead_pixel_claim": True,
            "no_preprocessing_threshold_selected": True,
        },
        "determinism": {
            "file_order": "POSIX relative path ascending",
            "json_order": "sort_keys=true",
            "csv_order": "stable field order and sorted rows",
            "randomness_used": False,
            "timestamps_in_evidence_payload": False,
        },
        "validation_requirements": {
            "source_immutability_status": immutability["status"],
            "accounting_invariant": accounting_invariant,
            "source_checksum_strategy": "SHA-256 per discovered source file plus size and mtime_ns before/after",
        },
    }

    output.mkdir(parents=True, exist_ok=True)
    _write_utf8(output / "summary.json", _json_pretty(summary))
    _write_csv(
        output / "file_ledger.csv",
        _ledger_rows(records),
        [
            "relative_path",
            "logical_source_identifier",
            "extension",
            "file_type",
            "byte_size",
            "mtime_ns",
            "sha256",
            "readability_status",
            "accounting_class",
            "exception",
            "npz_keys",
            "key_schemas",
            "thermal_frame_count",
            "schema_family",
            "schema_status",
            "metadata_fields",
            "exclusion_reason",
            "archive_summary",
        ],
    )
    _write_csv(
        output / "frame_statistics.csv",
        state.frame_rows,
        [
            "frame_id",
            "relative_path",
            "array_key",
            "frame_index",
            "source_shape",
            "frame_shape",
            "dtype",
            "pixel_count",
            "finite_count",
            "nonfinite_count",
            "min",
            "max",
            "p2",
            "p98",
            "p98_minus_p2",
            "exact_zero_count",
            "exact_65535_count",
            "dtype_min_count",
            "dtype_max_count",
            "nan_count",
            "negative_inf_count",
            "positive_inf_count",
        ],
    )
    _write_utf8(
        output / "schema_families.json",
        _json_pretty(
            {
                "schema_version": "safenest.thermal.b6r1.schema_families.v1",
                "families": [schema_families[key] for key in sorted(schema_families)],
                "array_schema_records": sorted(state.schema_records, key=lambda row: (row["relative_path"], row["array_key"])),
            }
        ),
    )
    _write_utf8(output / "metadata_discovery.json", _json_pretty(_metadata_discovery(state)))
    _write_utf8(
        output / "exception_registry.json",
        _json_pretty(
            {
                "schema_version": "safenest.thermal.b6r1.exception_registry.v1",
                "exceptions": sorted(state.exceptions, key=lambda item: (item["relative_path"], item["code"], item["message"])),
            }
        ),
    )
    _write_csv(
        output / "coordinate_frequency_profile.csv",
        coordinate_rows,
        [
            "row",
            "column",
            "criterion",
            "count",
            "eligible_frame_count",
            "fraction",
            "minimum_repeat_count",
            "supporting_statistics",
        ],
    )
    _write_utf8(
        output / "source_immutability.json",
        _json_pretty({"schema_version": "safenest.thermal.b6r1.source_immutability.v1", "before": before, "after": after, "comparison": immutability}),
    )
    _write_utf8(
        output / "source_resolution.json",
        _json_pretty(
            {
                "schema_version": "safenest.thermal.b6r1.source_resolution.v1",
                "artifact_id": ARTIFACT_ID,
                "selected_logical_source_id": logical_source_id,
                "selected_root_status": before["root_status"],
                "selected_identity_status": identity_status,
                "authoritative_mi48_identity_confirmed": identity_status == "RESOLVED",
                "source_promotion_to_mi48": identity_status == "RESOLVED",
                "resolution_note": "This is the caller-selected root status; external candidate discovery evidence may add a more detailed source_resolution.json without changing raw inputs.",
            }
        ),
    )
    _write_source_checksums(output, records)
    _write_checksums(output)
    _write_utf8(
        output / "validation_result.json",
        _json_pretty({"status": "PENDING", "artifact_id": ARTIFACT_ID}),
    )
    _write_checksums(output)
    validation = validate_evidence(output)
    _write_utf8(output / "validation_result.json", _json_pretty(validation))
    _write_checksums(output)
    return summary


def _read_checksum_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError(f"invalid checksum line {path}:{line_number}") from exc
        values[relative] = digest
    return values


def validate_evidence(output_root: Path) -> dict[str, Any]:
    root = Path(output_root).resolve()
    required = {
        "summary.json",
        "file_ledger.csv",
        "frame_statistics.csv",
        "schema_families.json",
        "metadata_discovery.json",
        "exception_registry.json",
        "coordinate_frequency_profile.csv",
        "source_immutability.json",
        "source_resolution.json",
        "source_checksums.sha256",
        "checksums.sha256",
        "validation_result.json",
    }
    errors: list[dict[str, str]] = []
    for name in sorted(required):
        if not (root / name).is_file():
            errors.append({"code": "REQUIRED_ARTIFACT_MISSING", "path": name, "message": "Required B6R-1 artifact is missing."})
    if errors:
        return {"status": "FAIL", "errors": errors}
    try:
        summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        immutability = json.loads((root / "source_immutability.json").read_text(encoding="utf-8"))
        ledger_rows = list(csv.DictReader((root / "file_ledger.csv").read_text(encoding="utf-8").splitlines()))
        frame_rows = list(csv.DictReader((root / "frame_statistics.csv").read_text(encoding="utf-8").splitlines()))
    except Exception as exc:
        errors.append({"code": "ARTIFACT_PARSE_ERROR", "path": "artifacts", "message": f"{type(exc).__name__}: {exc}"})
        return {"status": "FAIL", "errors": errors}

    accounting = Counter(row.get("accounting_class") for row in ledger_rows)
    total = len(ledger_rows)
    if any(item not in ACCOUNTING_CLASSES for item in accounting):
        errors.append({"code": "ACCOUNTING_CLASS_INVALID", "path": "file_ledger.csv", "message": "Every source file must have one of the three accounting classes."})
    if total != sum(accounting.get(item, 0) for item in ACCOUNTING_CLASSES):
        errors.append({"code": "ACCOUNTING_INVARIANT_FAILED", "path": "file_ledger.csv", "message": "TOTAL_DISCOVERED does not equal readable + corrupt + explicitly excluded."})
    if summary.get("accounting", {}).get("invariant_total_equals_readable_plus_corrupt_plus_excluded") is not True:
        errors.append({"code": "SUMMARY_ACCOUNTING_INVARIANT_FAILED", "path": "summary.json", "message": "Summary did not record a passing accounting invariant."})
    if immutability.get("comparison", {}).get("status") != "PASS":
        errors.append({"code": "SOURCE_IMMUTABILITY_FAILED", "path": "source_immutability.json", "message": "Source size, mtime, or hash changed during profiling."})
    if summary.get("source", {}).get("raw_source_modified_by_profiler") is not False:
        errors.append({"code": "SOURCE_MUTATION_FLAG_INVALID", "path": "summary.json", "message": "Raw source mutation flag must remain false."})
    if len(frame_rows) != int(summary.get("thermal_frames", {}).get("identified_without_guessing", -1)):
        errors.append({"code": "FRAME_ACCOUNTING_MISMATCH", "path": "frame_statistics.csv", "message": "Frame statistics row count does not match summary."})
    checksum_path = root / "checksums.sha256"
    try:
        expected = _read_checksum_file(checksum_path)
        for relative, digest in expected.items():
            path = root / PurePosixPath(relative)
            if not path.is_file():
                errors.append({"code": "CHECKSUM_TARGET_MISSING", "path": relative, "message": "Checksum target is missing."})
            elif sha256_file(path) != digest:
                errors.append({"code": "CHECKSUM_MISMATCH", "path": relative, "message": "Generated artifact checksum mismatch."})
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix()
            if relative not in {"checksums.sha256", "source_checksums.sha256", "validation_result.json"} and relative not in expected:
                errors.append({"code": "CHECKSUM_COVERAGE_GAP", "path": relative, "message": "Generated artifact is not covered by checksums.sha256."})
    except Exception as exc:
        errors.append({"code": "CHECKSUM_PARSE_ERROR", "path": "checksums.sha256", "message": f"{type(exc).__name__}: {exc}"})
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": sorted(errors, key=lambda item: (item["code"], item["path"])),
        "artifact_id": summary.get("artifact_id"),
        "B6R_1_MI48_DATASET_STATUS": summary.get("decision", {}).get("B6R_1_MI48_DATASET_STATUS"),
        "total_discovered": total,
        "frame_count": len(frame_rows),
        "accounting": dict(sorted((key, int(value)) for key, value in accounting.items())),
        "source_immutability": immutability.get("comparison", {}).get("status"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Profile one explicitly selected MI48 snapshot root for B6R-1.")
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile", help="Read a source root and write a separate deterministic evidence package.")
    profile.add_argument("snapshot_root", type=Path)
    profile.add_argument("output_root", type=Path)
    profile.add_argument("--logical-source-id", required=True)
    profile.add_argument("--identity-status", choices=IDENTITY_STATUSES, default="UNRESOLVED")
    validate = sub.add_parser("validate", help="Validate an existing B6R-1 evidence package.")
    validate.add_argument("output_root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "profile":
        result = profile_snapshot(
            args.snapshot_root,
            args.output_root,
            logical_source_id=args.logical_source_id,
            identity_status=args.identity_status,
        )
        print(_json_pretty(result), end="")
        return 0
    result = validate_evidence(args.output_root)
    print(_json_pretty(result), end="")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
