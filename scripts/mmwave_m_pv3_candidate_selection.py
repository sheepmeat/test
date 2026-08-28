#!/usr/bin/env python3
"""Evaluate the merged SafeNest mmWave M-PV2 30-second candidate registry.

This phase is deliberately evaluation-only.  It reconstructs the already
frozen M-PV1/M-PV2 inputs, loads the nine committed float checkpoints, and
writes auditable selection evidence.  It never calls a training routine,
creates a model architecture, fits calibration, touches D2/MR60 labels, or
converts/deploys a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import mmwave_m_pv2_candidate_training as pv2  # noqa: E402


CONTRACT_REL = Path("config/mmwave/m_pv3_selection_contract.json")
M_PV2_CONTRACT_REL = Path("config/mmwave/m_pv2_candidate_training_contract.json")
M_PV2_REGISTRY_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json")
M_PV2_SCALER_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/scaler_statistics.json")
M_PV2_TENSOR_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/tensor_materialization_audit.json")
M_PV2_MEMBERSHIP_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/membership_audit.json")
M_PV2_D2_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/d2_lock_audit.json")
M_PV2_DETERMINISM_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/determinism_audit.json")
OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV3_candidate_selection")

FAMILIES = ("family_a", "family_b", "family_c")
SEEDS = (11, 23, 47)
Q2_MODES = (
    "SOURCE_FREEZE",
    "LARGE_GAP",
    "STALE_SOURCE",
    "FLAT_EXACT",
    "REPUBLICATION_TO_FREEZE",
)
REQUIRED_PROVENANCE_KEYS = (
    "source_id",
    "subject_id",
    "recording_id",
    "model_input_id",
    "split",
    "context_start_s",
    "context_end_s",
    "target_start_s",
    "target_end_s",
    "r1_profile",
    "r2_profile",
    "breathing_state",
    "breathing_supervision_eligible",
    "rr_supervision_eligible",
    "quality_status",
    "tensor_derivation",
    "synthetic",
)


class PV3Error(RuntimeError):
    """Fail-closed M-PV3 evaluation error."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PV3Error(f"failed to read JSON {path}: {exc}") from exc


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pv2._json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha(path: Path) -> str:
    return pv2._sha256_file(path)


def _json_sha(value: Any) -> str:
    return pv2._sha256_json(value)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_checkpoint(entry: Mapping[str, Any]) -> tuple[Any, dict[str, Any], Path]:
    family = str(entry.get("family"))
    seed = int(entry.get("seed"))
    training = entry.get("training") if isinstance(entry.get("training"), Mapping) else {}
    input_dim = int(training.get("input_dim", 0))
    if family not in FAMILIES or seed not in SEEDS or input_dim <= 0:
        raise PV3Error(f"invalid candidate identity in registry: {family}/{seed}")
    checkpoint_rel = Path(str(entry.get("checkpoint", {}).get("path", "")))
    checkpoint = ROOT / checkpoint_rel
    expected_root = ROOT / "models/mmwave/m_pv2"
    if not checkpoint.is_file() or not checkpoint.is_relative_to(expected_root):
        raise PV3Error(f"checkpoint missing or outside M-PV2 model root: {checkpoint_rel}")
    try:
        payload = __import__("torch").load(checkpoint, map_location="cpu", weights_only=False)
    except TypeError:  # pragma: no cover - compatibility with older torch
        payload = __import__("torch").load(checkpoint, map_location="cpu")
    if not isinstance(payload, Mapping) or not isinstance(payload.get("state_dict"), Mapping):
        raise PV3Error(f"checkpoint is not an M-PV2 state dictionary: {checkpoint_rel}")
    model = pv2._make_model(family, input_dim)
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except (RuntimeError, ValueError) as exc:
        raise PV3Error(f"tensor state incompatible for {family}/{seed}: {exc}") from exc
    model.eval()
    metadata = dict(payload.get("metadata", {})) if isinstance(payload.get("metadata"), Mapping) else {}
    return model, metadata, checkpoint


def _prediction_sha(predictions: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in ("breathing", "rr", "quality"):
        values = np.asarray(predictions.get(name, np.zeros(0)), dtype=np.float32)
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(values.shape, dtype=np.int64).tobytes())
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _input_sha(records: Sequence[Any]) -> str:
    rows = []
    for record in records:
        rows.append({
            "model_input_id": record.model_input_id,
            "source_id": record.source_id,
            "subject_id": record.subject_id,
            "recording_id": record.recording_id,
            "split": record.split,
            "breathing_mask": float(record.breathing_mask),
            "rr_mask": float(record.rr_mask),
            "quality_mask": float(record.quality_mask),
            "synthetic": bool(record.is_synthetic),
            "corruption_mode": record.corruption_mode,
        })
    return _json_sha(rows)


def _rr_metrics_with_six(records: Sequence[Any], predictions: np.ndarray) -> dict[str, Any]:
    active = np.asarray([float(record.rr_mask) > 0.0 for record in records], dtype=bool)
    y = np.asarray([float(record.rr_bpm) for record in records], dtype=np.float64)[active]
    p = np.asarray(predictions, dtype=np.float64)[active]
    if y.size == 0:
        return {"status": "NO_ELIGIBLE_RR", "eligible_count": 0}
    ae = np.abs(p - y)
    return {
        "status": "DEFINED",
        "eligible_count": int(y.size),
        "MAE_bpm": float(np.mean(ae)),
        "median_absolute_error_bpm": float(np.median(ae)),
        "RMSE_bpm": float(np.sqrt(np.mean((p - y) ** 2))),
        "within_2_bpm": float(np.mean(ae <= 2.0)),
        "within_4_bpm": float(np.mean(ae <= 4.0)),
        "within_6_bpm": float(np.mean(ae <= 6.0)),
        "target_range_bpm": {"min": float(np.min(y)), "max": float(np.max(y))},
        "prediction_range_bpm": {"min": float(np.min(p)), "max": float(np.max(p))},
        "target": "continuous_rr_bpm",
    }


