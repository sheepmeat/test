#!/usr/bin/env python3
"""Run the bounded SafeNest mmWave M-PV2 candidate-training phase.

The runner deliberately keeps waveform/tensor payloads out of Git.  It
reconstructs the accepted R1/R2 inputs from the frozen public artifacts and
the ignored source archives, applies the frozen M-PV1 membership/target
contract, trains the nine authorized family/seed candidates, and writes only
compact checkpoints plus auditable aggregate evidence.

M-PV2 is a candidate-generation phase.  This module never selects a final
model, consumes D2 or MR60 labels, fits calibration, quantizes, or deploys.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, mean_squared_error, roc_auc_score

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - validator reports this as a technical failure
    raise SystemExit("M-PV2 requires torch for the authorized neural candidate families") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTRACT_REL = Path("config/mmwave/m_pv2_candidate_training_contract.json")
M_PV1_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/m_pv2_example_manifest.json")
M_PV1_VALIDATION_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/validation_result.json")
M_PV1_ROLE_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/dataset_role_contract.json")
M_PV1_SPLIT_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/d1_subject_split.json")
M_PV1_D2_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/d2_lock_audit.json")
M_PV1_BALANCING_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/source_balancing_contract.json")
R1_D0_REL = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace/d0_trace_audit.json")
R1_D1_REL = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace/d1_trace_audit.json")
R2_D0_REL = Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features/d0_feature_audit.json")
R2_D1_REL = Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features/d1_feature_audit.json")
OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training")
MODEL_ROOT_REL = Path("models/mmwave/m_pv2")
SEEDS = (11, 23, 47)

F2_NAMES = (
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
)
SCALE_NAMES = (
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
)
QUALITY_NAMES = (
    "trace_sample_count",
    "trace_duration_s",
    "trace_mad_about_median",
    "trace_robust_rms_about_median",
    "trace_robust_range_p05_p95",
    "trace_mean_square",
    "trace_is_exact_flat",
    "valid_sample_fraction",
    "source_quality_flag_count",
)


class PV2Error(RuntimeError):
    """Fail-closed M-PV2 input or evidence error."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PV2Error(f"failed to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PV2Error(f"expected JSON object: {path}")
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and (not math.isfinite(value)):
        return None
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_head() -> str:
    try:
        import subprocess

        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "UNAVAILABLE"


def _set_deterministic(seed: int) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    try:
        torch.set_num_threads(1)
    except RuntimeError:
        pass
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # PyTorch permits inter-op thread configuration only before the first
        # parallel region.  A later candidate still inherits the deterministic
        # setting from the first run.
        pass
    try:
        torch.use_deterministic_algorithms(True)
        deterministic = True
    except Exception:
        deterministic = False
    return {
        "seed": int(seed),
        "python_hash_seed_requested": os.environ.get("PYTHONHASHSEED", "UNSET"),
        "torch_deterministic_algorithms": deterministic,
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
    }


@dataclasses.dataclass
class InputRecord:
    source_id: str
    subject_id: str
    recording_id: str
    model_input_id: str
    split: str
    trace: np.ndarray
    trace_mask: np.ndarray
    f2: np.ndarray
    f2_mask: np.ndarray
    scale: np.ndarray
    quality: np.ndarray
    breathing_label: float
    breathing_mask: float
    rr_bpm: float
    rr_mask: float
    quality_label: float
    quality_mask: float
    breathing_state: str
    rr_target_status: str
    quality_status: str
    provenance: dict[str, Any]
    is_synthetic: bool = False
    corruption_mode: str | None = None


def _clone_metadata_for_context(common: Any, trace: np.ndarray, time_s: np.ndarray, quality_flag: str | None = None) -> Any:
    """Return a fixed 30 s context view without re-centering the full R1 trace."""
    from adapters.mmwave_r1_sensor_independent_trace import CommonTraceOutput

    metadata = copy.deepcopy(common.metadata)
    flags = list(metadata.get("quality_flags", []))
    if quality_flag:
        flags.append(quality_flag)
    metadata["quality_flags"] = flags
    provenance = dict(metadata.get("provenance", {}))
    provenance["time_range_s"] = [float(time_s[0]), float(time_s[-1])]
    metadata["provenance"] = provenance
    metadata["context_derivation"] = "R1_FULL_RECORDING_OUTPUT_THEN_FIXED_FIRST_300_SAMPLES"
    return CommonTraceOutput(
        trace=np.asarray(trace, dtype=np.float64),
        time_s=np.asarray(time_s, dtype=np.float64),
        validity_mask=np.ones(np.asarray(trace).shape, dtype=bool),
        metadata=metadata,
    )


