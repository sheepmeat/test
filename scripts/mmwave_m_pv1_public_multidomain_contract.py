#!/usr/bin/env python3
"""Generate the SafeNest mmWave V2 M-PV1 contract freeze.

M-PV1 is deliberately a data/contract phase.  This module never imports a
training framework, scores a model, opens D2, or writes waveform arrays.  It
consumes the accepted D0/D1/R1/R2/R3/Q2/I1 evidence, optionally reads the
ignored canonical D1 archive, and emits compact deterministic JSON manifests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import resample_poly, welch
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EVIDENCE_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract")
CONFIG_REL = Path("config/mmwave/m_pv1_public_multidomain_contract.json")
D1_PAYLOAD_REL = Path("datasets/raw_archives/external_datasets/d1_2417ghz/datasets_scidata_vsmdb.zip")
D1_EXTRACTED_REL = Path("datasets/raw_archives/external_datasets/d1_2417ghz/extracted")

CONTRACT_ID = "MMWAVE_V2_M_PV1_PUBLIC_MULTIDOMAIN_CONTRACT_V1"
INPUT_ID = "MMWAVE_V2_M_PV1_MODEL_INPUT_CONTRACT_V1"
TARGET_ID = "MMWAVE_V2_M_PV1_TARGET_MAPPING_PROFILE_V1"
TEMPORAL_ID = "MMWAVE_V2_M_PV1_TEMPORAL_CONTEXT_CONTRACT_V1"
BALANCING_ID = "MMWAVE_V2_M_PV1_SOURCE_BALANCING_CONTRACT_V1"
EXAMPLE_ID = "MMWAVE_V2_M_PV1_M_PV2_EXAMPLE_MANIFEST_V1"
D1_SPLIT_ID = "MMWAVE_V2_M_PV1_D1_DEV_SUBJECT_SPLIT_V1"

D1_EXPECTED_BYTES = 583_572_264
D1_EXPECTED_MD5 = "801c13ae6daef54584ee4ba8fbabed19"
D1_EXPECTED_SHA256 = "3869fb70a3dda0d810d97594399789e76d9c9e59627515c20170b83e3d915836"
D1_DOWNLOAD_URL = "https://ndownloader.figshare.com/files/17357702"
D1_DOI = "10.6084/m9.figshare.9691544.v1"
D1_SOURCE_ADAPTER = "D1_NATIVE_SIXPORT_PHASE_DISPLACEMENT_V1"
D1_REFERENCE_METHOD = "D1_RESPIRATION_WELCH_PERIODICITY_V1"

# Corrective M-PV1 target binding.  Every model-ready context has one causal
# breathing target at the final fixed interval of that context.  RR remains a
# separate full-context reference task (see ``_alignment_metadata`` below).
MODEL_CONTEXT_DURATION_S = 30.0
BREATHING_TARGET_DURATION_S = 5.0
BREATHING_TARGET_ANCHOR = "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT"
RR_REFERENCE_ANCHOR = "FULL_CAUSAL_CONTEXT_REFERENCE_INTERVAL"
TEMPORAL_HOLD_LEARNING_BOUNDARY = "DETERMINISTIC_POST_BREATHING_COMPOSITION_ONLY"

PROFILE_TASK_COMPATIBILITY = {
    "PROFILE_A_FEATURE_F2_V1": {
        "breathing_evidence": False,
        "rr": True,
        "quality": True,
        "temporal_hold": False,
        "reason": "global 30 s F2 vector does not preserve the final 5 s target location",
    },
    "PROFILE_B_TRACE_F3_R1_V1": {
        "breathing_evidence": True,
        "rr": True,
        "quality": True,
        "temporal_hold": False,
        "reason": "ordered 10 Hz trace and mask preserve the fixed final target interval",
    },
    "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1": {
        "breathing_evidence": True,
        "rr": True,
        "quality": True,
        "temporal_hold": False,
        "reason": "trace branch preserves target location; F2 remains auxiliary",
    },
}

D0_R3_DIR = Path("datasets/mmwave/manifests/M-PV0_R3_breathing_rr_temporal_hold")
D0_SPLIT_PATH = Path("datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit/v2_subject_split.json")
D0_A6_PATH = Path("datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl")
D1_INV_PATH = Path("datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/recording_inventory.json")
D1_ACQ_PATH = Path("datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/source_acquisition.json")

UPSTREAM = {
    "M-PV0": Path("datasets/mmwave/manifests/M-PV0_public_multidomain_registry/validation_result.json"),
    "D0": Path("datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit/validation_result.json"),
    "D1": Path("datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/validation_result.json"),
    "R1": Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace/validation_result.json"),
    "R2": Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features/validation_result.json"),
    "R3": Path("datasets/mmwave/manifests/M-PV0_R3_breathing_rr_temporal_hold/validation_result.json"),
    "Q2": Path("datasets/mmwave/manifests/M-PV0_Q2_input_unavailable_contract/validation_result.json"),
    "I1": Path("datasets/mmwave/manifests/M-PV0_I1_runtime_io_contract/validation_result.json"),
}

F2_FEATURES = [
    "spectral_shape_fraction_0p10_0p25_hz",
    "spectral_shape_fraction_0p25_0p40_hz",
    "spectral_shape_fraction_0p40_0p55_hz",
    "spectral_shape_fraction_0p55_0p70_hz",
    "spectral_shape_centroid_hz",
    "spectral_shape_peak_frequency_hz",
    "spectral_shape_peak_fraction",
    "spectral_shape_entropy_normalized",
    "native_mad_about_median",
    "native_robust_rms_about_median",
    "native_robust_range_p05_p95",
    "native_peak_to_peak",
    "common_trace_mad_about_median",
    "common_trace_robust_rms_about_median",
    "total_signal_energy",
    "total_signal_mean_square",
    "log_total_signal_energy",
    "respiratory_band_power",
    "respiratory_band_energy",
    "log_respiratory_band_energy",
    "autocorr_periodicity_peak_strength",
    "autocorr_periodicity_peak_lag_s",
    "autocorr_periodicity_peak_frequency_hz",
    "autocorr_periodicity_lag_mean",
    "autocorr_abs_entropy_normalized",
]
F3_QUALITY = [
    "trace_sample_count",
    "trace_duration_s",
    "trace_mad_about_median",
    "trace_robust_rms_about_median",
    "trace_robust_range_p05_p95",
    "trace_mean_square",
    "trace_is_exact_flat",
    "valid_sample_fraction",
    "source_quality_flag_count",
]
SCALE_DESCRIPTORS = [
    "native_mad_about_median",
    "native_robust_rms_about_median",
    "native_robust_range_p05_p95",
    "native_peak_to_peak",
    "common_trace_mad_about_median",
    "common_trace_robust_rms_about_median",
    "total_signal_energy",
    "total_signal_mean_square",
    "log_total_signal_energy",
    "respiratory_band_energy",
    "respiratory_band_power",
    "log_respiratory_band_energy",
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stable_bytes(value))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_breathing_interval(context_start_s: float, context_end_s: float) -> Tuple[float, float]:
    """Return the only permitted breathing target interval for a context."""
    context_start_s = float(context_start_s)
    context_end_s = float(context_end_s)
    if context_end_s - context_start_s < BREATHING_TARGET_DURATION_S:
        raise ValueError("context is shorter than the fixed breathing target")
    return (
        float(context_end_s - BREATHING_TARGET_DURATION_S),
        context_end_s,
    )


def _target_record(
    *,
    model_input_id: str,
    task: str,
    state: str,
    target_start_s: float,
    target_end_s: float,
    target_anchor: str,
    supervision_eligible: bool,
    provenance: Mapping[str, Any],
    reference_interval_s: Optional[Sequence[float]] = None,
    representation_profile_compatibility: Optional[Mapping[str, Any]] = None,
    learning_boundary: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an explicit task target so interval semantics cannot be hidden."""
    record: Dict[str, Any] = {
        "target_id": f"{model_input_id}__{task.upper()}",
        "model_input_id": model_input_id,
        "target_task": task,
        "target_state": state,
        "target_start_s": float(target_start_s),
        "target_end_s": float(target_end_s),
        "target_duration_s": float(target_end_s - target_start_s),
        "target_anchor": target_anchor,
        "causal_context": True,
        "supervision_eligible": bool(supervision_eligible),
        "provenance": dict(provenance),
    }
    if reference_interval_s is not None:
        record["reference_interval_s"] = [float(reference_interval_s[0]), float(reference_interval_s[1])]
        record["reference_duration_s"] = float(reference_interval_s[1] - reference_interval_s[0])
    if representation_profile_compatibility is not None:
        record["representation_profile_compatibility"] = dict(representation_profile_compatibility)
    if learning_boundary is not None:
        record["learning_boundary"] = learning_boundary
    return record