def _ece(records: Sequence[Any], probabilities: np.ndarray, bins: int = 10) -> dict[str, Any]:
    active = np.asarray([float(record.breathing_mask) > 0.0 for record in records], dtype=bool)
    y = np.asarray([float(record.breathing_label) for record in records], dtype=np.float64)[active]
    p = np.asarray(probabilities, dtype=np.float64)[active]
    if y.size == 0:
        return {"status": "NOT_DEFINED", "eligible_count": 0, "bins": bins}
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    total = 0.0
    for index in range(bins):
        lower, upper = float(edges[index]), float(edges[index + 1])
        mask = (p >= lower) & ((p < upper) if index < bins - 1 else (p <= upper))
        count = int(np.sum(mask))
        if count:
            confidence = float(np.mean(p[mask]))
            accuracy = float(np.mean(y[mask]))
            gap = abs(confidence - accuracy)
            total += gap * count / y.size
            rows.append({"bin": index, "lower": lower, "upper": upper, "count": count, "confidence": confidence, "accuracy": accuracy, "gap": gap})
        else:
            rows.append({"bin": index, "lower": lower, "upper": upper, "count": 0, "confidence": None, "accuracy": None, "gap": None})
    return {"status": "DIAGNOSTIC_ONLY", "eligible_count": int(y.size), "bins": bins, "ECE": float(total), "rows": rows}


def _evaluate_group(model: Any, family: str, records: Sequence[Any], stats: Mapping[str, Any], *, include_quality_gate: bool = True) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    predictions = pv2._predict(model, family, records, stats)
    breathing = {"status": "NOT_SUPPORTED_F2_BREATHING_LOCATION_SUPPORT_NO"} if family == "family_a" else pv2._breathing_metrics(records, predictions["breathing"])
    if family != "family_a":
        breathing["calibration_ece"] = _ece(records, predictions["breathing"])
    rr = _rr_metrics_with_six(records, predictions["rr"])
    quality = pv2._quality_metrics(records, predictions["quality"])
    result: dict[str, Any] = {
        "record_count": len(records),
        "clean_count": int(sum(not record.is_synthetic for record in records)),
        "synthetic_count": int(sum(record.is_synthetic for record in records)),
        "breathing": breathing,
        "rr": rr,
        "quality": quality,
    }
    if include_quality_gate:
        invalid = np.asarray([record.is_synthetic and record.quality_status == "INPUT_UNAVAILABLE" for record in records], dtype=bool)
        clean = np.asarray([not record.is_synthetic and record.quality_status == "CLEAN" for record in records], dtype=bool)
        quality_probability = np.asarray(predictions["quality"], dtype=np.float64)
        exposed_invalid = int(np.sum(quality_probability[invalid] >= 0.5)) if np.any(invalid) else 0
        result["consumer_quality_gate"] = {
            "cutoff": 0.5,
            "invalid_input_count": int(np.sum(invalid)),
            "invalid_input_physiology_exposed_count": exposed_invalid,
            "invalid_input_physiology_suppressed_count": int(np.sum(invalid)) - exposed_invalid,
            "clean_input_count": int(np.sum(clean)),
            "physiology_exposure_rule": "quality_probability >= 0.5",
            "raw_physiology_heads_not_consumer_visible_when_quality_invalid": True,
        }
    return result, predictions


def _make_validation_records(records: Sequence[Any]) -> tuple[list[Any], list[Any], list[Any]]:
    d1_val = pv2._record_group(records, "D1_DEV_VAL")
    d0_train = pv2._record_group(records, "D0_TRAIN")
    clean_sorted = sorted(d1_val, key=lambda record: record.model_input_id)
    q2 = [pv2._quality_synthetic(base, mode, index) for index, (base, mode) in enumerate(zip(clean_sorted, Q2_MODES))]
    return d1_val, d0_train, q2


def _provenance_audit(records: Sequence[Any], membership: Mapping[str, Any], d2_lock: Mapping[str, Any]) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    absolute: list[str] = []
    ids: list[str] = []
    for record in records:
        provenance = record.provenance if isinstance(record.provenance, Mapping) else {}
        ids.append(record.model_input_id)
        for key in REQUIRED_PROVENANCE_KEYS:
            if key not in provenance:
                missing.append({"model_input_id": record.model_input_id, "key": key})
        for key, value in provenance.items():
            if isinstance(value, str) and (value.startswith("/") or value.startswith("file://") or value.startswith("~")):
                absolute.append(f"{record.model_input_id}:{key}")
    unique_ids = len(ids) == len(set(ids))
    d2_zero = bool(membership.get("d2_rows", 0) == 0 and d2_lock.get("model_inference_count", 0) == 0 and d2_lock.get("semantic_access") in (False, "NO"))
    return {
        "status": "PASS" if not missing and not absolute and unique_ids and d2_zero else "FAIL",
        "record_count": len(records),
        "unique_model_input_count": len(set(ids)),
        "duplicate_model_input_count": len(ids) - len(set(ids)),
        "missing_required_fields": missing,
        "absolute_or_machine_paths": absolute,
        "d2_rows": membership.get("d2_rows"),
        "d2_lock": {key: d2_lock.get(key) for key in ("semantic_access", "feature_extraction", "model_inference_count", "selection")},
        "provenance_intact": not missing and not absolute and unique_ids,
        "d2_forbidden_access_absent": d2_zero,
    }