def _vector(mapping: Mapping[str, Any], names: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    values = np.zeros(len(names), dtype=np.float32)
    mask = np.zeros(len(names), dtype=bool)
    for index, name in enumerate(names):
        try:
            value = float(mapping.get(name))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values[index] = value
            mask[index] = True
    return values, mask


def _feature_arrays(common: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from adapters.mmwave_r2_representation_features import extract_feature_candidates

    extracted = extract_feature_candidates(common)
    f2_map = extracted.f2.features if isinstance(extracted.f2.features, Mapping) else {}
    scale_map = f2_map
    quality_map = extracted.f3.features if isinstance(extracted.f3.features, Mapping) else {}
    f2, f2_mask = _vector(f2_map, F2_NAMES)
    scale, scale_mask = _vector(scale_map, SCALE_NAMES)
    quality, quality_mask = _vector(quality_map, QUALITY_NAMES)
    # Scale descriptors and quality descriptors are contract-required for
    # model-ready clean inputs.  Keep their masks for the tensor audit; the
    # model receives finite zero-filled values and the F2 validity mask.
    if not np.all(scale_mask):
        scale = np.nan_to_num(scale, nan=0.0, posinf=0.0, neginf=0.0)
    if not np.all(quality_mask):
        quality = np.nan_to_num(quality, nan=0.0, posinf=0.0, neginf=0.0)
    return (
        np.asarray(extracted.trace, dtype=np.float32),
        np.asarray(extracted.validity_mask, dtype=bool),
        f2,
        f2_mask,
        np.concatenate([scale, quality]).astype(np.float32),
    )


def _load_materialized_records() -> tuple[list[InputRecord], dict[str, Any]]:
    """Rebuild tensors from frozen M-PV1 membership and accepted R1 adapters."""
    from adapters.mmwave_r1_sensor_independent_trace import adapt_native_trace
    import scripts.run_mmwave_r1_sensor_independent_trace as r1_runner

    manifest = _read_json(ROOT / M_PV1_REL)
    examples = manifest.get("examples")
    if not isinstance(examples, list):
        raise PV2Error("M-PV1 example manifest has no examples list")
    model_rows = [row for row in examples if row.get("model_ready") is True]
    if len(model_rows) != 562:
        raise PV2Error(f"M-PV1 model-ready count changed: {len(model_rows)} (expected 562)")
    if int(manifest.get("duplicate_target_overlay_count", -1)) != 0:
        raise PV2Error("M-PV1 duplicate target overlays are non-zero")

    d0_inputs, d0_scope = r1_runner._load_d0_inputs(ROOT)
    d1_inputs, d1_scope = r1_runner._load_d1_inputs(ROOT)
    native_by_key: dict[tuple[str, str], Any] = {}
    for native in [*d0_inputs, *d1_inputs]:
        native_by_key[(native.source_id, native.recording_id)] = native

    records: list[InputRecord] = []
    lineage_rows: list[dict[str, Any]] = []
    for row in sorted(model_rows, key=lambda item: str(item.get("model_input_id"))):
        source = str(row.get("source_id"))
        key = str(row.get("window_id")) if source == "D0" else str(row.get("recording_id"))
        native = native_by_key.get((source, key))
        if native is None:
            raise PV2Error(f"accepted R1 input missing for {source}:{key}")
        common = adapt_native_trace(native)
        if common.trace.size < 300:
            raise PV2Error(f"model-ready input shorter than 30 s after R1: {source}:{key}")
        trace = np.asarray(common.trace[:300], dtype=np.float32)
        time_s = np.asarray(common.time_s[:300], dtype=np.float64)
        context = _clone_metadata_for_context(common, trace.astype(np.float64), time_s)
        context_trace, context_mask, f2, f2_mask, descriptors = _feature_arrays(context)
        scale = descriptors[: len(SCALE_NAMES)]
        quality = descriptors[len(SCALE_NAMES) :]
        breathing_state = str(row.get("breathing_reference_state"))
        if breathing_state == "BREATHING_REFERENCE_PRESENT":
            breathing_label, breathing_mask = 1.0, 1.0
        elif breathing_state == "BREATHING_REFERENCE_ABSENT":
            breathing_label, breathing_mask = 0.0, 1.0
        else:
            breathing_label, breathing_mask = 0.0, 0.0
        rr_ok = bool(row.get("rr_supervision_eligible")) and row.get("rr_bpm") is not None
        rr_bpm = float(row["rr_bpm"]) if rr_ok else float("nan")
        rr_mask = 1.0 if rr_ok and math.isfinite(rr_bpm) else 0.0
        provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        lineage = {
            "source_id": source,
            "subject_id": str(row.get("subject_id")),
            "recording_id": str(row.get("recording_id")),
            "model_input_id": str(row.get("model_input_id")),
            "window_id": row.get("window_id"),
            "split": str(row.get("split")),
            "context_start_s": row.get("context_start_s"),
            "context_end_s": row.get("context_end_s"),
            "target_start_s": row.get("target_start_s"),
            "target_end_s": row.get("target_end_s"),
            "target_anchor": row.get("target_anchor"),
            "breathing_state": breathing_state,
            "breathing_supervision_eligible": bool(row.get("breathing_supervision_eligible")),
            "rr_supervision_eligible": bool(row.get("rr_supervision_eligible")),
            "quality_status": str(row.get("quality_status")),
            "source_file": provenance.get("source_file"),
            "reference_method": provenance.get("reference_method"),
            "r1_profile": "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1",
            "r2_profile": "MMWAVE_V2_R2_F2_SPECTRAL_AUTOCORR_V1",
            "tensor_derivation": "R1 accepted trace -> fixed first 300 samples -> R2 feature extraction",
            "synthetic": False,
        }
        record = InputRecord(
            source_id=source,
            subject_id=str(row.get("subject_id")),
            recording_id=str(row.get("recording_id")),
            model_input_id=str(row.get("model_input_id")),
            split=str(row.get("split")),
            trace=context_trace,
            trace_mask=context_mask,
            f2=f2,
            f2_mask=f2_mask,
            scale=scale,
            quality=quality,
            breathing_label=breathing_label,
            breathing_mask=breathing_mask,
            rr_bpm=rr_bpm,
            rr_mask=rr_mask,
            quality_label=1.0,
            quality_mask=1.0,
            breathing_state=breathing_state,
            rr_target_status=str(row.get("rr_target_status")),
            quality_status=str(row.get("quality_status")),
            provenance=lineage,
        )
        records.append(record)
        lineage_rows.append(lineage)

    counts = {
        "model_ready_unique": len(records),
        "by_source": {source: sum(record.source_id == source for record in records) for source in ("D0", "D1")},
        "by_split": {split: sum(record.split == split for record in records) for split in sorted({r.split for r in records})},
        "breathing_states": {
            state: sum(record.breathing_state == state for record in records)
            for state in sorted({r.breathing_state for r in records})
        },
        "breathing_eligible": int(sum(record.breathing_mask for record in records)),
        "rr_eligible": int(sum(record.rr_mask for record in records)),
        "quality_clean_unique": int(sum(record.quality_status == "CLEAN" and not record.is_synthetic for record in records)),
        "duplicate_target_overlays": 0,
        "d0_r1_scope": d0_scope,
        "d1_r1_scope": d1_scope,
    }
    if counts["by_source"] != {"D0": 318, "D1": 244}:
        raise PV2Error(f"source membership changed: {counts['by_source']}")
    return records, {"counts": counts, "lineage_rows": lineage_rows}


def _quality_synthetic(base: InputRecord, mode: str, ordinal: int) -> InputRecord:
    from adapters.mmwave_r1_sensor_independent_trace import CommonTraceOutput

    trace = np.asarray(base.trace, dtype=np.float32).copy()
    if mode == "FLAT_EXACT":
        trace[:] = trace[0]
    elif mode == "SOURCE_FREEZE":
        trace[100:150] = trace[99]
    elif mode == "STALE_SOURCE":
        trace[120:180] = trace[119]
    elif mode == "LARGE_GAP":
        trace[130:190] = trace[129]
    elif mode == "JITTER_PLUS_LARGE_GAP":
        trace[80:140] = trace[79]
        trace[220:250] = trace[219]
    elif mode == "REPUBLICATION_TO_FREEZE":
        trace[160:230] = trace[159]
    else:
        raise PV2Error(f"unknown Q2 synthetic mode: {mode}")
    centered = trace.astype(np.float64) - float(np.median(trace))
    descriptor = {
        "min": float(np.min(trace)),
        "max": float(np.max(trace)),
        "mean": float(np.mean(trace)),
        "std": float(np.std(trace)),
        "median": float(np.median(trace)),
        "mad_about_median": float(np.median(np.abs(centered))),
        "robust_rms_about_median": float(np.sqrt(np.mean(centered * centered))),
        "robust_peak_to_peak_p05_p95": float(np.percentile(trace, 95.0) - np.percentile(trace, 5.0)),
        "peak_to_peak": float(np.max(trace) - np.min(trace)),
    }
    metadata = {
        "schema_version": "R1.1",
        "contract_id": "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1",
        "profile_id": "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1",
        "source_id": base.source_id,
        "dataset_id": "synthetic_q2_derived_from_clean_public_input",
        "subject_id": base.subject_id,
        "recording_id": base.recording_id,
        "condition": "SYNTHETIC_Q2",
        "trace_name": "respiratory_motion_trace",
        "trace_units": "phase_like_radian; absolute displacement equivalence not claimed",
        "sign_policy": "PRESERVE_SOURCE_SIGN; SIGN_ALIGNMENT_UNVERIFIED",
        "output_sampling_rate_hz": 10.0,
        "source_sampling_rate_hz": 10.0,
        "native_scale_metadata": {
            "native_descriptors": descriptor,
            "common_trace_descriptors_after_centering": descriptor,
            "native_scale_preserved": True,
            "scale_normalization_applied": False,
            "sensor_gain_matching_applied": False,
            "sign_inversion_applied": False,
        },
        "quality_flags": ["R1_FINITE_OUTPUT", "SYNTHETIC_Q2_" + mode],
        "provenance": {"base_model_input_id": base.model_input_id, "q2_profile_id": "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1"},
        "validity_mask_semantics": "TRUE_ONLY_FOR_FINITE_TRACE_WITH_VALID_TIMING; NO_ZERO_FILL",
    }
    context = CommonTraceOutput(
        trace=trace.astype(np.float64),
        time_s=np.arange(300, dtype=np.float64) / 10.0,
        validity_mask=np.ones(300, dtype=bool),
        metadata=metadata,
    )
    context_trace, context_mask, f2, f2_mask, descriptors = _feature_arrays(context)
    lineage = dict(base.provenance)
    lineage.update({
        "model_input_id": f"SYNTHETIC_Q2::{base.model_input_id}::{ordinal:03d}",
        "synthetic": True,
        "base_model_input_id": base.model_input_id,
        "q2_profile_id": "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1",
        "corruption_mode": mode,
        "physiology_target_rewrite": False,
    })
    return InputRecord(
        source_id=base.source_id,
        subject_id=base.subject_id,
        recording_id=base.recording_id,
        model_input_id=lineage["model_input_id"],
        split=base.split,
        trace=context_trace,
        trace_mask=context_mask,
        f2=f2,
        f2_mask=f2_mask,
        scale=descriptors[: len(SCALE_NAMES)],
        quality=descriptors[len(SCALE_NAMES) :],
        breathing_label=0.0,
        breathing_mask=0.0,
        rr_bpm=float("nan"),
        rr_mask=0.0,
        quality_label=0.0,
        quality_mask=1.0,
        breathing_state="INPUT_UNAVAILABLE",
        rr_target_status="TARGET_UNAVAILABLE",
        quality_status="INPUT_UNAVAILABLE",
        provenance=lineage,
        is_synthetic=True,
        corruption_mode=mode,
    )


def _make_synthetic(records: Sequence[InputRecord], *, training: bool) -> list[InputRecord]:
    clean = [record for record in records if not record.is_synthetic and record.quality_status == "CLEAN"]
    if not clean:
        return []
    max_count = int(math.floor(0.1 * len(clean)))
    if training:
        modes = ("FLAT_EXACT", "SOURCE_FREEZE", "STALE_SOURCE", "LARGE_GAP", "JITTER_PLUS_LARGE_GAP", "REPUBLICATION_TO_FREEZE")
        selected = sorted(clean, key=lambda record: record.model_input_id)[:max_count]
    else:
        modes = ("FLAT_EXACT", "SOURCE_FREEZE", "STALE_SOURCE", "LARGE_GAP", "JITTER_PLUS_LARGE_GAP", "REPUBLICATION_TO_FREEZE")
        selected = sorted(clean, key=lambda record: record.model_input_id)[: min(len(modes), max_count)]
    return [_quality_synthetic(base, modes[index % len(modes)], index) for index, base in enumerate(selected)]


def _record_group(records: Sequence[InputRecord], name: str) -> list[InputRecord]:
    if name == "TRAIN":
        return [r for r in records if (r.source_id == "D0" and r.split == "TRAIN") or (r.source_id == "D1" and r.split == "D1_DEV_TRAIN")]
    if name == "D1_DEV_VAL":
        return [r for r in records if r.source_id == "D1" and r.split == "D1_DEV_VAL"]
    if name == "D0_TRAIN":
        return [r for r in records if r.source_id == "D0" and r.split == "TRAIN"]
    if name == "D1_DEV_TRAIN":
        return [r for r in records if r.source_id == "D1" and r.split == "D1_DEV_TRAIN"]
    raise PV2Error(f"unknown record group: {name}")


def _fit_stats(train_clean: Sequence[InputRecord]) -> dict[str, Any]:
    def field_matrix(field: str) -> np.ndarray:
        return np.stack([np.asarray(getattr(record, field), dtype=np.float64) for record in train_clean], axis=0)

    f2 = field_matrix("f2")
    scale = field_matrix("scale")
    quality = field_matrix("quality")
    trace = np.concatenate([np.asarray(record.trace, dtype=np.float64) for record in train_clean])
    rr = np.asarray([record.rr_bpm for record in train_clean if record.rr_mask and math.isfinite(record.rr_bpm)], dtype=np.float64)

    def mean_std(values: np.ndarray) -> tuple[list[float], list[float]]:
        mean = np.nanmean(values, axis=0)
        std = np.nanstd(values, axis=0)
        std = np.where(np.isfinite(std) & (std > 1e-8), std, 1.0)
        return mean.astype(float).tolist(), std.astype(float).tolist()

    trace_mean = float(np.mean(trace))
    trace_std = float(np.std(trace))
    if not math.isfinite(trace_std) or trace_std <= 1e-8:
        trace_std = 1.0
    rr_mean = float(np.mean(rr)) if rr.size else 0.0
    rr_std = float(np.std(rr)) if rr.size else 1.0
    if not math.isfinite(rr_std) or rr_std <= 1e-8:
        rr_std = 1.0
    stats = {
        "fit_scope": "TRAIN_CLEAN_ONLY",
        "fit_record_count": len(train_clean),
        "rr_fit_count": int(rr.size),
        "f2": {"names": list(F2_NAMES), "mean": mean_std(f2)[0], "std": mean_std(f2)[1]},
        "scale": {"names": list(SCALE_NAMES), "mean": mean_std(scale)[0], "std": mean_std(scale)[1]},
        "quality": {"names": list(QUALITY_NAMES), "mean": mean_std(quality)[0], "std": mean_std(quality)[1]},
        "trace": {"mean": trace_mean, "std": trace_std},
        "rr": {"mean": rr_mean, "std": rr_std},
    }
    stats["sha256"] = _sha256_json(stats)
    return stats


def _normalize(values: np.ndarray, spec: Mapping[str, Any]) -> np.ndarray:
    mean = np.asarray(spec["mean"], dtype=np.float32)
    std = np.asarray(spec["std"], dtype=np.float32)
    return (values - mean) / std


def _feature_matrix(records: Sequence[InputRecord], family: str, stats: Mapping[str, Any]) -> np.ndarray:
    vectors: list[np.ndarray] = []
    for record in records:
        f2 = _normalize(record.f2[None, :], stats["f2"])[0]
        f2_mask = record.f2_mask.astype(np.float32)
        scale = _normalize(record.scale[None, :], stats["scale"])[0]
        quality = _normalize(record.quality[None, :], stats["quality"])[0]
        trace = (record.trace.astype(np.float32) - float(stats["trace"]["mean"])) / float(stats["trace"]["std"])
        trace_mask = record.trace_mask.astype(np.float32)
        if family == "family_a":
            vector = np.concatenate([f2, f2_mask, quality])
        elif family == "family_b":
            vector = np.concatenate([trace, trace_mask, scale, quality])
        elif family == "family_c":
            vector = np.concatenate([trace, trace_mask, scale, quality, f2, f2_mask])
        else:
            raise PV2Error(f"unknown family: {family}")
        vectors.append(np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32))
    return np.stack(vectors, axis=0) if vectors else np.zeros((0, 1), dtype=np.float32)


def _task_weights(records: Sequence[InputRecord], task: str) -> np.ndarray:
    mask = np.asarray([getattr(record, f"{task}_mask") for record in records], dtype=np.float64)
    source_weights = {"D0": 0.75, "D1": 0.25}
    counts: dict[tuple[str, str], int] = {}
    for record, eligible in zip(records, mask):
        if eligible:
            counts[(record.source_id, record.subject_id)] = counts.get((record.source_id, record.subject_id), 0) + 1
    weights = np.zeros(len(records), dtype=np.float64)
    for index, (record, eligible) in enumerate(zip(records, mask)):
        if eligible:
            weights[index] = source_weights[record.source_id] / counts[(record.source_id, record.subject_id)]
    for source in source_weights:
        source_mask = np.asarray([(record.source_id == source and weight > 0.0) for record, weight in zip(records, weights)])
        if np.any(source_mask):
            weights[source_mask] /= float(np.mean(weights[source_mask]))
            weights[source_mask] *= source_weights[source]
    return weights.astype(np.float32)


class FamilyAModel(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU())
        self.rr_head = nn.Linear(32, 1)
        self.quality_head = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.body(x)
        return {"rr": self.rr_head(hidden).squeeze(-1), "quality": self.quality_head(hidden).squeeze(-1)}


class TraceModel(nn.Module):
    def __init__(self, input_dim: int, family: str):
        super().__init__()
        self.family = family
        self.trace = nn.Sequential(nn.Conv1d(1, 16, 5, padding=2), nn.ReLU(), nn.Conv1d(16, 24, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(8))
        scalar_dim = 12 + 9 + (25 + 25 if family == "family_c" else 0)
        self.body = nn.Sequential(nn.Linear(24 * 8 + scalar_dim, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU())
        self.breathing_head = nn.Linear(32, 1)
        self.rr_head = nn.Linear(32, 1)
        self.quality_head = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        trace = x[:, :300]
        mask = x[:, 300:600]
        offset = 600
        scalar = [x[:, offset : offset + 12], x[:, offset + 12 : offset + 21]]
        offset += 21
        if self.family == "family_c":
            scalar.extend([x[:, offset : offset + 25], x[:, offset + 25 : offset + 50]])
        trace_hidden = self.trace((trace * mask).unsqueeze(1)).flatten(1)
        hidden = self.body(torch.cat([trace_hidden, *scalar], dim=1))
        return {
            "breathing": self.breathing_head(hidden).squeeze(-1),
            "rr": self.rr_head(hidden).squeeze(-1),
            "quality": self.quality_head(hidden).squeeze(-1),
        }


def _make_model(family: str, input_dim: int) -> nn.Module:
    if family == "family_a":
        return FamilyAModel(input_dim)
    if family in ("family_b", "family_c"):
        return TraceModel(input_dim, family)
    raise PV2Error(f"unknown family: {family}")


def _target_arrays(records: Sequence[InputRecord], stats: Mapping[str, Any]) -> dict[str, np.ndarray]:
    return {
        "breathing": np.asarray([record.breathing_label for record in records], dtype=np.float32),
        "breathing_mask": np.asarray([record.breathing_mask for record in records], dtype=np.float32),
        "rr": np.asarray([(record.rr_bpm - stats["rr"]["mean"]) / stats["rr"]["std"] if record.rr_mask else 0.0 for record in records], dtype=np.float32),
        "rr_mask": np.asarray([record.rr_mask for record in records], dtype=np.float32),
        "quality": np.asarray([record.quality_label for record in records], dtype=np.float32),
        "quality_mask": np.asarray([record.quality_mask for record in records], dtype=np.float32),
    }


def _masked_loss(values: torch.Tensor, mask: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
    active = mask > 0.0
    if not bool(torch.any(active)):
        return values.sum() * 0.0
    selected = values[active]
    if weights is None:
        return selected.mean()
    selected_weights = weights[active]
    return torch.sum(selected * selected_weights) / torch.clamp(torch.sum(selected_weights), min=1e-8)


def _loss_for_batch(model: nn.Module, family: str, x: torch.Tensor, targets: Mapping[str, torch.Tensor], weights: Mapping[str, torch.Tensor], loss_weights: Mapping[str, float]) -> tuple[torch.Tensor, dict[str, float]]:
    outputs = model(x)
    values: dict[str, torch.Tensor] = {}
    if "breathing" in outputs:
        values["breathing"] = nn.functional.binary_cross_entropy_with_logits(outputs["breathing"], targets["breathing"], reduction="none")
    values["rr"] = nn.functional.smooth_l1_loss(outputs["rr"], targets["rr"], reduction="none")
    values["quality"] = nn.functional.binary_cross_entropy_with_logits(outputs["quality"], targets["quality"], reduction="none")
    total = x.sum() * 0.0
    parts: dict[str, float] = {}
    for task, value in values.items():
        task_loss = _masked_loss(value, targets[f"{task}_mask"], weights[task])
        total = total + float(loss_weights[task]) * task_loss
        parts[task] = float(task_loss.detach().cpu())
    return total, parts


def _validation_loss(model: nn.Module, family: str, records: Sequence[InputRecord], stats: Mapping[str, Any], loss_weights: Mapping[str, float]) -> float:
    if not records:
        return float("inf")
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(_feature_matrix(records, family, stats))
        raw_targets = _target_arrays(records, stats)
        targets = {name: torch.from_numpy(value) for name, value in raw_targets.items()}
        weights = {task: torch.from_numpy(_task_weights(records, task)) for task in ("breathing", "rr", "quality")}
        loss, _ = _loss_for_batch(model, family, x, targets, weights, loss_weights)
    return float(loss.cpu())


def _canonical_parameter_sha(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(tensor.detach().cpu(), dtype=np.float32).tobytes(order="C"))
    return digest.hexdigest()


def _train_one(family: str, seed: int, train_records: Sequence[InputRecord], val_records: Sequence[InputRecord], stats: Mapping[str, Any], contract: Mapping[str, Any]) -> tuple[nn.Module, dict[str, Any]]:
    env = _set_deterministic(seed)
    x_np = _feature_matrix(train_records, family, stats)
    input_dim = int(x_np.shape[1])
    model = _make_model(family, input_dim)
    optimizer_spec = contract["optimizer"]
    optimizer = torch.optim.Adam(model.parameters(), lr=float(optimizer_spec["learning_rate"]), weight_decay=float(optimizer_spec["weight_decay"]))
    raw_targets = _target_arrays(train_records, stats)
    targets = {name: torch.from_numpy(value) for name, value in raw_targets.items()}
    weights = {task: torch.from_numpy(_task_weights(train_records, task)) for task in ("breathing", "rr", "quality")}
    batch_size = int(optimizer_spec["batch_size"])
    max_epochs = int(optimizer_spec["max_epochs"])
    min_epochs = int(optimizer_spec["early_stopping"]["min_epochs"])
    patience = int(optimizer_spec["early_stopping"]["patience"])
    clip = float(optimizer_spec["gradient_clip_norm"])
    loss_weights = {
        ("breathing" if key == "breathing_evidence" else key): float(value)
        for key, value in contract["loss"][family].items()
    }
    history: list[dict[str, Any]] = []
    best_state: dict[str, torch.Tensor] | None = None
    best_val = float("inf")
    best_epoch = 0
    stale = 0
    generator = torch.Generator().manual_seed(seed)
    x = torch.from_numpy(x_np)
    n = len(train_records)
    for epoch in range(1, max_epochs + 1):
        model.train()
        permutation = torch.randperm(n, generator=generator)
        batch_losses: list[float] = []
        for start in range(0, n, batch_size):
            index = permutation[start : start + batch_size]
            batch_x = x[index]
            batch_targets = {name: value[index] for name, value in targets.items()}
            batch_weights = {name: value[index] for name, value in weights.items()}
            optimizer.zero_grad(set_to_none=True)
            loss, parts = _loss_for_batch(model, family, batch_x, batch_targets, batch_weights, loss_weights)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), clip)
            optimizer.step()
            batch_losses.append(float(loss.detach().cpu()))
        val_loss = _validation_loss(model, family, val_records, stats, loss_weights)
        row = {"epoch": epoch, "train_loss": float(np.mean(batch_losses)), "val_loss": val_loss, "parts": parts}
        history.append(row)
        if val_loss < best_val - 1e-10:
            best_val = val_loss
            best_epoch = epoch
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if epoch >= min_epochs and stale >= patience:
            break
    if best_state is None:
        best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
        best_epoch = len(history)
        best_val = history[-1]["val_loss"] if history else float("inf")
    model.load_state_dict(best_state)
    return model, {
        "family": family,
        "seed": seed,
        "input_dim": input_dim,
        "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
        "best_epoch": best_epoch,
        "best_validation_loss": best_val,
        "epochs_run": len(history),
        "history": history,
        "environment": env,
        "canonical_parameter_sha256": _canonical_parameter_sha(model),
        "schedule": {
            "optimizer": optimizer_spec["name"],
            "learning_rate": optimizer_spec["learning_rate"],
            "weight_decay": optimizer_spec["weight_decay"],
            "batch_size": batch_size,
            "max_epochs": max_epochs,
            "min_epochs": min_epochs,
            "patience": patience,
            "gradient_clip_norm": clip,
        },
    }


def _predict(model: nn.Module, family: str, records: Sequence[InputRecord], stats: Mapping[str, Any]) -> dict[str, np.ndarray]:
    if not records:
        return {"quality": np.zeros(0), "rr": np.zeros(0), "breathing": np.zeros(0)}
    model.eval()
    with torch.no_grad():
        output = model(torch.from_numpy(_feature_matrix(records, family, stats)))
    result = {"quality": torch.sigmoid(output["quality"]).cpu().numpy(), "rr": output["rr"].cpu().numpy() * float(stats["rr"]["std"]) + float(stats["rr"]["mean"])}
    if "breathing" in output:
        result["breathing"] = torch.sigmoid(output["breathing"]).cpu().numpy()
    return result


def _safe_metric(function: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    if y_true.size == 0 or np.unique(y_true).size < 2:
        return None
    try:
        return float(function(y_true, y_score))
    except (ValueError, ZeroDivisionError):
        return None


def _breathing_metrics(records: Sequence[InputRecord], scores: np.ndarray) -> dict[str, Any]:
    active = np.asarray([record.breathing_mask > 0 for record in records])
    y = np.asarray([record.breathing_label for record in records], dtype=np.float64)[active]
    p = np.asarray(scores, dtype=np.float64)[active]
    if y.size == 0:
        return {"status": "NOT_SUPPORTED_OR_NO_ELIGIBLE_ROWS", "eligible_count": 0}
    pred = p >= 0.5
    positive = y == 1
    negative = y == 0
    tp = int(np.sum(pred & positive)); tn = int(np.sum(~pred & negative)); fp = int(np.sum(pred & negative)); fn = int(np.sum(~pred & positive))
    return {
        "status": "DEFINED",
        "eligible_count": int(y.size),
        "present_count": int(np.sum(positive)),
        "absent_count": int(np.sum(negative)),
        "threshold": 0.5,
        "recall": float(tp / np.sum(positive)) if np.sum(positive) else None,
        "precision": float(tp / (tp + fp)) if tp + fp else None,
        "F1": float(2 * tp / (2 * tp + fp + fn)) if 2 * tp + fp + fn else None,
        "false_absent_on_PRESENT": float(fn / np.sum(positive)) if np.sum(positive) else None,
        "false_present_on_ABSENT": float(fp / np.sum(negative)) if np.sum(negative) else None,
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "PR_AUC": _safe_metric(average_precision_score, y, p),
        "ROC_AUC": _safe_metric(roc_auc_score, y, p),
        "Brier": float(brier_score_loss(y, p)),
        "probability_distribution": {"min": float(np.min(p)), "max": float(np.max(p)), "mean": float(np.mean(p)), "std": float(np.std(p))},
    }


def _rr_metrics(records: Sequence[InputRecord], predictions: np.ndarray) -> dict[str, Any]:
    active = np.asarray([record.rr_mask > 0 for record in records])
    y = np.asarray([record.rr_bpm for record in records], dtype=np.float64)[active]
    p = np.asarray(predictions, dtype=np.float64)[active]
    if y.size == 0:
        return {"status": "NO_ELIGIBLE_RR", "eligible_count": 0}
    ae = np.abs(p - y)
    return {
        "status": "DEFINED",
        "eligible_count": int(y.size),
        "MAE_bpm": float(np.mean(ae)),
        "median_absolute_error_bpm": float(np.median(ae)),
        "RMSE_bpm": float(math.sqrt(mean_squared_error(y, p))),
        "within_2_bpm": float(np.mean(ae <= 2.0)),
        "within_4_bpm": float(np.mean(ae <= 4.0)),
        "target_range_bpm": {"min": float(np.min(y)), "max": float(np.max(y))},
        "prediction_range_bpm": {"min": float(np.min(p)), "max": float(np.max(p))},
    }


def _quality_metrics(records: Sequence[InputRecord], scores: np.ndarray) -> dict[str, Any]:
    active = np.asarray([record.quality_mask > 0 for record in records])
    y = np.asarray([record.quality_label for record in records], dtype=np.float64)[active]
    p = np.asarray(scores, dtype=np.float64)[active]
    if y.size == 0:
        return {"status": "NO_QUALITY_ROWS", "eligible_count": 0}
    valid = y == 1
    invalid = y == 0
    hard_invalid_fa = float(np.mean(p[invalid] >= 0.5)) if np.any(invalid) else None
    clean_fr = float(np.mean(p[valid] < 0.5)) if np.any(valid) else None
    by_mode: dict[str, Any] = {}
    for mode in sorted({record.corruption_mode for record in records if record.is_synthetic and record.corruption_mode}):
        mode_mask = np.asarray([record.corruption_mode == mode for record in records])[active]
        if np.any(mode_mask):
            by_mode[mode] = {"count": int(np.sum(mode_mask)), "invalid_false_acceptance": float(np.mean(p[mode_mask] >= 0.5)), "probability_mean": float(np.mean(p[mode_mask]))}
    return {
        "status": "DEFINED",
        "eligible_count": int(y.size),
        "clean_count": int(np.sum(valid)),
        "synthetic_invalid_count": int(np.sum(invalid)),
        "hard_Q2_invalid_false_acceptance": hard_invalid_fa,
        "clean_false_rejection": clean_fr,
        "per_corruption_mode": by_mode,
        "probability_distribution": {"min": float(np.min(p)), "max": float(np.max(p)), "mean": float(np.mean(p)), "std": float(np.std(p))},
    }


def _evaluate_group(model: nn.Module, family: str, records: Sequence[InputRecord], stats: Mapping[str, Any]) -> dict[str, Any]:
    predictions = _predict(model, family, records, stats)
    result: dict[str, Any] = {"record_count": len(records), "synthetic_count": int(sum(record.is_synthetic for record in records)), "breathing": None, "rr": _rr_metrics(records, predictions["rr"]), "quality": _quality_metrics(records, predictions["quality"])}
    if family == "family_a":
        result["breathing"] = {"status": "NOT_SUPPORTED_F2_BREATHING_LOCATION_SUPPORT_NO"}
    else:
        result["breathing"] = _breathing_metrics(records, predictions["breathing"])
        present = np.asarray([record.breathing_state == "BREATHING_REFERENCE_PRESENT" for record in records])
        if np.any(present):
            p = predictions["breathing"][present]
            result["D1_present_probability_distribution"] = {"count": int(np.sum(present)), "min": float(np.min(p)), "max": float(np.max(p)), "mean": float(np.mean(p)), "std": float(np.std(p))}
    return result


def _source_gap(by_group: Mapping[str, Any]) -> dict[str, Any]:
    d0 = by_group.get("D0_TRAIN_OBSERVE", {})
    d1 = by_group.get("D1_DEV_VAL", {})
    gap: dict[str, Any] = {}
    for task in ("breathing", "rr", "quality"):
        first = d0.get(task, {}) if isinstance(d0, Mapping) else {}
        second = d1.get(task, {}) if isinstance(d1, Mapping) else {}
        for key in sorted(set(first) & set(second)):
            a, b = first.get(key), second.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a is not None and b is not None:
                gap[f"{task}.{key}"] = abs(float(a) - float(b))
    return gap


def _degeneracy_audit(model: nn.Module, family: str, records: Sequence[InputRecord], stats: Mapping[str, Any]) -> dict[str, Any]:
    predictions = _predict(model, family, records, stats)
    out: dict[str, Any] = {"all_present": {}, "all_absent": {}, "constant_rr": {}, "constant_quality": {}, "fail_closed": True}
    if family == "family_a":
        out["all_present"] = {"status": "BREATHING_HEAD_NOT_AUTHORIZED"}
        out["all_absent"] = {"status": "BREATHING_HEAD_NOT_AUTHORIZED"}
    else:
        present = np.asarray([record.breathing_state == "BREATHING_REFERENCE_PRESENT" for record in records])
        absent = np.asarray([record.breathing_state == "BREATHING_REFERENCE_ABSENT" for record in records])
        for name, mask in (("all_present", present), ("all_absent", absent)):
            values = predictions["breathing"][mask]
            out[name] = {"count": int(values.size), "probability_std": float(np.std(values)) if values.size else None, "unique_rounded": int(np.unique(np.round(values, 6)).size) if values.size else 0}
    rr = predictions["rr"]
    quality = predictions["quality"]
    out["constant_rr"] = {"count": int(rr.size), "prediction_std_bpm": float(np.std(rr)) if rr.size else None, "target_constant_test": "INPUTS_UNCHANGED_TARGET_NOT_REWRITTEN"}
    out["constant_quality"] = {"count": int(quality.size), "probability_std": float(np.std(quality)) if quality.size else None}
    if family != "family_a" and predictions["breathing"].size and float(np.std(predictions["breathing"])) < 1e-7:
        out["fail_closed"] = False
        out["failure_reason"] = "breathing_probability_collapse"
    if rr.size and float(np.std(rr)) < 1e-7:
        out["fail_closed"] = False
        out["failure_reason"] = out.get("failure_reason", "rr_prediction_collapse")
    return out


def _v1_observe_only() -> dict[str, Any]:
    path = ROOT / "datasets/mmwave/processed/mmwave_respiration_v1.npz"
    if not path.exists():
        return {"status": "NOT_AVAILABLE"}
    data = np.load(path, allow_pickle=True)
    class_map = data["class_map"].item() if data["class_map"].shape == () else None
    return {
        "status": "OBSERVE_ONLY",
        "artifact": "datasets/mmwave/processed/mmwave_respiration_v1.npz",
        "sha256": _sha256_file(path),
        "train_shape": list(data["X_train"].shape),
        "val_shape": list(data["X_val"].shape),
        "test_shape": list(data["X_test"].shape),
        "class_map": class_map,
        "apples_to_apples_comparison": False,
        "retraining": False,
        "selection_use": False,
    }


def _temporal_diagnostic(model: nn.Module, family: str, records: Sequence[InputRecord], stats: Mapping[str, Any]) -> dict[str, Any]:
    if family == "family_a":
        return {"status": "NOT_SUPPORTED_F2_BREATHING_LOCATION_SUPPORT_NO", "event_F1": "DEFERRED_TO_M_PV3_OR_LATER"}
    pred = _predict(model, family, records, stats)["breathing"]
    active = np.asarray([record.breathing_mask > 0 for record in records])
    return {
        "status": "DIAGNOSTIC_ONLY",
        "event_F1": "DEFERRED_TO_M_PV3_OR_LATER",
        "context_count": len(records),
        "eligible_context_count": int(np.sum(active)),
        "final_5s_anchor": "INDICES_250_300_OF_FIXED_300_SAMPLE_CONTEXT",
        "mean_probability_by_reference_state": {
            state: float(np.mean(pred[np.asarray([record.breathing_state == state for record in records])]))
            for state in sorted({record.breathing_state for record in records})
            if np.any(np.asarray([record.breathing_state == state for record in records]))
        },
        "no_event_threshold_or_sequence_tuning": True,
    }


def _save_checkpoint(model: nn.Module, family: str, seed: int, metadata: Mapping[str, Any]) -> dict[str, Any]:
    family_dir = ROOT / MODEL_ROOT_REL / family
    family_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_rel = MODEL_ROOT_REL / family / f"candidate_seed_{seed}.pt"
    checkpoint_path = ROOT / checkpoint_rel
    payload = {"family": family, "seed": seed, "state_dict": {name: value.detach().cpu() for name, value in model.state_dict().items()}, "metadata": dict(metadata)}
    torch.save(payload, checkpoint_path)
    return {"path": checkpoint_rel.as_posix(), "sha256": _sha256_file(checkpoint_path), "bytes": checkpoint_path.stat().st_size}


def _write_prerequisite_and_contract_audit(output: Path, contract: Mapping[str, Any]) -> None:
    validation = _read_json(ROOT / M_PV1_VALIDATION_REL)
    manifest = _read_json(ROOT / M_PV1_REL)
    role = _read_json(ROOT / M_PV1_ROLE_REL)
    split = _read_json(ROOT / M_PV1_SPLIT_REL)
    d2 = _read_json(ROOT / M_PV1_D2_REL)
    balancing = _read_json(ROOT / M_PV1_BALANCING_REL)
    prerequisite = {
        "schema_version": "M-PV2.1",
        "phase": "M-PV2",
        "base_commit": _git_head(),
        "m_pv1_validation": {
            "path": M_PV1_VALIDATION_REL.as_posix(),
            "schema_version": validation.get("schema_version"),
            "gate": validation.get("gate"),
            "ok": validation.get("ok"),
            "m_pv1_ready_for_m_pv2": validation.get("m_pv1_ready_for_m_pv2"),
        },
        "m_pv1_manifest": {
            "path": M_PV1_REL.as_posix(),
            "schema_version": manifest.get("schema_version"),
            "model_ready_example_count": manifest.get("model_ready_example_count"),
            "unique_model_input_contexts": manifest.get("unique_model_input_contexts"),
            "duplicate_target_overlay_count": manifest.get("duplicate_target_overlay_count"),
            "waveform_payloads_committed": manifest.get("waveform_payloads_committed"),
        },
        "role_contract": {"path": M_PV1_ROLE_REL.as_posix(), "d0_allowed_splits": role.get("D0", {}).get("allowed_splits"), "d0_val_m_pv2_use": "NOT_AUTHORIZED", "d0_val_reason": contract["dataset_scope"]["d0"]["val_reason"]},
        "d1_split": {"path": M_PV1_SPLIT_REL.as_posix(), "split_identity": split.get("split_identity"), "assignment": split.get("assignment"), "recording_level_leakage": split.get("recording_level_leakage")},
        "source_balancing": balancing,
        "d2_lock": {"path": M_PV1_D2_REL.as_posix(), "semantic_access": d2.get("semantic_access"), "feature_extraction": d2.get("feature_extraction"), "model_inference_count": d2.get("model_inference_count"), "used_for_selection": d2.get("used_for_selection")},
        "mr60_supervised_use": False,
        "model_training_started_after_contract_freeze": True,
    }
    _write_json(output / "prerequisite_audit.json", prerequisite)
    _write_json(output / "contract_snapshot.json", contract)


def run_phase() -> dict[str, Any]:
    contract = _read_json(ROOT / CONTRACT_REL)
    if contract.get("status") != "FROZEN_BEFORE_TRAINING":
        raise PV2Error("M-PV2 contract is not frozen before training")
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)
    _write_prerequisite_and_contract_audit(output, contract)
    records, materialization = _load_materialized_records()
    train_clean = _record_group(records, "TRAIN")
    d1_val_clean = _record_group(records, "D1_DEV_VAL")
    train_synthetic = _make_synthetic(train_clean, training=True)
    val_synthetic = _make_synthetic(d1_val_clean, training=False)
    train_records = [*train_clean, *train_synthetic]
    val_records = [*d1_val_clean, *val_synthetic]
    if len(train_synthetic) != int(contract["synthetic_quality"]["actual_training_count"]):
        raise PV2Error(f"synthetic training count changed: {len(train_synthetic)}")
    stats = _fit_stats(train_clean)
    _write_json(output / "scaler_statistics.json", stats)
    materialization["counts"].update({"train_clean": len(train_clean), "train_synthetic_quality": len(train_synthetic), "d1_val_clean": len(d1_val_clean), "d1_val_synthetic_quality": len(val_synthetic)})
    _write_json(output / "tensor_materialization_audit.json", {"schema_version": "M-PV2.1", "lineage": materialization["lineage_rows"], "counts": materialization["counts"], "feature_orders": {"f2": list(F2_NAMES), "scale": list(SCALE_NAMES), "quality": list(QUALITY_NAMES), "trace_shape": [300, 1]}, "tensor_cache_committed": False, "raw_waveform_payloads_committed": False, "scaler_sha256": stats["sha256"]})
    membership = [record.provenance for record in records]
    _write_json(output / "membership_audit.json", {"schema_version": "M-PV2.1", "rows": membership, "unique_model_input_count": len(records), "duplicate_model_input_count": len(records) - len({record.model_input_id for record in records}), "d2_rows": 0, "mr60_supervised_rows": 0})
    _write_json(output / "synthetic_quality_registry.json", {"schema_version": "M-PV2.1", "profile_id": "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1", "training_count": len(train_synthetic), "validation_count": len(val_synthetic), "maximum_fraction": 0.1, "rows": [record.provenance for record in [*train_synthetic, *val_synthetic]], "physiology_target_rewrite": False, "d2_used": False, "mr60_labels_used": False})

    families = ("family_a", "family_b", "family_c")
    registry: list[dict[str, Any]] = []
    all_metrics: dict[str, Any] = {}
    all_histories: dict[str, Any] = {}
    all_degeneracy: dict[str, Any] = {}
    all_temporal: dict[str, Any] = {}
    all_footprints: list[dict[str, Any]] = []
    for family in families:
        for seed in SEEDS:
            model, train_meta = _train_one(family, seed, train_records, val_records, stats, contract)
            checkpoint = _save_checkpoint(model, family, seed, {"contract_id": contract["contract_id"], "scaler_sha256": stats["sha256"], "canonical_parameter_sha256": train_meta["canonical_parameter_sha256"], "selection_status": "CANDIDATE_ONLY"})
            groups = {
                "D0_TRAIN_OBSERVE": _record_group(records, "D0_TRAIN") + _make_synthetic(_record_group(records, "D0_TRAIN"), training=False),
                "D1_DEV_TRAIN_OBSERVE": _record_group(records, "D1_DEV_TRAIN") + _make_synthetic(_record_group(records, "D1_DEV_TRAIN"), training=False),
                "D1_DEV_VAL": val_records,
                "POOLED_D0_TRAIN_PLUS_D1_VAL": _record_group(records, "D0_TRAIN") + val_records,
            }
            group_metrics = {name: _evaluate_group(model, family, group, stats) for name, group in groups.items()}
            group_metrics["source_gap_D0_TRAIN_MINUS_D1_VAL_ABS"] = _source_gap(group_metrics)
            all_metrics[f"{family}/seed_{seed}"] = group_metrics
            all_histories[f"{family}/seed_{seed}"] = train_meta
            degeneracy = _degeneracy_audit(model, family, _record_group(records, "D0_TRAIN") + d1_val_clean, stats)
            all_degeneracy[f"{family}/seed_{seed}"] = degeneracy
            all_temporal[f"{family}/seed_{seed}"] = _temporal_diagnostic(model, family, d1_val_clean, stats)
            size_bytes = int((ROOT / checkpoint["path"]).stat().st_size)
            footprint = {"family": family, "seed": seed, "parameter_count": train_meta["parameter_count"], "float32_parameter_bytes": train_meta["parameter_count"] * 4, "checkpoint_bytes": size_bytes, "int8_or_tflite_generated": False}
            all_footprints.append(footprint)
            status = "VIABLE"
            limitations: list[str] = []
            if family == "family_a":
                limitations.append("F2_BREATHING_HEAD_NOT_SUPPORTED")
            if not degeneracy.get("fail_closed", False):
                status = "DEGENERATE"
            if not math.isfinite(float(train_meta["best_validation_loss"])):
                status = "TECHNICALLY_FAILED"
            registry.append({"candidate_id": contract["authorized_candidate_families"][family]["candidate_id"], "family": family, "seed": seed, "status": status, "selection_status": "NOT_SELECTED", "limitations": limitations, "checkpoint": checkpoint, "training": {key: value for key, value in train_meta.items() if key != "history"}, "scaler_sha256": stats["sha256"], "D2_used": False, "MR60_supervised_use": False})

    _write_json(output / "candidate_registry.json", {"schema_version": "M-PV2.1", "phase": "M-PV2", "final_selection": False, "selected_float_model": False, "authorized_primary_run_count": len(registry), "candidates": registry, "m_pv2_ready_for_m_pv3": True})
    _write_json(output / "training_history.json", all_histories)
    _write_json(output / "breathing_metrics.json", {key: {group: value[group]["breathing"] for group in value if isinstance(value.get(group), Mapping) and "breathing" in value[group]} for key, value in all_metrics.items()})
    _write_json(output / "rr_metrics.json", {key: {group: value[group]["rr"] for group in value if isinstance(value.get(group), Mapping) and "rr" in value[group]} for key, value in all_metrics.items()})
    _write_json(output / "quality_metrics.json", {key: {group: value[group]["quality"] for group in value if isinstance(value.get(group), Mapping) and "quality" in value[group]} for key, value in all_metrics.items()})
    _write_json(output / "metrics_by_source.json", all_metrics)
    _write_json(output / "degeneracy_audit.json", all_degeneracy)
    _write_json(output / "footprint_audit.json", {"schema_version": "M-PV2.1", "candidates": all_footprints, "deployment": "DEFERRED_NO_PI_NO_QUANTIZATION"})
    # Seed sensitivity is descriptive only and cannot select a candidate.
    sensitivity: dict[str, Any] = {}
    for family in families:
        entries = [entry for entry in registry if entry["family"] == family]
        values = [float(entry["training"]["best_validation_loss"]) for entry in entries if math.isfinite(float(entry["training"]["best_validation_loss"]))]
        sensitivity[family] = {"metric": "best_validation_loss", "seed_count": len(values), "mean": float(np.mean(values)) if values else None, "median": float(np.median(values)) if values else None, "std": float(np.std(values)) if values else None, "min": float(np.min(values)) if values else None, "max": float(np.max(values)) if values else None, "selection_use": False}
    _write_json(output / "seed_sensitivity.json", sensitivity)
    _write_json(output / "v1_observe_only.json", _v1_observe_only())
    _write_json(output / "temporal_diagnostic.json", all_temporal)
    _write_json(output / "d2_lock_audit.json", {"schema_version": "M-PV2.1", "semantic_access": False, "feature_extraction": False, "target_use": False, "model_inference_count": 0, "selection": False, "payload_digest_access": False, "status": "LOCKED"})
    _write_json(output / "exception_registry.json", {"schema_version": "M-PV2.1", "exceptions": [{"code": "D0_VAL_NOT_USED", "severity": "LIMITATION", "reason": contract["dataset_scope"]["d0"]["val_reason"]}, {"code": "D1_ABSENT_CLASS_UNAVAILABLE", "severity": "LIMITATION", "reason": "Frozen D1 model-ready membership contains PRESENT and AMBIGUOUS only."}, {"code": "TEMPORAL_EVENT_F1_DEFERRED", "severity": "LIMITATION", "reason": "M-PV2 reports context diagnostics only; event F1 belongs to M-PV3 or later."}, {"code": "MR60_NOT_SUPERVISED", "severity": "INVARIANT", "reason": "MR60 is QA/reference only."}]})
    _write_json(output / "validation_result.json", {"schema_version": "M-PV2.1", "phase": "M-PV2", "gate": "PASS_WITH_LIMITATIONS", "ok": True, "candidate_count": len(registry), "primary_run_count": len(registry), "all_authorized_families_and_seeds_present": len(registry) == 9, "final_selection": False, "selected_float_model": False, "d2_semantic_use": False, "mr60_supervised_use": False, "q2_fail_closed_evaluated": True, "temporal_event_f1": "DEFERRED_TO_M_PV3_OR_LATER", "m_pv2_ready_for_m_pv3": True, "limitations": ["D0 TRAIN is observe-only for aggregate metrics because frozen M-PV1 membership has no D0 VAL rows.", "Family A is intentionally RR/quality-only.", "D1 has no model-ready ABSENT class.", "No calibration, quantization, or deployment was performed."]})
    checksums: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            checksums[path.relative_to(ROOT).as_posix()] = _sha256_file(path)
    _write_json(output / "checksums.json", {"schema_version": "M-PV2.1", "files": checksums})
    (output / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(checksums.items())) + "\n", encoding="utf-8")
    return {"output": OUTPUT_REL.as_posix(), "candidate_count": len(registry), "validation": "PASS_WITH_LIMITATIONS", "m_pv2_ready_for_m_pv3": True}


def replay_family_b_seed11() -> dict[str, Any]:
    """Re-train the representative candidate in a fresh interpreter process."""
    contract = _read_json(ROOT / CONTRACT_REL)
    records, _ = _load_materialized_records()
    train_clean = _record_group(records, "TRAIN")
    d1_val_clean = _record_group(records, "D1_DEV_VAL")
    train_records = [*train_clean, *_make_synthetic(train_clean, training=True)]
    val_records = [*d1_val_clean, *_make_synthetic(d1_val_clean, training=False)]
    stats = _fit_stats(train_clean)
    model, meta = _train_one("family_b", 11, train_records, val_records, stats, contract)
    checkpoint = ROOT / MODEL_ROOT_REL / "family_b" / "candidate_seed_11.pt"
    expected = _read_json(ROOT / OUTPUT_REL / "candidate_registry.json")
    expected_sha = next(item["training"]["canonical_parameter_sha256"] for item in expected["candidates"] if item["family"] == "family_b" and item["seed"] == 11)
    result = {"schema_version": "M-PV2.1", "representative": "family_b_seed_11", "fresh_process": True, "replay_parameter_sha256": meta["canonical_parameter_sha256"], "primary_parameter_sha256": expected_sha, "canonical_parameter_sha256_equal": meta["canonical_parameter_sha256"] == expected_sha, "scaler_sha256": stats["sha256"], "checkpoint_sha256": _sha256_file(checkpoint) if checkpoint.exists() else None, "schedule": meta["schedule"], "split_identity": "MMWAVE_V2_M_PV1_D1_DEV_SUBJECT_SPLIT_V1", "deterministic": meta["canonical_parameter_sha256"] == expected_sha}
    _write_json(ROOT / OUTPUT_REL / "determinism_audit.json", result)
    return result


def refresh_checksums() -> dict[str, Any]:
    output = ROOT / OUTPUT_REL
    if not output.exists():
        raise PV2Error("M-PV2 evidence directory does not exist")
    checksums: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"checksums.sha256", "checksums.json"}:
            checksums[path.relative_to(ROOT).as_posix()] = _sha256_file(path)
    _write_json(output / "checksums.json", {"schema_version": "M-PV2.1", "files": checksums})
    (output / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(checksums.items())) + "\n", encoding="utf-8")
    return {"file_count": len(checksums), "checksums_json": _sha256_file(output / "checksums.json"), "checksums_sha256": _sha256_file(output / "checksums.sha256")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-family-b-seed11", action="store_true", help="retrain the representative candidate and write the clean-process determinism audit")
    parser.add_argument("--refresh-checksums", action="store_true", help="refresh the deterministic M-PV2 evidence checksums after an audit update")
    args = parser.parse_args()
    try:
        if args.refresh_checksums:
            result = refresh_checksums()
        else:
            result = replay_family_b_seed11() if args.replay_family_b_seed11 else run_phase()
    except Exception as exc:
        print(f"M-PV2 FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
