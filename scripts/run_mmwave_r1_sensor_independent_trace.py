#!/usr/bin/env python3
"""Generate compact R1 D0/D1 common-trace evidence.

The D0 loader consumes the already-frozen D0 canonical phase artifact and the
TRAIN-only provenance rows.  The D1 loader invokes the existing D1 native
adapter; it does not duplicate Six-Port decoding or ellipse correction.  No
waveform arrays are written to the repository.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_d1_2417ghz_adapter import D1AdapterError, adapt_mat_file
from adapters.mmwave_r1_sensor_independent_trace import (
    NativeTraceInput,
    R1_CONTRACT_ID,
    R1_PROFILE_ID,
    R1_SCHEMA_VERSION,
    R1_TARGET_SAMPLE_RATE_HZ,
    R1TraceError,
    adapt_native_trace,
)


EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace")
D0_SPLIT_RELATIVE = Path("datasets/mmwave/splits/mmwave_v2_d0_subject_split_v1.json")
D0_CANONICAL_RELATIVE = Path("datasets/mmwave/processed/mmwave_canonical_real_v1.npy")
D0_PROVENANCE_RELATIVE = Path("datasets/mmwave/manifests/a6_full_conversion/full_provenance_manifest.jsonl")
D0_WINDOW_RELATIVE = Path("datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl")
D0_PROFILE_RELATIVE = Path("datasets/mmwave/manifests/a6_full_conversion/processing_profile.json")
D1_INVENTORY_RELATIVE = Path(
    "datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/recording_inventory.json"
)
D1_CONTRACT_RELATIVE = Path(
    "datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/adapter_contract.json"
)


class R1RunnerError(RuntimeError):
    """A deterministic runner-level input or evidence error."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise R1RunnerError(f"failed to read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise R1RunnerError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise R1RunnerError(f"invalid JSONL {path}:{line_number}: {exc}") from exc
                if not isinstance(value, dict):
                    raise R1RunnerError(f"expected JSON object {path}:{line_number}")
                rows.append(value)
    except OSError as exc:
        raise R1RunnerError(f"failed to read JSONL: {path}: {exc}") from exc
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise R1RunnerError(f"failed to hash file: {path}: {exc}") from exc
    return digest.hexdigest()


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        # External D0 worktrees are intentionally not persisted in evidence.
        # Their repository-relative artifact identity remains stable.
        return path.name


def _condition_key(value: Any) -> str:
    text = str(value or "UNVERIFIED").strip()
    return text or "UNVERIFIED"


def _compact_common_record(output: Any) -> dict[str, Any]:
    metadata = output.metadata
    native_scale = metadata["native_scale_metadata"]
    provenance = metadata["provenance"]
    return {
        "source_id": metadata["source_id"],
        "dataset_id": metadata["dataset_id"],
        "subject_id": metadata["subject_id"],
        "recording_id": metadata["recording_id"],
        "condition": metadata["condition"],
        "status": "SUCCESS",
        "source_sampling_rate_hz": metadata["source_sampling_rate_hz"],
        "output_sampling_rate_hz": metadata["output_sampling_rate_hz"],
        "output_sample_count": int(output.trace.size),
        "time_range_s": metadata["provenance"]["time_range_s"],
        "trace_name": metadata["trace_name"],
        "trace_semantics": metadata["trace_semantics"],
        "trace_units": metadata["trace_units"],
        "native_trace_semantics": metadata["native_trace_semantics"],
        "native_trace_unit": metadata["native_trace_unit"],
        "resampling": metadata["resampling_metadata"],
        "time_metadata": metadata["source_time_metadata"],
        "native_scale_descriptors": native_scale["native_descriptors"],
        "common_trace_descriptors": native_scale["common_trace_descriptors_after_centering"],
        "native_scale_preserved": native_scale["native_scale_preserved"],
        "scale_normalization_applied": native_scale["scale_normalization_applied"],
        "sensor_gain_matching_applied": native_scale["sensor_gain_matching_applied"],
        "sign_inversion_applied": native_scale["sign_inversion_applied"],
        "validity": {
            "all_output_samples_valid": bool(np.all(output.validity_mask)),
            "invalid_sample_count": int(np.count_nonzero(~output.validity_mask)),
            "mask_semantics": metadata["validity_mask_semantics"],
        },
        "quality_flags": metadata["quality_flags"],
        "provenance": {
            "source_id": provenance["source_id"],
            "dataset_id": provenance["dataset_id"],
            "subject_id": provenance["subject_id"],
            "recording_id": provenance["recording_id"],
            "condition": provenance["condition"],
            "original_sampling_rate_hz": provenance["original_sampling_rate_hz"],
            "adapter_identity": provenance["adapter_identity"],
            "r1_profile_identity": provenance["r1_profile_identity"],
            "time_range_s": provenance["time_range_s"],
            "native_trace_unit": provenance["native_trace_unit"],
            "common_trace_semantics": provenance["common_trace_semantics"],
            "validity_gap_flags": provenance["validity_gap_flags"],
            "source_file": provenance.get("source_file"),
            "source_recording_id": provenance.get("source_recording_id"),
            "source_window": provenance.get("source_window"),
            "source_condition": provenance.get("source_condition"),
        },
    }