def _inventory(contract: Mapping[str, Any], m_pv2_contract: Mapping[str, Any], registry: Mapping[str, Any], stats: Mapping[str, Any], records: Sequence[Any], tensor: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = registry.get("candidates", [])
    expected_keys = {(family, seed) for family in FAMILIES for seed in SEEDS}
    actual_keys = {(str(item.get("family")), int(item.get("seed"))) for item in candidates}
    train_clean = pv2._record_group(records, "TRAIN")
    expected_dims = {family: int(pv2._feature_matrix([train_clean[0]], family, stats).shape[1]) for family in FAMILIES}
    expected_schedules = {
        "optimizer": m_pv2_contract.get("optimizer", {}).get("name"),
        "learning_rate": m_pv2_contract.get("optimizer", {}).get("learning_rate"),
        "weight_decay": m_pv2_contract.get("optimizer", {}).get("weight_decay"),
        "batch_size": m_pv2_contract.get("optimizer", {}).get("batch_size"),
        "max_epochs": m_pv2_contract.get("optimizer", {}).get("max_epochs"),
        "min_epochs": m_pv2_contract.get("optimizer", {}).get("early_stopping", {}).get("min_epochs"),
        "patience": m_pv2_contract.get("optimizer", {}).get("early_stopping", {}).get("patience"),
        "gradient_clip_norm": m_pv2_contract.get("optimizer", {}).get("gradient_clip_norm"),
    }
    rows: list[dict[str, Any]] = []
    all_pass = actual_keys == expected_keys and len(candidates) == 9
    for entry in sorted(candidates, key=lambda item: (str(item.get("family")), int(item.get("seed", -1)))):
        family, seed = str(entry.get("family")), int(entry.get("seed"))
        training = entry.get("training") if isinstance(entry.get("training"), Mapping) else {}
        checkpoint_ref = entry.get("checkpoint") if isinstance(entry.get("checkpoint"), Mapping) else {}
        checkpoint_rel = Path(str(checkpoint_ref.get("path", "")))
        checkpoint = ROOT / checkpoint_rel
        checkpoint_exists = checkpoint.is_file() and checkpoint.is_relative_to(ROOT / "models/mmwave/m_pv2")
        actual_file_sha = _file_sha(checkpoint) if checkpoint_exists else None
        bytes_match = bool(checkpoint_exists and int(checkpoint_ref.get("bytes", -1)) == checkpoint.stat().st_size)
        sha_match = bool(checkpoint_exists and str(checkpoint_ref.get("sha256")) == actual_file_sha)
        model = None
        metadata: dict[str, Any] = {}
        load_error = None
        state_ok = False
        canonical_sha = None
        parameter_count = None
        try:
            model, metadata, _ = _load_checkpoint(entry)
            state_ok = True
            canonical_sha = pv2._canonical_parameter_sha(model)
            parameter_count = int(sum(parameter.numel() for parameter in model.parameters()))
        except Exception as exc:  # inventory records the failure and continues
            load_error = str(exc)
        canonical_match = bool(canonical_sha and canonical_sha == training.get("canonical_parameter_sha256"))
        schedule = training.get("schedule") if isinstance(training.get("schedule"), Mapping) else {}
        schedule_normalized = {key: schedule.get(key) for key in expected_schedules}
        schedule_match = schedule_normalized == expected_schedules
        input_dim_match = int(training.get("input_dim", -1)) == expected_dims.get(family)
        parameter_match = parameter_count is not None and parameter_count == int(training.get("parameter_count", -1))
        family_seed_match = family in FAMILIES and seed in SEEDS and training.get("family") == family and int(training.get("seed", -1)) == seed
        contract_match = metadata.get("contract_id") == m_pv2_contract.get("contract_id")
        scaler_match = entry.get("scaler_sha256") == stats.get("sha256") and metadata.get("scaler_sha256") in (None, stats.get("sha256"))
        row_ok = all((checkpoint_exists, bytes_match, sha_match, state_ok, canonical_match, schedule_match, input_dim_match, parameter_match, family_seed_match, contract_match, scaler_match))
        all_pass = all_pass and row_ok
        rows.append({
            "candidate_id": entry.get("candidate_id"),
            "family": family,
            "seed": seed,
            "checkpoint": {
                "path": checkpoint_rel.as_posix(),
                "exists_under_m_pv2_root": checkpoint_exists,
                "bytes_expected": checkpoint_ref.get("bytes"),
                "bytes_actual": checkpoint.stat().st_size if checkpoint_exists else None,
                "bytes_match": bytes_match,
                "sha256_expected": checkpoint_ref.get("sha256"),
                "sha256_actual": actual_file_sha,
                "sha256_match": sha_match,
            },
            "load": {"state_dict_compatible": state_ok, "canonical_parameter_sha256": canonical_sha, "canonical_sha256_match": canonical_match, "error": load_error},
            "training_config": {
                "family_seed_identity_match": family_seed_match,
                "input_dim_expected": expected_dims.get(family),
                "input_dim_registry": training.get("input_dim"),
                "input_dim_match": input_dim_match,
                "parameter_count_expected": parameter_count,
                "parameter_count_registry": training.get("parameter_count"),
                "parameter_count_match": parameter_match,
                "schedule_expected": expected_schedules,
                "schedule_registry": schedule_normalized,
                "schedule_match": schedule_match,
                "m_pv2_contract_id_match": contract_match,
                "scaler_sha256_match": scaler_match,
            },
            "tensor_contract_compatible": row_ok,
            "selection_eligible_for_metric_evaluation": state_ok and input_dim_match,
        })
    provenance = _provenance_audit(records, _read(ROOT / M_PV2_MEMBERSHIP_REL), _read(ROOT / M_PV2_D2_REL))
    inventory = {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "lane": "30S_CANDIDATE_ONLY",
        "selection_contract_id": contract.get("contract_id"),
        "m_pv2_registry_path": _relative(ROOT / M_PV2_REGISTRY_REL),
        "registry_phase": registry.get("phase"),
        "registry_final_selection": registry.get("final_selection"),
        "registry_selected_float_model": registry.get("selected_float_model"),
        "authorized_candidate_count": 9,
        "observed_candidate_count": len(candidates),
        "authorized_family_seed_keys": sorted([f"{family}/seed_{seed}" for family, seed in sorted(expected_keys)]),
        "observed_family_seed_keys": sorted([f"{family}/seed_{seed}" for family, seed in sorted(actual_keys)]),
        "expected_input_dimensions": expected_dims,
        "m_pv2_scaler_sha256": stats.get("sha256"),
        "tensor_materialization_counts": tensor.get("counts", {}),
        "provenance_audit": provenance,
        "candidates": rows,
        "all_inventory_checks_pass": all_pass and provenance.get("status") == "PASS",
        "evaluation_only": True,
        "training_invocations": 0,
        "d2_access": False,
        "mr60_supervised_physiology": False,
    }
    return inventory, {"expected_dims": expected_dims, "provenance": provenance}


def _load_and_evaluate_candidates(contract: Mapping[str, Any], registry: Mapping[str, Any], records: Sequence[Any], stats: Mapping[str, Any], inventory: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    d1_val, d0_train, q2 = _make_validation_records(records)
    primary_records = [*d1_val, *q2]
    d0_records = [*d0_train, *[pv2._quality_synthetic(base, mode, index) for index, (base, mode) in enumerate(zip(sorted(d0_train, key=lambda record: record.model_input_id), Q2_MODES))]]
    audits: list[dict[str, Any]] = []
    predictions_for_replay: dict[str, np.ndarray] | None = None
    replay_input = [*d1_val, *q2]
    for entry in sorted(registry.get("candidates", []), key=lambda item: (str(item.get("family")), int(item.get("seed", -1)))):
        family, seed = str(entry.get("family")), int(entry.get("seed"))
        row_inventory = next((row for row in inventory.get("candidates", []) if row.get("family") == family and row.get("seed") == seed), {})
        model, metadata, checkpoint = _load_checkpoint(entry)
        validation, validation_predictions = _evaluate_group(model, family, primary_records, stats)
        clean_validation, _ = _evaluate_group(model, family, d1_val, stats, include_quality_gate=False)
        d0_observe, _ = _evaluate_group(model, family, d0_records, stats)
        replay_predictions = _predict_for_replay(model, family, replay_input, stats)
        if family == "family_b" and seed == 11:
            predictions_for_replay = replay_predictions
        breathing = validation.get("breathing", {})
        rr = validation.get("rr", {})
        quality = validation.get("quality", {})
        consumer_gate = validation.get("consumer_quality_gate", {})
        safety_checks = {
            "checkpoint_integrity": bool(row_inventory.get("checkpoint", {}).get("sha256_match")),
            "canonical_parameter_hash": bool(row_inventory.get("load", {}).get("canonical_sha256_match")),
            "provenance_intact": bool(inventory.get("provenance_audit", {}).get("provenance_intact")),
            "d2_and_mr60_forbidden_access_absent": bool(inventory.get("provenance_audit", {}).get("d2_forbidden_access_absent")),
            "quality_handling_present": "quality" in validation and "consumer_quality_gate" in validation,
            "q2_invalid_physiology_not_exposed": consumer_gate.get("invalid_input_physiology_exposed_count") == 0,
            "q2_all_required_modes_evaluated": sorted(quality.get("per_corruption_mode", {}).keys()) == sorted(Q2_MODES),
            "clean_false_rejection_limit": quality.get("clean_false_rejection") is not None and float(quality.get("clean_false_rejection")) <= 0.10,
            "unavailable_inputs_not_used_as_physiology": all(float(record.breathing_mask) == 0.0 and float(record.rr_mask) == 0.0 for record in q2),
        }
        safety_pass = all(bool(value) for value in safety_checks.values())
        if family == "family_a":
            utility_checks = {"family_has_breathing_head": False, "family_a_support_limitation": True}
            utility_pass = False
        else:
            utility_checks = {
                "family_has_breathing_head": True,
                "present_recall": breathing.get("recall") is not None and float(breathing.get("recall")) >= 0.95,
                "brier": breathing.get("Brier") is not None and float(breathing.get("Brier")) <= 0.05,
                "rr_mae": rr.get("MAE_bpm") is not None and float(rr.get("MAE_bpm")) <= 5.0,
                "rr_within_2": rr.get("within_2_bpm") is not None and float(rr.get("within_2_bpm")) >= 0.40,
                "rr_within_4": rr.get("within_4_bpm") is not None and float(rr.get("within_4_bpm")) >= 0.60,
                "rr_within_6": rr.get("within_6_bpm") is not None and float(rr.get("within_6_bpm")) >= 0.75,
            }
            utility_pass = all(bool(value) for value in utility_checks.values())
        audits.append({
            "candidate_id": entry.get("candidate_id"),
            "candidate_key": f"{family}/seed_{seed}",
            "architecture": family,
            "seed": seed,
            "parameter_count": entry.get("training", {}).get("parameter_count"),
            "checkpoint": {"path": _relative(checkpoint), "sha256": _file_sha(checkpoint), "metadata": metadata},
            "validation": {
                "primary_group": "D1_DEV_VAL_PLUS_Q2_EVALUATION",
                "D1_DEV_VAL": clean_validation,
                "D1_DEV_VAL_PLUS_Q2": validation,
                "D0_TRAIN_OBSERVE_PLUS_Q2": d0_observe,
            },
            "safety": {"checks": safety_checks, "pass": safety_pass},
            "utility": {"checks": utility_checks, "pass": utility_pass, "full_task": family in ("family_b", "family_c")},
            "reproducibility": {"canonical_parameter_sha256": row_inventory.get("load", {}).get("canonical_parameter_sha256"), "registry_canonical_sha256": entry.get("training", {}).get("canonical_parameter_sha256"), "checkpoint_sha256_match": row_inventory.get("checkpoint", {}).get("sha256_match"), "prediction_sha256": _prediction_sha(replay_predictions)},
            "selection_eligible": bool(safety_pass and utility_pass),
        })
    if predictions_for_replay is None:
        raise PV3Error("representative family_b/seed_11 was not evaluated")
    metrics = {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "primary_validation_group": "D1_DEV_VAL",
        "q2_evaluation_modes": list(Q2_MODES),
        "candidates": audits,
        "all_nine_reported": len(audits) == 9,
        "training_invocations": 0,
        "retraining": False,
        "d2_used": False,
        "mr60_supervised_physiology": False,
        "calibration_fitting": False,
        "final_threshold_tuning": False,
        "int8_or_tflite": False,
        "representative_replay_input_sha256": _input_sha(replay_input),
        "representative_replay_prediction_sha256": _prediction_sha(predictions_for_replay),
    }
    return metrics, {"d1_val": d1_val, "q2": q2, "replay_input": replay_input, "representative_predictions": predictions_for_replay}


def _predict_for_replay(model: Any, family: str, records: Sequence[Any], stats: Mapping[str, Any]) -> dict[str, np.ndarray]:
    return pv2._predict(model, family, records, stats)


def _seed_sensitivity(audits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for family in FAMILIES:
        rows = [row for row in audits if row.get("architecture") == family]
        def values(path: Sequence[str]) -> list[float]:
            result: list[float] = []
            for row in rows:
                value: Any = row
                for key in path:
                    value = value.get(key) if isinstance(value, Mapping) else None
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    result.append(float(value))
            return result
        measures = {
            "breathing_present_recall": values(("validation", "D1_DEV_VAL", "breathing", "recall")),
            "breathing_brier": values(("validation", "D1_DEV_VAL", "breathing", "Brier")),
            "rr_mae_bpm": values(("validation", "D1_DEV_VAL", "rr", "MAE_bpm")),
            "rr_within_4_bpm": values(("validation", "D1_DEV_VAL", "rr", "within_4_bpm")),
            "rr_within_6_bpm": values(("validation", "D1_DEV_VAL", "rr", "within_6_bpm")),
        }
        output[family] = {}
        for metric, values_list in measures.items():
            output[family][metric] = {"seed_count": len(values_list), "mean": float(np.mean(values_list)) if values_list else None, "median": float(np.median(values_list)) if values_list else None, "std": float(np.std(values_list)) if values_list else None, "min": float(np.min(values_list)) if values_list else None, "max": float(np.max(values_list)) if values_list else None, "selection_use": False}
    return output


def _ranking(metrics: Mapping[str, Any], contract: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    rows = list(metrics.get("candidates", []))
    acceptable = [row for row in rows if row.get("selection_eligible") and row.get("utility", {}).get("full_task")]
    # The sort is descriptive only; it never collapses a Pareto tie into a final selection.
    def key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        breathing = row.get("validation", {}).get("D1_DEV_VAL", {}).get("breathing", {})
        rr = row.get("validation", {}).get("D1_DEV_VAL", {}).get("rr", {})
        return (
            0 if row.get("safety", {}).get("pass") else 1,
            0 if row.get("utility", {}).get("pass") else 1,
            -(float(breathing.get("recall")) if breathing.get("recall") is not None else -1.0),
            float(breathing.get("Brier")) if breathing.get("Brier") is not None else float("inf"),
            float(rr.get("MAE_bpm")) if rr.get("MAE_bpm") is not None else float("inf"),
            -(float(rr.get("within_4_bpm")) if rr.get("within_4_bpm") is not None else -1.0),
            -(float(rr.get("within_6_bpm")) if rr.get("within_6_bpm") is not None else -1.0),
            int(row.get("parameter_count") or 0),
            str(row.get("candidate_key")),
        )
    ordered = sorted(rows, key=key)
    def metric(row: Mapping[str, Any], name: str) -> float:
        breathing = row.get("validation", {}).get("D1_DEV_VAL", {}).get("breathing", {})
        rr = row.get("validation", {}).get("D1_DEV_VAL", {}).get("rr", {})
        values = {
            "recall": breathing.get("recall"),
            "brier": breathing.get("Brier"),
            "mae": rr.get("MAE_bpm"),
            "within4": rr.get("within_4_bpm"),
            "within6": rr.get("within_6_bpm"),
        }
        value = values.get(name)
        if value is None:
            return float("nan")
        return float(value)
    # Strict dominance requires every secondary metric to be at least as good
    # and one to be strictly better.  Safety is already equalized by the gate.
    directions = {"recall": 1, "brier": -1, "mae": -1, "within4": 1, "within6": 1}
    pareto: list[str] = []
    for candidate in acceptable:
        dominated = False
        for other in acceptable:
            if other is candidate:
                continue
            no_worse = True
            strictly_better = False
            for name, direction in directions.items():
                left, right = metric(other, name), metric(candidate, name)
                if not (math.isfinite(left) and math.isfinite(right)):
                    no_worse = False
                    break
                if direction == 1:
                    if left < right - 1e-12:
                        no_worse = False
                        break
                    if left > right + 1e-12:
                        strictly_better = True
                else:
                    if left > right + 1e-12:
                        no_worse = False
                        break
                    if left < right - 1e-12:
                        strictly_better = True
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            pareto.append(str(candidate.get("candidate_key")))
    rank_rows = []
    for index, row in enumerate(ordered, start=1):
        rank_rows.append({
            "rank": index,
            "candidate_key": row.get("candidate_key"),
            "candidate_id": row.get("candidate_id"),
            "safety_pass": row.get("safety", {}).get("pass"),
            "utility_pass": row.get("utility", {}).get("pass"),
            "full_task": row.get("utility", {}).get("full_task"),
            "pareto_front": row.get("candidate_key") in pareto,
            "metrics_used_for_descriptive_order": {
                "breathing_present_recall": metric(row, "recall"),
                "breathing_brier": metric(row, "brier"),
                "rr_mae_bpm": metric(row, "mae"),
                "rr_within_4_bpm": metric(row, "within4"),
                "rr_within_6_bpm": metric(row, "within6"),
                "parameter_count": row.get("parameter_count"),
            },
        })
    ranking = {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "policy": contract.get("ranking_policy"),
        "descriptive_order": rank_rows,
        "acceptable_full_task_candidates": sorted(str(row.get("candidate_key")) for row in acceptable),
        "pareto_front_candidates": sorted(pareto),
        "combined_score": None,
        "selection_use": "PARETO_AND_FROZEN_GATES_ONLY",
    }
    return ranking, sorted(pareto), sorted(str(row.get("candidate_key")) for row in acceptable)


def _selection_decision(contract: Mapping[str, Any], inventory: Mapping[str, Any], metrics: Mapping[str, Any], ranking: Mapping[str, Any], pareto: Sequence[str], acceptable: Sequence[str], determinism: Mapping[str, Any]) -> dict[str, Any]:
    safety_ok = bool(inventory.get("all_inventory_checks_pass")) and bool(determinism.get("deterministic"))
    if not safety_ok:
        result = "NO_SELECTION_READY"
    elif len(pareto) == 1:
        result = "SELECTED_FLOAT_MODEL"
    elif len(pareto) > 1:
        result = "MULTIPLE_ACCEPTABLE_CANDIDATES"
    else:
        result = "NO_SELECTION_READY"
    selected = pareto[0] if result == "SELECTED_FLOAT_MODEL" else None
    if result == "SELECTED_FLOAT_MODEL":
        reason = "One full-task candidate passed every frozen safety/utility gate and was the sole non-dominated candidate."
    elif result == "MULTIPLE_ACCEPTABLE_CANDIDATES":
        reason = "More than one full-task candidate remains on the frozen utility Pareto front; the gate does not force a winner when breathing calibration and RR utility trade off."
    else:
        reason = "The evidence does not support a safe unique selection."
    limitations = [
        "D0 TRAIN is observe-only; the frozen M-PV1 membership has no D0 VAL rows.",
        "D1_DEV_VAL contains PRESENT and AMBIGUOUS rows but no model-ready ABSENT class, so absent-class discrimination is not established.",
        "Q2 corruption cases are deterministic evaluation profiles, not live MR60 captures.",
        "No calibration fitting, production threshold tuning, INT8/TFLite conversion, Pi deployment, or clinical claim was made.",
        "The parallel 15-second lane was intentionally excluded and remains unreviewed here.",
    ]
    return {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "lane": "30S_CANDIDATE_ONLY",
        "selection_contract_id": contract.get("contract_id"),
        "gate": "PASS_WITH_LIMITATIONS" if safety_ok else "BLOCKED",
        "selection_result": result,
        "selected_candidate": selected,
        "shortlist": list(pareto),
        "acceptable_full_task_candidates": list(acceptable),
        "reason": reason,
        "safety_basis": {"inventory_pass": bool(inventory.get("all_inventory_checks_pass")), "determinism_pass": bool(determinism.get("deterministic")), "all_candidates_evaluated": bool(metrics.get("all_nine_reported"))},
        "ready_for_m_pv4": result == "SELECTED_FLOAT_MODEL",
        "shortlist_ready_for_m_pv4_review": bool(result in ("SELECTED_FLOAT_MODEL", "MULTIPLE_ACCEPTABLE_CANDIDATES")),
        "final_production_ready": False,
        "limitations": limitations,
        "15s_lane_status": "EXCLUDED_NOT_WAITED_NOT_MERGED",
        "no_forced_selection": True,
    }


def _determinism_audit(contract: Mapping[str, Any], registry: Mapping[str, Any], stats: Mapping[str, Any], replay_input: Sequence[Any], primary_predictions: Mapping[str, np.ndarray]) -> dict[str, Any]:
    entry = next((item for item in registry.get("candidates", []) if item.get("family") == "family_b" and int(item.get("seed", -1)) == 11), None)
    if entry is None:
        raise PV3Error("representative family_b/seed_11 absent from registry")
    model, _, checkpoint = _load_checkpoint(entry)
    pv2._set_deterministic(0)
    primary_canonical = pv2._canonical_parameter_sha(model)
    primary_prediction_sha = _prediction_sha(primary_predictions)
    primary_checkpoint_sha = _file_sha(checkpoint)
    expected_canonical = entry.get("training", {}).get("canonical_parameter_sha256")
    expected_checkpoint = entry.get("checkpoint", {}).get("sha256")
    config_sha = _file_sha(ROOT / M_PV2_CONTRACT_REL)
    input_sha = _input_sha(replay_input)
    child_env = dict(os.environ)
    child_env.update({"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    command = [sys.executable, str(Path(__file__).resolve()), "--replay-only"]
    child = subprocess.run(command, cwd=ROOT, env=child_env, capture_output=True, text=True, timeout=240, check=False)
    child_result: dict[str, Any] | None = None
    child_error = None
    if child.returncode == 0:
        try:
            child_result = json.loads(child.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            child_error = f"invalid replay JSON: {exc}"
    else:
        child_error = f"replay subprocess exit={child.returncode}: {child.stderr[-1000:]}"
    equalities = {
        "canonical_parameter_sha256_equal": bool(primary_canonical == expected_canonical and child_result and child_result.get("canonical_parameter_sha256") == primary_canonical),
        "checkpoint_sha256_equal": bool(primary_checkpoint_sha == expected_checkpoint and child_result and child_result.get("checkpoint_sha256") == primary_checkpoint_sha),
        "prediction_sha256_equal": bool(child_result and child_result.get("prediction_sha256") == primary_prediction_sha),
        "input_sha256_equal": bool(child_result and child_result.get("input_sha256") == input_sha),
        "scaler_sha256_equal": bool(child_result and child_result.get("scaler_sha256") == stats.get("sha256")),
        "config_sha256_equal": bool(child_result and child_result.get("config_sha256") == config_sha),
    }
    deterministic = all(equalities.values()) and child_result is not None
    return {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "representative": "family_b_seed_11",
        "fresh_process": True,
        "replay_subprocess_returncode": child.returncode,
        "primary_parameter_sha256": primary_canonical,
        "registry_parameter_sha256": expected_canonical,
        "primary_checkpoint_sha256": primary_checkpoint_sha,
        "registry_checkpoint_sha256": expected_checkpoint,
        "primary_prediction_sha256": primary_prediction_sha,
        "primary_input_sha256": input_sha,
        "scaler_sha256": stats.get("sha256"),
        "config_sha256": config_sha,
        "replay": child_result,
        "equalities": equalities,
        "canonical_parameter_sha256_equal": equalities["canonical_parameter_sha256_equal"],
        "deterministic": deterministic,
        "training_invocations": 0,
        "retraining": False,
        "error": child_error,
    }


def _replay_only() -> dict[str, Any]:
    contract = _read(ROOT / CONTRACT_REL)
    registry = _read(ROOT / M_PV2_REGISTRY_REL)
    records, _ = pv2._load_materialized_records()
    train_clean = pv2._record_group(records, "TRAIN")
    stats = pv2._fit_stats(train_clean)
    d1_val, _, q2 = _make_validation_records(records)
    replay_input = [*d1_val, *q2]
    entry = next((item for item in registry.get("candidates", []) if item.get("family") == "family_b" and int(item.get("seed", -1)) == 11), None)
    if entry is None:
        raise PV3Error("representative family_b/seed_11 absent")
    model, _, checkpoint = _load_checkpoint(entry)
    pv2._set_deterministic(0)
    predictions = _predict_for_replay(model, "family_b", replay_input, stats)
    return {
        "schema_version": "M-PV3.1",
        "representative": "family_b_seed_11",
        "contract_id": contract.get("contract_id"),
        "checkpoint_sha256": _file_sha(checkpoint),
        "canonical_parameter_sha256": pv2._canonical_parameter_sha(model),
        "prediction_sha256": _prediction_sha(predictions),
        "input_sha256": _input_sha(replay_input),
        "scaler_sha256": stats.get("sha256"),
        "config_sha256": _file_sha(ROOT / M_PV2_CONTRACT_REL),
        "training_invocations": 0,
        "retraining": False,
    }


def _write_checksums(output: Path) -> None:
    checksums: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"checksums.sha256", "checksums.json"}:
            checksums[_relative(path)] = _file_sha(path)
    _write(output / "checksums.json", {"schema_version": "M-PV3.1", "files": checksums})
    all_for_line = dict(checksums)
    all_for_line[_relative(output / "checksums.json")] = _file_sha(output / "checksums.json")
    (output / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(all_for_line.items())) + "\n", encoding="utf-8")


def run_phase() -> dict[str, Any]:
    contract = _read(ROOT / CONTRACT_REL)
    if contract.get("status") != "FROZEN_BEFORE_EVALUATION":
        raise PV3Error("M-PV3 selection contract is not frozen before evaluation")
    registry = _read(ROOT / M_PV2_REGISTRY_REL)
    m_pv2_contract = _read(ROOT / M_PV2_CONTRACT_REL)
    if registry.get("phase") != "M-PV2" or registry.get("final_selection") is not False or registry.get("selected_float_model") is not False:
        raise PV3Error("M-PV2 registry is not the merged candidate-only registry")
    records, materialization = pv2._load_materialized_records()
    train_clean = pv2._record_group(records, "TRAIN")
    stats = pv2._fit_stats(train_clean)
    stored_stats = _read(ROOT / M_PV2_SCALER_REL)
    tensor = _read(ROOT / M_PV2_TENSOR_REL)
    membership = _read(ROOT / M_PV2_MEMBERSHIP_REL)
    d2_lock = _read(ROOT / M_PV2_D2_REL)
    if stats.get("sha256") != stored_stats.get("sha256"):
        raise PV3Error("reconstructed TRAIN-only scaler differs from M-PV2 scaler evidence")
    pv2._set_deterministic(0)
    inventory, inventory_meta = _inventory(contract, m_pv2_contract, registry, stats, records, tensor)
    metrics, evaluation_context = _load_and_evaluate_candidates(contract, registry, records, stats, inventory)
    determinism = _determinism_audit(contract, registry, stats, evaluation_context["replay_input"], evaluation_context["representative_predictions"])
    ranking, pareto, acceptable = _ranking(metrics, contract)
    decision = _selection_decision(contract, inventory, metrics, ranking, pareto, acceptable, determinism)
    exceptions = {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "exceptions": [
            {"code": "D0_VAL_NOT_AUTHORIZED", "severity": "LIMITATION", "reason": "Frozen M-PV1 model-ready membership provides D0 TRAIN only; D0 metrics are observe-only."},
            {"code": "D1_ABSENT_CLASS_UNAVAILABLE", "severity": "LIMITATION", "reason": "D1_DEV_VAL has no model-ready ABSENT rows; absent-class discrimination is not established."},
            {"code": "Q2_IS_SYNTHETIC_EVALUATION", "severity": "LIMITATION", "reason": "Q2 modes are deterministic unavailable-input profiles, not live MR60 captures."},
            {"code": "FAMILY_A_BREATHING_UNSUPPORTED", "severity": "LIMITATION", "reason": "Family A has no breathing head and remains RR/quality-only."},
            {"code": "NO_15S_MIXING", "severity": "INVARIANT", "reason": "The parallel 15-second lane was not waited on and no 15-second artifact entered this registry or gate."},
            {"code": "NO_CALIBRATION_OR_DEPLOYMENT", "severity": "INVARIANT", "reason": "No calibration fitting, final threshold tuning, INT8/TFLite conversion, Pi deployment, or clinical claim was performed."},
            {"code": "FINAL_SELECTION_STATUS", "severity": "LIMITATION" if decision["selection_result"] != "SELECTED_FLOAT_MODEL" else "INVARIANT", "reason": decision["reason"]},
        ],
        "d2_access": False,
        "mr60_supervised_physiology": False,
        "training_invocations": 0,
    }
    validation = {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "gate": decision["gate"],
        "ok": decision["gate"] != "BLOCKED",
        "selection_result": decision["selection_result"],
        "candidate_count": len(metrics.get("candidates", [])),
        "all_nine_evaluated": bool(metrics.get("all_nine_reported")),
        "inventory_pass": bool(inventory.get("all_inventory_checks_pass")),
        "determinism_pass": bool(determinism.get("deterministic")),
        "q2_fail_closed_all_candidates": all(bool(row.get("safety", {}).get("checks", {}).get("q2_invalid_physiology_not_exposed")) for row in metrics.get("candidates", [])),
        "provenance_intact": bool(inventory.get("provenance_audit", {}).get("provenance_intact")),
        "d2_semantic_use": False,
        "mr60_supervised_use": False,
        "training_invocations": 0,
        "retraining": False,
        "d2_access": False,
        "int8_or_tflite": False,
        "limitations": decision.get("limitations", []),
        "materialization_counts": materialization.get("counts", {}),
        "selection_contract_sha256": _file_sha(ROOT / CONTRACT_REL),
    }
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "selection_contract.json", contract)
    _write(output / "candidate_selection_inventory.json", inventory)
    _write(output / "candidate_metrics_audit.json", metrics)
    _write(output / "candidate_ranking.json", ranking)
    _write(output / "selection_decision.json", decision)
    _write(output / "determinism_audit.json", determinism)
    _write(output / "exception_registry.json", exceptions)
    _write(output / "validation_result.json", validation)
    _write_checksums(output)
    return {"phase": "M-PV3", "gate": decision["gate"], "selection_result": decision["selection_result"], "shortlist": decision["shortlist"], "ready_for_m_pv4": decision["ready_for_m_pv4"], "output": OUTPUT_REL.as_posix(), "candidate_count": len(metrics.get("candidates", []))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-only", action="store_true", help="run the fresh-process representative replay used by the gate")
    args = parser.parse_args()
    try:
        result = _replay_only() if args.replay_only else run_phase()
    except Exception as exc:
        print(f"M-PV3 FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(pv2._json_safe(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
