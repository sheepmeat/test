"""Focused T-A2 geometry, calibration, and canonical-frame tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasets.thermal.canonical_geometry import (  # noqa: E402
    CANONICAL_SHAPE,
    SOURCE_SHAPE,
    GeometryPathError,
    GeometryShapeError,
    InvalidPixelError,
    _ensure_portable_relative_path,
    canonical_to_source_trace,
    canonicalize_physical_frame,
    make_candidate_profiles,
    precision_error,
    selected_geometry_profile,
    source_to_canonical_trace,
)


def _gradient() -> np.ndarray:
    row = np.arange(SOURCE_SHAPE[0], dtype=np.float64)[:, None]
    column = np.arange(SOURCE_SHAPE[1], dtype=np.float64)[None, :]
    return row * 1000.0 + column


def test_source_shape_and_selected_canonical_shape() -> None:
    profile = selected_geometry_profile()
    result = canonicalize_physical_frame(np.zeros(SOURCE_SHAPE), profile)
    assert result.physical_frame.shape == CANONICAL_SHAPE
    assert result.physical_frame.dtype == np.float32
    assert result.validity_mask.shape == CANONICAL_SHAPE
    assert np.all(result.validity_mask)


def test_wrong_source_shape_rejected() -> None:
    with pytest.raises(GeometryShapeError):
        canonicalize_physical_frame(np.zeros((62, 80)), selected_geometry_profile())


def test_gradient_preserves_row_column_order_without_transpose_or_flip() -> None:
    result = canonicalize_physical_frame(_gradient(), selected_geometry_profile())
    values = result.physical_frame
    assert values[0, 0] < values[0, -1]
    assert values[0, 0] < values[-1, 0]
    assert values[-1, -1] > values[0, -1]
    assert values[-1, -1] > values[-1, 0]


def test_known_corner_mapping_and_coordinate_trace() -> None:
    profile = selected_geometry_profile()
    trace = canonical_to_source_trace(profile, 0, 0)
    assert trace["status"] == "MEASURED_SOURCE_SUPPORT"
    assert trace["source_coordinate"][0] == pytest.approx(3.3709677419)
    assert trace["source_coordinate"][1] == pytest.approx(13.375)
    assert source_to_canonical_trace(profile, 0, 0)["status"] == "SOURCE_CROPPED_OUT"
    assert source_to_canonical_trace(profile, 0, 10)["status"] == "MEASURED_CANONICAL_COORDINATE"
    assert canonical_to_source_trace(profile, 0, 0)["source_support"] == [[3, 13], [3, 14], [4, 13], [4, 14]]


def test_asymmetric_hot_region_maps_to_expected_canonical_region() -> None:
    source = np.zeros(SOURCE_SHAPE, dtype=np.float64)
    source[220:260, 280:320] = 100.0
    result = canonicalize_physical_frame(source, selected_geometry_profile())
    peak = np.unravel_index(np.nanargmax(result.physical_frame), result.physical_frame.shape)
    assert 20 <= peak[0] <= 40
    assert 30 <= peak[1] <= 45


def test_all_predeclared_interpolations_are_deterministic() -> None:
    source = _gradient()
    for profile in make_candidate_profiles():
        first = canonicalize_physical_frame(source, profile)
        second = canonicalize_physical_frame(source, profile)
        assert first.canonical_frame_hash == second.canonical_frame_hash
        assert np.array_equal(first.physical_frame, second.physical_frame, equal_nan=True)


def test_fixed_crop_and_masked_padding_are_explicit() -> None:
    source = _gradient()
    crop = selected_geometry_profile()
    cropped = canonicalize_physical_frame(source, crop)
    assert cropped.validity_mask.sum() == 62 * 80
    assert crop.crop_xyxy == (10, 0, 630, 480)

    padded = next(profile for profile in make_candidate_profiles() if profile.geometry_policy == "ASPECT_PRESERVING_PAD" and profile.interpolation == "bilinear")
    padded_result = canonicalize_physical_frame(source, padded)
    assert padded_result.validity_mask.sum() == 60 * 80
    assert np.all(np.isnan(padded_result.physical_frame[0]))
    assert np.all(np.isnan(padded_result.physical_frame[-1]))


def test_constant_temperature_is_preserved_physically() -> None:
    result = canonicalize_physical_frame(np.full(SOURCE_SHAPE, 26.85), selected_geometry_profile())
    assert np.all(result.physical_frame == np.float32(26.85))
    assert np.all(result.validity_mask)


def test_nan_inf_and_partial_invalid_mask_fail_closed() -> None:
    nan_source = np.full(SOURCE_SHAPE, 26.85, dtype=np.float64)
    nan_source[0, 0] = np.nan
    with pytest.raises(InvalidPixelError):
        canonicalize_physical_frame(nan_source, selected_geometry_profile())

    inf_source = np.full(SOURCE_SHAPE, 26.85, dtype=np.float64)
    inf_source[0, 0] = np.inf
    with pytest.raises(InvalidPixelError):
        canonicalize_physical_frame(inf_source, selected_geometry_profile())

    mask = np.ones(SOURCE_SHAPE, dtype=bool)
    mask[0, 0] = False
    with pytest.raises(InvalidPixelError):
        canonicalize_physical_frame(np.full(SOURCE_SHAPE, 26.85), selected_geometry_profile(), source_validity_mask=mask)


def test_source_array_is_not_mutated_and_source_hash_is_separate() -> None:
    source = _gradient()
    before = source.copy()
    result = canonicalize_physical_frame(source, selected_geometry_profile(), source_frame_hash="source-hash")
    assert np.array_equal(source, before)
    assert result.source_frame_hash == "source-hash"
    assert result.canonical_frame_hash != "source-hash"


def test_float32_precision_is_below_source_resolution() -> None:
    reference = np.linspace(-20.0, 80.0, num=SOURCE_SHAPE[0] * SOURCE_SHAPE[1], dtype=np.float64).reshape(SOURCE_SHAPE)
    candidate = reference.astype(np.float32).astype(np.float64)
    error = precision_error(reference, candidate)
    assert error["max_abs_error"] < 0.005
    assert error["mean_abs_error"] < 0.001


def test_absolute_and_unsafe_paths_rejected() -> None:
    for value in ("/Users/example/source.zip", "~/source.zip", "file://source.zip", "../source.zip", "a\\b.zip"):
        with pytest.raises(GeometryPathError):
            _ensure_portable_relative_path(value)
    assert _ensure_portable_relative_path("datasets/raw_archives/test.zip") == "datasets/raw_archives/test.zip"


def test_geometry_module_has_no_model_or_normalization_boundary() -> None:
    source = (ROOT / "datasets/thermal/canonical_geometry.py").read_text(encoding="utf-8").lower()
    assert "thermalinterpreter" not in source
    assert "tflite" not in source
    assert "per-frame min-max" not in source
    assert "z-score" not in source
    assert "\bint8\b" not in source


def test_tracked_t_a2_json_is_canonical_and_portable() -> None:
    evidence = ROOT / "datasets/thermal/manifests/T-A2_geometry_calibration_canonical_frame"
    if not evidence.exists():
        pytest.skip("T-A2 evidence is generated after geometry unit tests")
    for path in sorted(evidence.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        assert text == json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        assert "/Users/" not in text
        assert "file://" not in text


def test_validator_independently_rejects_changed_selected_crop(tmp_path: Path) -> None:
    evidence = ROOT / "datasets/thermal/manifests/T-A2_geometry_calibration_canonical_frame"
    if not evidence.exists():
        pytest.skip("T-A2 evidence is generated after geometry unit tests")
    copied = tmp_path / "evidence"
    shutil.copytree(evidence, copied)
    path = copied / "selected_geometry_profile.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["profile"]["crop_xyxy"] = [0, 0, 640, 480]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from scripts.validate_thermal_t_a2 import validate_evidence

    result = validate_evidence(repo_root=ROOT, evidence_dir=copied, check_checksums=False, verify_real_payload=False)
    assert result["evidence_validation"] == "FAIL"
    assert "SELECTED_PROFILE_MISMATCH" in {item["code"] for item in result["errors"]}


def test_real_sdt_geometry_integration_when_materialized() -> None:
    archive = ROOT / "datasets/raw_archives/thermal_split_zips/test.zip"
    if not archive.is_file():
        pytest.skip("owner-local SDT test.zip unavailable")
    from datasets.thermal.raw_reader import SDTThermalRawReader
    from datasets.thermal.canonical_geometry import canonicalize_source_frame

    reader = SDTThermalRawReader(repo_root=ROOT)
    profile = selected_geometry_profile()
    for index in (0, 2000, 4000, 6000):
        frame = reader.read_frame(index)
        result = canonicalize_source_frame(frame, profile)
        assert result.physical_frame.shape == CANONICAL_SHAPE
        assert result.physical_frame.dtype == np.float32
        assert np.all(result.validity_mask)
        assert result.source_frame_hash == frame.raw_encoded_frame_sha256