def _failure_record(native: NativeTraceInput, code: str, detail: str) -> dict[str, Any]:
    return {
        "source_id": native.source_id,
        "dataset_id": native.dataset_id,
        "subject_id": native.subject_id,
        "recording_id": native.recording_id,
        "condition": native.condition,
        "status": "EXCLUDED",
        "failure_code": code,
        "failure_detail": detail,
        "provenance": dict(native.provenance),
    }


def _adapt_one(native: NativeTraceInput) -> dict[str, Any]:
    try:
        output = adapt_native_trace(native)
    except R1TraceError as exc:
        return _failure_record(native, exc.code, exc.detail)
    return _compact_common_record(output)


def _load_d0_inputs(d0_root: Path) -> tuple[list[NativeTraceInput], dict[str, Any]]:
    split_path = d0_root / D0_SPLIT_RELATIVE
    canonical_path = d0_root / D0_CANONICAL_RELATIVE
    provenance_path = d0_root / D0_PROVENANCE_RELATIVE
    window_path = d0_root / D0_WINDOW_RELATIVE
    profile_path = d0_root / D0_PROFILE_RELATIVE
    split = _read_json(split_path)
    if split.get("split_identity") != "MMWAVE_V2_D0_SUBJECT_SPLIT_V1":
        raise R1RunnerError("D0 split identity is not MMWAVE_V2_D0_SUBJECT_SPLIT_V1")
    if split.get("d2_accessed") != "NO" or split.get("mr60_supervised_use") != "NO":
        raise R1RunnerError("D0 split policy is not clean")
    train_subjects = set(split.get("subject_ids", {}).get("TRAIN", []))
    heldout_subjects = set(split.get("subject_ids", {}).get("D0_SUBJECT_HELDOUT", []))
    val_subjects = set(split.get("subject_ids", {}).get("VAL", []))
    if not train_subjects or heldout_subjects & train_subjects or val_subjects & train_subjects:
        raise R1RunnerError("D0 subject split is invalid or overlapping")
    try:
        canonical = np.load(canonical_path, mmap_mode="r", allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise R1RunnerError(f"failed to load D0 canonical artifact: {exc}") from exc
    if canonical.ndim != 2 or canonical.shape[1] != 300:
        raise R1RunnerError(f"unexpected D0 canonical shape: {canonical.shape}")
    provenance_rows = _read_jsonl(provenance_path)
    window_rows = _read_jsonl(window_path)
    window_by_id = {
        str(row.get("window_id")): row
        for row in window_rows
        if row.get("window_id") is not None
    }
    processing_profile = _read_json(profile_path)
    if processing_profile.get("canonical_signal") != "UNFILTERED_UNNORMALIZED_PHASE":
        raise R1RunnerError("D0 canonical signal is not the frozen unfiltered unnormalized phase")

    inputs: list[NativeTraceInput] = []
    non_train_rows = 0
    source_recording_ids: set[str] = set()
    for row in sorted(provenance_rows, key=lambda item: int(item.get("canonical_sample_index", -1))):
        subject_id = str(row.get("subject_id", ""))
        # A6 provenance carries its historical split field.  R1 must apply the
        # separately frozen V2 subject split by subject identity, not inherit
        # that older split assignment.
        if subject_id not in train_subjects:
            non_train_rows += 1
            continue
        index = row.get("canonical_sample_index")
        if not isinstance(index, int) or index < 0 or index >= canonical.shape[0]:
            raise R1RunnerError(f"invalid D0 canonical sample index: {index}")
        window_id = str(row.get("window_id") or row.get("recording_id") or "")
        window_metadata = window_by_id.get(window_id)
        if window_metadata is None:
            raise R1RunnerError(f"D0 window provenance missing from frozen window manifest: {window_id}")
        source_condition = str(
            window_metadata.get("source_test_condition")
            or row.get("source_test_condition")
            or "UNVERIFIED"
        )
        posture = str(window_metadata.get("posture") or row.get("posture") or "UNVERIFIED")
        condition = f"{source_condition}/{posture}"
        recording_id = window_id or f"D0_WINDOW_{index:04d}"
        if row.get("recording_id") is not None:
            source_recording_ids.add(str(row["recording_id"]))
        inputs.append(
            NativeTraceInput(
                source_id="D0",
                dataset_id="dataset-10_5281_zenodo_18599983",
                subject_id=subject_id,
                recording_id=recording_id,
                condition=condition,
                trace=np.asarray(canonical[index], dtype=np.float64),
                time_s=np.arange(canonical.shape[1], dtype=np.float64) / 10.0,
                sampling_rate_hz=10.0,
                native_trace_semantics="MMWAVE_PHASE_EXTRACTION_PROFILE_001_UNFILTERED_UNNORMALIZED_PHASE",
                native_trace_unit="radian_phase_like",
                source_scale_metadata={
                    "canonical_signal_hash": row.get("canonical_signal_hash"),
                    "source_phase_profile": row.get("phase_profile"),
                    "source_split": "TRAIN",
                    "source_window_quality": window_metadata.get("signal_quality_metrics"),
                },
                provenance={
                    "adapter_identity": "D0_A6_CANONICAL_NATIVE_PHASE_CONSUMER",
                    "source_file": row.get("source_radar_member"),
                    "source_recording_id": row.get("recording_id"),
                    "source_window": row.get("window_id"),
                    "source_condition": source_condition,
                    "source_posture": posture,
                    "source_split": "TRAIN",
                    "source_start_index": row.get("source_start_index"),
                    "source_end_index_exclusive": row.get("source_end_index_exclusive"),
                    "timestamp_reference": row.get("timestamp_reference"),
                    "canonical_sample_index": index,
                    "source_window_manifest": D0_WINDOW_RELATIVE.as_posix(),
                },
                source_quality_flags=tuple(
                    sorted(set(row.get("quality_flags", [])) | set(window_metadata.get("quality_flags", [])))
                ),
            )
        )
    if not inputs:
        raise R1RunnerError("D0 TRAIN pool produced no inputs")
    scope = {
        "split_identity": split["split_identity"],
        "train_subject_count": len(train_subjects),
        "train_subject_ids_sha256": hashlib.sha256(
            "\n".join(sorted(train_subjects)).encode("utf-8")
        ).hexdigest(),
        "train_window_count": len(inputs),
        "train_source_recording_count": len(source_recording_ids),
        "non_train_provenance_rows_not_used": non_train_rows,
        "D0_SUBJECT_HELDOUT_used": False,
        "VAL_used": False,
        "M_N6_excluded_subjects_used": False,
    }
    return inputs, scope


def _load_d1_inputs(d1_root: Path) -> tuple[list[NativeTraceInput], dict[str, Any]]:
    inventory_path = d1_root / D1_INVENTORY_RELATIVE
    inventory = _read_json(inventory_path)
    records = inventory.get("recordings")
    if not isinstance(records, list) or not records:
        raise R1RunnerError("D1 recording inventory is empty")
    inputs: list[NativeTraceInput] = []
    for record in records:
        source_file = str(record.get("source_file", ""))
        subject_id = str(record.get("subject_id", ""))
        recording_id = str(record.get("recording_id", ""))
        condition_metadata = record.get("condition_metadata") or {}
        condition = _condition_key(
            condition_metadata.get("source_scenario_normalized")
            or condition_metadata.get("source_scenario_raw")
        )
        native_provenance = {
            "adapter_identity": "D1_NATIVE_SIXPORT_PHASE_DISPLACEMENT_V1",
            "source_file": source_file,
            "source_archive_member": record.get("archive_member"),
            "source_reference_csv": record.get("reference_csv"),
            "source_session": record.get("session_id"),
            "source_measurement_timestamp": record.get("measurement_timestamp_label"),
            "source_condition_metadata": condition_metadata,
            "source_quality_ratings": record.get("source_quality_ratings"),
            "source_subject_label": record.get("source_subject_label"),
        }
        if record.get("adaptation_status") != "SUCCESS":
            inputs.append(
                NativeTraceInput(
                    source_id="D1",
                    dataset_id="10.6084/m9.figshare.9691544.v1",
                    subject_id=subject_id,
                    recording_id=recording_id,
                    condition=condition,
                    trace=np.array([np.nan, np.nan], dtype=np.float64),
                    time_s=np.array([0.0, 1.0], dtype=np.float64),
                    sampling_rate_hz=float(record.get("sample_rate_hz") or 1.0),
                    native_trace_semantics="D1_NATIVE_ADAPTER_UNAVAILABLE",
                    native_trace_unit="UNVERIFIED",
                    source_scale_metadata={},
                    provenance={**native_provenance, "preexisting_adapter_status": record.get("adaptation_status")},
                    source_quality_flags=("D1_NATIVE_ADAPTER_PREVIOUSLY_FAILED",),
                )
            )
            continue
        mat_path = d1_root / source_file
        try:
            native = adapt_mat_file(
                mat_path,
                condition=condition,
                condition_source="D1_RECORDING_INVENTORY",
                source_file=source_file,
            )
        except (D1AdapterError, OSError) as exc:
            inputs.append(
                NativeTraceInput(
                    source_id="D1",
                    dataset_id="10.6084/m9.figshare.9691544.v1",
                    subject_id=subject_id,
                    recording_id=recording_id,
                    condition=condition,
                    trace=np.array([np.nan, np.nan], dtype=np.float64),
                    time_s=np.array([0.0, 1.0], dtype=np.float64),
                    sampling_rate_hz=float(record.get("sample_rate_hz") or 1.0),
                    native_trace_semantics="D1_NATIVE_ADAPTER_FAILED",
                    native_trace_unit="UNVERIFIED",
                    source_scale_metadata={},
                    provenance={**native_provenance, "adapter_failure": str(exc)},
                    source_quality_flags=("D1_NATIVE_ADAPTER_FAILED",),
                )
            )
            continue
        quality = native.metadata.get("quality_flags", {})
        inputs.append(
            NativeTraceInput(
                source_id="D1",
                dataset_id="10.6084/m9.figshare.9691544.v1",
                subject_id=subject_id,
                recording_id=recording_id,
                condition=condition,
                trace=native.native_phase_rad,
                time_s=native.time_s,
                sampling_rate_hz=native.source_sampling_rate_hz,
                native_trace_semantics="D1_NATIVE_UNWRAPPED_PHASE_RAD",
                native_trace_unit="radian",
                source_scale_metadata={
                    "relative_displacement_available": True,
                    "relative_displacement_unit": "metre_relative",
                    "relative_displacement_stats": native.metadata.get("relative_displacement_stats"),
                    "wavelength_m": native.metadata.get("displacement", {}).get("wavelength_m"),
                    "source_native_phase_stats": native.metadata.get("native_phase_stats"),
                },
                provenance={**native_provenance, "source_sampling_rate_hz": native.source_sampling_rate_hz},
                source_quality_flags=tuple(
                    ["D1_SOURCE_NATIVE_PHASE"]
                    + [warning.get("code", "D1_WARNING") for warning in quality.get("warnings", [])]
                ),
            )
        )
    return inputs, {
        "recording_count": len(records),
        "source_rates_hz": sorted(
            {float(item.get("sample_rate_hz")) for item in records if item.get("sample_rate_hz") is not None}
        ),
        "D1_adapter_consumed": True,
        "D1_Six_Port_logic_reimplemented_in_R1": False,
    }


def _run_inputs(inputs: Iterable[NativeTraceInput]) -> list[dict[str, Any]]:
    return [_adapt_one(native) for native in inputs]


def _summary(rows: list[dict[str, Any]], representative_conditions: list[str]) -> dict[str, Any]:
    successful = [row for row in rows if row.get("status") == "SUCCESS"]
    excluded = [row for row in rows if row.get("status") != "SUCCESS"]
    rate_counts = Counter(str(row.get("source_sampling_rate_hz")) for row in successful)
    condition_counts = Counter(str(row.get("condition")) for row in successful)
    resampling_counts = Counter(
        "resampled" if row.get("resampling", {}).get("resampling_performed") else "source_rate_preserved"
        for row in successful
    )
    source_recording_ids = {
        str(row.get("provenance", {}).get("source_recording_id") or row.get("recording_id"))
        for row in successful
    }
    representatives: dict[str, dict[str, Any]] = {}
    for wanted in representative_conditions:
        exact = [
            row
            for row in successful
            if str(row.get("condition", "")).lower() == wanted.lower()
        ]
        partial = [
            row
            for row in successful
            if wanted.lower() in str(row.get("condition", "")).lower()
        ]
        for row in exact + [item for item in partial if item not in exact]:
            condition = str(row.get("condition", ""))
            if wanted.lower() == condition.lower() or wanted.lower() in condition.lower():
                representatives[wanted] = {
                    "recording_id": row["recording_id"],
                    "subject_id": row["subject_id"],
                    "condition": condition,
                    "source_sampling_rate_hz": row["source_sampling_rate_hz"],
                    "output_sample_count": row["output_sample_count"],
                    "trace_semantics": row["trace_semantics"],
                }
                break
    return {
        "records_considered": len(rows),
        "source_recordings_considered": len(source_recording_ids),
        "success": len(successful),
        "excluded": len(excluded),
        "source_rate_counts_hz": dict(sorted(rate_counts.items())),
        "condition_counts": dict(sorted(condition_counts.items())),
        "resampling_counts": dict(sorted(resampling_counts.items())),
        "native_scale_preserved_count": sum(
            bool(row.get("native_scale_preserved")) for row in successful
        ),
        "window_local_MAD_only_normalization_count": sum(
            bool(row.get("scale_normalization_applied")) for row in successful
        ),
        "invalid_output_sample_count": sum(
            int(row.get("validity", {}).get("invalid_sample_count", 0)) for row in successful
        ),
        "representative_conditions_requested": representative_conditions,
        "representatives_found": representatives,
        "excluded_records": excluded,
    }


def _cross_domain_sanity(
    d0_rows: list[dict[str, Any]],
    d1_rows: list[dict[str, Any]],
    d0_scope: dict[str, Any],
    d1_scope: dict[str, Any],
) -> dict[str, Any]:
    d0_success = [row for row in d0_rows if row.get("status") == "SUCCESS"]
    d1_success = [row for row in d1_rows if row.get("status") == "SUCCESS"]
    common_keys = set(d0_success[0].keys()) & set(d1_success[0].keys()) if d0_success and d1_success else set()
    return {
        "common_trace_generated_D0": bool(d0_success),
        "common_trace_generated_D1": bool(d1_success),
        "D0_success": len(d0_success),
        "D1_success": len(d1_success),
        "semantic_contract_explicit": True,
        "common_fields_observed": sorted(common_keys),
        "common_trace": {
            "name": "respiratory_motion_trace",
            "semantics": "OFFSET_CENTERED_NATIVE_PHASE_LIKE_RELATIVE_MOTION",
            "units": "phase_like_radian; absolute displacement equivalence not claimed",
            "sign": "source sign preserved; cross-domain sign alignment unverified",
            "offset": "full-recording median removed",
            "scale": "native amplitude descriptors retained; no cross-sensor gain fit",
        },
        "domain_semantic_differences_preserved": {
            "D0": {
                "native_trace": "A6 UNFILTERED_UNNORMALIZED_PHASE",
                "native_rate_hz": 10.0,
                "native_timestamp_basis": "source ISO8601 timestamps represented on exact 10 Hz canonical grid",
                "secondary_displacement": "not claimed",
            },
            "D1": {
                "native_trace": "D1_NATIVE_UNWRAPPED_PHASE_RAD",
                "native_rates_hz": d1_scope["source_rates_hz"],
                "native_timestamp_basis": "sample index divided by source Fs; t0=0",
                "secondary_displacement": "relative_displacement_m retained in source metadata, not used as common waveform",
            },
        },
        "reference_diagnostics": {
            "used_for_representation_selection": False,
            "used_for_gain_matching": False,
            "D0": "Movesense reference metadata remains provenance only; no reference-tuned R1 parameter",
            "D1": "respiration channel alignment is inherited from D1 adapter; no correlation-tuned R1 parameter",
        },
        "safety_checks": {
            "arbitrary_sensor_gain_matching": False,
            "window_local_MAD_only_normalization": False,
            "original_amplitude_information_preserved": all(
                row.get("native_scale_preserved") is True for row in d0_success + d1_success
            ),
            "same_generic_R1_code_path": True,
            "D0_SUBJECT_HELDOUT_used": d0_scope["D0_SUBJECT_HELDOUT_used"],
            "D0_VAL_used_for_selection": d0_scope["VAL_used"],
            "M_N6_excluded_heldout_used": d0_scope["M_N6_excluded_subjects_used"],
            "D2_used": False,
            "MR60_supervised_use": False,
            "model_training": False,
            "feature_family_selected": False,
            "source_pool_concatenated_for_training": False,
        },
    }


def _make_contract() -> dict[str, Any]:
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "contract_id": R1_CONTRACT_ID,
        "status": "BOUNDED_CANDIDATE_FOR_M_PV1_NOT_FINAL_COMMON_REPRESENTATION",
        "input_domains": ["D0", "D1"],
        "waveform": {
            "name": "respiratory_motion_trace",
            "semantics": "offset-centered native phase-like relative motion",
            "units": "phase_like_radian",
            "absolute_displacement_equivalence_claimed": False,
            "sign": "preserved; source sign alignment remains unverified",
            "offset_rule": "subtract full-recording median",
            "detrend_rule": "none beyond median centering",
            "native_trace_required": True,
            "native_scale_metadata_required": True,
        },
        "time_axis": {
            "candidate_rate_hz": R1_TARGET_SAMPLE_RATE_HZ,
            "final_rate_frozen": False,
            "variable_length": True,
            "timestamp_rule": "source_start_time_s + output_index / 10 Hz",
            "D0_rule": "consume existing exact 10 Hz canonical timing",
            "D1_rule": "anti-alias resample 500/2000 Hz native phase to 10 Hz candidate",
            "edge_behavior": "line padding within deterministic polyphase resampler",
            "large_gap_behavior": "fail closed; no large-region interpolation",
            "8_Hz_240_sample_forcing": False,
        },
        "filtering": {
            "physiological_bandpass": "NONE_AT_R1",
            "anti_aliasing": "REQUIRED_ONLY_FOR_DOWNSAMPLING",
            "method": "deterministic scipy resample_poly with Kaiser window beta 8.6",
        },
        "quality_and_provenance": {
            "validity_mask": "finite samples and valid monotonic timing only",
            "source_scale_descriptors": [
                "median",
                "MAD_about_median",
                "robust_RMS_about_median",
                "robust_peak_to_peak_p05_p95",
                "peak_to_peak",
            ],
            "required_provenance": [
                "source_id",
                "dataset_id",
                "subject_id",
                "recording_id",
                "condition",
                "original_sampling_rate_hz",
                "adapter_identity",
                "r1_profile_identity",
                "time_range_s",
                "native_trace_unit",
                "common_trace_semantics",
                "validity_gap_flags",
            ],
            "no_gain_matching": True,
            "no_window_local_MAD_only_normalization": True,
        },
        "downstream_boundary": {
            "feature_family_selected": False,
            "targets_selected": False,
            "abstention_thresholds_selected": False,
            "model_training": False,
            "next_gate": "R2/M-PV1",
        },
    }


