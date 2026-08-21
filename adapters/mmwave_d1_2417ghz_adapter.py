"""Native adapter for the SafeNest D1 24.17 GHz Six-Port dataset.

The D1 publication describes four Six-Port detector outputs ``B3``--``B6``
whose differential, orthogonal baseband channels are

    I = B5 - B6
    Q = B3 - B4

The public MATLAB payload exposes those named differential channels as
``radar_I`` and ``radar_Q``.  The adapter therefore never relies on array
column order or silently treats an arbitrary pair of arrays as I/Q.  If a
future payload exposes the four detector channels instead, the explicit
mapping above is used.

This module intentionally stops at a native, source-defined signal:

* full-recording ellipse correction, because the publication requires it;
* ``atan2(Q, I)`` phase and sample-index unwrapping;
* source-defined relative-distance conversion using lambda / 2;
* the synchronously sampled, raw ``respiration`` channel.

It does not resample, filter, normalize, window, differentiate, extract
features, or construct SafeNest labels.  Missing or malformed required data
raises ``D1AdapterError`` rather than producing a synthetic trace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import loadmat


SOURCE_ID = "D1"
ADAPTER_ID = "D1_NATIVE_SIXPORT_PHASE_DISPLACEMENT_V1"
ADAPTER_SCHEMA_VERSION = "D1.1"
EXPECTED_SOURCE_FS_HZ = 2000.0
SUPPORTED_SOURCE_FS_HZ = (500.0, 2000.0)
RADAR_FREQUENCY_HZ = 24.17e9
SPEED_OF_LIGHT_M_S = 299_792_458.0
WAVELENGTH_M = SPEED_OF_LIGHT_M_S / RADAR_FREQUENCY_HZ
RELATIVE_DISTANCE_PER_RAD_M = WAVELENGTH_M / (2.0 * math.pi)

REQUIRED_MAT_FIELDS = ("respiration", "Fs")
PUBLISHED_NAMED_IQ_FIELDS = ("radar_I", "radar_Q")
SIX_PORT_FIELDS = ("B3", "B4", "B5", "B6")
OPTIONAL_SIGNAL_FIELDS = ("ecg_lead2", "ecg_lead3", "pcg_audio")


class D1AdapterError(ValueError):
    """A fail-closed adapter error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class D1NativeRecord:
    """An adapted native D1 record kept in memory for the caller."""

    source_path: Path
    source_sampling_rate_hz: float
    time_s: np.ndarray
    radar_i_native: np.ndarray
    radar_q_native: np.ndarray
    native_phase_rad: np.ndarray
    relative_displacement_m: np.ndarray
    respiration_reference_native: np.ndarray
    metadata: dict[str, Any]


def _as_float_vector(value: Any, field_name: str) -> np.ndarray:
    """Convert a named MATLAB value to a finite 1-D float vector."""

    array = np.asarray(value)
    if np.iscomplexobj(array):
        raise D1AdapterError("COMPLEX_INPUT_UNEXPECTED", field_name)
    array = np.squeeze(array)
    if array.ndim != 1 or array.size == 0:
        raise D1AdapterError(
            "CHANNEL_NOT_ONE_DIMENSIONAL",
            f"{field_name} shape={tuple(np.asarray(value).shape)}",
        )
    try:
        vector = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise D1AdapterError("CHANNEL_NOT_NUMERIC", field_name) from exc
    if not np.all(np.isfinite(vector)):
        raise D1AdapterError("NONFINITE_REQUIRED_CHANNEL", field_name)
    return vector


def _as_scalar_float(value: Any, field_name: str) -> float:
    array = np.asarray(value).squeeze()
    if array.size != 1 or np.iscomplexobj(array):
        raise D1AdapterError("SCALAR_NOT_FINITE", field_name)
    try:
        scalar = float(array.reshape(-1)[0])
    except (TypeError, ValueError, IndexError) as exc:
        raise D1AdapterError("SCALAR_NOT_FINITE", field_name) from exc
    if not math.isfinite(scalar):
        raise D1AdapterError("SCALAR_NOT_FINITE", field_name)
    return scalar


