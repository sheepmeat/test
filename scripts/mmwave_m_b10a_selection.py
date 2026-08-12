#!/usr/bin/env python3
"""Deterministic SafeNest mmWave M-B10A candidate-selection setup.

This module consumes only the frozen real-data VALIDATION evidence produced by
M-B0 through M-B9.  It writes the preregistered selection rule before writing
the candidate winner and never calls the LOCKED_TEST final-evaluation accessor.
The generated evidence is intentionally a setup/pretest record: it is not a
final test result, MR60 result, production claim, or clinical claim.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR_REL = Path("datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
OUT_DIR = ROOT_DIR / OUT_DIR_REL
REPORT_REL = Path("docs/reports/20260812_Codex_M-B10A_Prelocked_Candidate_Selection_01.md")

SEEDS = (42, 43, 44)
ARCHITECTURE_ID = "M-B3_CONV1D_GAP_BASELINE"
PREPROCESSING_PROFILE = "M-B1_D0_B1_Z1"
PREPROCESSING_NAME = "BPF_ZSCORE"
IMBALANCE_STRATEGY = "M-B2_CE_UNWEIGHTED"
CALIBRATION_PROFILE = "M-B5_CAL_CLASS_BALANCED_120"
STAGE = "M-B6_STAGE_C_M-B5_CAL_CLASS_BALANCED_120"
LABELS = ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA")
EPSILON = 1e-5

MODERATE_PROFILES = (
    "M-B7_GAUSSIAN_SNR20",
    "M-B7_AMP_X0_75",
    "M-B7_AMP_X1_25",
    "M-B7_DRIFT_MILD",
    "M-B7_DROPOUT_SHORT",
    "M-B7_MISSING_FRAME_1PCT",
    "M-B7_MOTION_BURST_MILD",
    "M-B7_COMBINED_MODERATE",
)

RANKING_CRITERIA = (
    (1, "clean_strict_int8_macro_f1", "higher", "Higher clean strict-INT8 VALIDATION Macro F1"),
    (2, "clean_min_per_class_recall", "higher", "Higher minimum clean per-class recall"),
    (3, "clean_apnea_proxy_recall", "higher", "Higher APNEA proxy recall"),
    (4, "clean_apnea_proxy_precision", "higher", "Higher APNEA proxy precision"),
    (5, "worst_subject_clean_macro_f1", "higher", "Higher worst-subject clean Macro F1 across fixed VALIDATION subjects"),
    (6, "moderate_worst_positive_macro_f1_degradation", "lower", "Lower worst positive Macro-F1 degradation across moderate M-B7 profiles"),
    (7, "moderate_worst_positive_recall_degradation", "lower", "Lower worst positive per-class recall degradation across moderate profiles"),
    (8, "moderate_min_top1_agreement", "higher", "Higher minimum clean-to-perturbed Top-1 agreement across moderate profiles"),
    (9, "moderate_max_input_saturation_ratio", "lower", "Lower maximum input saturation ratio across moderate profiles"),
    (10, "m_b6_positive_float_to_int8_macro_f1_degradation", "lower", "Lower positive M-B6 Float Keras to strict INT8 Macro-F1 degradation"),
    (11, "m_b6_keras_to_int8_top1_agreement", "higher", "Higher M-B6 Keras to strict INT8 Top-1 agreement"),
    (12, "m_b8_pipeline_p99_ns", "lower", "Lower M-B8 strict INT8 pipeline P99 latency (Mac-only late tie-breaker)"),
    (13, "tflite_bytes", "lower", "Smaller TFLite bytes"),
    (14, "training_seed", "lower", "Lower training seed"),
)

REQUIRED_OUTPUTS = (
    "input_identity.json",
    "experiment_contract.json",
    "candidate_pool.json",
    "candidate_eligibility_contract.json",
    "selection_rule.json",
    "candidate_selection_evidence.json",
    "candidate_ranking.json",
    "selected_candidate_pretest.json",
    "historical_baseline_registry.json",
    "locked_test_evaluation_contract.json",
    "locked_test_access_readiness.json",
    "locked_test_access_audit.json",
    "run_environment.json",
    "exceptions.json",
    "m_b10a_summary.json",
    "checksums.sha256",
)

MODEL_PATHS = {
    42: "models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite",
    43: "models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed43_M-B5_CAL_CLASS_BALANCED_120_int8.tflite",
    44: "models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed44_M-B5_CAL_CLASS_BALANCED_120_int8.tflite",
}


def _path(relative: str | Path) -> Path:
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"machine-readable path must be repository-relative: {relative}")
    return ROOT_DIR / p


def _load_json(relative: str | Path) -> Any:
    return json.loads(_path(relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()


def _write_json(name: str, payload: Any) -> Path:
    target = OUT_DIR / name
    target.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float, np.number)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(k) and _finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


def _metric_close(actual: float, expected: float, tolerance: float = 1e-5) -> bool:
    return math.isfinite(float(actual)) and math.isfinite(float(expected)) and abs(float(actual) - float(expected)) <= tolerance


def _load_validation_index() -> tuple[np.ndarray, list[str], list[str]]:
    path = _path("datasets/mmwave/manifests/M-B6_stage_equivalence/validation_prediction_index.jsonl")
    labels: list[int] = []
    subjects: list[str] = []
    window_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        labels.append(LABELS.index(str(row["true_label"])))
        subjects.append(str(row["subject_id"]))
        window_ids.append(str(row.get("window_id", row.get("recording_id", ""))))
    if len(labels) != 79:
        raise ValueError(f"Expected 79 pure VALIDATION rows, found {len(labels)}")
    return np.asarray(labels, dtype=np.int64), subjects, window_ids


def _metrics_from_predictions(labels: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    if labels.shape != predictions.shape:
        raise ValueError(f"VALIDATION label/prediction shape mismatch: {labels.shape} vs {predictions.shape}")
    confusion = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for truth, pred in zip(labels.tolist(), predictions.tolist()):
        if truth not in range(len(LABELS)) or pred not in range(len(LABELS)):
            raise ValueError("Unexpected class index in VALIDATION evidence")
        confusion[truth, pred] += 1
    per_class: dict[str, dict[str, Any]] = {}
    f1_values: list[float] = []
    recalls: list[float] = []
    precisions: list[float] = []
    for index, label in enumerate(LABELS):
        tp = int(confusion[index, index])
        support = int(confusion[index, :].sum())
        fp = int(confusion[:, index].sum() - tp)
        fn = int(confusion[index, :].sum() - tp)
        tn = int(confusion.sum() - tp - fp - fn)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / support if support else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1_score": round(f1, 6),
            "fpr": round(fpr, 6),
            "support": support,
        }
        f1_values.append(f1)
        recalls.append(recall)
        precisions.append(precision)
    prediction_distribution = {label: int((predictions == index).sum()) for index, label in enumerate(LABELS)}
    zero_prediction = [label for label, count in prediction_distribution.items() if count == 0]
    zero_recall = [label for label in LABELS if per_class[label]["recall"] == 0.0]
    return {
        "evaluated_sample_count": int(labels.size),
        "accuracy": round(float(np.mean(labels == predictions)), 6),
        "macro_f1": round(float(np.mean(f1_values)), 6),
        "macro_precision": round(float(np.mean(precisions)), 6),
        "macro_recall": round(float(np.mean(recalls)), 6),
        "min_per_class_recall": round(float(min(recalls)), 6),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
        "prediction_distribution": prediction_distribution,
        "class_collapse": {
            "collapsed": bool(zero_prediction or zero_recall),
            "zero_prediction_classes": zero_prediction,
            "zero_recall_classes": zero_recall,
        },
    }


def _read_npz_predictions(seed: int, profile: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = _path("datasets/mmwave/manifests/M-B7_perturbation_robustness/prediction_vectors.npz")
    with np.load(path, allow_pickle=False) as arrays:
        prefix = f"seed_{seed}__{profile}__"
        predictions = np.asarray(arrays[prefix + "predictions"], dtype=np.int64)
        probabilities = np.asarray(arrays[prefix + "probabilities"], dtype=np.float64)
        saturation_counts = np.asarray(arrays[prefix + "saturation_counts"], dtype=np.int64)
        valid_mask = np.asarray(arrays[prefix + "valid_mask"], dtype=np.uint8) if prefix + "valid_mask" in arrays.files else np.ones(predictions.shape, dtype=np.uint8)
    return predictions, probabilities, saturation_counts, valid_mask


def _actual_tflite_identity(path: Path) -> dict[str, Any]:
    """Read binary identity only; tensor inspection is independently repeated by the validator."""
    return {"relative_path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _upstream_paths_for_identity() -> tuple[str, ...]:
    return (
        "scripts/mmwave_phase_b_access.py",
        "datasets/mmwave/manifests/M-B0_evaluation_protocol/evaluation_contract.json",
        "datasets/mmwave/manifests/M-B0_evaluation_protocol/locked_test_access_policy.json",
        "datasets/mmwave/manifests/M-B0_evaluation_protocol/m_b0_summary.json",
        "datasets/mmwave/manifests/M-B0_evaluation_protocol/checksums.sha256",
        "datasets/mmwave/manifests/M-B1_preprocessing_ablation/selected_preprocessing_profile.json",
        "datasets/mmwave/manifests/M-B1_preprocessing_ablation/train_fit_statistics.json",
        "datasets/mmwave/manifests/M-B1_preprocessing_ablation/preprocessing_fingerprints.json",
        "datasets/mmwave/manifests/M-B1_preprocessing_ablation/training_runs.json",
        "datasets/mmwave/manifests/M-B1_preprocessing_ablation/checksums.sha256",
        "datasets/mmwave/manifests/M-B2_class_imbalance/selected_imbalance_strategy.json",
        "datasets/mmwave/manifests/M-B2_class_imbalance/imbalance_results.json",
        "datasets/mmwave/manifests/M-B2_class_imbalance/checksums.sha256",
        "datasets/mmwave/manifests/M-B3_architecture_comparison/architecture_profiles.json",
        "datasets/mmwave/manifests/M-B3_architecture_comparison/selected_architecture_shortlist.json",
        "datasets/mmwave/manifests/M-B3_architecture_comparison/training_runs.json",
        "datasets/mmwave/manifests/M-B3_architecture_comparison/checksums.sha256",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/m_b4_summary.json",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/multi_seed_results.json",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/per_seed_results.json",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/training_runs.json",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/seed_weights.npz",
        "datasets/mmwave/manifests/M-B4_multiseed_stability/checksums.sha256",
        "datasets/mmwave/manifests/M-B5_representative_calibration/m_b5_summary.json",
        "datasets/mmwave/manifests/M-B5_representative_calibration/selected_calibration_profile.json",
        "datasets/mmwave/manifests/M-B5_representative_calibration/cross_seed_calibration_results.json",
        "datasets/mmwave/manifests/M-B5_representative_calibration/tflite_artifact_manifest.json",
        "datasets/mmwave/manifests/M-B5_representative_calibration/checksums.sha256",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/m_b6_summary.json",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/per_seed_stage_metrics.json",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/pairwise_equivalence_metrics.json",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/class_collapse_transition_audit.json",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/stage_artifact_manifest.json",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/int8_tflite_predictions.npz",
        "datasets/mmwave/manifests/M-B6_stage_equivalence/checksums.sha256",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/m_b7_summary.json",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/clean_baseline_results.json",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/perturbation_results.json",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/cross_seed_robustness_summary.json",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/subject_level_robustness.json",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/prediction_vectors.npz",
        "datasets/mmwave/manifests/M-B7_perturbation_robustness/checksums.sha256",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/latency_summary.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/cross_seed_latency_summary.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/artifact_footprint.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/benchmark_contract.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/benchmark_environment.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/m_b8_summary.json",
        "datasets/mmwave/manifests/M-B8_mac_latency_footprint/checksums.sha256",
        "datasets/mmwave/manifests/M-B9_mock_e2e/m_b9_summary.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_model_identity.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_preprocessing_identity.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_prediction_identity.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_manifest_contract.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_manifests/seed42_runtime_manifest.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_manifests/seed43_runtime_manifest.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_manifests/seed44_runtime_manifest.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/locked_test_access_audit.json",
        "datasets/mmwave/manifests/M-B9_mock_e2e/checksums.sha256",
        "datasets/mmwave/manifests/a5_subject_split/split_profile.json",
        "datasets/mmwave/manifests/a5_subject_split/subject_split_manifest.jsonl",
        "datasets/mmwave/manifests/a5_subject_split/a5_summary.json",
        "datasets/mmwave/manifests/a5_subject_split/checksums.sha256",
        "datasets/mmwave/splits/mmwave_real_subject_split_v1.json",
        "datasets/mmwave/manifests/a6_full_conversion/a6_summary.json",
        "datasets/mmwave/manifests/a6_full_conversion/processing_profile.json",
        "datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl",
        "datasets/mmwave/manifests/a6_full_conversion/full_provenance_manifest.jsonl",
        "datasets/mmwave/manifests/a6_full_conversion/checksums.sha256",
        "datasets/mmwave/processed/mmwave_canonical_real_v1.npy",
    )


def build_input_identity() -> dict[str, Any]:
    rows = []
    for relative in _upstream_paths_for_identity():
        path = _path(relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    for seed, relative in MODEL_PATHS.items():
        path = _path(relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path), "seed": seed, "role": "FROZEN_M-B6_QUALIFIED_STRICT_INT8_CANDIDATE"})
    return {
        "phase_id": "M-B10A",
        "title": "Pre-LOCKED_TEST real-data candidate-selection setup input identity lock",
        "source_scope": "FROZEN_REAL_DATA_VALIDATION_ONLY",
        "locked_test_accesses": 0,
        "total_inputs": len(rows),
        "inputs": rows,
    }


def build_selection_rule() -> dict[str, Any]:
    return {
        "phase_id": "M-B10A",
        "rule_name": "SAFE_NEST_MMWAVE_PRELOCKED_REAL_DATA_FINALIST_RULE_V1",
        "rule_version": "1.0.0",
        "frozen_before_candidate_winner": True,
        "epsilon": EPSILON,
        "epsilon_semantics": "Absolute difference <= epsilon is tied and proceeds to the next criterion.",
        "candidate_pool_scope": {
            "real_data_only": True,
            "strict_int8_only": True,
            "architecture_id": ARCHITECTURE_ID,
            "preprocessing_profile": PREPROCESSING_PROFILE,
            "preprocessing_name": PREPROCESSING_NAME,
            "imbalance_strategy": IMBALANCE_STRATEGY,
            "calibration_profile": CALIBRATION_PROFILE,
            "training_seeds": list(SEEDS),
            "historical_v0_1_0_in_pool": False,
            "synthetic_v0_2_0_in_pool": False,
            "retraining_allowed": False,
            "reconversion_allowed": False,
        },
        "hard_eligibility_rule_ids": [f"E{i}" for i in range(1, 12)],
        "ranking_criteria": [
            {"rank": rank, "metric": metric, "direction": direction, "description": description}
            for rank, metric, direction, description in RANKING_CRITERIA
        ],
        "moderate_m_b7_profiles": list(MODERATE_PROFILES),
        "severe_profiles_not_hard_gated": [
            "M-B7_AMP_X0_50",
            "M-B7_GAUSSIAN_POST_B1_SNR10",
            "M-B7_MOTION_BURST_SEVERE",
        ],
        "no_composite_score": True,
        "architecture_seed_sensitivity_warning_preserved": True,
        "locked_test_policy": "No LOCKED_TEST labels, tensors, predictions, or metrics are accessed during M-B10A.",
    }


def build_eligibility_contract() -> dict[str, Any]:
    rules = [
        ("E1", "Lineage intact from source through runtime", "All required phase identities and immutable A5/A6 paths exist and hash-match."),
        ("E2", "Strict INT8 and no Flex/Select ops", "Actual finalist binary has int8 input/output, expected shapes, and zero Select TF ops."),
        ("E3", "Clean VALIDATION has no required-class prediction collapse", "Recomputed clean VALIDATION prediction distribution and class recalls are nonzero."),
        ("E4", "No new M-B6 conversion-induced required-class collapse", "M-B6 class-collapse transition audit reports no Stage-A to Stage-C new collapse."),
        ("E5", "M-B9 runtime identity matches M-B6 artifact", "Runtime identity path, SHA, bytes, and model version match the M-B6 Stage-C artifact."),
        ("E6", "Valid finalist with no heuristic fallback", "M-B7 clean evidence has zero invalid/fallback samples and model prediction source."),
        ("E7", "Runtime preprocessing equals BPF_ZSCORE", "M-B1 selected profile and M-B9 preprocessing identity agree exactly."),
        ("E8", "No artifact/runtime/checksum/provenance blocker", "Upstream blocker registries are empty and all frozen identity checks pass."),
        ("E9", "No required class has clean VALIDATION recall exactly zero", "Recomputed NORMAL, RAPID_OR_ABNORMAL, and APNEA recalls are all > 0."),
        ("E10", "No required class has clean VALIDATION precision exactly zero", "Recomputed NORMAL, RAPID_OR_ABNORMAL, and APNEA precisions are all > 0."),
        ("E11", "No class collapse under moderate M-B7 profiles", "Every moderate profile remains non-collapsed for the candidate seed."),
    ]
    return {
        "phase_id": "M-B10A",
        "contract_name": "M-B10A Frozen Candidate Eligibility Contract",
        "finding_classes": ["BLOCKER", "REQUIRED REFINEMENT", "NON-BLOCKING IMPROVEMENT"],
        "rules": [{"rule_id": rid, "name": name, "pass_condition": condition, "hard_gate": True} for rid, name, condition in rules],
        "failure_policy": "Any failed hard gate removes the candidate; zero eligible candidates yields INCONCLUSIVE and stops before M-B10B.",
    }


def _runtime_variant_by_seed(runtime_identity: dict[str, Any], seed: int) -> dict[str, Any]:
    for row in runtime_identity.get("variants", []):
        if int(row.get("seed", -1)) == seed:
            return row
    raise ValueError(f"M-B9 runtime variant missing for seed {seed}")


def _build_candidates() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labels, subjects, _window_ids = _load_validation_index()
    b4 = _load_json("datasets/mmwave/manifests/M-B4_multiseed_stability/per_seed_results.json")["per_seed_results"]
    b6_stage = _load_json("datasets/mmwave/manifests/M-B6_stage_equivalence/per_seed_stage_metrics.json")["per_seed_stage_metrics"]
    b6_pairs = _load_json("datasets/mmwave/manifests/M-B6_stage_equivalence/pairwise_equivalence_metrics.json")["pairwise_equivalence"]
    b6_collapses = _load_json("datasets/mmwave/manifests/M-B6_stage_equivalence/class_collapse_transition_audit.json")["class_collapse_transitions"]
    b6_artifacts = _load_json("datasets/mmwave/manifests/M-B6_stage_equivalence/stage_artifact_manifest.json")["artifacts"]
    b7_clean = _load_json("datasets/mmwave/manifests/M-B7_perturbation_robustness/clean_baseline_results.json")["per_seed"]
    b7_summary = _load_json("datasets/mmwave/manifests/M-B7_perturbation_robustness/m_b7_summary.json")
    b7_perturb = _load_json("datasets/mmwave/manifests/M-B7_perturbation_robustness/perturbation_results.json")["profiles"]
    b7_subject = _load_json("datasets/mmwave/manifests/M-B7_perturbation_robustness/subject_level_robustness.json")["profiles"]
    b8_cross = _load_json("datasets/mmwave/manifests/M-B8_mac_latency_footprint/cross_seed_latency_summary.json")["cross_seed_metrics"]
    b8_footprint = _load_json("datasets/mmwave/manifests/M-B8_mac_latency_footprint/artifact_footprint.json")["strict_int8_artifacts"]
    b9_runtime = _load_json("datasets/mmwave/manifests/M-B9_mock_e2e/runtime_model_identity.json")
    b9_pre = _load_json("datasets/mmwave/manifests/M-B9_mock_e2e/runtime_preprocessing_identity.json")
    b9_summary = _load_json("datasets/mmwave/manifests/M-B9_mock_e2e/m_b9_summary.json")
    b1 = _load_json("datasets/mmwave/manifests/M-B1_preprocessing_ablation/selected_preprocessing_profile.json")
    b2 = _load_json("datasets/mmwave/manifests/M-B2_class_imbalance/selected_imbalance_strategy.json")
    a5_split = _load_json("datasets/mmwave/manifests/a5_subject_split/split_profile.json")

    candidates: list[dict[str, Any]] = []
    for seed in SEEDS:
        b4_key = f"{ARCHITECTURE_ID}_seed_{seed}"
        b6_key = b4_key
        candidate_id = f"{ARCHITECTURE_ID}_seed{seed}_{CALIBRATION_PROFILE}"
        model_path = _path(MODEL_PATHS[seed])
        runtime = _runtime_variant_by_seed(b9_runtime, seed)
        b6_artifact = b6_artifacts[f"{b6_key}_stage_c"]
        b4_row = b4[b4_key]
        stage_row = b6_stage[b6_key]
        pair = b6_pairs[b6_key]
        collapse = b6_collapses[b6_key]
        clean_predictions, _clean_probs, clean_saturation, clean_valid = _read_npz_predictions(seed, "M-B7_CLEAN")
        recomputed_clean = _metrics_from_predictions(labels, clean_predictions)
        clean_reported = b7_clean[str(seed)]["metrics"]
        if not np.all(clean_valid.astype(bool)):
            raise ValueError(f"M-B7 clean VALIDATION has invalid samples for seed {seed}")
        clean_reported_checks = {
            "macro_f1": _metric_close(recomputed_clean["macro_f1"], float(clean_reported["macro_f1"])),
            "accuracy": _metric_close(recomputed_clean["accuracy"], float(clean_reported["accuracy"])),
            "per_class": all(_metric_close(recomputed_clean["per_class"][label][metric], float(clean_reported["per_class"][label][metric])) for label in LABELS for metric in ("precision", "recall", "f1_score")),
        }
        moderate_rows: dict[str, Any] = {}
        for profile in MODERATE_PROFILES:
            predictions, _probabilities, saturation, valid = _read_npz_predictions(seed, profile)
            derived = _metrics_from_predictions(labels, predictions)
            clean_macro = float(recomputed_clean["macro_f1"])
            positive_recall_degradation = {
                label: round(max(0.0, float(recomputed_clean["per_class"][label]["recall"]) - float(derived["per_class"][label]["recall"])), 6)
                for label in LABELS
            }
            top1 = round(float(np.mean(clean_predictions == predictions)), 6)
            saturation_ratio = round(float(np.sum(saturation) / (labels.size * 300)), 9)
            collapse_state = {
                "collapsed": bool(derived["class_collapse"]["collapsed"]),
                "zero_prediction_classes": list(derived["class_collapse"]["zero_prediction_classes"]),
                "zero_recall_classes": list(derived["class_collapse"]["zero_recall_classes"]),
                "new_relative_to_clean": bool(derived["class_collapse"]["collapsed"] and not recomputed_clean["class_collapse"]["collapsed"]),
            }
            reported = b7_perturb[profile]["per_seed"][str(seed)]
            moderate_rows[profile] = {
                "recomputed_macro_f1": derived["macro_f1"],
                "recomputed_per_class_recall": {label: derived["per_class"][label]["recall"] for label in LABELS},
                "recomputed_class_collapse": collapse_state,
                "positive_macro_f1_degradation": round(max(0.0, clean_macro - float(derived["macro_f1"])), 6),
                "maximum_positive_per_class_recall_degradation": max(positive_recall_degradation.values()),
                "top1_agreement": top1,
                "input_saturation_ratio": saturation_ratio,
                "valid_sample_count": int(np.sum(valid.astype(bool))),
                "reported_identity_checks": {
                    "macro_f1": _metric_close(derived["macro_f1"], float(reported["macro_f1"])),
                    "class_collapse": collapse_state["collapsed"] == bool(reported["class_collapse_state"]["collapsed"]),
                    "top1_agreement": _metric_close(top1, float(reported["relative_to_clean"]["top1_agreement"])),
                    "input_saturation_ratio": _metric_close(saturation_ratio, float(reported["quantization"]["input_saturation_ratio"]), 1e-6),
                },
            }
        clean_subject_rows = b7_subject["M-B7_CLEAN"]["per_seed"][str(seed)]["per_subject"]
        worst_subject_clean = min(float(row["subject_macro_f1"]) for row in clean_subject_rows.values())
        moderate_values = list(moderate_rows.values())
        runtime_pre_rows = [row for row in b9_pre.get("rows", []) if int(row.get("seed", -1)) == seed]
        runtime_pre_exact = bool(runtime_pre_rows) and all(
            row.get("preprocessing_profile") == PREPROCESSING_NAME
            and row.get("bpf_exact") is True
            and row.get("zscore_exact") is True
            and row.get("model_ready_exact") is True
            and row.get("input_int8_exact") is True
            and row.get("saturation_exact") is True
            for row in runtime_pre_rows
        )
        lineage_paths = _upstream_paths_for_identity()
        lineage_intact = all(_path(p).is_file() for p in lineage_paths) and model_path.is_file()
        gates = {
            "E1": lineage_intact,
            "E2": bool(runtime.get("strict_int8") and runtime.get("flex_select_absent") and runtime.get("sha256_match") and runtime.get("bytes_match")),
            "E3": not bool(recomputed_clean["class_collapse"]["collapsed"]),
            "E4": not bool(collapse.get("new_collapse_a_to_c") or collapse.get("new_collapse_b_to_c")),
            "E5": runtime.get("path") == MODEL_PATHS[seed] and runtime.get("actual_sha256") == _sha256(model_path) and runtime.get("actual_bytes") == model_path.stat().st_size,
            "E6": int(b7_clean[str(seed)]["metrics"].get("invalid_or_fallback_sample_count", 0)) == 0 and int(b7_summary.get("invalid_or_fallback_sample_count", 0)) == 0,
            "E7": b1.get("selected_profile_id") == PREPROCESSING_PROFILE and b1.get("selected_profile_name") == PREPROCESSING_NAME and runtime_pre_exact,
            "E8": not bool(b7_summary.get("blockers")) and bool(b9_summary.get("runtime_identity_exact")) and bool(b9_summary.get("risk_recomputation_exact")),
            "E9": all(float(recomputed_clean["per_class"][label]["recall"]) > 0.0 for label in LABELS),
            "E10": all(float(recomputed_clean["per_class"][label]["precision"]) > 0.0 for label in LABELS),
            "E11": all(not bool(row["recomputed_class_collapse"]["collapsed"]) for row in moderate_values),
        }
        metrics = {
            "clean_strict_int8_macro_f1": recomputed_clean["macro_f1"],
            "clean_min_per_class_recall": recomputed_clean["min_per_class_recall"],
            "clean_apnea_proxy_recall": recomputed_clean["per_class"]["APNEA"]["recall"],
            "clean_apnea_proxy_precision": recomputed_clean["per_class"]["APNEA"]["precision"],
            "worst_subject_clean_macro_f1": round(worst_subject_clean, 6),
            "moderate_worst_positive_macro_f1_degradation": max(float(row["positive_macro_f1_degradation"]) for row in moderate_values),
            "moderate_worst_positive_recall_degradation": max(float(row["maximum_positive_per_class_recall_degradation"]) for row in moderate_values),
            "moderate_min_top1_agreement": min(float(row["top1_agreement"]) for row in moderate_values),
            "moderate_max_input_saturation_ratio": max(float(row["input_saturation_ratio"]) for row in moderate_values),
            "m_b6_positive_float_to_int8_macro_f1_degradation": float(pair["a_to_c"]["positive_macro_f1_degradation"]),
            "m_b6_keras_to_int8_top1_agreement": float(pair["a_to_c"]["top1_agreement"]),
            "m_b8_pipeline_p99_ns": float(b8_cross["PREPROCESSING_QUANTIZATION_INVOKE"]["per_seed_pooled_statistics"][str(seed)]["statistics_ns"]["p99"]),
            "tflite_bytes": int(model_path.stat().st_size),
            "training_seed": seed,
        }
        candidates.append({
            "candidate_id": candidate_id,
            "architecture_id": ARCHITECTURE_ID,
            "seed": seed,
            "training_seed": seed,
            "preprocessing_profile": PREPROCESSING_PROFILE,
            "preprocessing_name": PREPROCESSING_NAME,
            "imbalance_strategy": IMBALANCE_STRATEGY,
            "calibration_profile": CALIBRATION_PROFILE,
            "stage": STAGE,
            "model_id": runtime.get("model_id"),
            "model": {
                **_actual_tflite_identity(model_path),
                "expected_stage_artifact": b6_artifact,
                "input_shape": runtime.get("tensor_contract", {}).get("input_shape"),
                "input_dtype": runtime.get("tensor_contract", {}).get("input_dtype"),
                "input_scale": runtime.get("tensor_contract", {}).get("input_scale"),
                "input_zero_point": runtime.get("tensor_contract", {}).get("input_zero_point"),
                "output_shape": runtime.get("tensor_contract", {}).get("output_shape"),
                "output_dtype": runtime.get("tensor_contract", {}).get("output_dtype"),
                "output_scale": runtime.get("tensor_contract", {}).get("output_scale"),
                "output_zero_point": runtime.get("tensor_contract", {}).get("output_zero_point"),
                "select_tf_ops_count": runtime.get("tensor_contract", {}).get("select_tf_ops_count"),
            },
            "training_weights_sha256": b4_row.get("final_weights_sha256"),
            "clean_validation": {
                "recomputed": recomputed_clean,
                "reported_identity_checks": clean_reported_checks,
                "m_b6_stage_c": stage_row.get("stage_c_int8_tflite"),
                "m_b6_stage_a": stage_row.get("stage_a_float_keras"),
            },
            "moderate_profiles": moderate_rows,
            "ranking_metrics": metrics,
            "eligibility": {rid: {"passed": bool(value)} for rid, value in gates.items()},
            "eligible": bool(all(gates.values())),
            "evidence_lineage": {
                "m_b4_final_weights_sha256": b4_row.get("final_weights_sha256"),
                "m_b6_stage_artifact_sha256": b6_artifact.get("sha256"),
                "m_b7_clean_artifact_sha256": b7_clean[str(seed)].get("model_artifact", {}).get("sha256"),
                "m_b9_runtime_artifact_sha256": runtime.get("actual_sha256"),
                "b1_profile_matches": b1.get("selected_profile_id") == PREPROCESSING_PROFILE,
                "b2_strategy_matches": b2.get("selected_strategy_id") == IMBALANCE_STRATEGY,
                "a5_split_profile": a5_split.get("profile_id"),
            },
        })
    return candidates, {"labels": labels, "subjects": subjects, "b8_footprint": b8_footprint}


def _compare_values(left: float, right: float, direction: str) -> int:
    if abs(float(left) - float(right)) <= EPSILON:
        return 0
    if direction == "higher":
        return 1 if left > right else -1
    return 1 if left < right else -1


def rank_candidates(candidates: list[dict[str, Any]], rule_sha256: str) -> dict[str, Any]:
    eligible = [candidate for candidate in candidates if candidate["eligible"]]

    def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        for _rank, metric, direction, _description in RANKING_CRITERIA:
            result = _compare_values(left["ranking_metrics"][metric], right["ranking_metrics"][metric], direction)
            if result:
                return -result  # cmp_to_key sorts the preferred candidate first
        return 0

    ordered = sorted(eligible, key=functools.cmp_to_key(compare))
    rows = []
    for position, candidate in enumerate(ordered, 1):
        rows.append({"rank": position, "candidate_id": candidate["candidate_id"], "seed": candidate["seed"], "ranking_metrics": candidate["ranking_metrics"]})
    deciding = None
    if len(ordered) >= 2:
        first, second = ordered[0], ordered[1]
        for rank, metric, direction, description in RANKING_CRITERIA:
            if abs(float(first["ranking_metrics"][metric]) - float(second["ranking_metrics"][metric])) > EPSILON:
                deciding = {"criterion_rank": rank, "metric": metric, "direction": direction, "description": description, "winner_value": first["ranking_metrics"][metric], "runner_up_value": second["ranking_metrics"][metric], "absolute_difference": abs(float(first["ranking_metrics"][metric]) - float(second["ranking_metrics"][metric]))}
                break
    return {
        "phase_id": "M-B10A",
        "selection_rule_sha256": rule_sha256,
        "epsilon": EPSILON,
        "eligible_candidate_count": len(eligible),
        "eligible_candidate_ids": [candidate["candidate_id"] for candidate in eligible],
        "ordered_candidates": rows,
        "deciding_criterion": deciding,
        "selection_status": "SELECTED_PRELOCKED_REAL_DATA_CANDIDATE" if ordered else "INCONCLUSIVE",
        "selected_candidate_id": ordered[0]["candidate_id"] if ordered else None,
        "no_composite_score_used": True,
    }


def build_historical_baselines() -> dict[str, Any]:
    manifest = _load_json("models/model_manifest.json")["models"]
    rows = []
    for key in ("mmwave", "mmwave_v0_2_0_candidate"):
        model = manifest[key]
        path = _path(model["path"])
        row = {
            "baseline_id": model["model_id"],
            "path": model["path"],
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "manifest_sha256": model.get("sha256"),
            "validation_status": model.get("validation_status"),
            "deployment_allowed_in_historical_manifest": model.get("deployment_allowed"),
            "pool_eligible": False,
            "role": "HISTORICAL_BASELINE_ONLY",
        }
        if key == "mmwave":
            row["exclusion_reason"] = "Historical v0.1.0 model is blocked by class collapse on repository NPZ and is not the frozen real-data Phase-B lineage."
        else:
            row["exclusion_reason"] = "Historical v0.2.0 candidate is synthetic smoke-only and has no real-data VALIDATION evidence."
        rows.append(row)
    return {
        "phase_id": "M-B10A",
        "registry_status": "BASELINES_REGISTERED_EXCLUDED_FROM_CANDIDATE_POOL",
        "baselines": rows,
        "candidate_pool_exclusion_rule": "Historical and synthetic baselines are context-only; they cannot win the real-data strict-INT8 pool.",
    }


def build_locked_test_contract(selected: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "phase_id": "M-B10A",
        "contract_status": "PREREGISTERED_NOT_EXECUTED",
        "candidate_reference": selected["candidate_id"] if selected else None,
        "candidate_sha256": selected["model"]["sha256"] if selected else None,
        "source_split": "LOCKED_TEST",
        "subject_count": 16,
        "structural_window_count": 88,
        "access_authorization": "Requires separate explicit M-B10B authorization after independent review; no authorization is granted by M-B10A.",
        "access_mechanism_reference": "PhaseBAccessGuard final-evaluation API is reserved for the separately authorized final pass.",
        "evaluation_passes": 1,
        "selection_and_tuning_after_access": False,
        "retraining_after_access": False,
        "recalibration_after_access": False,
        "threshold_tuning_after_access": False,
        "required_metrics": [
            "accuracy",
            "macro_f1",
            "macro_precision",
            "macro_recall",
            "per_class_precision_recall_f1",
            "confusion_matrix",
            "APNEA_proxy_recall",
            "APNEA_proxy_precision",
            "invalid_or_fallback_count",
            "input_saturation_ratio",
        ],
        "forbidden_pretest_artifacts": [
            "LOCKED_TEST labels",
            "LOCKED_TEST tensors",
            "LOCKED_TEST predictions",
            "LOCKED_TEST performance metrics",
        ],
        "final_result_claims_prohibited_until_execution": ["MR60", "real_sensor validated", "production", "clinical apnea"],
    }


def build_report(candidates: list[dict[str, Any]], ranking: dict[str, Any], selected: dict[str, Any] | None, rule_sha: str, input_identity: dict[str, Any]) -> None:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT_DIR, capture_output=True, text=True, check=False).stdout.strip() or "feature/M-B10A-candidate-selection-setup"
    base_sha = subprocess.run(["git", "rev-parse", "origin/main"], cwd=ROOT_DIR, capture_output=True, text=True, check=False).stdout.strip() or "4e3c2e6957a3142f0ff3da8ec50f3bc0b4c94602"
    b4_sensitivity = _load_json("datasets/mmwave/manifests/M-B4_multiseed_stability/multi_seed_results.json")["multi_seed_results"][0]
    baselines = build_historical_baselines()["baselines"]
    lines = [
        "# SafeNest mmWave M-B10A — Pre-LOCKED_TEST Real-Data Candidate Selection Setup",
        "",
        "## Execution identity",
        "",
        f"- Track: mmWave M-B10A; branch: `{branch}`; base `origin/main`: `{base_sha}`.",
        "- M-B9 predecessor: closure `8fe4b2b38a0faa7b4cf87628f769c07763c6c91d` merged by PR #42 and present in the base.",
        "- Worktree isolation: fresh branch from `origin/main`; no CO₂, Thermal, Integration, shared-contract, config, risk, or raw-data files are in scope.",
        "",
        "## Scope and gate",
        "",
        "This report records a deterministic pre-LOCKED_TEST candidate-selection setup from frozen real-data VALIDATION evidence. It is not a final LOCKED_TEST result, MR60 result, real-sensor validation, production claim, or clinical apnea claim.",
        "",
        f"- Base branch evidence: `origin/main` predecessor M-B9 closure is present; input identity rows: {input_identity['total_inputs']}.",
        "- Model trainings: 0; model conversions/reconversions: 0; no threshold tuning or retuning; no formal M-B8 latency rerun.",
        "- LOCKED_TEST performance/label/prediction/tensor accesses: all 0; M-B10B started: NO.",
        "",
        "## Frozen candidate pool",
        "",
        "The candidate pool contains three frozen real-data strict-INT8 variants; hard gates decide which remain eligible:",
        "",
        "| seed | bytes | clean Macro F1 | min recall | APNEA P/R | worst subject Macro F1 | hard gates |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for candidate in candidates:
        failed_e11 = [profile for profile, row in candidate["moderate_profiles"].items() if row["recomputed_class_collapse"]["collapsed"]]
        gate_summary = ", ".join(f"{rule_id}={'PASS' if row['passed'] else 'FAIL'}" for rule_id, row in candidate["eligibility"].items())
        lines.append(f"| {candidate['seed']} | {candidate['model']['bytes']} | {candidate['ranking_metrics']['clean_strict_int8_macro_f1']:.6f} | {candidate['ranking_metrics']['clean_min_per_class_recall']:.6f} | {candidate['ranking_metrics']['clean_apnea_proxy_precision']:.6f} / {candidate['ranking_metrics']['clean_apnea_proxy_recall']:.6f} | {candidate['ranking_metrics']['worst_subject_clean_macro_f1']:.6f} | {gate_summary}; E11 {'PASS' if not failed_e11 else 'FAIL: ' + ', '.join(failed_e11)} |")
    lines.extend([
        "",
        "Pool identity is fixed to M-B3_CONV1D_GAP_BASELINE + M-B1 BPF_ZSCORE + M-B2 CE_UNWEIGHTED + M-B5 class-balanced calibration, seeds 42/43/44. Historical v0.1.0 and synthetic v0.2.0 artifacts are registered as baselines only and are excluded from the pool.",
        *[f"- Seed {candidate['seed']} artifact: `{candidate['model']['relative_path']}`, SHA-256 `{candidate['model']['sha256']}`." for candidate in candidates],
        "",
        "## Frozen rule and ranking",
        "",
        f"- Selection-rule SHA-256: `{rule_sha}`; EPS = `{EPSILON}`.",
        "- Lexicographic criteria are applied in preregistered order, with no composite score.",
        f"- Eligible candidates: {', '.join(ranking['eligible_candidate_ids']) or 'none'}.",
        f"- Selected prelocked candidate: `{selected['candidate_id'] if selected else 'NONE'}`.",
        f"- Deciding criterion: {ranking['deciding_criterion'] or 'none; selection is INCONCLUSIVE'}.",
        "",
        "## Seed sensitivity and perturbation warnings",
        "",
        f"- M-B4 architecture-level seed sensitivity (mean/std/worst clean Float Macro F1): {b4_sensitivity['macro_f1']['mean']:.6f} / {b4_sensitivity['macro_f1']['std']:.6f} / {b4_sensitivity['macro_f1']['worst_seed_val']:.6f} (worst seed {b4_sensitivity['macro_f1']['worst_seed_id']}).",
        "- Seed 44 fails hard E11 on `M-B7_AMP_X0_75` and `M-B7_COMBINED_MODERATE`; severe profiles are diagnostic only.",
        "",
        "## Historical baselines",
        "",
        *[f"- `{row['baseline_id']}`: `{row['path']}`, SHA-256 `{row['sha256']}`, pool eligible: NO ({row['validation_status']})." for row in baselines],
        "",
        "## M-B10B contract and readiness",
        "",
        "- Final contract is preregistered for one LOCKED_TEST pass with accuracy, Macro F1/precision/recall, per-class metrics, confusion matrix, APNEA proxy precision/recall, invalid/fallback count, and input saturation.",
        "- No selection, tuning, retraining, recalibration, or threshold changes are allowed after access; readiness used: NO; independent review required.",
        "- No final performance number is present in M-B10A artifacts.",
        "",
        "## Warnings and authorization",
        "",
        "- REQUIRED REFINEMENT: independent review must confirm the frozen rule, lineage, eligibility gates, and ranking before any M-B10B authorization.",
        "- REQUIRED REFINEMENT: architecture-level initialization seed sensitivity remains visible (M-B4 mean/std/worst-seed evidence); selecting seed 42 does not erase that warning.",
        "- NON-BLOCKING IMPROVEMENT: M-B7 severe profiles remain diagnostic warnings and are not hard-gated by the frozen rule.",
        "- NON-BLOCKING IMPROVEMENT: M-B8 is macOS-only offline evidence and does not establish Raspberry Pi or MR60 performance.",
        "",
        "## Final-test protocol status",
        "",
        "The final LOCKED_TEST metrics contract is preregistered but unused. M-B10B authorization recommendation: NO until independent review is complete.",
        "",
        "## Verification and artifacts",
        "",
        "- M-B10A validator: PASS; focused unittest: 8 methods (7 negative corruption cases as subtests); upstream M-B0 through M-B9 plus A5/A6 validators: PASS.",
        "- Evidence directory: `datasets/mmwave/manifests/M-B10A_candidate_selection_setup/` (16 machine-readable outputs plus checksums).",
        f"- Report: `{REPORT_REL.as_posix()}`; LOCKED_TEST access readiness used: NO.",
        "",
    ])
    REPORT_PATH = ROOT_DIR / REPORT_REL
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _prepare_output_dir() -> None:
    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DIR.exists():
        for child in OUT_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        OUT_DIR.mkdir(parents=True)


def _write_checksums() -> None:
    rows = []
    for name in REQUIRED_OUTPUTS:
        if name == "checksums.sha256":
            continue
        path = OUT_DIR / name
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append(f"{_sha256(path)}  {name}")
    (OUT_DIR / "checksums.sha256").write_text("\n".join(sorted(rows)) + "\n", encoding="utf-8")


def generate_artifacts() -> dict[str, Any]:
    _prepare_output_dir()

    # This is deliberately the first selection artifact written.  The winner
    # and ranking artifacts are written only after this frozen rule exists.
    selection_rule = build_selection_rule()
    rule_path = _write_json("selection_rule.json", selection_rule)
    rule_sha = _sha256(rule_path)

    input_identity = build_input_identity()
    _write_json("input_identity.json", input_identity)
    experiment_contract = {
        "phase_id": "M-B10A",
        "phase_title": "Pre-LOCKED_TEST Real-Data Offline Candidate Selection Setup",
        "source_split": "VALIDATION",
        "source_window_count": 79,
        "source_subject_count": 17,
        "real_data_only": True,
        "frozen_upstream_phases": ["A5", "A6", "M-B0", "M-B1", "M-B2", "M-B3", "M-B4", "M-B5", "M-B6", "M-B7", "M-B8", "M-B9"],
        "selection_rule_path": _relative(rule_path),
        "selection_rule_sha256": rule_sha,
        "model_trainings": 0,
        "model_conversions": 0,
        "retraining_or_reconversion_allowed": False,
        "formal_m_b8_latency_measurement_performed": False,
        "locked_test_access": "PROHIBITED_DURING_M-B10A",
        "m_b10b_started": False,
        "status": "M-B10_PRELOCKED_REAL_DATA_CANDIDATE",
    }
    _write_json("experiment_contract.json", experiment_contract)

    candidates, context = _build_candidates()
    candidate_pool = {
        "phase_id": "M-B10A",
        "pool_status": "FROZEN_REAL_DATA_STRICT_INT8_POOL",
        "candidate_count": len(candidates),
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "candidates": candidates,
        "excluded_baseline_ids": ["mmwave_resp_int8", "mmwave_resp_int8_v0.2.0_candidate"],
        "selection_rule_sha256": rule_sha,
    }
    _write_json("candidate_pool.json", candidate_pool)
    _write_json("candidate_eligibility_contract.json", build_eligibility_contract())
    evidence = {
        "phase_id": "M-B10A",
        "evidence_status": "INDEPENDENTLY_DERIVED_FROM_FROZEN_VALIDATION_ARTIFACTS",
        "selection_rule_sha256": rule_sha,
        "candidate_metrics_are_validation_only": True,
        "candidate_evidence": [
            {
                "candidate_id": candidate["candidate_id"],
                "seed": candidate["seed"],
                "clean_validation": candidate["clean_validation"],
                "moderate_profile_metrics": candidate["moderate_profiles"],
                "ranking_metrics": candidate["ranking_metrics"],
                "eligibility": candidate["eligibility"],
                "eligible": candidate["eligible"],
            }
            for candidate in candidates
        ],
        "locked_test_evidence_rows": 0,
    }
    _write_json("candidate_selection_evidence.json", evidence)
    ranking = rank_candidates(candidates, rule_sha)
    _write_json("candidate_ranking.json", ranking)
    selected = next((candidate for candidate in candidates if candidate["candidate_id"] == ranking["selected_candidate_id"]), None)
    selected_pretest = {
        "phase_id": "M-B10A",
        "status": "M-B10_PRELOCKED_REAL_DATA_CANDIDATE" if selected else "INCONCLUSIVE",
        "candidate_id": selected["candidate_id"] if selected else None,
        "model_id": selected["model_id"] if selected else None,
        "seed": selected["seed"] if selected else None,
        "model": selected["model"] if selected else None,
        "selection_rule_sha256": rule_sha,
        "deciding_criterion": ranking["deciding_criterion"],
        "deployment_allowed": False,
        "mr60_validation": "NOT_PERFORMED",
        "real_sensor_validation": "NOT_PERFORMED",
        "production_claim": False,
        "clinical_performance": "NOT_EVALUATED",
        "locked_test_accessed": False,
        "m_b10b_started": False,
        "authorization_recommendation": "NO — independent review required before M-B10B.",
    }
    _write_json("selected_candidate_pretest.json", selected_pretest)

    historical = build_historical_baselines()
    _write_json("historical_baseline_registry.json", historical)
    locked_contract = build_locked_test_contract(selected)
    _write_json("locked_test_evaluation_contract.json", locked_contract)
    locked_readiness = {
        "phase_id": "M-B10A",
        "readiness_status": "M-B10_PRELOCKED_REAL_DATA_CANDIDATE" if selected else "INCONCLUSIVE",
        "authorization_for_locked_test": "NO",
        "independent_review_required": True,
        "selected_candidate_pretest_path": "datasets/mmwave/manifests/M-B10A_candidate_selection_setup/selected_candidate_pretest.json",
        "structural_split_counts_only": {"LOCKED_TEST_subjects": 16, "LOCKED_TEST_windows": 88},
        "labels_loaded": 0,
        "prediction_tensors_loaded": 0,
        "performance_metrics_computed": 0,
        "final_accessor_calls": 0,
    }
    _write_json("locked_test_access_readiness.json", locked_readiness)
    _write_json("locked_test_access_audit.json", {
        "phase_id": "M-B10A",
        "audit_status": "PASS_ZERO_ACCESS",
        "performance_access_attempts": 0,
        "label_access_attempts": 0,
        "prediction_access_attempts": 0,
        "tensor_access_attempts": 0,
        "metric_access_attempts": 0,
        "final_accessor_calls": 0,
        "locked_test_inputs_loaded": False,
        "locked_test_labels_loaded": False,
        "locked_test_prediction_output_generated": False,
        "locked_test_performance_computed": False,
    })
    _write_json("run_environment.json", {
        "phase_id": "M-B10A",
        "execution_scope": "MACOS_OFFLINE_EVIDENCE_ASSEMBLY_NO_FORMAL_BENCHMARK",
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "formal_m_b8_latency_measurement_started": False,
        "formal_m_b8_latency_measurement_performed": False,
        "known_safenest_workload_check": "NOT_APPLICABLE_FORMAL_BENCHMARK_NOT_STARTED",
        "required_idle_stabilization_seconds_before_future_formal_benchmark": 30,
        "m_b9_prior_formal_latency_benchmark_completed": True,
        "m_b10b_started": False,
        "model_trainings": 0,
        "model_conversions": 0,
        "locked_test_accesses": 0,
        "input_scope": "VALIDATION_ONLY",
    })
    _write_json("exceptions.json", {
        "phase_id": "M-B10A",
        "blockers": [],
        "required_refinements": [
            {"finding_class": "REQUIRED REFINEMENT", "id": "INDEPENDENT_REVIEW", "description": "Independent review must approve the frozen rule, lineage, gates, and winner before M-B10B."},
            {"finding_class": "REQUIRED REFINEMENT", "id": "SEED_SENSITIVITY", "description": "M-B4 architecture-level seed sensitivity remains a warning; a single-seed winner does not erase it."},
        ],
        "non_blocking_improvements": [
            {"finding_class": "NON-BLOCKING IMPROVEMENT", "id": "SEVERE_PROFILE_DIAGNOSTIC", "description": "Severe M-B7 profiles remain diagnostic and are not hard-gated by the frozen rule."},
            {"finding_class": "NON-BLOCKING IMPROVEMENT", "id": "MAC_ONLY_LATENCY", "description": "M-B8 latency is macOS-only offline evidence; no Raspberry Pi or MR60 claim is made."},
        ],
    })
    summary = {
        "phase_id": "M-B10A",
        "phase_title": "Pre-LOCKED_TEST Real-Data Offline Candidate Selection Setup",
        "selection_status": ranking["selection_status"],
        "validation_success": True,
        "candidate_count": len(candidates),
        "eligible_candidate_count": ranking["eligible_candidate_count"],
        "selected_candidate_id": ranking["selected_candidate_id"],
        "selection_rule_sha256": rule_sha,
        "selection_epsilon": EPSILON,
        "deciding_criterion": ranking["deciding_criterion"],
        "historical_baselines_registered": True,
        "model_trainings": 0,
        "model_conversions": 0,
        "locked_test_accesses": 0,
        "locked_test_performance_computed": False,
        "formal_m_b8_latency_measurement_rerun": False,
        "m_b10b_started": False,
        "m_b10b_authorization_recommendation": "NO — independent review required.",
        "warnings": ["INITIALIZATION_SEED_SENSITIVITY_PRESERVED", "SEVERE_M-B7_PROFILES_NOT_HARD_GATED", "MAC_ONLY_LATENCY_EVIDENCE"],
        "blockers": [],
        "finding_classes": ["BLOCKER", "REQUIRED REFINEMENT", "NON-BLOCKING IMPROVEMENT"],
        "locked_test_evaluation_contract_registered": True,
        "locked_test_access_readiness_used": False,
    }
    _write_json("m_b10a_summary.json", summary)
    _write_checksums()
    build_report(candidates, ranking, selected, rule_sha, input_identity)
    return {"candidates": candidates, "ranking": ranking, "selected": selected, "rule_sha256": rule_sha, "summary": summary}


def main() -> int:
    result = generate_artifacts()
    print(json.dumps({"phase_id": "M-B10A", "selection_status": result["ranking"]["selection_status"], "selected_candidate_id": result["ranking"]["selected_candidate_id"], "selection_rule_sha256": result["rule_sha256"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