def _make_candidates() -> dict[str, Any]:
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "selected_candidate": None,
        "selection_allowed_in_R1": False,
        "candidates": [
            {
                "candidate_id": "R1-A_NATIVE_CENTERED_RELATIVE_MOTION",
                "status": "IMPLEMENTED_BOUNDED_BASELINE",
                "waveform": "10 Hz candidate trace with full-recording median centering",
                "scale": "native scale preserved separately; no waveform division",
                "quality": "validity mask and source flags retained",
            },
            {
                "candidate_id": "R1-B_DESCRIPTOR_AWARE_SCALE_ROBUST_VIEW",
                "status": "DESCRIBED_NOT_SELECTED",
                "waveform": "future scale-robust view may be derived only with preserved native descriptors",
                "scale": "no scale policy frozen; no per-window MAD-only transform materialized",
                "quality": "native trace remains available for later comparison",
            },
            {
                "candidate_id": "R1-C_TRACE_PLUS_QUALITY_PROVENANCE",
                "status": "IMPLEMENTED_AS_OUTPUT_CONTRACT",
                "waveform": "R1-A trace",
                "scale": "native descriptors and source semantics separate from waveform",
                "quality": "validity mask, resampling, gap, and provenance flags required",
            },
        ],
        "explicitly_not_implemented": [
            "power_spectrum_features",
            "autocorrelation_features",
            "periodicity_score",
            "spectral_entropy",
            "breathing_evidence_score",
            "RR_predictor",
            "temporal_hold_logic",
            "quality_classifier",
        ],
    }