def _alignment_metadata(
    *,
    model_input_id: str,
    context_start_s: float,
    context_end_s: float,
    breathing_state: str,
    breathing_target_status: str,
    breathing_supervision_eligible: bool,
    rr_target_status: str,
    rr_bpm: Optional[float],
    rr_validity: str,
    rr_unavailable_reason: Optional[str],
    temporal_state: str,
    quality_status: str,
    quality_supervision_eligible: bool,
    provenance: Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach the frozen causal context/target contract to one unique input."""
    context_start_s = float(context_start_s)
    context_end_s = float(context_end_s)
    target_start_s, target_end_s = fixed_breathing_interval(context_start_s, context_end_s)
    rr_start_s, rr_end_s = context_start_s, context_end_s
    task_compatibility = {
        profile: dict(values) for profile, values in PROFILE_TASK_COMPATIBILITY.items()
    }
    target_records = [
        _target_record(
            model_input_id=model_input_id,
            task="breathing_evidence",
            state=breathing_state,
            target_start_s=target_start_s,
            target_end_s=target_end_s,
            target_anchor=BREATHING_TARGET_ANCHOR,
            supervision_eligible=breathing_supervision_eligible,
            provenance=provenance,
            reference_interval_s=(context_start_s, context_end_s),
            representation_profile_compatibility={
                profile: values["breathing_evidence"]
                for profile, values in task_compatibility.items()
            },
        ),
        _target_record(
            model_input_id=model_input_id,
            task="rr",
            state="AVAILABLE" if rr_target_status == "AVAILABLE" and rr_bpm is not None else "TARGET_UNAVAILABLE",
            target_start_s=rr_start_s,
            target_end_s=rr_end_s,
            target_anchor=RR_REFERENCE_ANCHOR,
            supervision_eligible=rr_target_status == "AVAILABLE" and rr_bpm is not None,
            provenance=provenance,
            reference_interval_s=(rr_start_s, rr_end_s),
            representation_profile_compatibility={
                profile: values["rr"] for profile, values in task_compatibility.items()
            },
        ),
        _target_record(
            model_input_id=model_input_id,
            task="temporal_hold",
            state=temporal_state,
            target_start_s=target_start_s,
            target_end_s=target_end_s,
            target_anchor=BREATHING_TARGET_ANCHOR,
            supervision_eligible=False,
            provenance=provenance,
            reference_interval_s=(context_start_s, context_end_s),
            representation_profile_compatibility={
                profile: values["temporal_hold"]
                for profile, values in task_compatibility.items()
            },
            learning_boundary=TEMPORAL_HOLD_LEARNING_BOUNDARY,
        ),
        _target_record(
            model_input_id=model_input_id,
            task="quality",
            state=quality_status,
            target_start_s=rr_start_s,
            target_end_s=rr_end_s,
            target_anchor=RR_REFERENCE_ANCHOR,
            supervision_eligible=quality_supervision_eligible,
            provenance=provenance,
            reference_interval_s=(rr_start_s, rr_end_s),
            representation_profile_compatibility={
                profile: values["quality"] for profile, values in task_compatibility.items()
            },
        ),
    ]
    return {
        "model_input_id": model_input_id,
        "model_ready": True,
        "model_input_tensor_status": "VALID_DECLARED_REGENERABLE_FROM_ACCEPTED_CONTRACTS",
        "model_input_tensor_contract": INPUT_ID,
        "context_start_s": context_start_s,
        "context_end_s": context_end_s,
        "context_duration_s": float(context_end_s - context_start_s),
        "model_context_duration_s": float(context_end_s - context_start_s),
        "causal_context": True,
        "target_task": "breathing_evidence",
        "target_start_s": target_start_s,
        "target_end_s": target_end_s,
        "target_duration_s": BREATHING_TARGET_DURATION_S,
        "target_anchor": BREATHING_TARGET_ANCHOR,
        "target_interval_start_s": target_start_s,
        "target_interval_end_s": target_end_s,
        "target_interval_duration_s": BREATHING_TARGET_DURATION_S,
        "rr_reference_interval_start_s": rr_start_s,
        "rr_reference_interval_end_s": rr_end_s,
        "rr_reference_interval_duration_s": float(rr_end_s - rr_start_s),
        "rr_reference_interval_anchor": RR_REFERENCE_ANCHOR,
        "representation_profile_compatibility": task_compatibility,
        "supervision_eligibility": {
            "breathing_evidence": bool(breathing_supervision_eligible),
            "rr": bool(rr_target_status == "AVAILABLE" and rr_bpm is not None),
            "temporal_hold": False,
            "quality": bool(quality_supervision_eligible),
        },
        "target_records": target_records,
    }


def git_output(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def upstream_audit() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    details: Dict[str, Any] = {}
    for name, path in UPSTREAM.items():
        present = (ROOT / path).is_file()
        document = load_json(ROOT / path) if present else {}
        ok = bool(document.get("ok")) and document.get("gate") in {"PASS", "PASS_WITH_LIMITATIONS"}
        checks[name + "_ACCEPTED"] = "YES" if ok else "NO"
        checks[name + "_EVIDENCE_PRESENT"] = "YES" if present else "NO"
        details[name] = {
            "validation_path": rel(ROOT / path) if present else path.as_posix(),
            "ok": bool(document.get("ok")),
            "gate": document.get("gate"),
            "schema_version": document.get("schema_version"),
        }
    r1_contract = ROOT / "datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace/common_trace_contract.json"
    r2_contract = ROOT / "datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features/feature_candidate_set.json"
    checks["R1_CONTRACT_PRESENT"] = "YES" if r1_contract.is_file() else "NO"
    checks["R2_CONTRACT_PRESENT"] = "YES" if r2_contract.is_file() else "NO"
    d3 = ROOT / "adapters/mmwave_d3_raw_adc_adapter.py"
    checks["D3_STATUS"] = "INCLUDED" if d3.is_file() else "NOT_INCLUDED_NON_BLOCKING"
    checks["DIRECT_PREREQUISITES_ACCEPTED"] = "YES" if all(
        checks.get(name + "_ACCEPTED") == "YES" for name in ("D0", "D1", "R3", "Q2", "I1")
    ) and checks["R1_CONTRACT_PRESENT"] == "YES" and checks["R2_CONTRACT_PRESENT"] == "YES" else "NO"
    checks["I2_DIRECT_PREREQUISITE"] = "NO"
    checks["I3_ANCESTOR_REQUIRED"] = "NO"
    return {
        "contract_id": CONTRACT_ID,
        "base_ref": "origin/main",
        "base_commit": git_output("rev-parse", "origin/main"),
        "checks": checks,
        "details": details,
        "m_pv0_registry_id": "MMWAVE_M_PV0_PUBLIC_MULTIDOMAIN_REGISTRY_V1",
        "d2_not_reconstructed": True,
        "m_pv1_scope": "CONTRACT_FREEZE_ONLY_NO_TRAINING_NO_SELECTION",
    }


def d1_subject_split(subjects: Sequence[str]) -> Dict[str, Any]:
    namespace = "MMWAVE_V2_M_PV1_D1_DEV_SPLIT"
    seed = 20260823
    ranked = sorted(
        (sha256_bytes((namespace + ":" + str(seed) + ":" + subject).encode("utf-8")), subject)
        for subject in sorted(set(subjects))
    )
    dev_train = sorted(subject for _, subject in ranked[:8])
    dev_val = sorted(subject for _, subject in ranked[8:])
    assignment = {
        subject: ("D1_DEV_TRAIN" if subject in dev_train else "D1_DEV_VAL")
        for subject in sorted(set(subjects))
    }
    return {
        "split_identity": D1_SPLIT_ID,
        "split_unit": "SUBJECT",
        "namespace": namespace,
        "seed": seed,
        "algorithm": "SHA256(namespace:seed:subject_id) ascending; first 8 DEV_TRAIN; remaining 3 DEV_VAL",
        "counts": {"D1_DEV_TRAIN": len(dev_train), "D1_DEV_VAL": len(dev_val)},
        "subject_ids": {"D1_DEV_TRAIN": dev_train, "D1_DEV_VAL": dev_val},
        "assignment": assignment,
        "recording_level_leakage": "NO",
        "performance_selection": "FORBIDDEN",
        "final_test_created": False,
    }


def safe_extract(payload: Path, extracted: Path) -> None:
    extracted.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(payload) as archive:
        for member in archive.infolist():
            target = (extracted / member.filename).resolve()
            if not str(target).startswith(str(extracted.resolve()) + os.sep):
                raise RuntimeError("D1 archive contains a path traversal member")
        archive.extractall(extracted)


def _stats(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    median = float(np.median(values))
    return {
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "median": median,
        "mad_about_median": float(np.median(np.abs(values - median))),
        "robust_rms_about_median": float(np.sqrt(np.mean((values - median) ** 2))),
        "robust_range_p05_p95": float(np.percentile(values, 95) - np.percentile(values, 5)),
        "peak_to_peak": float(np.max(values) - np.min(values)),
    }


def _reference_window(reference: np.ndarray, fs: float) -> Dict[str, Any]:
    """Analyze one 30 s, 10 Hz reference window using fixed engineering rules."""
    target_fs = 10.0
    if not math.isclose(fs, 500.0) and not math.isclose(fs, 2000.0):
        return {"status": "TARGET_UNAVAILABLE", "reason": "UNSUPPORTED_SOURCE_FS"}
    if reference.size < int(round(30.0 * fs)):
        return {"status": "TARGET_UNAVAILABLE", "reason": "SHORTER_THAN_30S_CONTEXT"}
    # The D1 adapter already guarantees finite required channels.  This guard
    # makes the materializer fail closed if a future canonical payload changes.
    if not np.all(np.isfinite(reference)):
        return {"status": "TARGET_UNAVAILABLE", "reason": "NONFINITE_REFERENCE"}
    down = int(round(fs / target_fs))
    common = resample_poly(reference.astype(np.float64), 1, down, window=("kaiser", 8.6))
    sample_count = 300
    if common.size < sample_count:
        return {"status": "TARGET_UNAVAILABLE", "reason": "SHORT_AFTER_ANTI_ALIAS_RESAMPLE"}
    trace = np.asarray(common[:sample_count], dtype=np.float64)
    trace = trace - np.median(trace)
    nperseg = min(256, trace.size)
    noverlap = int(math.floor(0.5 * nperseg))
    frequency, power = welch(
        trace,
        fs=target_fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        nfft=nperseg,
        detrend="constant",
        scaling="density",
    )
    band = (frequency >= 0.1) & (frequency <= 0.7)
    if not bool(np.any(band)):
        return {"status": "AMBIGUOUS", "reason": "NO_RESPIRATORY_BAND_BINS", "sample_count": sample_count}
    band_power = float(np.sum(power[band]) * (frequency[1] - frequency[0]))
    band_freq = frequency[band]
    band_psd = power[band]
    peak_index = int(np.argmax(band_psd))
    peak_frequency = float(band_freq[peak_index])
    peak_power = float(band_psd[peak_index])
    fraction = peak_power / float(np.sum(band_psd)) if float(np.sum(band_psd)) > 0.0 else 0.0
    centered = trace - float(np.mean(trace))
    energy = float(np.dot(centered, centered))
    if energy <= 0.0 or not math.isfinite(energy):
        autocorr_strength = 0.0
    else:
        correlation = np.correlate(centered, centered, mode="full")[centered.size - 1 :]
        correlation = correlation / float(correlation[0])
        lag_min = max(1, int(math.ceil(target_fs / 0.7)))
        lag_max = min(correlation.size - 1, int(math.floor(target_fs / 0.1)))
        autocorr_strength = float(np.max(correlation[lag_min : lag_max + 1])) if lag_max >= lag_min else 0.0
    # These are fixed reference-side engineering guards, never learned from
    # radar output or selected by a model metric.  Failure is AMBIGUOUS, not
    # physiological ABSENT, because a weak reference is not proof of no breath.
    periodic = (
        math.isfinite(band_power)
        and band_power > np.finfo(np.float64).tiny
        and fraction >= 0.10
        and autocorr_strength >= 0.10
        and 0.1 <= peak_frequency <= 0.7
    )
    result: Dict[str, Any] = {
        "analysis_sampling_rate_hz": target_fs,
        "analysis_duration_s": 30.0,
        "resampling": {
            "method": "scipy.signal.resample_poly",
            "window": ["kaiser", 8.6],
            "down": down,
            "up": 1,
            "anti_aliasing": True,
        },
        "reference_method": D1_REFERENCE_METHOD,
        "reference_band_hz": [0.1, 0.7],
        "minimum_duration_s": 30.0,
        "minimum_cycles_at_lower_band": 3.0,
        "peak_frequency_hz": peak_frequency,
        "rr_bpm": float(peak_frequency * 60.0),
        "band_power": band_power,
        "peak_fraction_of_band_power": fraction,
        "autocorr_periodicity_peak_strength": autocorr_strength,
        "sample_count": sample_count,
        "missing_or_nonfinite_behavior": "TARGET_UNAVAILABLE; no interpolation",
        "source_apnea_term_used_as_target": False,
    }
    if periodic:
        result.update({
            "status": "PRESENT",
            "breathing_target_status": "AVAILABLE",
            "rr_target_status": "AVAILABLE",
            "rr_validity": "VALID_CONTINUOUS_REFERENCE_RR",
            "rr_unavailable_reason": None,
        })
    else:
        result.update({
            "status": "AMBIGUOUS",
            "breathing_target_status": "AMBIGUOUS",
            "rr_target_status": "TARGET_UNAVAILABLE",
            "rr_validity": "UNAVAILABLE",
            "rr_bpm": None,
            "rr_unavailable_reason": "REFERENCE_PERIODICITY_AMBIGUOUS",
        })
    return result


def d1_materialize() -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    payload = ROOT / D1_PAYLOAD_REL
    extracted = ROOT / D1_EXTRACTED_REL
    acquisition = load_json(ROOT / D1_ACQ_PATH)
    inventory = load_json(ROOT / D1_INV_PATH)
    if not payload.is_file():
        return (
            {
                "status": "NOT_MATERIALIZED_CANONICAL_PAYLOAD_ABSENT",
                "payload_source": D1_DOWNLOAD_URL,
                "checksum_verified": False,
                "waveforms_accessed": False,
                "raw_waveforms_committed": False,
                "recording_count": inventory.get("recording_count", 0),
                "limitations": ["Canonical D1 payload is absent locally; no mirror/substitute was used."],
            },
            [],
            {"subject_ids": sorted({r.get("subject_id") for r in inventory.get("recordings", []) if r.get("subject_id")})},
        )
    size = int(payload.stat().st_size)
    md5 = md5_file(payload)
    sha = sha256_file(payload)
    checksum_ok = size == D1_EXPECTED_BYTES and md5 == D1_EXPECTED_MD5 and sha == D1_EXPECTED_SHA256
    if not checksum_ok:
        raise RuntimeError("D1 canonical payload checksum does not match the frozen M-PV0 identity")
    if not (extracted / "datasets").is_dir() or not (extracted / "overview_and_rating.xlsx").is_file():
        safe_extract(payload, extracted)
    from adapters.mmwave_d1_2417ghz_adapter import adapt_mat_file, D1AdapterError

    inventory_by_source = {row.get("source_file"): row for row in inventory.get("recordings", [])}
    mat_paths = sorted((extracted / "datasets").rglob("*.mat"), key=lambda p: p.as_posix())
    if len(mat_paths) != 265:
        raise RuntimeError("D1 extracted canonical recording count is not 265")
    split = d1_subject_split([row["subject_id"] for row in inventory.get("recordings", [])])
    condition_by_split: Dict[str, Counter] = defaultdict(Counter)
    for inventory_row in inventory.get("recordings", []):
        assigned = split["assignment"].get(inventory_row.get("subject_id"), "UNASSIGNED")
        condition = inventory_row.get("condition_metadata", {}).get("source_scenario_normalized", "UNVERIFIED")
        condition_by_split[assigned][condition] += 1
    split["recording_counts_by_split"] = {
        name: int(sum(counter.values())) for name, counter in sorted(condition_by_split.items())
    }
    split["condition_coverage_by_split"] = {
        name: dict(sorted(counter.items())) for name, counter in sorted(condition_by_split.items())
    }
    rows: List[Dict[str, Any]] = []
    recording_status = Counter()
    for path in mat_paths:
        source_file = rel(path)
        inventory_row = inventory_by_source.get(source_file)
        if inventory_row is None:
            raise RuntimeError("D1 extracted path is absent from the accepted recording inventory: " + source_file)
        try:
            adapted = adapt_mat_file(path, condition="SOURCE_METADATA_ONLY", condition_source="D1_M_PV1", source_file=source_file)
        except D1AdapterError as exc:
            recording_status["BLOCKED"] += 1
            rows.append({
                "example_id": "D1_BLOCKED_" + inventory_row["recording_id"],
                "source_id": "D1",
                "recording_id": inventory_row["recording_id"],
                "subject_id": inventory_row["subject_id"],
                "split": split["assignment"].get(inventory_row["subject_id"], "UNASSIGNED"),
                "example_role": "REFERENCE_AUDIT_ONLY",
                "model_ready": False,
                "model_input_id": None,
                "model_context_duration_s": MODEL_CONTEXT_DURATION_S,
                "target_status": "TARGET_UNAVAILABLE",
                "breathing_supervision_eligible": False,
                "rr_supervision_eligible": False,
                "temporal_hold_supervision_eligible": False,
                "quality_supervision_eligible": False,
                "quality_status": "REFERENCE_AUDIT_ONLY",
                "unavailable_reason": "D1_ADAPTER_" + exc.code,
                "audit_only_reason": "D1_ADAPTER_BLOCKED_NO_MODEL_INPUT_TENSOR",
                "provenance": {"source_file": source_file, "adapter_id": D1_SOURCE_ADAPTER},
            })
            continue
        recording_status["SUCCESS"] += 1
        reference = adapted.respiration_reference_native
        fs = float(adapted.source_sampling_rate_hz)
        duration = float((reference.size - 1) / fs)
        context_count = max(0, int(math.floor(duration / 30.0)))
        if context_count == 0:
            rows.append({
                "example_id": "D1_REF_" + inventory_row["recording_id"] + "__SHORT",
                "source_id": "D1",
                "recording_id": inventory_row["recording_id"],
                "subject_id": inventory_row["subject_id"],
                "split": split["assignment"][inventory_row["subject_id"]],
                "example_role": "REFERENCE_AUDIT_ONLY",
                "model_ready": False,
                "model_input_id": None,
                "context_start_s": 0.0,
                "context_end_s": duration,
                "context_duration_s": duration,
                "model_context_duration_s": MODEL_CONTEXT_DURATION_S,
                "breathing_target_status": "TARGET_UNAVAILABLE",
                "breathing_reference_state": "TARGET_UNAVAILABLE",
                "rr_target_status": "TARGET_UNAVAILABLE",
                "rr_bpm": None,
                "temporal_hold_target_status": "TARGET_UNAVAILABLE",
                "breathing_supervision_eligible": False,
                "rr_supervision_eligible": False,
                "temporal_hold_supervision_eligible": False,
                "quality_supervision_eligible": False,
                "quality_status": "CLEAN_REFERENCE_ONLY",
                "unavailable_reason": "SHORTER_THAN_30S_CONTEXT",
                "audit_only_reason": "SHORTER_THAN_30S_CONTEXT_NO_PADDING",
                "provenance": {
                    "source_dataset": D1_DOI,
                    "source_id": "D1",
                    "subject_id": inventory_row["subject_id"],
                    "recording_id": inventory_row["recording_id"],
                    "source_file": source_file,
                    "adapter_id": D1_SOURCE_ADAPTER,
                    "reference_method": D1_REFERENCE_METHOD,
                    "native_sampling_rate_hz": fs,
                    "context_time_range_s": [0.0, duration],
                },
            })
            continue
        for index in range(context_count):
            start = float(index * MODEL_CONTEXT_DURATION_S)
            end = float(start + MODEL_CONTEXT_DURATION_S)
            sample_start = int(round(start * fs))
            sample_end = int(round(end * fs))
            result = _reference_window(reference[sample_start:sample_end], fs)
            status = result.get("status", "TARGET_UNAVAILABLE")
            model_input_id = "D1::" + inventory_row["recording_id"] + "__C" + str(index).zfill(3)
            provenance = {
                "source_dataset": D1_DOI,
                "dataset_version": "figshare_v1",
                "source_id": "D1",
                "subject_id": inventory_row["subject_id"],
                "recording_id": inventory_row["recording_id"],
                "source_file": source_file,
                "adapter_id": D1_SOURCE_ADAPTER,
                "reference_channel": "respiration",
                "reference_method": D1_REFERENCE_METHOD,
                "native_sampling_rate_hz": fs,
                "context_time_range_s": [start, end],
                "resampled_model_rate_hz": 10.0,
                "target_anchor": BREATHING_TARGET_ANCHOR,
            }
            aligned = _alignment_metadata(
                model_input_id=model_input_id,
                context_start_s=start,
                context_end_s=end,
                breathing_state=("BREATHING_REFERENCE_PRESENT" if status == "PRESENT" else "BREATHING_REFERENCE_AMBIGUOUS"),
                breathing_target_status=result.get("breathing_target_status", "TARGET_UNAVAILABLE"),
                breathing_supervision_eligible=status == "PRESENT",
                rr_target_status=result.get("rr_target_status", "TARGET_UNAVAILABLE"),
                rr_bpm=result.get("rr_bpm"),
                rr_validity=result.get("rr_validity", "UNAVAILABLE"),
                rr_unavailable_reason=result.get("rr_unavailable_reason"),
                temporal_state="TARGET_UNAVAILABLE",
                quality_status="CLEAN",
                quality_supervision_eligible=True,
                provenance=provenance,
            )
            rows.append({
                "example_id": "D1_" + inventory_row["recording_id"] + "__C" + str(index).zfill(3),
                "source_id": "D1",
                "recording_id": inventory_row["recording_id"],
                "subject_id": inventory_row["subject_id"],
                "split": split["assignment"][inventory_row["subject_id"]],
                "example_role": "MODEL_READY_REFERENCE_WINDOW",
                "context_start_s": start,
                "context_end_s": end,
                "model_context_duration_s": MODEL_CONTEXT_DURATION_S,
                "breathing_target_status": result.get("breathing_target_status", "TARGET_UNAVAILABLE"),
                "breathing_reference_state": "BREATHING_REFERENCE_PRESENT" if status == "PRESENT" else "BREATHING_REFERENCE_AMBIGUOUS",
                "rr_target_status": result.get("rr_target_status", "TARGET_UNAVAILABLE"),
                "rr_bpm": result.get("rr_bpm"),
                "rr_validity": result.get("rr_validity", "UNAVAILABLE"),
                "rr_unavailable_reason": result.get("rr_unavailable_reason"),
                "temporal_hold_target_status": "TARGET_UNAVAILABLE",
                "temporal_hold_unavailable_reason": "D1_REFERENCE_BOUNDARY_NOT_MATERIALIZED",
                "breathing_supervision_eligible": status == "PRESENT",
                "rr_supervision_eligible": status == "PRESENT" and result.get("rr_target_status") == "AVAILABLE",
                "temporal_hold_supervision_eligible": False,
                "quality_supervision_eligible": True,
                "quality_status": "CLEAN",
                "reference_analysis": result,
                "temporal_hold_learning_boundary": TEMPORAL_HOLD_LEARNING_BOUNDARY,
                "provenance": provenance,
                **aligned,
            })
    audit = {
        "status": "MATERIALIZED_COMPACT_REFERENCE_TARGETS",
        "payload_source": D1_DOWNLOAD_URL,
        "payload_doi": D1_DOI,
        "payload_path": rel(payload),
        "checksum_verified": checksum_ok,
        "payload_size_bytes": size,
        "payload_md5": md5,
        "payload_sha256": sha,
        "waveforms_accessed": True,
        "waveforms_persisted": False,
        "raw_waveforms_committed": False,
        "recording_count": 265,
        "adapted_recording_count": recording_status["SUCCESS"],
        "blocked_recording_count": recording_status["BLOCKED"],
        "model_ready_context_count": sum(r.get("example_role") == "MODEL_READY_REFERENCE_WINDOW" for r in rows),
        "short_recording_audit_only_count": sum(r.get("example_role") == "REFERENCE_AUDIT_ONLY" for r in rows),
        "reference_channel": "respiration",
        "reference_alignment": "same source sample index and per-recording Fs as radar_I/radar_Q",
        "native_rates_hz": [500.0, 2000.0],
        "common_rate_hz": 10.0,
        "reference_method": D1_REFERENCE_METHOD,
        "minimum_signal_duration_s": 30.0,
        "temporal_hold_supervision": "UNAVAILABLE",
        "source_apnea_term_used_as_target": False,
        "condition_labels_remain_provenance": True,
        "limitations": [
            "respiration native units remain unverified",
            "source payload has no per-sample timestamps; sample index/Fs is used",
            "D1 source protocol strings do not define SafeNest hold onset/offset",
            "reference-side weak periodicity is AMBIGUOUS, never physiological ABSENT",
        ],
    }
    return audit, rows, split


def d0_examples() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    r3_rows = load_jsonl(ROOT / D0_R3_DIR / "d0_target_rows.jsonl")
    a6 = {row["window_id"]: row for row in load_jsonl(ROOT / D0_A6_PATH)}
    examples: List[Dict[str, Any]] = []
    event_alignment_audit: List[Dict[str, Any]] = []
    event_count = 0
    short_event_count = 0
    corrected_absent_count = 0
    corrected_ambiguous_event_count = 0
    corrected_audit_only_count = 0
    for row in sorted(r3_rows, key=lambda item: item["window_id"]):
        window_id = row["window_id"]
        evidence = row["breathing_evidence"]
        rr = row["rr_target"]
        hold = row["temporal_hold"]
        context_start = float(row["reference_time_range_s"][0])
        context_end = float(row["reference_time_range_s"][1])
        target_start, target_end = fixed_breathing_interval(context_start, context_end)
        events = a6.get(window_id, {}).get("annotation_events_overlapping", [])
        full_target_events: List[Mapping[str, Any]] = []
        partial_target_events: List[Mapping[str, Any]] = []
        for event in events:
            event_count += 1
            event_start = float(event["event_start_seconds"])
            event_end = float(event["event_end_seconds"])
            overlap_start = max(event_start, target_start)
            overlap_end = min(event_end, target_end)
            target_overlap = max(0.0, overlap_end - overlap_start)
            old_context_overlap = max(0.0, min(event_end, context_end) - max(event_start, context_start))
            old_candidate = old_context_overlap >= BREATHING_TARGET_DURATION_S
            if old_context_overlap < BREATHING_TARGET_DURATION_S:
                short_event_count += 1
            fully_contains_target = event_start <= target_start and event_end >= target_end
            if fully_contains_target:
                full_target_events.append(event)
                decision = "ABSENT_SUPERVISION"
                reason = "FIXED_FINAL_TARGET_FULLY_INSIDE_AUTHORITATIVE_EVENT"
            elif target_overlap > 0.0:
                partial_target_events.append(event)
                decision = "AUDIT_ONLY_TARGET_UNAVAILABLE"
                reason = "TARGET_OVERLAPS_EVENT_BUT_IS_NOT_FULLY_INSIDE_FIXED_FINAL_INTERVAL"
            else:
                decision = "AUDIT_ONLY_TARGET_UNAVAILABLE"
                reason = "EVENT_DOES_NOT_REACH_FIXED_FINAL_INTERVAL"
            if decision != "ABSENT_SUPERVISION":
                corrected_audit_only_count += 1
            event_alignment_audit.append({
                "model_input_id": "D0::" + window_id,
                "window_id": window_id,
                "event_id": str(event["event_id"]),
                "authoritative_event_interval_s": [event_start, event_end],
                "fixed_target_interval_s": [target_start, target_end],
                "target_overlap_s": target_overlap,
                "old_event_relative_candidate": old_candidate,
                "decision": decision,
                "reason": reason,
                "model_input_tensor_status": "VALID_DECLARED_REGENERABLE_FROM_ACCEPTED_CONTRACTS",
            })

        if full_target_events:
            breathing_state = "BREATHING_REFERENCE_ABSENT"
            breathing_target_status = "AVAILABLE"
            breathing_supervision_eligible = True
            corrected_absent_count += 1
            temporal_state = "EVENT_POSITIVE"
            event_reference = full_target_events[0]
        elif partial_target_events or evidence["breathing_reference_state"] == "BREATHING_REFERENCE_AMBIGUOUS":
            breathing_state = "BREATHING_REFERENCE_AMBIGUOUS"
            breathing_target_status = "AMBIGUOUS"
            breathing_supervision_eligible = False
            if partial_target_events:
                corrected_ambiguous_event_count += 1
            temporal_state = "AMBIGUOUS"
            event_reference = (partial_target_events or events or [None])[0]
        elif evidence["breathing_reference_state"] == "BREATHING_REFERENCE_PRESENT":
            breathing_state = "BREATHING_REFERENCE_PRESENT"
            breathing_target_status = "AVAILABLE"
            breathing_supervision_eligible = True
            temporal_state = "NON_EVENT"
            event_reference = None
        else:
            breathing_state = "BREATHING_REFERENCE_AMBIGUOUS"
            breathing_target_status = "TARGET_UNAVAILABLE"
            breathing_supervision_eligible = False
            temporal_state = "TARGET_UNAVAILABLE"
            event_reference = None

        provenance = {
            "source_dataset": row["dataset_id"],
            "dataset_version": row["provenance"]["dataset_version"],
            "subject_id": row["subject_id"],
            "recording_id": row["recording_id"],
            "window_id": window_id,
            "source_file": row["provenance"]["source_file"],
            "adapter_id": row["provenance"]["extraction_profile"],
            "r1_contract": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
            "r2_contract": "MMWAVE_V2_R2_SPECTRAL_AUTOCORR_V1",
            "r3_contract": row["schema_version"],
            "q2_contract": "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1",
            "reference_method": rr.get("reference_method"),
            "context_time_range_s": row["reference_time_range_s"],
            "breathing_target_interval_s": [target_start, target_end],
            "target_anchor": BREATHING_TARGET_ANCHOR,
            "authoritative_event_ids_reaching_target": [str(e["event_id"]) for e in events if max(float(e["event_start_seconds"]), target_start) < min(float(e["event_end_seconds"]), target_end)],
            "authoritative_event_ids_fully_containing_target": [str(e["event_id"]) for e in full_target_events],
            "clinical_apnea_claimed": False,
        }
        aligned = _alignment_metadata(
            model_input_id="D0::" + window_id,
            context_start_s=context_start,
            context_end_s=context_end,
            breathing_state=breathing_state,
            breathing_target_status=breathing_target_status,
            breathing_supervision_eligible=breathing_supervision_eligible,
            rr_target_status=rr["target_status"],
            rr_bpm=rr.get("rr_bpm"),
            rr_validity=rr.get("validity", "UNAVAILABLE"),
            rr_unavailable_reason=rr.get("unavailable_reason"),
            temporal_state=temporal_state,
            quality_status="CLEAN",
            quality_supervision_eligible=True,
            provenance=provenance,
        )
        examples.append({
            "example_id": "D0_" + window_id,
            "source_id": "D0",
            "dataset_id": row["dataset_id"],
            "subject_id": row["subject_id"],
            "recording_id": row["recording_id"],
            "window_id": window_id,
            "split": "TRAIN",
            "example_role": "MODEL_CONTEXT_WINDOW",
            "evaluation_stride_s": 5.0,
            "breathing_reference_state": breathing_state,
            "breathing_target_status": breathing_target_status,
            "rr_target_status": rr["target_status"],
            "rr_bpm": rr.get("rr_bpm"),
            "rr_validity": rr.get("validity", "UNAVAILABLE"),
            "rr_unavailable_reason": rr.get("unavailable_reason"),
            "temporal_hold_target_status": temporal_state,
            "temporal_event_state": hold["event_state"],
            "temporal_hold_learning_boundary": TEMPORAL_HOLD_LEARNING_BOUNDARY,
            "temporal_hold_supervision_eligible": False,
            "breathing_supervision_eligible": breathing_supervision_eligible,
            "rr_supervision_eligible": rr["target_status"] == "AVAILABLE" and rr.get("rr_bpm") is not None,
            "quality_supervision_eligible": True,
            "quality_status": "CLEAN",
            "provenance": provenance,
            **aligned,
        })
    audit = {
        "source_id": "D0",
        "selection_scope": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1 -> TRAIN only",
        "base_window_count": len(r3_rows),
        "base_present_count": sum(r["breathing_evidence"]["breathing_reference_state"] == "BREATHING_REFERENCE_PRESENT" for r in r3_rows),
        "base_ambiguous_count": sum(r["breathing_evidence"]["breathing_reference_state"] == "BREATHING_REFERENCE_AMBIGUOUS" for r in r3_rows),
        "base_absent_count": 0,
        "event_overlap_count": event_count,
        "old_event_relative_candidate_count": sum(1 for item in event_alignment_audit if item["old_event_relative_candidate"]),
        "corrected_event_interval_absent_count": corrected_absent_count,
        "corrected_event_interval_ambiguous_count": corrected_ambiguous_event_count,
        "corrected_event_audit_only_count": corrected_audit_only_count,
        "event_interval_absent_count": corrected_absent_count,
        "event_overlap_below_5s_count": short_event_count,
        "event_alignment_audit": event_alignment_audit,
        "event_interval_policy": {
            "duration_s": BREATHING_TARGET_DURATION_S,
            "selection": "fixed final 5 s interval [context_end-5 s, context_end]",
            "target_anchor": BREATHING_TARGET_ANCHOR,
            "requires_full_containment": True,
            "requires_causal_context": True,
            "event_overlay_rows_are_model_inputs": False,
            "radar_or_model_used": False,
            "whole_window_apnea_default": False,
        },
        "zero_class_resolution": "FIXED_FINAL_TARGET_ALIGNMENT; only fully contained final intervals are ABSENT; rejected candidates remain audit-only",
        "d0_split_identity": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1",
        "d0_heldout_used": False,
        "m_n6_excluded_used": False,
    }
    return examples, audit


def target_coverage(examples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    breathing_states = ["PRESENT", "ABSENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"]
    rr_states = ["AVAILABLE", "TARGET_UNAVAILABLE"]
    hold_states = ["EVENT_POSITIVE", "NON_EVENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"]
    quality_states = ["CLEAN", "SYNTHETIC_INPUT_UNAVAILABLE"]
    domains = sorted(set(example["source_id"] for example in examples))
    splits = sorted(set(example["split"] for example in examples))

    def counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = list(rows)
        model_ready_rows = [row for row in rows if row.get("model_ready") is True]
        model_input_ids = [row.get("model_input_id") for row in model_ready_rows]
        unique_model_input_ids = {value for value in model_input_ids if value}
        target_records = [record for row in model_ready_rows for record in row.get("target_records", [])]
        return {
            "example_count": len(rows),
            "model_ready_example_count": len(model_ready_rows),
            "audit_only_example_count": len(rows) - len(model_ready_rows),
            "unique_model_input_contexts": len(unique_model_input_ids),
            "target_record_count": len(target_records),
            "duplicate_target_overlay_count": len(model_ready_rows) - len(unique_model_input_ids),
            "breathing": {state: sum(_breathing_state(r) == state for r in model_ready_rows) for state in breathing_states},
            "breathing_audit_only": {state: sum(_breathing_state(r) == state for r in rows if r.get("model_ready") is not True) for state in breathing_states},
            "rr": {state: sum(_rr_state(r) == state for r in model_ready_rows) for state in rr_states},
            "temporal_hold": {state: sum(r.get("temporal_hold_target_status") == state for r in model_ready_rows) for state in hold_states},
            "quality": {
                "CLEAN": sum(r.get("quality_status") == "CLEAN" for r in model_ready_rows),
                "SYNTHETIC_INPUT_UNAVAILABLE": 0,
                "clean_unique_model_input_contexts": sum(r.get("quality_status") == "CLEAN" for r in model_ready_rows),
            },
            "task_eligibility": {
                "breathing": sum(bool(r.get("breathing_supervision_eligible")) for r in model_ready_rows),
                "rr": sum(bool(r.get("rr_supervision_eligible")) for r in model_ready_rows),
                "temporal_hold": sum(bool(r.get("temporal_hold_supervision_eligible")) for r in model_ready_rows),
                "quality": sum(bool(r.get("quality_supervision_eligible")) for r in model_ready_rows),
            },
            "target_records_by_task": dict(sorted(Counter(record.get("target_task") for record in target_records).items())),
        }

    by_domain = {domain: counts(r for r in examples if r["source_id"] == domain) for domain in domains}
    by_split = {split: counts(r for r in examples if r["split"] == split) for split in splits}
    by_subject = {subject: counts(r for r in examples if r["subject_id"] == subject) for subject in sorted(set(r["subject_id"] for r in examples))}
    return {
        "contract_id": CONTRACT_ID,
        "status_vocabulary": {
            "breathing": breathing_states,
            "rr": rr_states,
            "temporal_hold": hold_states,
            "quality": quality_states,
        },
        "by_domain": by_domain,
        "by_split": by_split,
        "by_subject": by_subject,
        "unique_model_input_contexts": len({row.get("model_input_id") for row in examples if row.get("model_ready") is True and row.get("model_input_id")}),
        "target_record_count": sum(len(row.get("target_records", [])) for row in examples if row.get("model_ready") is True),
        "duplicate_target_overlay_count": sum(1 for row in examples if row.get("model_ready") is True) - len({row.get("model_input_id") for row in examples if row.get("model_ready") is True and row.get("model_input_id")}),
        "quality_clean_unique_model_input_count": sum(1 for row in examples if row.get("model_ready") is True and row.get("quality_status") == "CLEAN"),
        "zero_counts_are_visible": True,
        "synthetic_quality_recipe_counts": {"Q1_MR60_TIMING_CORRUPTION": 0, "Q2_INPUT_UNAVAILABLE": 0},
        "synthetic_quality_is_not_physio_label": True,
    }


def _breathing_state(example: Mapping[str, Any]) -> str:
    value = str(example.get("breathing_reference_state", "TARGET_UNAVAILABLE"))
    return {
        "BREATHING_REFERENCE_PRESENT": "PRESENT",
        "BREATHING_REFERENCE_ABSENT": "ABSENT",
        "BREATHING_REFERENCE_AMBIGUOUS": "AMBIGUOUS",
        "PRESENT": "PRESENT",
        "ABSENT": "ABSENT",
        "AMBIGUOUS": "AMBIGUOUS",
    }.get(value, "TARGET_UNAVAILABLE")


def _rr_state(example: Mapping[str, Any]) -> str:
    return "AVAILABLE" if example.get("rr_target_status") == "AVAILABLE" and example.get("rr_bpm") is not None else "TARGET_UNAVAILABLE"


def build_documents(determinism_checked: bool) -> Dict[str, Any]:
    prereq = upstream_audit()
    if prereq["checks"].get("DIRECT_PREREQUISITES_ACCEPTED") != "YES":
        raise RuntimeError("M-PV1 direct prerequisite gate is not accepted")
    split = load_json(ROOT / D0_SPLIT_PATH)
    d0_rows, d0_audit = d0_examples()
    d1_audit, d1_rows, d1_split = d1_materialize()
    examples = sorted(d0_rows + d1_rows, key=lambda row: row["example_id"])

    role_contract = {
        "contract_id": CONTRACT_ID,
        "D0": {
            "role": "PRIMARY_SUPERVISED_DEVELOPMENT_DOMAIN",
            "source": "10.5281/zenodo.18599983_v1.1",
            "allowed_splits": ["TRAIN", "VAL", "D0_SUBJECT_HELDOUT"],
            "m_pv1_examples": "TRAIN only; one unique causal context per D0 window with fixed final breathing target",
            "mr60_supervised": False,
        },
        "D1": {
            "role": "AUXILIARY_CROSS_DOMAIN_REFERENCE_DEVELOPMENT_DOMAIN",
            "source": D1_DOI,
            "recordings": 265,
            "m_pv1_examples": "D1_DEV_TRAIN and D1_DEV_VAL subject-disjoint 30 s reference contexts where duration permits; breathing target is fixed final 5 s",
            "mr60_supervised": False,
        },
        "D2": {"role": "LOCKED_PUBLIC_CROSS_DEVICE_TEST", "m_pv1_access": "custody-state only"},
        "D3": {"status": prereq["checks"]["D3_STATUS"]},
        "MR60": {"role": "REFERENCE_OR_QA_ONLY", "supervised_physiology": "FORBIDDEN"},
    }
    d0_model_audit = {
        "contract_id": CONTRACT_ID,
        "inherited_split_identity": split["split_identity"],
        "split_changed": False,
        "m_n6_excluded_subjects_used": False,
        "d0_train_subject_count": len(split["subject_ids"]["TRAIN"]),
        "d0_val_subject_count": len(split["subject_ids"]["VAL"]),
        "d0_internal_heldout_subject_count": len(split["subject_ids"]["D0_SUBJECT_HELDOUT"]),
        "d0_train_model_contexts": d0_audit["base_window_count"],
        "unique_model_input_contexts": d0_audit["base_window_count"],
        "event_relative_absent_contexts": d0_audit["event_interval_absent_count"],
        "corrected_event_interval_absent_count": d0_audit["corrected_event_interval_absent_count"],
        "corrected_event_interval_audit_only_count": d0_audit["corrected_event_audit_only_count"],
        "base_present_count": d0_audit["base_present_count"],
        "base_absent_count": d0_audit["base_absent_count"],
        "base_ambiguous_count": d0_audit["base_ambiguous_count"],
        "event_overlap_below_5s_count": d0_audit["event_overlap_below_5s_count"],
        "zero_class_resolution": d0_audit["zero_class_resolution"],
        "reference_labels_not_derived_from_radar": True,
        "d0_val_or_internal_heldout_used_for_m_pv1_selection": False,
        "d0_audit": d0_audit,
    }
    representation = {
        "contract_id": CONTRACT_ID,
        "common_rate_hz": 10.0,
        "rate_decision": {
            "status": "FROZEN",
            "engineering_basis": [
                "D0 canonical trace is already exact 10 Hz",
                "D1 500/2000 Hz reference and radar are anti-aliased to 10 Hz",
                "10 Hz Nyquist is far above the 0.1-0.7 Hz respiratory band",
                "fixed 300-sample context is small enough for on-device candidate families",
                "deterministic scipy resample_poly path is already inherited by R1",
            ],
            "model_accuracy_used": False,
        },
        "scalar_profile": {
            "profile_id": "PROFILE_A_FEATURE_F2_V1",
            "source_contract": "MMWAVE_V2_R2_F2_SPECTRAL_AUTOCORR_V1",
            "status": "ACTIVE_M_PV2_CANDIDATE_FOR_RR_QUALITY_ONLY",
            "feature_order": F2_FEATURES,
            "feature_count": len(F2_FEATURES),
            "quality_sidecar_order": F3_QUALITY,
            "normalization": "TRAIN_FITTED_FEATURE_SCALER_ONLY_IF_NEEDED",
            "breathing_evidence_supported": False,
            "unsupported_reason": "global 30 s F2 representation has no defensible final 5 s target location",
        },
        "trace_profile": {
            "profile_id": "PROFILE_B_TRACE_F3_R1_V1",
            "source_contract": "MMWAVE_V2_R2_F3_TRACE_PLUS_QUALITY_DESCRIPTOR_V1",
            "trace_contract": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
            "status": "ACTIVE_M_PV2_CANDIDATE",
            "rate_hz": 10.0,
            "context_samples": 300,
            "trace_order": "oldest_to_newest, index 0 at context_start_s",
            "mask": "TRUE only for finite trace with valid timing; no zero-fill",
            "scale_descriptor_order": SCALE_DESCRIPTORS,
            "quality_sidecar_order": F3_QUALITY,
            "breathing_evidence_supported": True,
        },
        "hybrid_profile": {
            "profile_id": "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1",
            "status": "AUTHORIZED_CONDITIONAL_M_PV2_CANDIDATE",
            "composition": ["PROFILE_B_TRACE_F3_R1_V1", "PROFILE_A_FEATURE_F2_V1"],
            "new_feature_engineering": False,
            "use_only_if": "M-PV2 family comparison requires a trace+scalar composition",
            "breathing_evidence_supported": True,
        },
        "F1_role": "ABLATION_BASELINE_ONLY",
        "F2_role": "ACTIVE_SCALAR_CANDIDATE",
        "F3_role": "ACTIVE_TRACE_QUALITY_CANDIDATE",
        "task_compatibility_matrix": PROFILE_TASK_COMPATIBILITY,
        "window_local_MAD_divide_only": False,
        "source_specific_gain_matching": False,
        "low_amplitude_auto_normalization": False,
        "original_scale_information_preserved": True,
        "native_scale_descriptors": SCALE_DESCRIPTORS,
    }
    input_contract = {
        "contract_id": INPUT_ID,
        "dtype": "FLOAT32 development; boolean masks are BOOL",
        "availability_precedence": ["presence", "Q2 input availability", "physiology targets", "temporal composition"],
        "presence_authority": "human_detected_raw external production field; not trained from D0/D1",
        "profiles": {
            "PROFILE_A_FEATURE_F2_V1": {
                "inputs": [
                    {"name": "f2_features", "dtype": "float32", "shape": ["B", len(F2_FEATURES)], "feature_order": F2_FEATURES, "required": True},
                    {"name": "f2_feature_valid_mask", "dtype": "bool", "shape": ["B", len(F2_FEATURES)], "feature_order": F2_FEATURES, "required": True},
                    {"name": "quality_descriptors", "dtype": "float32", "shape": ["B", len(F3_QUALITY)], "feature_order": F3_QUALITY, "required": True},
                ],
                "metadata_not_tensor": ["availability_state", "source_domain", "subject_id", "recording_id", "context_id", "split", "target_start_s", "target_end_s", "target_anchor"],
                "breathing_target_location_support": "NO; do not use this profile for breathing_evidence supervision",
                "history_dimension": "none; temporal history is sequential composer state",
            },
            "PROFILE_B_TRACE_F3_R1_V1": {
                "inputs": [
                    {"name": "trace", "dtype": "float32", "shape": ["B", 300, 1], "time_axis": "oldest_to_newest", "required": True},
                    {"name": "trace_valid_mask", "dtype": "bool", "shape": ["B", 300, 1], "required": True},
                    {"name": "scale_descriptors", "dtype": "float32", "shape": ["B", len(SCALE_DESCRIPTORS)], "feature_order": SCALE_DESCRIPTORS, "required": True},
                    {"name": "quality_descriptors", "dtype": "float32", "shape": ["B", len(F3_QUALITY)], "feature_order": F3_QUALITY, "required": True},
                ],
                "padding": "none for model-ready clean examples; invalid/gap regions are masked and fail the Q2 window gate",
                "breathing_target_location_support": "YES; final 5 s is represented by ordered trace indices 250:300",
                "history_dimension": "none; temporal history is sequential composer state",
            },
            "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1": {
                "inputs": ["all inputs from PROFILE_B_TRACE_F3_R1_V1", "all inputs from PROFILE_A_FEATURE_F2_V1"],
                "shape_semantics": "trace and scalar inputs retain independent masks and feature order",
                "breathing_target_location_support": "YES via trace branch; F2 is auxiliary only",
                "history_dimension": "none; temporal history is sequential composer state",
            },
        },
        "fitted_statistics": "M-PV2 may fit a global robust/z-score feature scaler on TRAIN membership only; no source-specific gain matching",
        "variable_length_policy": "fixed 30 s context for model-ready examples; short D1 recordings remain audit-only",
        "target_anchor_metadata_is_not_a_tensor": True,
    }
    target_contract = {
        "contract_id": TARGET_ID,
        "DIRECT_THREE_CLASS_PRIMARY_TARGET": False,
        "breathing_evidence": {
            "states": ["PRESENT", "ABSENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"],
            "semantic_meaning": "reference-supported breathing evidence over the final fixed target interval of the causal context",
            "target_duration_s": BREATHING_TARGET_DURATION_S,
            "target_anchor": BREATHING_TARGET_ANCHOR,
            "context_duration_s": MODEL_CONTEXT_DURATION_S,
            "causal_context": True,
            "output_semantics": "breathing evidence over final target interval of current causal context",
            "present_absent_same_target_duration": True,
            "present_absent_same_target_semantics": True,
            "arbitrary_internal_target_interval": False,
            "d0_reference": "authoritative A6/Movesense evidence plus fixed-final-interval event binding",
            "d1_reference": "synchronized respiration waveform over the 30 s reference context with fixed-final-5 s anchor; weak periodicity is AMBIGUOUS, not ABSENT",
            "radar_amplitude_as_label": False,
            "source_apnea_term_auto_target": False,
            "whole_window_apnea_default": False,
        },
        "rr": {
            "field": "rr_bpm",
            "type": "continuous_float_bpm_or_null",
            "validity_required": True,
            "unavailable_reason_required": True,
            "zero_is_not_unavailable": True,
            "d0_method": "INHERITED_A4_MOVESENSE_CHEST_ACC_SPECTRAL_PEAK_V1",
            "d1_method": D1_REFERENCE_METHOD,
            "search_band_hz": [0.1, 0.7],
            "reference_interval_duration_s": MODEL_CONTEXT_DURATION_S,
            "reference_interval_anchor": RR_REFERENCE_ANCHOR,
            "separate_from_breathing_interval": True,
        },
        "temporal_hold": {
            "semantic_meaning": "event-relative voluntary breath-hold proxy; not clinical apnea",
            "d0": "event-relative authoritative intervals plus baseline/non-event",
            "d1": "UNAVAILABLE; source protocol strings do not define onset/offset",
            "baseline_required": True,
            "onset_and_recovery_explicit": True,
            "learning_boundary": TEMPORAL_HOLD_LEARNING_BOUNDARY,
            "direct_neural_supervision": False,
            "final_persistence_threshold": "DEFERRED_TO_POST_MODEL_DEVELOPMENT_CALIBRATION; no heldout tuning in M-PV1",
        },
        "supervision_masks": [
            "breathing_supervision_eligible",
            "rr_supervision_eligible",
            "temporal_hold_supervision_eligible",
            "quality_supervision_eligible",
        ],
    }
    temporal = {
        "contract_id": TEMPORAL_ID,
        "model_context_duration_s": MODEL_CONTEXT_DURATION_S,
        "model_context_samples": 300,
        "model_evaluation_stride_s": 5.0,
        "model_context_semantics": "[t-30 s, t] causal context",
        "causal_context": True,
        "target_interval": {
            "default": "breathing evidence always uses final fixed 5 s interval [t-5 s, t]",
            "breathing_target_duration_s": BREATHING_TARGET_DURATION_S,
            "breathing_target_anchor": BREATHING_TARGET_ANCHOR,
            "breathing_target_semantics": "same fixed final interval for PRESENT, ABSENT, AMBIGUOUS, and TARGET_UNAVAILABLE",
            "event_relative_hold_interval_s": BREATHING_TARGET_DURATION_S,
            "must_be_fully_inside_authoritative_event": True,
            "arbitrary_internal_target_interval": False,
            "future_information_allowed": False,
        },
        "rr_reference_interval": {
            "duration_s": MODEL_CONTEXT_DURATION_S,
            "anchor": RR_REFERENCE_ANCHOR,
            "separate_from_breathing_target": True,
        },
        "minimum_usable_duration_s": MODEL_CONTEXT_DURATION_S,
        "short_record_policy": "D1 <30 s is reference/feature audit only and is excluded from model-ready fixed-context examples",
        "padding_policy": "no physiological padding; no zero-fill as valid signal",
        "mask_policy": "valid timing and finite trace mask; Q2 invalid windows are INPUT_UNAVAILABLE",
        "gap_policy": "Q2 fail closed; no interpolation across large gaps or source freeze",
        "temporal_history": {
            "representation": "sequential composer state keyed by previous valid breathing context",
            "crosses_subject": False,
            "crosses_recording": False,
            "crosses_session": False,
            "previous_valid_baseline_required": True,
            "history_is_not_a_training_label": True,
        },
        "hold_composition": "breathing evidence + RR + hard quality gate -> deterministic sequential temporal composer",
        "temporal_hold_learning_boundary": TEMPORAL_HOLD_LEARNING_BOUNDARY,
        "direct_temporal_hold_neural_supervision": False,
        "persistence_threshold": "not finalized; later development-only calibration may choose an application threshold without clinical apnea language",
    }
    quality = {
        "contract_id": "MMWAVE_V2_M_PV1_QUALITY_ABSTENTION_CONTRACT_V1",
        "q2_inherited": "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1",
        "hard_pre_gate": [
            "human_detected_raw presence gate",
            "timestamp validity/monotonicity",
            "source freshness/stale",
            "source freeze",
            "large gap",
            "exact flat/nonfinite",
        ],
        "invalid_state": "INPUT_UNAVAILABLE",
        "presence_suppressed_state": "PRESENCE_SUPPRESSED",
        "valid_state": "PHYSIOLOGY_ELIGIBLE",
        "learned_soft_quality": "optional later score for nonperiodic/motion-contaminated uncertainty; cannot override hard invalid",
        "synthetic_quality_profiles": [
            {"profile_id": "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1", "target": "quality/abstain only"},
            {"profile_id": "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1", "target": "INPUT_UNAVAILABLE/ABSTAIN only"},
        ],
        "synthetic_corruption_rewrites_physiology": False,
        "invalid_input_physiology_supervision": False,
        "no_gap_interpolation": True,
    }
    balancing = {
        "contract_id": BALANCING_ID,
        "source_weights": {"D0": 0.75, "D1": 0.25},
        "rationale": "D0 is the primary 66-subject supervised domain; D1 is an 11-subject auxiliary domain. Both remain subject-balanced within source without blind window-count equalization.",
        "subject_weighting": "inverse eligible-example count per subject within source and split, normalized within source",
        "repeated_window_cap": "at most 1 clean fixed context per D1 recording in an epoch; D0 has one unique model input per base context and no event-overlay input duplication",
        "task_eligibility": "each task consumes only its explicit supervision mask; an RR-unavailable row is never encoded as zero",
        "quality_counting_unit": "unique clean model_input_id, never target overlay rows",
        "synthetic_ratio": {"maximum_fraction_of_clean_examples_per_task": 0.10, "denominator": "unique clean model inputs per task", "profile_ids": ["MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1", "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1"], "selection_method": "fixed recipe; no VAL tuning"},
        "oversampling": "no blind D1 window oversampling until counts equal D0",
        "weights_tuned_by_validation": False,
    }
    families = {
        "contract_id": CONTRACT_ID,
        "task_compatibility_matrix": {
            "FAMILY_A_FEATURE_MLP": {
                "input_profile": "PROFILE_A_FEATURE_F2_V1",
                "breathing_evidence": "NO",
                "rr": "YES",
                "quality": "YES",
                "temporal_hold": "COMPOSER_ONLY",
                "reason": "global F2 vector cannot encode final 5 s target location",
            },
            "FAMILY_B_SMALL_CONV1D_TCN": {
                "input_profile": "PROFILE_B_TRACE_F3_R1_V1",
                "breathing_evidence": "YES",
                "rr": "YES",
                "quality": "YES",
                "temporal_hold": "COMPOSER_ONLY",
            },
            "FAMILY_C_TRACE_FEATURE_HYBRID": {
                "input_profile": "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1",
                "breathing_evidence": "YES",
                "rr": "YES",
                "quality": "YES",
                "temporal_hold": "COMPOSER_ONLY",
            },
        },
        "authorized_m_pv2_families": [
            {"family_id": "FAMILY_A_FEATURE_MLP", "input_profile": "PROFILE_A_FEATURE_F2_V1", "targets": ["rr", "quality"], "breathing_evidence": "unsupported", "temporal_hold": "composer_only"},
            {"family_id": "FAMILY_B_SMALL_CONV1D_TCN", "input_profile": "PROFILE_B_TRACE_F3_R1_V1", "targets": ["breathing_evidence", "rr", "quality"], "temporal_hold": "composer_only"},
            {"family_id": "FAMILY_C_TRACE_FEATURE_HYBRID", "input_profile": "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1", "targets": ["breathing_evidence", "rr", "quality"], "temporal_hold": "composer_only", "condition": "only if bounded hybrid comparison is justified in M-PV2"},
        ],
        "not_authorized": ["transformer", "large_cnn", "rnn_zoo", "unbounded_architecture_search"],
        "training_performed": False,
    }
    example_manifest = {
        "contract_id": EXAMPLE_ID,
        "schema_version": "M-PV1.2_CORRECTIVE_ALIGNMENT",
        "example_count": len(examples),
        "model_ready_example_count": sum(row.get("model_ready") is True for row in examples),
        "audit_only_example_count": sum(row.get("model_ready") is not True for row in examples),
        "unique_model_input_contexts": len({row.get("model_input_id") for row in examples if row.get("model_ready") is True and row.get("model_input_id")}),
        "duplicate_target_overlay_count": 0,
        "target_interval_contract": {
            "breathing_target_duration_s": BREATHING_TARGET_DURATION_S,
            "breathing_target_anchor": BREATHING_TARGET_ANCHOR,
            "causal_context": True,
            "arbitrary_internal_target_interval": False,
        },
        "examples": examples,
        "synthetic_quality_recipes": [
            {"profile_id": "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1", "lineage_required": True, "physiology_target_rewrite": False},
            {"profile_id": "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1", "lineage_required": True, "target": "INPUT_UNAVAILABLE", "physiology_target_rewrite": False},
        ],
        "waveform_payloads_committed": False,
        "regeneration_policy": "derive traces/features from accepted D0/R1/R2 evidence or canonical D1 adapter; one row is one unique model input and target records are task-specific overlays on that same input",
    }
    compatibility = {
        "contract_id": CONTRACT_ID,
        "BREATHING_SEMANTIC_COMPATIBILITY": {"status": "YES_FIXED_FINAL_TARGET", "reason": "D0 and D1 use the same 5 s final target interval and anchor; D1 weak references remain AMBIGUOUS rather than fabricated ABSENT"},
        "RR_SEMANTIC_COMPATIBILITY": {"status": "YES_WITH_DOMAIN_METHODS", "reason": "both expose rr_bpm, validity, source, method, and explicit unavailable reason"},
        "TEMPORAL_HOLD_SEMANTIC_COMPATIBILITY": {"status": "COMPOSER_ONLY", "reason": "D0 has authoritative voluntary hold intervals; D1 has no defensible within-recording onset/offset; neither is a direct neural target"},
        "COMMON_INPUT_SCHEMA": "YES",
        "D0_AND_D1_FIXED_CONTEXT": "YES where duration >=30 s and Q2-compatible timing is valid",
        "BREATHING_TARGET_FIXED_ANCHOR": "YES",
        "BREATHING_PRESENT_ABSENT_SAME_TARGET_DURATION": "YES",
        "BREATHING_PRESENT_ABSENT_SAME_TARGET_SEMANTICS": "YES",
        "FEATURE_PROFILE_TARGET_LOCATION_AMBIGUOUS": "NO; F2 breathing task is disabled",
        "RR_INTERVAL_SEPARATE_FROM_BREATHING_INTERVAL": "YES",
        "MODEL_FAMILY_TASK_COMPATIBILITY_FROZEN": "YES",
    }
    d2_lock = load_json(ROOT / "datasets/mmwave/manifests/M-PV0_D2_locked_acquisition/access_state.json")
    d2_audit = {
        "contract_id": CONTRACT_ID,
        "source_id": "D2",
        "role": d2_lock.get("role"),
        "lock_state": d2_lock.get("lock_state"),
        "semantic_access": "NO",
        "feature_extraction": "NO",
        "target_use": "NO",
        "model_inference_count": 0,
        "selection_use": "NO",
        "payload_acquired": False,
        "custody_fields_inspected": ["access_state", "payload_digest_lock"],
    }
    exceptions = {
        "contract_id": CONTRACT_ID,
        "entries": [
            {"id": "M-PV1-CORRECTIVE-TARGET-CONTEXT-MISMATCH", "severity": "RESOLVED_BY_REFORMULATION", "detail": "The first M-PV1 manifest attached arbitrary internal 5 s event intervals to 30 s inputs. Corrective M-PV1 freezes the final 5 s causal target for every breathing state and removes duplicate event-overlay input rows."},
            {"id": "M-PV1-D0-ABSENT-RECOUNT", "severity": "RESOLVED_BY_RECOUNT", "detail": "The original 133 event-relative candidates were re-evaluated; only fully contained final target intervals remain ABSENT supervision, and the remainder are audit-only."},
            {"id": "M-PV1-D1-TEMPORAL-HOLD-UNAVAILABLE", "severity": "LIMITATION", "detail": "D1 respiration waveform is materialized, but source protocol strings do not supply defensible onset/recovery boundaries; temporal hold remains unavailable."},
            {"id": "M-PV1-D1-SHORT-RECORDINGS", "severity": "LIMITATION", "detail": "D1 recordings shorter than 30 s remain reference/feature audit only; no fake padding."},
            {"id": "M-PV1-F2-BREATHING-UNSUPPORTED", "severity": "LIMITATION", "detail": "The global F2 scalar profile cannot encode the fixed final 5 s target location, so F2 MLP is limited to RR/quality and temporal composition."},
            {"id": "M-PV1-D3-NOT_INCLUDED", "severity": "NON_BLOCKING", "detail": "No accepted D3 adapter is present."},
        ],
        "mr60_supervised_use": False,
        "d2_access": False,
    }
    coverage = target_coverage(examples)
    validation = {
        "contract_id": CONTRACT_ID,
        "schema_version": "M-PV1.2_CORRECTIVE_ALIGNMENT",
        "phase": "M-PV1",
        "gate": "PASS_WITH_LIMITATIONS",
        "ok": True,
        "deterministic_generation": bool(determinism_checked),
        "checks": {
            "D0_CONTRACT_INHERITED": "YES",
            "D1_CONTRACT_INHERITED": "YES",
            "R1_CONTRACT_INHERITED": "YES",
            "R2_CONTRACT_INHERITED": "YES",
            "R3_CONTRACT_INHERITED": "YES",
            "Q2_CONTRACT_INHERITED": "YES",
            "I1_CONTRACT_INHERITED": "YES",
            "D0_SPLIT_CHANGED": "NO",
            "M_N6_EXCLUDED_USED": "NO",
            "D1_SUBJECT_SPLIT_VERSIONED": "YES",
            "D1_RECORDING_LEVEL_LEAKAGE": "NO",
            "D2_USED_FOR_SELECTION": "NO",
            "D2_MODEL_INFERENCE_COUNT": 0,
            "MR60_SUPERVISED_USE": "NO",
            "COMMON_INPUT_SCHEMA_FROZEN": "YES",
            "COMMON_TARGET_SCHEMA_FROZEN": "YES",
            "TEMPORAL_CONTEXT_FROZEN": "YES",
            "BREATHING_TARGET_FIXED_ANCHOR": "YES",
            "BREATHING_PRESENT_ABSENT_SAME_TARGET_DURATION": "YES",
            "BREATHING_PRESENT_ABSENT_SAME_TARGET_SEMANTICS": "YES",
            "EVENT_TARGET_CONTEXT_CAUSAL": "YES",
            "ARBITRARY_INTERNAL_TARGET_INTERVAL": "NO",
            "MODEL_READY_TARGET_WITHOUT_VALID_INPUT_TENSOR": "NO",
            "FEATURE_PROFILE_TARGET_LOCATION_AMBIGUOUS": "NO",
            "DUPLICATE_INPUT_CONTRADICTORY_BREATHING_LABELS": "NO",
            "QUALITY_CONTEXT_DUPLICATE_COUNTING": "NO",
            "SYNTHETIC_RATIO_USES_UNIQUE_CLEAN_INPUT_COUNT": "YES",
            "TEMPORAL_HOLD_LEARNING_BOUNDARY_FROZEN": "YES",
            "MODEL_FAMILY_TASK_COMPATIBILITY_FROZEN": "YES",
            "RR_INTERVAL_SEPARATE_FROM_BREATHING_INTERVAL": "YES",
            "SOURCE_BALANCING_FROZEN": "YES",
            "DIRECT_THREE_CLASS_PRIMARY_TARGET": "NO",
            "WHOLE_WINDOW_APNEA_DEFAULT": "NO",
            "WINDOW_LOCAL_MAD_ONLY_NORMALIZATION": "NO",
            "SOURCE_SPECIFIC_GAIN_MATCHING": "NO",
            "ORIGINAL_SCALE_INFORMATION_PRESERVED": "YES",
            "INVALID_INPUT_PHYSIOLOGY_SUPERVISION": "NO",
            "BREATHING_ZERO_COUNT_HIDDEN": "NO",
            "RR_UNAVAILABLE_ENCODED_AS_ZERO": "NO",
            "D1_PROTOCOL_APNEA_AUTO_TARGET": "NO",
            "MODEL_TRAINING": "NO",
            "MODEL_SELECTION": "NO",
            "SEED_SWEEP": "NO",
            "PROBABILITY_THRESHOLD_TUNING": "NO",
            "INT8_WORK": "NO",
            "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
        },
        "coverage_summary": {
            "D0_base_present": d0_audit["base_present_count"],
            "D0_base_absent": d0_audit["base_absent_count"],
            "D0_corrected_absent": d0_audit["corrected_event_interval_absent_count"],
            "D0_corrected_ambiguous": sum(_breathing_state(row) == "AMBIGUOUS" for row in d0_rows),
            "D0_unique_model_input_contexts": sum(row.get("model_ready") is True for row in d0_rows),
            "D1_model_ready_contexts": d1_audit.get("model_ready_context_count", 0),
            "D1_short_audit_only": d1_audit.get("short_recording_audit_only_count", 0),
            "total_unique_model_input_contexts": coverage["unique_model_input_contexts"],
            "total_target_records": coverage["target_record_count"],
            "duplicate_target_overlays": coverage["duplicate_target_overlay_count"],
            "quality_clean_unique_model_inputs": coverage["quality_clean_unique_model_input_count"],
        },
        "limitations": exceptions["entries"],
        "m_pv1_ready_for_m_pv2": True,
    }
    config = {
        "contract_id": CONTRACT_ID,
        "schema_version": "M-PV1.2_CORRECTIVE_ALIGNMENT",
        "phase": "M-PV1",
        "status": "FROZEN_FOR_M_PV2",
        "upstream_contracts": {
            "M-PV0": "MMWAVE_M_PV0_PUBLIC_MULTIDOMAIN_REGISTRY_V1",
            "D0": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1",
            "D1": "D1_NATIVE_SIXPORT_PHASE_DISPLACEMENT_V1",
            "R1": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
            "R2": "MMWAVE_V2_R2_REPRESENTATION_CANDIDATE_SET_V1",
            "R3": "MMWAVE_V2_R3_TARGET_CONTRACT_SET_V1",
            "Q2": "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1",
            "I1": "MMWAVE_V2_I1_RUNTIME_SEMANTIC_CONTRACT_V1",
        },
        "rate_hz": 10.0,
        "context_duration_s": MODEL_CONTEXT_DURATION_S,
        "model_context_duration_s": MODEL_CONTEXT_DURATION_S,
        "evaluation_stride_s": 5.0,
        "breathing_target_duration_s": BREATHING_TARGET_DURATION_S,
        "breathing_target_anchor": BREATHING_TARGET_ANCHOR,
        "breathing_target_semantics": "final fixed interval of current causal context",
        "causal_context": True,
        "arbitrary_internal_target_interval": False,
        "rr_reference_interval_duration_s": MODEL_CONTEXT_DURATION_S,
        "rr_reference_interval_anchor": RR_REFERENCE_ANCHOR,
        "temporal_hold_learning_boundary": TEMPORAL_HOLD_LEARNING_BOUNDARY,
        "representation_profiles": ["PROFILE_A_FEATURE_F2_V1", "PROFILE_B_TRACE_F3_R1_V1", "PROFILE_C_HYBRID_TRACE_PLUS_F2_V1"],
        "target_contract": TARGET_ID,
        "temporal_contract": TEMPORAL_ID,
        "source_balancing_contract": BALANCING_ID,
        "example_manifest": EXAMPLE_ID,
        "model_training_performed": False,
        "d2_used": False,
        "mr60_supervised_use": False,
        "m_pv1_ready_for_m_pv2": True,
    }
    return {
        "config/mmwave/m_pv1_public_multidomain_contract.json": config,
        "prerequisite_audit.json": prereq,
        "dataset_role_contract.json": role_contract,
        "d0_model_ready_audit.json": d0_model_audit,
        "d1_reference_materialization_audit.json": d1_audit,
        "d1_subject_split.json": d1_split,
        "representation_freeze.json": representation,
        "model_input_contract.json": input_contract,
        "target_mapping_profile.json": target_contract,
        "temporal_context_contract.json": temporal,
        "quality_abstention_contract.json": quality,
        "source_balancing_contract.json": balancing,
        "m_pv2_example_manifest.json": example_manifest,
        "target_coverage_audit.json": coverage,
        "cross_domain_compatibility.json": compatibility,
        "d2_lock_audit.json": d2_audit,
        "exception_registry.json": exceptions,
        "validation_result.json": validation,
    }


def generate(output_dir: Path, determinism_checked: bool) -> None:
    documents = build_documents(determinism_checked)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = documents.pop("config/mmwave/m_pv1_public_multidomain_contract.json")
    write_json(ROOT / CONFIG_REL, config)
    for name, document in documents.items():
        write_json(output_dir / name, document)
    file_hashes = {name: sha256_file(output_dir / name) for name in sorted(documents)}
    checksums = {
        "contract_id": CONTRACT_ID,
        "schema_version": "M-PV1.2_CORRECTIVE_ALIGNMENT",
        "files": file_hashes,
        "config": {"path": rel(ROOT / CONFIG_REL), "sha256": sha256_file(ROOT / CONFIG_REL)},
        "generator": {"path": rel(ROOT / "scripts/mmwave_m_pv1_public_multidomain_contract.py"), "sha256": sha256_file(ROOT / "scripts/mmwave_m_pv1_public_multidomain_contract.py")},
        "raw_payload_not_committed": True,
    }
    write_json(output_dir / "checksums.json", checksums)


def compare_dirs(left: Path, right: Path) -> Tuple[bool, List[str]]:
    left_files = sorted(path.relative_to(left).as_posix() for path in left.rglob("*") if path.is_file())
    right_files = sorted(path.relative_to(right).as_posix() for path in right.rglob("*") if path.is_file())
    differences = sorted(set(left_files) ^ set(right_files))
    for name in sorted(set(left_files) & set(right_files)):
        if (left / name).read_bytes() != (right / name).read_bytes():
            differences.append(name)
    return not differences, differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / EVIDENCE_REL)
    parser.add_argument("--check-determinism", action="store_true")
    args = parser.parse_args()
    if args.check_determinism:
        with tempfile.TemporaryDirectory(prefix="safenest_mpv1_a_") as left_name, tempfile.TemporaryDirectory(prefix="safenest_mpv1_b_") as right_name:
            left = Path(left_name)
            right = Path(right_name)
            # Both runs use the same deterministic validation flag; the flag
            # records that this exact double-generation path was executed.
            generate(left, True)
            generate(right, True)
            same, differences = compare_dirs(left, right)
            if not same:
                raise SystemExit("M-PV1 deterministic generation mismatch: " + ", ".join(differences))
        generate(args.output_dir, True)
    else:
        generate(args.output_dir, False)
    print(json.dumps({"ok": True, "gate": "PASS_WITH_LIMITATIONS", "evidence_dir": rel(args.output_dir), "config": rel(ROOT / CONFIG_REL)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
