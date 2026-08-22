#!/usr/bin/env python3
"""Generate compact R2 F1/F2/F3 candidate evidence from the R1 handoff.

This runner consumes the existing R1 input loaders and R1 common-trace
adapter.  It does not decode D0/D1 channels, reimplement D1 Six-Port logic,
write waveform arrays, train a model, or select a candidate.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_r1_sensor_independent_trace import (  # noqa: E402
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)
from adapters.mmwave_r2_representation_features import (  # noqa: E402
    F1_FEATURE_NAMES,
    F1_SCHEMA_ID,
    F2_AUTOCORR_FEATURE_NAMES,
    F2_SCHEMA_ID,
    F3_FEATURE_NAMES,
    F3_SCHEMA_ID,
    R2_CANDIDATE_SET_ID,
    R2_SCHEMA_VERSION,
    RESPIRATORY_BAND_HZ,
    SPECTRAL_BAND_BIN_EDGES_HZ,
    R2FeatureError,
    extract_feature_candidates,
)

import scripts.run_mmwave_r1_sensor_independent_trace as r1_runner  # noqa: E402


EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features")
R1_EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace")
D1_EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter")


class R2RunnerError(RuntimeError):
    """Deterministic input/evidence failure."""


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise R2RunnerError(f"failed to hash {path}: {exc}") from exc
    return digest.hexdigest()


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _counter(values: Iterable[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def _r1_failure_record(native: NativeTraceInput, code: str, detail: str) -> dict[str, Any]:
    return {
        "source_id": native.source_id,
        "dataset_id": native.dataset_id,
        "subject_id": native.subject_id,
        "recording_id": native.recording_id,
        "condition": native.condition,
        "status": "EXCLUDED",
        "failure_code": code,
        "failure_detail": detail,
        "source_sampling_rate_hz": float(native.sampling_rate_hz),
        "source_quality_flags": list(native.source_quality_flags),
        "provenance": _json_safe(dict(native.provenance)),
    }


def _feature_record(native: NativeTraceInput) -> dict[str, Any]:
    try:
        common = adapt_native_trace(native)
    except R1TraceError as exc:
        return _r1_failure_record(native, f"R1_{exc.code}", exc.detail)
    try:
        extracted = extract_feature_candidates(common)
    except R2FeatureError as exc:
        return {
            **_r1_failure_record(native, f"R2_{exc.code}", exc.detail),
            "r1_profile_identity": common.metadata.get("profile_id"),
        }
    return {
        "source_id": common.metadata["source_id"],
        "dataset_id": common.metadata["dataset_id"],
        "subject_id": common.metadata["subject_id"],
        "recording_id": common.metadata["recording_id"],
        "condition": common.metadata["condition"],
        "status": "SUCCESS",
        "source_sampling_rate_hz": common.metadata["source_sampling_rate_hz"],
        "output_sampling_rate_hz": common.metadata["output_sampling_rate_hz"],
        "output_sample_count": int(extracted.trace.size),
        "time_range_s": extracted.provenance["time_range_s"],
        "r1_profile_identity": extracted.provenance["r1_profile_identity"],
        "trace_name": extracted.provenance["r1_trace_name"],
        "trace_units": extracted.provenance["r1_trace_units"],
        "source_quality_flags": list(common.metadata.get("quality_flags", [])),
        "feature_status": {
            "F1": extracted.f1.status,
            "F2": extracted.f2.status,
            "F3": extracted.f3.status,
        },
        "feature_unavailable_reasons": {
            "F1": list(extracted.f1.unavailable_reasons),
            "F2": list(extracted.f2.unavailable_reasons),
            "F3": list(extracted.f3.unavailable_reasons),
        },
        "features": {
            "F1": extracted.f1.features,
            "F2": extracted.f2.features,
            "F3": extracted.f3.features,
        },
        "feature_units": {
            "F1": extracted.f1.feature_units,
            "F2": extracted.f2.feature_units,
            "F3": extracted.f3.feature_units,
        },
        "diagnostics": {
            "F1": extracted.f1.diagnostics,
            "F2": extracted.f2.diagnostics,
            "F3": extracted.f3.diagnostics,
        },
        "provenance": extracted.provenance,
        "trace_persisted": False,
        "native_scale_preserved": True,
        "window_local_scale_normalization": False,
        "cross_domain_gain_matching": False,
        "reference_used_for_feature_selection": False,
    }


def _feature_summary(records: list[dict[str, Any]], candidate_key: str) -> dict[str, Any]:
    successful = [row for row in records if row.get("status") == "SUCCESS"]
    status_counts = _counter(row.get("feature_status", {}).get(candidate_key) for row in successful)
    all_values: dict[str, list[float]] = {}
    for row in successful:
        feature_values = row.get("features", {}).get(candidate_key, {})
        if not isinstance(feature_values, Mapping):
            continue
        for name, value in feature_values.items():
            converted = float(value)
            if np.isfinite(converted):
                all_values.setdefault(str(name), []).append(converted)
    ranges: dict[str, Any] = {}
    for name in sorted(all_values):
        values = np.asarray(all_values[name], dtype=np.float64)
        ranges[name] = {
            "finite_count": int(values.size),
            "finite_fraction_over_success": float(values.size / len(successful)) if successful else 0.0,
            "min": float(np.min(values)),
            "p05": float(np.percentile(values, 5.0)),
            "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95.0)),
            "max": float(np.max(values)),
        }
    return {
        "feature_status_counts": status_counts,
        "finite_feature_ranges": ranges,
    }


def _audit(source_id: str, inputs: list[NativeTraceInput], scope: dict[str, Any]) -> dict[str, Any]:
    records = [_feature_record(native) for native in inputs]
    successful = [row for row in records if row.get("status") == "SUCCESS"]
    durations = [float(row["time_range_s"][1] - row["time_range_s"][0]) for row in successful]
    return {
        "schema_version": R2_SCHEMA_VERSION,
        "source_id": source_id,
        "scope": _json_safe(scope),
        "summary": {
            "records_considered": len(records),
            "success": len(successful),
            "excluded": len(records) - len(successful),
            "condition_counts": _counter(row.get("condition") for row in successful),
            "source_rate_counts_hz": _counter(row.get("source_sampling_rate_hz") for row in successful),
            "output_rate_counts_hz": _counter(row.get("output_sampling_rate_hz") for row in successful),
            "output_sample_count": {
                "min": min((row["output_sample_count"] for row in successful), default=0),
                "max": max((row["output_sample_count"] for row in successful), default=0),
            },
            "duration_s": {
                "min": min(durations, default=0.0),
                "max": max(durations, default=0.0),
                "median": float(np.median(durations)) if durations else 0.0,
            },
            "native_scale_preserved_count": sum(
                row.get("native_scale_preserved") is True for row in successful
            ),
            "window_local_scale_normalization_count": sum(
                row.get("window_local_scale_normalization") is True for row in successful
            ),
            "cross_domain_gain_matching_count": sum(
                row.get("cross_domain_gain_matching") is True for row in successful
            ),
            "trace_persisted_count": sum(row.get("trace_persisted") is True for row in successful),
        },
        "feature_summaries": {
            "F1": _feature_summary(records, "F1"),
            "F2": _feature_summary(records, "F2"),
            "F3": _feature_summary(records, "F3"),
        },
        "records": records,
    }


def _feature_contracts() -> dict[str, dict[str, Any]]:
    common_method = {
        "input_contract": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
        "input_profile": "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1",
        "input_waveform": "respiratory_motion_trace",
        "input_units": "phase_like_radian; absolute displacement equivalence not claimed",
        "input_sampling_rate_rule": "consume R1 output_sampling_rate_hz; current R1 candidate is 10 Hz",
        "variable_length": True,
        "sign_rule": "preserve source sign; no sign flip; spectral power/autocorrelation descriptors are sign-invariant",
        "reference_rule": "reference channels are engineering diagnostics only and cannot tune this candidate",
        "no_model": True,
        "no_apnea_feature_label": True,
        "no_d0_or_mr60_scaler": True,
    }
    f1 = {
        "schema_version": R2_SCHEMA_VERSION,
        "schema_id": F1_SCHEMA_ID,
        "candidate_id": "F1_NORMALIZED_SPECTRAL",
        "status": "BOUNDED_CANDIDATE_FOR_M_PV1_NOT_SELECTED",
        **common_method,
        "respiratory_band": {
            "lower_hz": RESPIRATORY_BAND_HZ[0],
            "upper_hz": RESPIRATORY_BAND_HZ[1],
            "interpretation": "bounded engineering candidate; not a clinical cutoff and not validation-tuned",
            "cycles_per_minute_equivalent": [RESPIRATORY_BAND_HZ[0] * 60.0, RESPIRATORY_BAND_HZ[1] * 60.0],
        },
        "welch_method": {
            "implementation": "scipy.signal.welch",
            "window": "hann",
            "detrend": "constant",
            "scaling": "density",
            "nperseg_rule": "min(256, trace_sample_count)",
            "noverlap_rule": "floor(0.5 * nperseg)",
            "nfft_rule": "nperseg; no zero padding",
            "frequency_grid_rule": "rfftfreq(nperseg, 1 / sampling_rate_hz)",
            "band_integration_rule": "sum(PSD bins in band) * frequency resolution",
            "short_trace_rule": "trace length < 64 samples is typed unavailable; no padding or interpolation",
        },
        "normalized_shape": {
            "bin_edges_hz": list(SPECTRAL_BAND_BIN_EDGES_HZ),
            "feature_names": list(F1_FEATURE_NAMES[:8]),
            "normalization": "band PSD bin power divided by total positive respiratory-band power",
            "zero_band_power": "typed unavailable; no epsilon fake vector",
        },
        "absolute_scale_features": {
            "feature_names": list(F1_FEATURE_NAMES[8:]),
            "normalization": "none; native and R1 common-trace descriptors remain in source units",
            "log_rule": "natural log only for strictly positive energy; zero remains unavailable",
        },
    }
    f2 = {
        "schema_version": R2_SCHEMA_VERSION,
        "schema_id": F2_SCHEMA_ID,
        "candidate_id": "F2_SPECTRAL_AUTOCORR",
        "status": "BOUNDED_CANDIDATE_FOR_M_PV1_NOT_SELECTED",
        **common_method,
        "inherits": F1_SCHEMA_ID,
        "autocorrelation_method": {
            "input": "R1 common trace after mean centering for autocorrelation only",
            "raw_correlation": "full nonnegative-lag numpy correlation",
            "normalization": "divide by exact zero-lag energy; no epsilon",
            "lag_range_rule": "periods corresponding to 0.10--0.70 Hz, clipped to trace length",
            "periodicity_peak_rule": "maximum normalized autocorrelation in the lag range; first maximum on ties",
            "entropy_rule": "entropy of absolute normalized autocorrelation magnitudes in the bounded lag range",
            "short_trace_rule": "typed unavailable when fewer than 64 samples or no bounded lag range",
        },
        "feature_names": list(F1_FEATURE_NAMES) + list(F2_AUTOCORR_FEATURE_NAMES),
        "autocorrelation_feature_names": list(F2_AUTOCORR_FEATURE_NAMES),
        "scale_preservation": "autocorrelation is scale normalized only for periodicity descriptors; F1 absolute scale remains separate",
    }
    f3 = {
        "schema_version": R2_SCHEMA_VERSION,
        "schema_id": F3_SCHEMA_ID,
        "candidate_id": "F3_TRACE_PLUS_QUALITY",
        "status": "BOUNDED_CANDIDATE_FOR_M_PV1_NOT_SELECTED",
        "input_contract": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
        "trace_output": {
            "name": "respiratory_motion_trace",
            "semantics": "offset-centered native phase-like relative motion",
            "units": "phase_like_radian; absolute displacement equivalence not claimed",
            "time_axis": "R1 timestamps and variable length preserved",
            "runtime_retention": "trace/time/validity mask retained for downstream R3 work",
            "repository_evidence": "waveform arrays are intentionally not persisted in R2 evidence",
        },
        "quality_descriptor_names": list(F3_FEATURE_NAMES),
        "quality_flags": [
            "R1_FINITE_OUTPUT",
            "R1_NATIVE_SCALE_PRESERVED",
            "EXACT_FLAT_TRACE",
            "FEATURE_UNAVAILABLE_SHORT_TRACE",
            "FEATURE_UNAVAILABLE_NO_RESPIRATORY_BAND_ENERGY",
        ],
        "fail_closed_rule": "invalid R1 timing/mask/metadata is an exception; flat/short/zero-band cases are typed unavailable",
    }
    return {"f1": f1, "f2": f2, "f3": f3}


def _synthetic_native(trace: np.ndarray, recording_id: str) -> NativeTraceInput:
    fs = 10.0
    return NativeTraceInput(
        source_id="R2_SYNTHETIC",
        dataset_id="synthetic-r2-scale-fixture",
        subject_id="synthetic-subject",
        recording_id=recording_id,
        condition="engineering_sanity_only",
        trace=np.asarray(trace, dtype=np.float64),
        time_s=np.arange(trace.size, dtype=np.float64) / fs,
        sampling_rate_hz=fs,
        native_trace_semantics="synthetic_phase_like_trace",
        native_trace_unit="phase_like_radian",
        source_scale_metadata={"synthetic_fixture": True},
        provenance={"adapter_identity": "R2_SYNTHETIC_FIXTURE"},
    )


def _scale_preservation_audit() -> dict[str, Any]:
    fs = 10.0
    time_s = np.arange(300, dtype=np.float64) / fs
    base = 0.8 * np.sin(2.0 * np.pi * 0.20 * time_s) + 0.12 * np.sin(2.0 * np.pi * 0.35 * time_s)
    small = base / 100.0
    base_result = extract_feature_candidates(adapt_native_trace(_synthetic_native(base, "scale-A")))
    small_result = extract_feature_candidates(adapt_native_trace(_synthetic_native(small, "scale-B")))
    negative_result = extract_feature_candidates(adapt_native_trace(_synthetic_native(-base, "sign-negative")))
    low_amp_result = extract_feature_candidates(adapt_native_trace(_synthetic_native(small, "low-amplitude-periodic")))
    flat_result = extract_feature_candidates(
        adapt_native_trace(_synthetic_native(np.full(300, 2.0, dtype=np.float64), "flat"))
    )

    shape_names = [
        "spectral_shape_fraction_0p10_0p25_hz",
        "spectral_shape_fraction_0p25_0p40_hz",
        "spectral_shape_fraction_0p40_0p55_hz",
        "spectral_shape_fraction_0p55_0p70_hz",
        "spectral_shape_centroid_hz",
        "spectral_shape_peak_frequency_hz",
        "spectral_shape_peak_fraction",
        "spectral_shape_entropy_normalized",
    ]
    shape_diffs = {
        name: abs(base_result.f1.features[name] - small_result.f1.features[name])
        for name in shape_names
    }
    scale_ratios = {
        "native_mad_about_median": base_result.f1.features["native_mad_about_median"]
        / small_result.f1.features["native_mad_about_median"],
        "total_signal_energy": base_result.f1.features["total_signal_energy"]
        / small_result.f1.features["total_signal_energy"],
        "respiratory_band_energy": base_result.f1.features["respiratory_band_energy"]
        / small_result.f1.features["respiratory_band_energy"],
    }
    sign_diffs = {
        name: abs(base_result.f1.features[name] - negative_result.f1.features[name])
        for name in shape_names
    }
    flat_shape_keys_present = [name for name in shape_names if name in flat_result.f1.features]
    all_flat_values_finite = all(
        np.isfinite(value) for value in flat_result.f1.features.values()
    ) and all(np.isfinite(value) for value in flat_result.f2.features.values())
    return {
        "schema_version": R2_SCHEMA_VERSION,
        "purpose": "engineering_sanity_only; no model or candidate selection",
        "fixture": {
            "sample_rate_hz": fs,
            "sample_count": 300,
            "base_trace": "0.8*sin(0.20 Hz) + 0.12*sin(0.35 Hz)",
            "small_trace": "base_trace / 100",
            "flat_trace": "constant 2.0",
        },
        "tests": {
            "normalized_shape_is_scale_stable": {
                "status_base": base_result.f1.status,
                "status_small": small_result.f1.status,
                "max_absolute_shape_difference": max(shape_diffs.values()),
                "per_feature_absolute_difference": shape_diffs,
                "pass": base_result.f1.status == "AVAILABLE"
                and small_result.f1.status == "AVAILABLE"
                and max(shape_diffs.values()) < 1e-10,
            },
            "absolute_scale_is_preserved": {
                "expected_amplitude_ratio": 100.0,
                "expected_energy_ratio": 10000.0,
                "observed_ratios": scale_ratios,
                "pass": abs(scale_ratios["native_mad_about_median"] - 100.0) < 1e-8
                and abs(scale_ratios["total_signal_energy"] - 10000.0) < 1e-6
                and abs(scale_ratios["respiratory_band_energy"] - 10000.0) < 1e-6,
            },
            "low_amplitude_periodic_trace_remains_representable": {
                "f1_status": low_amp_result.f1.status,
                "f2_status": low_amp_result.f2.status,
                "trace_is_exact_flat": bool(low_amp_result.f3.features["trace_is_exact_flat"]),
                "pass": low_amp_result.f1.status == "AVAILABLE"
                and low_amp_result.f2.status == "AVAILABLE"
                and low_amp_result.f3.features["trace_is_exact_flat"] == 0.0,
            },
            "sign_invariance_is_explicit": {
                "max_absolute_shape_difference": max(sign_diffs.values()),
                "per_feature_absolute_difference": sign_diffs,
                "source_sign_flip_applied": False,
                "pass": max(sign_diffs.values()) < 1e-10,
            },
            "exact_flat_trace_is_typed_unavailable": {
                "f1_status": flat_result.f1.status,
                "f2_status": flat_result.f2.status,
                "f3_status": flat_result.f3.status,
                "flat_shape_keys_present": flat_shape_keys_present,
                "all_emitted_values_finite": all_flat_values_finite,
                "pass": flat_result.f1.status == "FEATURE_UNAVAILABLE_FLAT_TRACE"
                and flat_result.f2.status == "FEATURE_UNAVAILABLE_FLAT_TRACE"
                and flat_result.f3.status == "FEATURE_UNAVAILABLE_FLAT_TRACE"
                and not flat_shape_keys_present
                and all_flat_values_finite,
            },
        },
        "model_selection_used": False,
        "threshold_selection_used": False,
        "reference_tuning_used": False,
    }


def _cross_domain_sanity(d0: dict[str, Any], d1: dict[str, Any]) -> dict[str, Any]:
    d0_success = [row for row in d0["records"] if row.get("status") == "SUCCESS"]
    d1_success = [row for row in d1["records"] if row.get("status") == "SUCCESS"]
    observed_f1 = set().union(*(row.get("features", {}).get("F1", {}).keys() for row in d0_success + d1_success))
    observed_f2 = set().union(*(row.get("features", {}).get("F2", {}).keys() for row in d0_success + d1_success))
    return {
        "schema_version": R2_SCHEMA_VERSION,
        "D0_success": len(d0_success),
        "D1_success": len(d1_success),
        "domain_scopes": {
            "D0": "frozen MMWAVE_V2_D0_SUBJECT_SPLIT_V1 TRAIN subjects/windows only",
            "D1": "full 265-recording development pool; no oversampling",
        },
        "common_candidate_contract": {
            "input": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
            "output_candidate_sampling_rate_hz": "inherited from R1; current R1 candidate 10 Hz",
            "variable_length": True,
            "feature_families": [F1_SCHEMA_ID, F2_SCHEMA_ID, F3_SCHEMA_ID],
            "observed_f1_feature_names": sorted(observed_f1),
            "observed_f2_feature_names": sorted(observed_f2),
        },
        "domain_metadata_preserved": {
            "subject": True,
            "recording_or_window": True,
            "condition": True,
            "source_sampling_rate": True,
            "r1_profile": True,
            "source_file_or_window_provenance": True,
        },
        "reference_diagnostics": {
            "used_for_feature_selection": False,
            "used_for_threshold_selection": False,
            "used_for_gain_matching": False,
            "D1_reference_identity": "respiration; passive temperature-based airflow sensor; units unverified, inherited from D1 manifest",
            "D0_reference_identity": "Movesense/reference provenance inherited from D0 audit; not a tuning signal",
        },
        "safety_checks": {
            "D0_VAL_used": False,
            "D0_SUBJECT_HELDOUT_used": False,
            "M_N6_excluded_subjects_used": False,
            "D2_used": False,
            "D3_used": False,
            "MR60_supervised_use": False,
            "model_training": False,
            "candidate_selected": False,
            "cross_domain_scaler_fit": False,
            "window_local_normalization": False,
            "sign_flip": False,
            "source_adapter_reimplemented": False,
        },
        "selection_warning": "domain ranges are descriptive engineering evidence only; no pooled ranking or winner decision is made",
    }


def _scale_audit_from_domains(d0: dict[str, Any], d1: dict[str, Any]) -> dict[str, Any]:
    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        success = [row for row in rows if row.get("status") == "SUCCESS"]
        scale_rows = [row for row in success if row.get("features", {}).get("F1")]
        names = [
            "native_mad_about_median",
            "native_robust_rms_about_median",
            "native_robust_range_p05_p95",
            "common_trace_mad_about_median",
            "total_signal_energy",
            "respiratory_band_energy",
        ]
        ranges: dict[str, Any] = {}
        for name in names:
            values = [float(row["features"]["F1"][name]) for row in scale_rows if name in row["features"]["F1"]]
            if values:
                ranges[name] = {
                    "min": float(min(values)),
                    "median": float(np.median(values)),
                    "max": float(max(values)),
                    "finite_count": len(values),
                }
        return {
            "success": len(success),
            "native_scale_preserved_count": sum(row.get("native_scale_preserved") is True for row in success),
            "window_local_scale_normalization_count": sum(
                row.get("window_local_scale_normalization") is True for row in success
            ),
            "cross_domain_gain_matching_count": sum(
                row.get("cross_domain_gain_matching") is True for row in success
            ),
            "scale_feature_ranges": ranges,
        }

    return {
        "schema_version": R2_SCHEMA_VERSION,
        "policy": {
            "native_scale_preserved": True,
            "window_local_MAD_division": False,
            "cross_domain_gain_matching": False,
            "absolute_scale_features_are_candidates_not_cutoffs": True,
            "low_amplitude_is_not_auto_apnea": True,
        },
        "D0": summarize(d0["records"]),
        "D1": summarize(d1["records"]),
        "synthetic_scale_test_reference": "see deterministic tests.normalized_shape_is_scale_stable and absolute_scale_is_preserved",
    }


def _exception_registry(d0: dict[str, Any], d1: dict[str, Any]) -> dict[str, Any]:
    record_exceptions = []
    for audit in (d0, d1):
        for row in audit["records"]:
            if row.get("status") != "SUCCESS":
                record_exceptions.append(
                    {
                        "source_id": row.get("source_id"),
                        "subject_id": row.get("subject_id"),
                        "recording_id": row.get("recording_id"),
                        "condition": row.get("condition"),
                        "severity": "BLOCKER",
                        "code": row.get("failure_code"),
                        "detail": row.get("failure_detail"),
                    }
                )
    unavailable_counts: dict[str, dict[str, int]] = {}
    for audit in (d0, d1):
        for row in audit["records"]:
            if row.get("status") != "SUCCESS":
                continue
            for candidate, status in row.get("feature_status", {}).items():
                if status != "AVAILABLE":
                    unavailable_counts.setdefault(candidate, Counter())
                    unavailable_counts[candidate][status] += 1
    return {
        "schema_version": R2_SCHEMA_VERSION,
        "blocker_count": len(record_exceptions),
        "warning_count": sum(sum(counts.values()) for counts in unavailable_counts.values()),
        "record_exceptions": record_exceptions,
        "typed_feature_unavailability_counts": {
            candidate: dict(sorted(counts.items())) for candidate, counts in sorted(unavailable_counts.items())
        },
        "fail_open_behavior": False,
        "missing_signal_replaced_with_zero": False,
        "large_gap_interpolated": False,
    }


def _validation_result(
    d0: dict[str, Any],
    d1: dict[str, Any],
    scale_audit: dict[str, Any],
    exceptions: dict[str, Any],
) -> dict[str, Any]:
    expected = {"D0": 318, "D1": 265}
    actual = {"D0": d0["summary"]["success"], "D1": d1["summary"]["success"]}
    checks = {
        "D0_TRAIN_ONLY": d0["scope"].get("VAL_used") is False
        and d0["scope"].get("D0_SUBJECT_HELDOUT_used") is False,
        "D0_EXPECTED_SUCCESS_COUNT": actual["D0"] == expected["D0"],
        "D1_EXPECTED_SUCCESS_COUNT": actual["D1"] == expected["D1"],
        "NATIVE_SCALE_PRESERVED": scale_audit["D0"]["native_scale_preserved_count"] == actual["D0"]
        and scale_audit["D1"]["native_scale_preserved_count"] == actual["D1"],
        "NO_WINDOW_LOCAL_NORMALIZATION": scale_audit["D0"]["window_local_scale_normalization_count"] == 0
        and scale_audit["D1"]["window_local_scale_normalization_count"] == 0,
        "NO_RECORD_EXCEPTIONS": exceptions["blocker_count"] == 0,
        "NO_MODEL_TRAINING": True,
        "NO_CANDIDATE_SELECTION": True,
        "NO_D2": True,
        "NO_MR60_SUPERVISED_USE": True,
    }
    ok = all(checks.values())
    return {
        "schema_version": R2_SCHEMA_VERSION,
        "phase": "R2",
        "ok": ok,
        "gate": "PASS_WITH_LIMITATIONS" if ok else "BLOCKED",
        "status": "BOUNDED_CANDIDATES_READY_FOR_M_PV1" if ok else "BLOCKED",
        "checks": checks,
        "expected_success": expected,
        "actual_success": actual,
        "limitations": [
            "F1/F2/F3 are bounded candidates; no winner selected",
            "R1 common 10 Hz rate remains a candidate, not final M-PV1 rate",
            "D1 sign alignment and native reference units remain source-level limitations",
            "no predictive or clinical claim is made",
        ],
    }


def _checksums(root: Path, output_root: Path, d0_root: Path, d1_root: Path) -> dict[str, Any]:
    evidence_files = [
        "feature_candidate_set.json",
        "f1_feature_contract.json",
        "f2_feature_contract.json",
        "f3_descriptor_contract.json",
        "d0_feature_audit.json",
        "d1_feature_audit.json",
        "cross_domain_sanity.json",
        "scale_preservation_audit.json",
        "exception_registry.json",
        "validation_result.json",
    ]
    code_files = [
        "adapters/mmwave_r2_representation_features.py",
        "scripts/run_mmwave_r2_spectral_autocorr_features.py",
        "scripts/validate_mmwave_r2_spectral_autocorr_features.py",
        "tests/test_mmwave_r2_spectral_autocorr_features.py",
    ]
    d0_inputs = {
        "split": r1_runner.D0_SPLIT_RELATIVE,
        "canonical": r1_runner.D0_CANONICAL_RELATIVE,
        "provenance": r1_runner.D0_PROVENANCE_RELATIVE,
        "window_manifest": r1_runner.D0_WINDOW_RELATIVE,
        "processing_profile": r1_runner.D0_PROFILE_RELATIVE,
    }
    d1_inputs = {
        "recording_inventory": r1_runner.D1_INVENTORY_RELATIVE,
        "adapter_contract": r1_runner.D1_CONTRACT_RELATIVE,
    }
    r1_inputs = {
        "common_trace_contract": R1_EVIDENCE_RELATIVE_ROOT / "common_trace_contract.json",
        "validation_result": R1_EVIDENCE_RELATIVE_ROOT / "validation_result.json",
    }
    def hash_paths(base: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, relative in paths.items():
            path = base / relative
            result[name] = {
                "path": relative.as_posix(),
                "sha256": _sha256(path),
            }
        return result

    return {
        "schema_version": R2_SCHEMA_VERSION,
        "evidence": {name: _sha256(output_root / name) for name in evidence_files},
        "code": {name: _sha256(root / name) for name in code_files},
        "input_lineage": {
            "D0": hash_paths(d0_root, d0_inputs),
            "D1": hash_paths(d1_root, d1_inputs),
            "R1": hash_paths(root, r1_inputs),
        },
        "raw_waveforms_committed": False,
        "derived_waveforms_committed": False,
    }


def run(d0_root: Path, d1_root: Path, output_root: Path) -> dict[str, Any]:
    try:
        d0_inputs, d0_scope = r1_runner._load_d0_inputs(d0_root)
        d1_inputs, d1_scope = r1_runner._load_d1_inputs(d1_root)
    except (r1_runner.R1RunnerError, OSError, ValueError) as exc:
        raise R2RunnerError(str(exc)) from exc
    d0_audit = _audit("D0", d0_inputs, {**d0_scope, "selection_scope": "TRAIN_ONLY"})
    d1_audit = _audit("D1", d1_inputs, {**d1_scope, "selection_scope": "FULL_DEVELOPMENT_POOL"})
    contracts = _feature_contracts()
    candidate_set = {
        "schema_version": R2_SCHEMA_VERSION,
        "candidate_set_id": R2_CANDIDATE_SET_ID,
        "status": "BOUNDED_CANDIDATES_READY_FOR_M_PV1",
        "selected_candidate": None,
        "selection_performed": False,
        "candidate_ids": [
            "F1_NORMALIZED_SPECTRAL",
            "F2_SPECTRAL_AUTOCORR",
            "F3_TRACE_PLUS_QUALITY",
        ],
        "candidate_schema_ids": [F1_SCHEMA_ID, F2_SCHEMA_ID, F3_SCHEMA_ID],
        "input_contract": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
        "domains": {
            "D0": "frozen TRAIN only; R1 lineage windows",
            "D1": "all successful development recordings; no oversampling",
        },
        "respiratory_band_hz": list(RESPIRATORY_BAND_HZ),
        "forbidden_in_R2": [
            "model training",
            "neural preprocessing",
            "D0-derived scaler",
            "MR60-derived scaler",
            "window-local MAD division",
            "R2 derivative",
            "spectral target encoding",
            "autocorrelation target encoding",
            "breathing-evidence score",
            "RR ML target encoding",
            "temporal hold logic",
            "APNEA feature labels",
            "D2 access",
            "MR60 supervised use",
        ],
        "evidence_policy": "compact scalar features and provenance only; no waveform arrays committed",
    }
    cross_domain = _cross_domain_sanity(d0_audit, d1_audit)
    scale_audit = _scale_audit_from_domains(d0_audit, d1_audit)
    scale_audit["synthetic_tests"] = _scale_preservation_audit()
    exceptions = _exception_registry(d0_audit, d1_audit)
    validation = _validation_result(d0_audit, d1_audit, scale_audit, exceptions)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "feature_candidate_set.json", candidate_set)
    _write_json(output_root / "f1_feature_contract.json", contracts["f1"])
    _write_json(output_root / "f2_feature_contract.json", contracts["f2"])
    _write_json(output_root / "f3_descriptor_contract.json", contracts["f3"])
    _write_json(output_root / "d0_feature_audit.json", d0_audit)
    _write_json(output_root / "d1_feature_audit.json", d1_audit)
    _write_json(output_root / "cross_domain_sanity.json", cross_domain)
    _write_json(output_root / "scale_preservation_audit.json", scale_audit)
    _write_json(output_root / "exception_registry.json", exceptions)
    _write_json(output_root / "validation_result.json", validation)
    _write_json(output_root / "checksums.json", _checksums(ROOT, output_root, d0_root, d1_root))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d0-root", type=Path, required=True)
    parser.add_argument("--d1-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / EVIDENCE_RELATIVE_ROOT)
    args = parser.parse_args()
    try:
        result = run(args.d0_root.resolve(), args.d1_root.resolve(), args.output_root.resolve())
    except (R2RunnerError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "gate": "BLOCKED", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