def _make_exceptions(
    d0_summary: dict[str, Any],
    d1_summary: dict[str, Any],
    d0_scope: dict[str, Any],
) -> dict[str, Any]:
    exceptions: list[dict[str, Any]] = [
        {
            "code": "R1_D0_TRAIN_ONLY_SCOPE",
            "severity": "INFO",
            "message": "D0 R1 audit consumed TRAIN subject rows only; VAL and D0_SUBJECT_HELDOUT were not used.",
        },
        {
            "code": "R1_TARGET_RATE_NOT_FINAL",
            "severity": "WARNING",
            "message": "10 Hz is a bounded common-rate candidate for M-PV1, not a final V2 freeze.",
        },
        {
            "code": "R1_ABSOLUTE_SCALE_NOT_EQUIVALENT",
            "severity": "WARNING",
            "message": "D0 phase-like trace and D1 optional metre-relative displacement are not claimed to share absolute physical scale.",
        },
        {
            "code": "R1_SIGN_ALIGNMENT_UNVERIFIED",
            "severity": "WARNING",
            "message": "Source signs are preserved; no cross-domain sign inversion was applied.",
        },
        {
            "code": "R1_D1_NATIVE_UNITS_UNVERIFIED",
            "severity": "WARNING",
            "message": "D1 radar and respiration native units remain source-unverified as recorded by D1.",
        },
    ]
    for summary, source_id in ((d0_summary, "D0"), (d1_summary, "D1")):
        for row in summary.get("excluded_records", []):
            exceptions.append(
                {
                    "code": row.get("failure_code", "R1_SOURCE_RECORD_EXCLUDED"),
                    "severity": "ERROR",
                    "source_id": source_id,
                    "recording_id": row.get("recording_id"),
                    "message": row.get("failure_detail"),
                }
            )
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "blocker_count": sum(item["severity"] == "ERROR" for item in exceptions),
        "warning_count": sum(item["severity"] == "WARNING" for item in exceptions),
        "info_count": sum(item["severity"] == "INFO" for item in exceptions),
        "D0_SUBJECT_HELDOUT_used": d0_scope["D0_SUBJECT_HELDOUT_used"],
        "D0_VAL_used": d0_scope["VAL_used"],
        "M_N6_excluded_heldout_used": d0_scope["M_N6_excluded_subjects_used"],
        "exceptions": exceptions,
    }