def _matlab_named_iq(mat: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Decode only explicit named D1 baseband fields.

    The published payload uses ``radar_I`` and ``radar_Q``.  The alternative
    B3--B6 branch is retained to make the source-specific Six-Port contract
    explicit for compatible payloads; it is never selected from positional
    array order.
    """

    has_named = all(name in mat for name in PUBLISHED_NAMED_IQ_FIELDS)
    present_b = [name for name in SIX_PORT_FIELDS if name in mat]
    if has_named:
        return (
            _as_float_vector(mat["radar_I"], "radar_I"),
            _as_float_vector(mat["radar_Q"], "radar_Q"),
            {
                "channel_source": "PUBLISHED_NAMED_DIFFERENTIAL_IQ",
                "input_channels": list(PUBLISHED_NAMED_IQ_FIELDS),
                "six_port_combination": {
                    "I": "radar_I (published differential channel; underlying B5-B6)",
                    "Q": "radar_Q (published differential channel; underlying B3-B4)",
                },
                "unexposed_detector_channels": list(SIX_PORT_FIELDS),
            },
        )
    if present_b and set(present_b) != set(SIX_PORT_FIELDS):
        raise D1AdapterError(
            "PARTIAL_SIX_PORT_CHANNEL_SET",
            f"present={present_b}; required={list(SIX_PORT_FIELDS)}",
        )
    if set(present_b) == set(SIX_PORT_FIELDS):
        b3 = _as_float_vector(mat["B3"], "B3")
        b4 = _as_float_vector(mat["B4"], "B4")
        b5 = _as_float_vector(mat["B5"], "B5")
        b6 = _as_float_vector(mat["B6"], "B6")
        return (
            b5 - b6,
            b3 - b4,
            {
                "channel_source": "PUBLISHED_SIX_PORT_B3_B6_DIFFERENTIAL_RECONSTRUCTION",
                "input_channels": list(SIX_PORT_FIELDS),
                "six_port_combination": {"I": "B5 - B6", "Q": "B3 - B4"},
            },
        )
    raise D1AdapterError(
        "REQUIRED_RADAR_CHANNELS_ABSENT",
        "expected named radar_I/radar_Q or complete B3/B4/B5/B6 set",
    )


def _symmetric_positive_square_root(matrix: np.ndarray) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if not np.all(np.isfinite(eigenvalues)) or np.any(eigenvalues <= 0.0):
        raise D1AdapterError("ELLIPSE_MATRIX_NOT_POSITIVE_DEFINITE", str(eigenvalues.tolist()))
    return (eigenvectors * np.sqrt(eigenvalues)) @ eigenvectors.T


def _ellipse_candidate(
    coefficients: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return normalized ellipse center and unit-circle transform."""

    a, b, c, d, e, f = [float(v) for v in coefficients]
    quadratic = np.array([[a, b / 2.0], [b / 2.0, c]], dtype=np.float64)
    linear = np.array([d, e], dtype=np.float64)
    if not np.all(np.isfinite(quadratic)) or not np.all(np.isfinite(linear)):
        return None
    try:
        center = -0.5 * np.linalg.solve(quadratic, linear)
    except np.linalg.LinAlgError:
        return None
    constant_at_center = float(center @ quadratic @ center + linear @ center + f)
    if not math.isfinite(constant_at_center) or constant_at_center >= 0.0:
        # The algebraic equation can be multiplied by -1.  Reorient it so
        # the translated ellipse matrix is positive definite.
        quadratic = -quadratic
        linear = -linear
        f = -f
        try:
            center = -0.5 * np.linalg.solve(quadratic, linear)
        except np.linalg.LinAlgError:
            return None
        constant_at_center = float(center @ quadratic @ center + linear @ center + f)
    if constant_at_center >= 0.0 or not math.isfinite(constant_at_center):
        return None
    try:
        transform = _symmetric_positive_square_root(quadratic / -constant_at_center)
    except D1AdapterError:
        return None
    return center, transform


def fit_ellipse_correction(
    radar_i: np.ndarray,
    radar_q: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fit and apply one full-recording Six-Port ellipse correction.

    The fit is an algebraic ellipse fit in conditioned coordinates.  The
    conditioning is only for numerical stability; it is recorded and the
    raw/native amplitude statistics are retained.  No per-window amplitude
    normalization is performed.
    """

    i = _as_float_vector(radar_i, "radar_I")
    q = _as_float_vector(radar_q, "radar_Q")
    if i.size != q.size:
        raise D1AdapterError("RADAR_CHANNEL_LENGTH_MISMATCH", f"I={i.size}, Q={q.size}")
    if i.size < 20:
        raise D1AdapterError("ELLIPSE_TOO_FEW_SAMPLES", str(i.size))

    center_native = np.array([float(np.mean(i)), float(np.mean(q))], dtype=np.float64)
    scale_native = float(max(np.std(i), np.std(q)))
    if not math.isfinite(scale_native) or scale_native <= np.finfo(np.float64).eps:
        raise D1AdapterError("ELLIPSE_DEGENERATE_RADAR_TRAJECTORY", "zero spread")
    points = np.column_stack(((i - center_native[0]) / scale_native, (q - center_native[1]) / scale_native))
    x = points[:, 0]
    y = points[:, 1]
    design = np.column_stack((x * x, x * y, y * y, x, y, np.ones_like(x)))
    scatter = design.T @ design
    constraint = np.zeros((6, 6), dtype=np.float64)
    constraint[0, 2] = 2.0
    constraint[1, 1] = -1.0
    constraint[2, 0] = 2.0
    try:
        eigenvalues, eigenvectors = np.linalg.eig(np.linalg.solve(scatter, constraint))
    except np.linalg.LinAlgError as exc:
        raise D1AdapterError("ELLIPSE_FIT_SINGULAR", str(exc)) from exc

    candidates: list[tuple[float, np.ndarray, np.ndarray]] = []
    for index in range(eigenvectors.shape[1]):
        vector = np.asarray(eigenvectors[:, index])
        if np.max(np.abs(vector.imag)) > 1e-7:
            continue
        vector = vector.real
        a, b, c = vector[:3]
        if 4.0 * a * c - b * b <= 1e-10:
            continue
        candidate = _ellipse_candidate(vector)
        if candidate is None:
            continue
        ellipse_center, transform = candidate
        corrected = (transform @ (points - ellipse_center).T).T
        radius_error = np.linalg.norm(corrected, axis=1) - 1.0
        residual = float(np.sqrt(np.mean(radius_error * radius_error)))
        if math.isfinite(residual):
            candidates.append((residual, ellipse_center, transform))
    if not candidates:
        raise D1AdapterError("ELLIPSE_FIT_NO_VALID_ELLIPSE", "no positive-definite algebraic candidate")
    residual, ellipse_center, transform = min(
        candidates,
        key=lambda item: (item[0], float(item[1][0]), float(item[1][1])),
    )
    corrected = (transform @ (points - ellipse_center).T).T
    diagnostics = {
        "fit_method": "DIRECT_ALGEBRAIC_ELLIPSE_FIT_CONDITIONED_COORDINATES",
        "fit_sample_count": int(i.size),
        "raw_center_native": [float(v) for v in center_native],
        "conditioning_scale_native": scale_native,
        "ellipse_center_conditioned": [float(v) for v in ellipse_center],
        "unit_circle_transform_conditioned": [[float(v) for v in row] for row in transform],
        "radius_residual_rms": residual,
        "corrected_radius_min": float(np.min(np.linalg.norm(corrected, axis=1))),
        "corrected_radius_max": float(np.max(np.linalg.norm(corrected, axis=1))),
        "raw_i_stats": _stats(i),
        "raw_q_stats": _stats(q),
        "corrected_i_stats": _stats(corrected[:, 0]),
        "corrected_q_stats": _stats(corrected[:, 1]),
    }
    return corrected[:, 0], corrected[:, 1], diagnostics


def _stats(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    return {
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "median": float(np.median(values)),
        "mad_about_median": float(np.median(np.abs(values - np.median(values)))),
    }


def _matlab_text(value: Any) -> str | None:
    """Best-effort text extraction for provenance, never used for decoding."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    array = np.asarray(value)
    if array.size == 0:
        return None
    if array.dtype.kind in {"U", "S"}:
        return "".join(str(v) for v in array.reshape(-1)).strip() or None
    if array.dtype.kind in {"i", "u", "f"} and array.size == 1:
        return str(array.reshape(-1)[0])
    return None


def _matlab_texts(value: Any) -> list[str]:
    if value is None:
        return []
    array = np.asarray(value, dtype=object).reshape(-1)
    return [str(item).strip() for item in array.tolist()]


def _optional_signal_diagnostics(mat: Mapping[str, Any], n_samples: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
    diagnostics: dict[str, Any] = {}
    warnings: list[dict[str, str]] = []
    for field in OPTIONAL_SIGNAL_FIELDS:
        if field not in mat:
            diagnostics[field] = {"present": False, "status": "MISSING_OPTIONAL"}
            warnings.append({"code": "OPTIONAL_CHANNEL_ABSENT", "channel": field})
            continue
        try:
            values = _as_float_vector(mat[field], field)
        except D1AdapterError as exc:
            diagnostics[field] = {"present": True, "status": "MALFORMED_OPTIONAL", "error_code": exc.code}
            warnings.append({"code": "OPTIONAL_CHANNEL_MALFORMED", "channel": field, "detail": exc.code})
            continue
        diagnostics[field] = {
            "present": True,
            "status": "VALID_OPTIONAL",
            "sample_count": int(values.size),
            "length_matches_required": bool(values.size == n_samples),
            "native_stats": _stats(values),
        }
        if values.size != n_samples:
            warnings.append({"code": "OPTIONAL_CHANNEL_LENGTH_MISMATCH", "channel": field})
    return diagnostics, warnings


def adapt_mat_file(
    path: str | Path,
    *,
    condition: str = "UNVERIFIED",
    condition_source: str = "UNVERIFIED",
    source_file: str | None = None,
    strict_source_sampling_rate: bool = True,
) -> D1NativeRecord:
    """Load and adapt one D1 MATLAB recording without writing waveforms."""

    source_path = Path(path)
    try:
        mat = loadmat(source_path, squeeze_me=True, struct_as_record=False)
    except Exception as exc:  # scipy's exception types vary by MATLAB format
        raise D1AdapterError("MAT_LOAD_FAILED", str(exc)) from exc
    if not isinstance(mat, Mapping):
        raise D1AdapterError("MAT_SCHEMA_NOT_MAPPING", source_path.name)

    for field in REQUIRED_MAT_FIELDS:
        if field not in mat:
            raise D1AdapterError("REQUIRED_FIELD_ABSENT", field)
    radar_i, radar_q, channel_metadata = _matlab_named_iq(mat)
    respiration = _as_float_vector(mat["respiration"], "respiration")
    fs_hz = _as_scalar_float(mat["Fs"], "Fs")
    if fs_hz <= 0.0:
        raise D1AdapterError("SOURCE_SAMPLING_RATE_INVALID", str(fs_hz))
    if strict_source_sampling_rate and not any(
        math.isclose(fs_hz, allowed, rel_tol=0.0, abs_tol=1e-9)
        for allowed in SUPPORTED_SOURCE_FS_HZ
    ):
        raise D1AdapterError(
            "SOURCE_SAMPLING_RATE_UNSUPPORTED",
            f"observed={fs_hz}, supported={list(SUPPORTED_SOURCE_FS_HZ)}",
        )
    if radar_i.size != radar_q.size or radar_i.size != respiration.size:
        raise D1AdapterError(
            "REQUIRED_CHANNEL_LENGTH_MISMATCH",
            f"radar_I={radar_i.size}, radar_Q={radar_q.size}, respiration={respiration.size}",
        )
    corrected_i, corrected_q, ellipse = fit_ellipse_correction(radar_i, radar_q)
    phase_wrapped = np.arctan2(corrected_q, corrected_i)
    phase_unwrapped = np.unwrap(phase_wrapped)
    relative_displacement_m = phase_unwrapped * RELATIVE_DISTANCE_PER_RAD_M
    optional, warnings = _optional_signal_diagnostics(mat, radar_i.size)
    measurement_info = _matlab_texts(mat.get("measurement_info"))
    metadata: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "adapter_id": ADAPTER_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "source_file": source_file or source_path.name,
        "subject_id": measurement_info[1] if len(measurement_info) > 1 else None,
        "measurement_timestamp_label": measurement_info[0] if measurement_info else None,
        "measurement_info": measurement_info,
        "condition": condition,
        "condition_source": condition_source,
        "source_sampling_rate_hz": fs_hz,
        "output_sampling_rate_hz": fs_hz,
        "timestamp_generation": "sample_index_divided_by_source_Fs; t[0]=0; no resampling",
        "sample_count": int(radar_i.size),
        "duration_s": float((radar_i.size - 1) / fs_hz),
        "time_basis": "shared source sample index",
        "channel_metadata": channel_metadata,
        "ellipse_correction": ellipse,
        "phase": {
            "name": "native_unwrapped_phase_rad",
            "unit": "radian",
            "calculation": "unwrap(atan2(corrected_Q, corrected_I))",
            "unwrap_rule": "numpy phase-unwrapping threshold at pi between adjacent samples",
        },
        "displacement": {
            "name": "relative_displacement_m",
            "unit": "metre_relative",
            "calculation": "native_unwrapped_phase_rad / (2*pi) * wavelength_m / 2",
            "wavelength_m": WAVELENGTH_M,
            "scale_m_per_rad": RELATIVE_DISTANCE_PER_RAD_M,
            "calibration_status": "SOURCE_DEFINED_RELATIVE_DISTANCE; ABSOLUTE_RANGE_OFFSET_UNKNOWN",
        },
        "respiration_reference": {
            "name": "respiration",
            "unit": "UNVERIFIED_NATIVE_SENSOR_UNITS",
            "sensor_semantics": "passive temperature-based airflow respiration sensor",
            "sample_rate_hz": fs_hz,
            "time_alignment": "same sample index and Fs as radar_I/radar_Q per payload and publication",
            "missing_data_behavior": "fail record on nonfinite or length mismatch; no interpolation",
            "native_stats": _stats(respiration),
        },
        "optional_channels": optional,
        "quality_flags": {
            "required_channels_finite": True,
            "required_channel_lengths_equal": True,
            "timestamps_valid": True,
            "large_missing_region_interpolated": False,
            "native_amplitude_preserved": True,
            "source_intrinsic_ellipse_correction_applied": True,
            "warnings": warnings,
        },
        "output_signal_names": ["native_unwrapped_phase_rad", "relative_displacement_m", "respiration"],
        "forbidden_processing_not_applied": [
            "window_local_MAD_normalization",
            "D0_or_MR60_scaler",
            "derivative_or_R2",
            "spectral_features",
            "autocorrelation_features",
            "breathing_evidence_score",
            "SafeNest_APNEA_proxy_label",
            "neural_preprocessing",
        ],
    }
    metadata["native_phase_stats"] = _stats(phase_unwrapped)
    metadata["relative_displacement_stats"] = _stats(relative_displacement_m)
    return D1NativeRecord(
        source_path=source_path,
        source_sampling_rate_hz=fs_hz,
        time_s=np.arange(radar_i.size, dtype=np.float64) / fs_hz,
        radar_i_native=radar_i,
        radar_q_native=radar_q,
        native_phase_rad=phase_unwrapped,
        relative_displacement_m=relative_displacement_m,
        respiration_reference_native=respiration,
        metadata=metadata,
    )


__all__ = [
    "ADAPTER_ID",
    "ADAPTER_SCHEMA_VERSION",
    "D1AdapterError",
    "D1NativeRecord",
    "EXPECTED_SOURCE_FS_HZ",
    "RADAR_FREQUENCY_HZ",
    "RELATIVE_DISTANCE_PER_RAD_M",
    "SOURCE_ID",
    "SUPPORTED_SOURCE_FS_HZ",
    "WAVELENGTH_M",
    "adapt_mat_file",
    "fit_ellipse_correction",
]