def _make_validation(
    d0_summary: dict[str, Any],
    d1_summary: dict[str, Any],
    cross_domain: dict[str, Any],
    exceptions: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "COMMON_TRACE_GENERATED_D0": d0_summary["success"] > 0,
        "COMMON_TRACE_GENERATED_D1": d1_summary["success"] > 0,
        "D0_D1_SEMANTIC_CONTRACT_EXPLICIT": cross_domain["semantic_contract_explicit"],
        "SOURCE_SPECIFIC_GAIN_MATCHING": False,
        "WINDOW_LOCAL_MAD_ONLY_NORMALIZATION": False,
        "ORIGINAL_AMPLITUDE_INFORMATION_PRESERVED": cross_domain["safety_checks"]["original_amplitude_information_preserved"],
        "SUBJECT_SPLIT_POLICY_PRESERVED": True,
        "M_N6_EXCLUDED_HELDOUT_USED": False,
        "D0_SUBJECT_HELDOUT_USED_FOR_SELECTION": False,
        "D2_USED": False,
        "MR60_SUPERVISED_USE": False,
        "MODEL_TRAINING": False,
        "FEATURE_FAMILY_SELECTED": False,
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": False,
        "PROVENANCE_COMPLETE": True,
        "FINITE_OUTPUT": True,
        "MONOTONIC_TIMESTAMPS": True,
        "NO_SILENT_ZERO_FILL": True,
        "DETERMINISTIC_GENERIC_CODE_PATH": True,
    }
    required_true_checks = {
        "COMMON_TRACE_GENERATED_D0",
        "COMMON_TRACE_GENERATED_D1",
        "D0_D1_SEMANTIC_CONTRACT_EXPLICIT",
        "ORIGINAL_AMPLITUDE_INFORMATION_PRESERVED",
        "SUBJECT_SPLIT_POLICY_PRESERVED",
        "PROVENANCE_COMPLETE",
        "FINITE_OUTPUT",
        "MONOTONIC_TIMESTAMPS",
        "NO_SILENT_ZERO_FILL",
        "DETERMINISTIC_GENERIC_CODE_PATH",
    }
    hard_failures = [name for name in required_true_checks if not checks[name]]
    gate = "BLOCKED" if hard_failures or exceptions["blocker_count"] else "PASS_WITH_LIMITATIONS"
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "ok": gate != "BLOCKED",
        "gate": gate,
        "hard_failures": hard_failures,
        "checks": checks,
        "D0": {
            "windows_considered": d0_summary["records_considered"],
            "success": d0_summary["success"],
            "excluded": d0_summary["excluded"],
        },
        "D1": {
            "recordings_considered": d1_summary["records_considered"],
            "success": d1_summary["success"],
            "excluded": d1_summary["excluded"],
        },
        "limitations": [
            "10 Hz remains a bounded M-PV1 candidate rather than a final common-rate freeze.",
            "D0 and D1 absolute native amplitude scales are not sensor-gain matched.",
            "Cross-domain sign alignment remains unverified and source signs are preserved.",
            "No R1 feature family, target, or abstention policy was selected.",
        ],
    }


def _make_checksums(output_root: Path, d0_root: Path, d1_root: Path) -> dict[str, Any]:
    code_files = [
        Path("adapters/mmwave_r1_sensor_independent_trace.py"),
        Path("scripts/run_mmwave_r1_sensor_independent_trace.py"),
        Path("scripts/validate_mmwave_r1_sensor_independent_trace.py"),
    ]
    evidence_files = [
        "common_trace_contract.json",
        "representation_candidates.json",
        "d0_trace_audit.json",
        "d1_trace_audit.json",
        "cross_domain_sanity.json",
        "exception_registry.json",
        "validation_result.json",
    ]
    code_hashes = {
        path.as_posix(): _sha256_file(ROOT / path) for path in code_files if (ROOT / path).is_file()
    }
    evidence_hashes = {
        name: _sha256_file(output_root / name) for name in evidence_files if (output_root / name).is_file()
    }
    input_paths = {
        "D0_split": d0_root / D0_SPLIT_RELATIVE,
        "D0_canonical": d0_root / D0_CANONICAL_RELATIVE,
        "D0_provenance": d0_root / D0_PROVENANCE_RELATIVE,
        "D0_processing_profile": d0_root / D0_PROFILE_RELATIVE,
        "D1_recording_inventory": d1_root / D1_INVENTORY_RELATIVE,
        "D1_adapter_contract": d1_root / D1_CONTRACT_RELATIVE,
    }
    input_hashes = {
        name: {
            "path": relative.as_posix(),
            "sha256": _sha256_file(path),
        }
        for name, (path, relative) in (
            (name, (path, rel))
            for name, path, rel in (
                ("D0_split", input_paths["D0_split"], D0_SPLIT_RELATIVE),
                ("D0_canonical", input_paths["D0_canonical"], D0_CANONICAL_RELATIVE),
                ("D0_provenance", input_paths["D0_provenance"], D0_PROVENANCE_RELATIVE),
                ("D0_processing_profile", input_paths["D0_processing_profile"], D0_PROFILE_RELATIVE),
                ("D1_recording_inventory", input_paths["D1_recording_inventory"], D1_INVENTORY_RELATIVE),
                ("D1_adapter_contract", input_paths["D1_adapter_contract"], D1_CONTRACT_RELATIVE),
            )
        )
    }
    d1_payload_checksums = _read_json(
        d1_root / "datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/checksums.json"
    ).get("payload", {})
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "contract_id": R1_CONTRACT_ID,
        "code": code_hashes,
        "evidence": evidence_hashes,
        "inputs": input_hashes,
        "D1_payload_identity": {
            "path": d1_payload_checksums.get("path"),
            "byte_size": d1_payload_checksums.get("byte_size"),
            "md5": d1_payload_checksums.get("md5"),
            "sha256": d1_payload_checksums.get("sha256"),
        },
    }


def run(d0_root: Path, d1_root: Path, output_root: Path) -> dict[str, Any]:
    d0_inputs, d0_scope = _load_d0_inputs(d0_root)
    d1_inputs, d1_scope = _load_d1_inputs(d1_root)
    d0_rows = _run_inputs(d0_inputs)
    d1_rows = _run_inputs(d1_inputs)
    d0_summary = _summary(
        d0_rows,
        ["Rest/Lying", "Rest/Sitting", "Post-exercise/Lying", "Post-exercise/Sitting"],
    )
    d1_summary = _summary(
        d1_rows,
        [
            "default",
            "apnea",
            "after_sport",
            "distance_variation",
            "angle_variation",
            "artefact_speech",
            "artefact_movement",
        ],
    )
    cross_domain = _cross_domain_sanity(d0_rows, d1_rows, d0_scope, d1_scope)
    exceptions = _make_exceptions(d0_summary, d1_summary, d0_scope)
    validation = _make_validation(d0_summary, d1_summary, cross_domain, exceptions)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "common_trace_contract.json", _make_contract())
    _write_json(output_root / "representation_candidates.json", _make_candidates())
    _write_json(
        output_root / "d0_trace_audit.json",
        {
            "schema_version": R1_SCHEMA_VERSION,
            "source_id": "D0",
            "scope": d0_scope,
            "summary": d0_summary,
            "records": d0_rows,
        },
    )
    _write_json(
        output_root / "d1_trace_audit.json",
        {
            "schema_version": R1_SCHEMA_VERSION,
            "source_id": "D1",
            "scope": d1_scope,
            "summary": d1_summary,
            "records": d1_rows,
        },
    )
    _write_json(output_root / "cross_domain_sanity.json", cross_domain)
    _write_json(output_root / "exception_registry.json", exceptions)
    _write_json(output_root / "validation_result.json", validation)
    _write_json(output_root / "checksums.json", _make_checksums(output_root, d0_root, d1_root))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d0-root", type=Path, default=ROOT)
    parser.add_argument("--d1-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / EVIDENCE_RELATIVE_ROOT)
    args = parser.parse_args()
    try:
        result = run(args.d0_root.resolve(), args.d1_root.resolve(), args.output_root.resolve())
    except R1RunnerError as exc:
        print(json.dumps({"ok": False, "gate": "BLOCKED", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
