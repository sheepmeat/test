#!/usr/bin/env python3
"""Independent fail-closed validator for the SafeNest M-B10A setup.

The validator treats the M-B10A JSON summaries, eligibility booleans, ranking,
and selected-candidate file as untrusted claims.  It rechecks hashes, actual
TFLite tensor contracts, frozen VALIDATION predictions, M-B6/M-B7 metrics,
eligibility gates, lexicographic ranking, baseline exclusion, and the
pre-registered final-test protocol.  It never calls the LOCKED_TEST final
accessor and never loads LOCKED_TEST labels, tensors, predictions, or metrics.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from mmwave_m_b10a_selection import (  # noqa: E402
    ARCHITECTURE_ID,
    CALIBRATION_PROFILE,
    EPSILON,
    LABELS,
    MODEL_PATHS,
    MODERATE_PROFILES,
    OUT_DIR_REL,
    RANKING_CRITERIA,
    REQUIRED_OUTPUTS,
    SEEDS,
    STAGE,
    _sha256,
)


class MB10AValidationError(RuntimeError):
    """Raised when M-B10A evidence fails closed."""


def _source_path(source_root: Path, relative: str | Path) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in str(relative) or str(relative).startswith("~"):
        raise MB10AValidationError(f"M-B10A_ABSOLUTE_OR_TRAVERSAL_PATH:{relative}")
    return source_root / path


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MB10AValidationError(f"M-B10A_JSON_PARSE_ERROR:{path.name}:{exc}") from exc


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float, np.number)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(k) and _finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    return True


def _close(actual: float, expected: float, tolerance: float = 1e-5) -> bool:
    return math.isfinite(float(actual)) and math.isfinite(float(expected)) and abs(float(actual) - float(expected)) <= tolerance


def _independent_metrics_from_predictions(labels: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    """Recompute confusion-derived metrics without importing the selector's calculator."""
    labels = np.asarray(labels, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    if labels.shape != predictions.shape:
        raise MB10AValidationError(f"M-B10A_VALIDATION_SHAPE_MISMATCH:{labels.shape}:{predictions.shape}")
    confusion = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for truth, prediction in zip(labels.tolist(), predictions.tolist()):
        if truth not in range(len(LABELS)) or prediction not in range(len(LABELS)):
            raise MB10AValidationError("M-B10A_VALIDATION_CLASS_INDEX")
        confusion[truth, prediction] += 1
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
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1_score": round(f1, 6),
            "support": support,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        }
        f1_values.append(f1)
        recalls.append(recall)
        precisions.append(precision)
    distribution = {label: int((predictions == index).sum()) for index, label in enumerate(LABELS)}
    zero_prediction = [label for label, count in distribution.items() if count == 0]
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
        "prediction_distribution": distribution,
        "class_collapse": {"collapsed": bool(zero_prediction or zero_recall), "zero_prediction_classes": zero_prediction, "zero_recall_classes": zero_recall},
    }


def _validate_checksums(output_dir: Path) -> None:
    checksums = output_dir / "checksums.sha256"
    if not checksums.is_file():
        raise MB10AValidationError("M-B10A_CHECKSUM_MANIFEST_MISSING")
    seen: set[str] = set()
    for line_number, line in enumerate(checksums.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0].lower()):
            raise MB10AValidationError(f"M-B10A_CHECKSUM_SYNTAX:{line_number}")
        digest, relative = parts[0].lower(), parts[1].strip()
        target_rel = Path(relative)
        if target_rel.is_absolute() or ".." in target_rel.parts or "\\" in relative or "file://" in relative or relative.startswith("~"):
            raise MB10AValidationError(f"M-B10A_CHECKSUM_PATH:{relative}")
        if relative in seen:
            raise MB10AValidationError(f"M-B10A_CHECKSUM_DUPLICATE:{relative}")
        seen.add(relative)
        target = output_dir / target_rel
        if target.parent.resolve() != output_dir.resolve() or not target.is_file():
            raise MB10AValidationError(f"M-B10A_CHECKSUM_TARGET:{relative}")
        if _sha256(target) != digest:
            raise MB10AValidationError(f"M-B10A_CHECKSUM_MISMATCH:{relative}")
    expected = set(REQUIRED_OUTPUTS) - {"checksums.sha256"}
    if seen != expected:
        raise MB10AValidationError(f"M-B10A_CHECKSUM_COVERAGE:missing={sorted(expected - seen)}:unexpected={sorted(seen - expected)}")
    actual_files = {path.name for path in output_dir.iterdir() if path.is_file() and path.name != "checksums.sha256"}
    if actual_files != expected:
        raise MB10AValidationError(f"M-B10A_UNREGISTERED_OUTPUT_FILES:{sorted(actual_files ^ expected)}")


def _validate_machine_paths(output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if path.suffix not in {".json", ".sha256"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "/Users/" in text or "/private/" in text or "file://" in text or "\\\\" in text:
            raise MB10AValidationError(f"M-B10A_LOCAL_PATH_IN_ARTIFACT:{path.name}")


FORBIDDEN_SAMPLE_LEVEL_KEYS = {
    "locked_test_predictions",
    "locked_test_labels",
    "locked_test_tensors",
    "locked_test_macro_f1",
    "locked_test_confusion",
    "locked_test_metrics",
    "test_subject_metrics",
    "test_prediction_distribution",
    "final_locked_test_predictions",
    "final_locked_test_labels",
}


def _scan_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_SAMPLE_LEVEL_KEYS:
                raise MB10AValidationError(f"M-B10A_FORBIDDEN_LOCKED_TEST_FIELD:{location}.{key}")
            _scan_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, f"{location}[{index}]")


def _load_output(output_dir: Path) -> dict[str, Any]:
    if not output_dir.is_dir():
        raise MB10AValidationError("M-B10A_OUTPUT_DIRECTORY_MISSING")
    _validate_checksums(output_dir)
    _validate_machine_paths(output_dir)
    loaded: dict[str, Any] = {}
    for name in REQUIRED_OUTPUTS:
        if name == "checksums.sha256":
            continue
        path = output_dir / name
        if not path.is_file():
            raise MB10AValidationError(f"M-B10A_REQUIRED_OUTPUT_MISSING:{name}")
        loaded[name] = _load_json(path)
        if not _finite(loaded[name]):
            raise MB10AValidationError(f"M-B10A_NONFINITE_ARTIFACT:{name}")
        _scan_forbidden_keys(loaded[name], name)
    return loaded


def _validate_input_identity(source_root: Path, identity: dict[str, Any]) -> None:
    rows = identity.get("inputs")
    if identity.get("phase_id") != "M-B10A" or not isinstance(rows, list) or identity.get("total_inputs") != len(rows) or len(rows) < 60:
        raise MB10AValidationError("M-B10A_INPUT_IDENTITY_INCOMPLETE")
    seen: set[str] = set()
    for row in rows:
        relative = row.get("path")
        if not isinstance(relative, str) or relative in seen:
            raise MB10AValidationError(f"M-B10A_INPUT_IDENTITY_DUPLICATE_OR_INVALID:{relative}")
        seen.add(relative)
        path = _source_path(source_root, relative)
        if not path.is_file():
            raise MB10AValidationError(f"M-B10A_INPUT_IDENTITY_MISSING:{relative}")
        if row.get("sha256") != _sha256(path) or int(row.get("bytes", -1)) != path.stat().st_size:
            raise MB10AValidationError(f"M-B10A_INPUT_IDENTITY_MISMATCH:{relative}")
    for seed, relative in MODEL_PATHS.items():
        rows_for_seed = [row for row in rows if row.get("path") == relative and int(row.get("seed", -1)) == seed]
        if len(rows_for_seed) != 1:
            raise MB10AValidationError(f"M-B10A_MODEL_IDENTITY_ROW_MISSING:{seed}")


def _inspect_tflite(source_root: Path, path_relative: str) -> dict[str, Any]:
    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:  # pragma: no cover - environment failure is itself a blocker
        raise MB10AValidationError(f"M-B10A_TFLITE_RUNTIME_UNAVAILABLE:{exc}") from exc
    path = _source_path(source_root, path_relative)
    try:
        interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=1)
        interpreter.allocate_tensors()
        input_detail = interpreter.get_input_details()[0]
        output_detail = interpreter.get_output_details()[0]
        op_details = interpreter._get_ops_details()  # noqa: SLF001 - independent structural inspection
        op_names = [str(row.get("op_name", "")) for row in op_details]
    except Exception as exc:
        raise MB10AValidationError(f"M-B10A_TFLITE_INSPECTION_FAILED:{path_relative}:{exc}") from exc
    input_quant = tuple(float(value) for value in input_detail.get("quantization", (0.0, 0)))
    output_quant = tuple(float(value) for value in output_detail.get("quantization", (0.0, 0)))
    return {
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "input_dtype": str(np.dtype(input_detail["dtype"])),
        "input_shape": [int(value) for value in input_detail["shape"]],
        "input_scale": input_quant[0],
        "input_zero_point": int(input_quant[1]),
        "output_dtype": str(np.dtype(output_detail["dtype"])),
        "output_shape": [int(value) for value in output_detail["shape"]],
        "output_scale": output_quant[0],
        "output_zero_point": int(output_quant[1]),
        "op_names": op_names,
        "flex_select_absent": not any("FLEX" in name.upper() or "SELECT" in name.upper() for name in op_names),
    }


def _independent_metrics(source_root: Path, seed: int, profile: str, labels: np.ndarray) -> dict[str, Any]:
    # The selection module's loader is path-rooted.  Reproduce the small read
    # here so validation cannot accept a summary-only claim.
    path = _source_path(source_root, "datasets/mmwave/manifests/M-B7_perturbation_robustness/prediction_vectors.npz")
    with np.load(path, allow_pickle=False) as arrays:
        prefix = f"seed_{seed}__{profile}__"
        if prefix + "predictions" not in arrays.files:
            raise MB10AValidationError(f"M-B10A_PREDICTION_VECTOR_MISSING:{seed}:{profile}")
        predictions = np.asarray(arrays[prefix + "predictions"], dtype=np.int64)
        saturation = np.asarray(arrays[prefix + "saturation_counts"], dtype=np.int64)
        valid = np.asarray(arrays[prefix + "valid_mask"], dtype=np.uint8) if prefix + "valid_mask" in arrays.files else np.ones(predictions.shape, dtype=np.uint8)
    if predictions.shape != labels.shape or not np.all(valid.astype(bool)):
        raise MB10AValidationError(f"M-B10A_INVALID_VALIDATION_VECTOR:{seed}:{profile}")
    result = _independent_metrics_from_predictions(labels, predictions)
    result["saturation_ratio"] = float(np.sum(saturation) / (labels.size * 300))
    result["predictions"] = predictions
    return result


def _candidate_by_id(pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = pool.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        raise MB10AValidationError("M-B10A_CANDIDATE_POOL_COUNT")
    result = {}
    for candidate in candidates:
        cid = candidate.get("candidate_id")
        if not isinstance(cid, str) or cid in result:
            raise MB10AValidationError("M-B10A_CANDIDATE_POOL_ID")
        result[cid] = candidate
    return result


def _validate_candidate_pool(source_root: Path, artifacts: dict[str, Any], labels: np.ndarray) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    pool = artifacts["candidate_pool.json"]
    by_id = _candidate_by_id(pool)
    if pool.get("pool_status") != "FROZEN_REAL_DATA_STRICT_INT8_POOL" or pool.get("selection_rule_sha256") != artifacts["candidate_ranking.json"].get("selection_rule_sha256"):
        raise MB10AValidationError("M-B10A_POOL_SCOPE_OR_RULE_BINDING")
    if sorted(int(candidate.get("seed", -1)) for candidate in by_id.values()) != list(SEEDS):
        raise MB10AValidationError("M-B10A_POOL_SEED_SET")
    runtime_identity = artifacts["input_identity.json"]
    b9_runtime = json.loads(_source_path(source_root, "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_model_identity.json").read_text(encoding="utf-8"))
    b9_pre = json.loads(_source_path(source_root, "datasets/mmwave/manifests/M-B9_mock_e2e/runtime_preprocessing_identity.json").read_text(encoding="utf-8"))
    b6_collapses = _load_json(_source_path(source_root, "datasets/mmwave/manifests/M-B6_stage_equivalence/class_collapse_transition_audit.json"))["class_collapse_transitions"]
    b6_pairs = _load_json(_source_path(source_root, "datasets/mmwave/manifests/M-B6_stage_equivalence/pairwise_equivalence_metrics.json"))["pairwise_equivalence"]
    b7_summary = _load_json(_source_path(source_root, "datasets/mmwave/manifests/M-B7_perturbation_robustness/m_b7_summary.json"))
    b7_clean = _load_json(_source_path(source_root, "datasets/mmwave/manifests/M-B7_perturbation_robustness/clean_baseline_results.json"))["per_seed"]
    b1 = _load_json(_source_path(source_root, "datasets/mmwave/manifests/M-B1_preprocessing_ablation/selected_preprocessing_profile.json"))
    a5_summary = _load_json(_source_path(source_root, "datasets/mmwave/manifests/a5_subject_split/a5_summary.json"))
    a6_summary = _load_json(_source_path(source_root, "datasets/mmwave/manifests/a6_full_conversion/a6_summary.json"))
    recomputed_candidates: list[dict[str, Any]] = []
    for seed in SEEDS:
        candidate = next((row for row in by_id.values() if int(row.get("seed", -1)) == seed), None)
        if candidate is None:
            raise MB10AValidationError(f"M-B10A_CANDIDATE_SEED_MISSING:{seed}")
        model_path = MODEL_PATHS[seed]
        actual = _inspect_tflite(source_root, model_path)
        model_claim = candidate.get("model", {})
        for field in ("bytes", "sha256", "input_dtype", "input_shape", "input_scale", "input_zero_point", "output_dtype", "output_shape", "output_scale", "output_zero_point"):
            if field == "input_shape" or field == "output_shape":
                if list(model_claim.get(field, [])) != list(actual[field]):
                    raise MB10AValidationError(f"M-B10A_MODEL_CONTRACT_MISMATCH:{seed}:{field}")
            elif field in ("input_scale", "output_scale"):
                if not _close(float(model_claim.get(field)), float(actual[field]), 1e-12):
                    raise MB10AValidationError(f"M-B10A_MODEL_CONTRACT_MISMATCH:{seed}:{field}")
            elif model_claim.get(field) != actual[field]:
                raise MB10AValidationError(f"M-B10A_MODEL_CONTRACT_MISMATCH:{seed}:{field}")
        if actual["input_dtype"] != "int8" or actual["output_dtype"] != "int8" or actual["input_shape"] != [1, 300, 1] or actual["output_shape"] != [1, 3] or not actual["flex_select_absent"]:
            raise MB10AValidationError(f"M-B10A_STRICT_INT8_CONTRACT:{seed}")
        clean = _independent_metrics(source_root, seed, "M-B7_CLEAN", labels)
        clean_predictions = clean.pop("predictions")
        moderate: dict[str, Any] = {}
        for profile in MODERATE_PROFILES:
            row = _independent_metrics(source_root, seed, profile, labels)
            predictions = row.pop("predictions")
            recall_degradation = {
                label: max(0.0, float(clean["per_class"][label]["recall"]) - float(row["per_class"][label]["recall"]))
                for label in LABELS
            }
            moderate[profile] = {
                "metrics": row,
                "positive_macro_f1_degradation": max(0.0, float(clean["macro_f1"]) - float(row["macro_f1"])),
                "maximum_positive_per_class_recall_degradation": max(recall_degradation.values()),
                "top1_agreement": float(np.mean(clean_predictions == predictions)),
                "input_saturation_ratio": row["saturation_ratio"],
                "collapsed": bool(row["class_collapse"]["collapsed"]),
            }
        runtime_rows = [row for row in b9_pre.get("rows", []) if int(row.get("seed", -1)) == seed]
        runtime_pre_exact = bool(runtime_rows) and all(
            row.get("preprocessing_profile") == "BPF_ZSCORE" and row.get("bpf_exact") is True and row.get("zscore_exact") is True and row.get("model_ready_exact") is True and row.get("input_int8_exact") is True and row.get("saturation_exact") is True
            for row in runtime_rows
        )
        runtime_variant = next((row for row in b9_runtime.get("variants", []) if int(row.get("seed", -1)) == seed), None)
        if runtime_variant is None:
            raise MB10AValidationError(f"M-B10A_RUNTIME_VARIANT_MISSING:{seed}")
        clean_class_collapse = bool(clean["class_collapse"]["collapsed"])
        gates = {
            "E1": True,  # input identity and upstream path/hash checks are performed before this function
            "E2": bool(actual["flex_select_absent"]),
            "E3": not clean_class_collapse,
            "E4": not bool(b6_collapses[f"{ARCHITECTURE_ID}_seed_{seed}"].get("new_collapse_a_to_c") or b6_collapses[f"{ARCHITECTURE_ID}_seed_{seed}"].get("new_collapse_b_to_c")),
            "E5": runtime_variant.get("path") == model_path and runtime_variant.get("actual_sha256") == actual["sha256"] and int(runtime_variant.get("actual_bytes", -1)) == actual["bytes"],
            "E6": int(b7_summary.get("invalid_or_fallback_sample_count", -1)) == 0 and int(_independent_metrics(source_root, seed, "M-B7_CLEAN", labels)["evaluated_sample_count"]) >= 79,
            "E7": b1.get("selected_profile_id") == "M-B1_D0_B1_Z1" and b1.get("selected_profile_name") == "BPF_ZSCORE" and runtime_pre_exact,
            "E8": (
                a5_summary.get("validation_success") is True
                and a5_summary.get("validation_errors") == []
                and a6_summary.get("validation_passed") is True
                and a6_summary.get("validator_verdict", {}).get("validation_success") is True
                and all(int(value) == 0 for value in a6_summary.get("validator_verdict", {}).get("leakage_recalculated", {}).values())
                and not bool(b7_summary.get("blockers"))
                and all(bool(row.get("sha256_match")) and bool(row.get("bytes_match")) for row in b9_runtime.get("variants", []))
            ),
            "E9": all(float(clean["per_class"][label]["recall"]) > 0.0 for label in LABELS),
            "E10": all(float(clean["per_class"][label]["precision"]) > 0.0 for label in LABELS),
            "E11": all(not row["collapsed"] for row in moderate.values()),
        }
        ranking_metrics = {
            "clean_strict_int8_macro_f1": clean["macro_f1"],
            "clean_min_per_class_recall": clean["min_per_class_recall"],
            "clean_apnea_proxy_recall": clean["per_class"]["APNEA"]["recall"],
            "clean_apnea_proxy_precision": clean["per_class"]["APNEA"]["precision"],
            "worst_subject_clean_macro_f1": candidate["ranking_metrics"]["worst_subject_clean_macro_f1"],
            "moderate_worst_positive_macro_f1_degradation": max(float(row["positive_macro_f1_degradation"]) for row in moderate.values()),
            "moderate_worst_positive_recall_degradation": max(float(row["maximum_positive_per_class_recall_degradation"]) for row in moderate.values()),
            "moderate_min_top1_agreement": min(float(row["top1_agreement"]) for row in moderate.values()),
            "moderate_max_input_saturation_ratio": max(float(row["input_saturation_ratio"]) for row in moderate.values()),
            "m_b6_positive_float_to_int8_macro_f1_degradation": float(b6_pairs[f"{ARCHITECTURE_ID}_seed_{seed}"]["a_to_c"]["positive_macro_f1_degradation"]),
            "m_b6_keras_to_int8_top1_agreement": float(b6_pairs[f"{ARCHITECTURE_ID}_seed_{seed}"]["a_to_c"]["top1_agreement"]),
            "m_b8_pipeline_p99_ns": float(candidate["ranking_metrics"]["m_b8_pipeline_p99_ns"]),
            "tflite_bytes": int(actual["bytes"]),
            "training_seed": seed,
        }
        recomputed_candidates.append({
            "candidate_id": candidate["candidate_id"],
            "seed": seed,
            "eligible": bool(all(gates.values())),
            "gates": gates,
            "clean": clean,
            "moderate": moderate,
            "ranking_metrics": ranking_metrics,
        })
        # Saved candidate metrics and saved eligibility booleans are compared,
        # never trusted as the source of truth.
        saved_gates = candidate.get("eligibility", {})
        for rule_id, value in gates.items():
            if bool(saved_gates.get(rule_id, {}).get("passed")) != bool(value):
                raise MB10AValidationError(f"M-B10A_ELIGIBILITY_CLAIM_MISMATCH:{seed}:{rule_id}")
        for metric, value in ranking_metrics.items():
            if not _close(float(candidate["ranking_metrics"].get(metric)), float(value), 2e-5):
                raise MB10AValidationError(f"M-B10A_RANKING_METRIC_CLAIM_MISMATCH:{seed}:{metric}")
    return recomputed_candidates, by_id


def _compare(left: dict[str, Any], right: dict[str, Any]) -> int:
    for _rank, metric, direction, _description in RANKING_CRITERIA:
        lvalue = float(left["ranking_metrics"][metric])
        rvalue = float(right["ranking_metrics"][metric])
        if abs(lvalue - rvalue) <= EPSILON:
            continue
        preferred = lvalue > rvalue if direction == "higher" else lvalue < rvalue
        return -1 if preferred else 1
    return 0


def _validate_ranking(artifacts: dict[str, Any], recomputed: list[dict[str, Any]], rule_sha: str) -> None:
    rule = artifacts["selection_rule.json"]
    if not rule.get("frozen_before_candidate_winner") or float(rule.get("epsilon")) != EPSILON or rule.get("no_composite_score") is not True:
        raise MB10AValidationError("M-B10A_SELECTION_RULE_NOT_FROZEN")
    expected_criteria = [{"rank": rank, "metric": metric, "direction": direction, "description": description} for rank, metric, direction, description in RANKING_CRITERIA]
    if rule.get("ranking_criteria") != expected_criteria:
        raise MB10AValidationError("M-B10A_SELECTION_RULE_CRITERIA_MISMATCH")
    ranking = artifacts["candidate_ranking.json"]
    selected = artifacts["selected_candidate_pretest.json"]
    eligible = sorted((row for row in recomputed if row["eligible"]), key=functools.cmp_to_key(_compare))
    expected_ids = [row["candidate_id"] for row in eligible]
    if ranking.get("selection_rule_sha256") != rule_sha or ranking.get("eligible_candidate_ids") != expected_ids:
        raise MB10AValidationError("M-B10A_RANKING_ELIGIBILITY_MISMATCH")
    saved_order = [row.get("candidate_id") for row in ranking.get("ordered_candidates", [])]
    if saved_order != expected_ids:
        raise MB10AValidationError("M-B10A_RANKING_ORDER_MISMATCH")
    expected_selected = expected_ids[0] if expected_ids else None
    if ranking.get("selected_candidate_id") != expected_selected or selected.get("candidate_id") != expected_selected:
        raise MB10AValidationError("M-B10A_SELECTED_WINNER_MISMATCH")
    expected_status = "SELECTED_PRELOCKED_REAL_DATA_CANDIDATE" if expected_selected else "INCONCLUSIVE"
    if ranking.get("selection_status") != expected_status or selected.get("status") not in {"M-B10_PRELOCKED_REAL_DATA_CANDIDATE", "INCONCLUSIVE"}:
        raise MB10AValidationError("M-B10A_SELECTION_STATUS_MISMATCH")
    if expected_selected and selected.get("status") != "M-B10_PRELOCKED_REAL_DATA_CANDIDATE":
        raise MB10AValidationError("M-B10A_SELECTED_STATUS_MISMATCH")
    if selected.get("locked_test_accessed") is not False or selected.get("m_b10b_started") is not False or selected.get("deployment_allowed") is not False:
        raise MB10AValidationError("M-B10A_SELECTED_PRETEST_OVERCLAIM")


def _validate_baselines(source_root: Path, registry: dict[str, Any], pool: dict[str, Any]) -> None:
    manifest = _load_json(_source_path(source_root, "models/model_manifest.json"))["models"]
    rows = registry.get("baselines")
    if registry.get("registry_status") != "BASELINES_REGISTERED_EXCLUDED_FROM_CANDIDATE_POOL" or not isinstance(rows, list) or len(rows) != 2:
        raise MB10AValidationError("M-B10A_BASELINE_REGISTRY_INVALID")
    for row in rows:
        baseline_id = row.get("baseline_id")
        key = "mmwave" if baseline_id == "mmwave_resp_int8" else "mmwave_v0_2_0_candidate" if baseline_id == "mmwave_resp_int8_v0.2.0_candidate" else None
        if key is None or row.get("pool_eligible") is not False:
            raise MB10AValidationError("M-B10A_BASELINE_POOL_LEAK")
        path = _source_path(source_root, row["path"])
        if row.get("sha256") != _sha256(path) or row.get("manifest_sha256") != manifest[key].get("sha256"):
            raise MB10AValidationError(f"M-B10A_BASELINE_HASH:{baseline_id}")
        if not row.get("exclusion_reason"):
            raise MB10AValidationError(f"M-B10A_BASELINE_REASON:{baseline_id}")
    pool_ids = set(pool.get("candidate_ids", []))
    if any("mmwave_resp_int8" in candidate_id for candidate_id in pool_ids):
        raise MB10AValidationError("M-B10A_HISTORICAL_BASELINE_IN_POOL")


def _validate_locked_protocol(artifacts: dict[str, Any], selected_id: str | None) -> None:
    contract = artifacts["locked_test_evaluation_contract.json"]
    readiness = artifacts["locked_test_access_readiness.json"]
    audit = artifacts["locked_test_access_audit.json"]
    if contract.get("contract_status") != "PREREGISTERED_NOT_EXECUTED" or contract.get("candidate_reference") != selected_id or contract.get("source_split") != "LOCKED_TEST":
        raise MB10AValidationError("M-B10A_FINAL_PROTOCOL_INVALID")
    if contract.get("selection_and_tuning_after_access") is not False or contract.get("retraining_after_access") is not False or contract.get("recalibration_after_access") is not False:
        raise MB10AValidationError("M-B10A_FINAL_PROTOCOL_RETUNING_ALLOWED")
    if readiness.get("authorization_for_locked_test") != "NO" or readiness.get("independent_review_required") is not True or readiness.get("final_accessor_calls") != 0:
        raise MB10AValidationError("M-B10A_LOCKED_TEST_READINESS_INVALID")
    zero_fields = ("performance_access_attempts", "label_access_attempts", "prediction_access_attempts", "tensor_access_attempts", "metric_access_attempts", "final_accessor_calls")
    if audit.get("audit_status") != "PASS_ZERO_ACCESS" or any(audit.get(field) != 0 for field in zero_fields):
        raise MB10AValidationError("M-B10A_LOCKED_TEST_AUDIT_NONZERO")
    if any(audit.get(field) is not False for field in ("locked_test_inputs_loaded", "locked_test_labels_loaded", "locked_test_prediction_output_generated", "locked_test_performance_computed")):
        raise MB10AValidationError("M-B10A_LOCKED_TEST_ARTIFACT_ACCESS")


def _validate_summary(artifacts: dict[str, Any], ranking: dict[str, Any], rule_sha: str) -> None:
    summary = artifacts["m_b10a_summary.json"]
    if summary.get("validation_success") is not True or summary.get("selection_rule_sha256") != rule_sha or summary.get("selected_candidate_id") != ranking.get("selected_candidate_id"):
        raise MB10AValidationError("M-B10A_SUMMARY_NOT_BOUND_TO_INDEPENDENT_RESULT")
    if summary.get("locked_test_accesses") != 0 or summary.get("locked_test_performance_computed") is not False or summary.get("m_b10b_started") is not False:
        raise MB10AValidationError("M-B10A_SUMMARY_LOCKED_TEST_CONTAMINATION")
    if summary.get("model_trainings") != 0 or summary.get("model_conversions") != 0 or summary.get("formal_m_b8_latency_measurement_rerun") is not False:
        raise MB10AValidationError("M-B10A_UNAUTHORIZED_WORK")


def _run_upstream_validators(source_root: Path) -> None:
    commands = [
        ["python3", "scripts/validate_mmwave_m_b9.py"],
        ["python3", "scripts/validate_mmwave_m_b8.py"],
        ["python3", "scripts/validate_mmwave_m_b7.py"],
        ["python3", "scripts/validate_mmwave_m_b6.py"],
        ["python3", "scripts/validate_mmwave_m_b5.py"],
        ["python3", "scripts/validate_mmwave_m_b4.py"],
        ["python3", "scripts/validate_mmwave_m_b3.py"],
        ["python3", "scripts/validate_mmwave_m_b2.py"],
        ["python3", "scripts/validate_mmwave_m_b1.py"],
        ["python3", "scripts/validate_mmwave_m_b0.py"],
        ["python3", "scripts/validate_mmwave_subject_split.py"],
        ["python3", "scripts/validate_mmwave_full_conversion.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=source_root, capture_output=True, text=True)
        if completed.returncode != 0:
            raise MB10AValidationError(f"M-B10A_UPSTREAM_VALIDATOR_FAILED:{' '.join(command)}\n{completed.stdout[-1200:]}\n{completed.stderr[-1200:]}")


def validate_m_b10a_artifacts(root_dir: Path = ROOT_DIR, output_dir: Path | None = None, run_upstream: bool = False) -> dict[str, Any]:
    """Validate M-B10A output; ``run_upstream`` is enabled by the CLI."""
    source_root = root_dir.resolve()
    out = (output_dir or (source_root / OUT_DIR_REL)).resolve()
    artifacts = _load_output(out)
    identity = artifacts["input_identity.json"]
    _validate_input_identity(source_root, identity)
    rule_sha = _sha256(out / "selection_rule.json")
    if artifacts["candidate_ranking.json"].get("selection_rule_sha256") != rule_sha or artifacts["experiment_contract.json"].get("selection_rule_sha256") != rule_sha:
        raise MB10AValidationError("M-B10A_RULE_SHA_BINDING")
    labels, _subjects, _window_ids = _load_validation_index_from_root(source_root)
    recomputed, by_id = _validate_candidate_pool(source_root, artifacts, labels)
    _validate_ranking(artifacts, recomputed, rule_sha)
    _validate_baselines(source_root, artifacts["historical_baseline_registry.json"], artifacts["candidate_pool.json"])
    _validate_locked_protocol(artifacts, artifacts["candidate_ranking.json"].get("selected_candidate_id"))
    _validate_summary(artifacts, artifacts["candidate_ranking.json"], rule_sha)
    if run_upstream:
        _run_upstream_validators(source_root)
    return {
        "validation_status": "PASS",
        "phase_id": "M-B10A",
        "selection_status": artifacts["candidate_ranking.json"].get("selection_status"),
        "selected_candidate_id": artifacts["candidate_ranking.json"].get("selected_candidate_id"),
        "eligible_candidate_count": len([row for row in recomputed if row["eligible"]]),
        "locked_test_accesses": 0,
        "m_b10b_started": False,
        "upstream_validators_run": run_upstream,
    }


def _load_validation_index_from_root(source_root: Path) -> tuple[np.ndarray, list[str], list[str]]:
    path = _source_path(source_root, "datasets/mmwave/manifests/M-B6_stage_equivalence/validation_prediction_index.jsonl")
    labels: list[int] = []
    subjects: list[str] = []
    window_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            labels.append(LABELS.index(str(row["true_label"])))
            subjects.append(str(row["subject_id"]))
            window_ids.append(str(row.get("window_id", row.get("recording_id", ""))))
    if len(labels) != 79:
        raise MB10AValidationError("M-B10A_VALIDATION_INDEX_COUNT")
    return np.asarray(labels, dtype=np.int64), subjects, window_ids


NEGATIVE_CASES = (
    "eligibility_gate_corruption",
    "ranking_winner_corruption",
    "identity_sha_corruption",
    "baseline_registry_corruption",
    "locked_test_protocol_corruption",
    "checksum_corruption",
    "forbidden_final_artifact",
)


def _negative_case_detected(case_id: str, root_dir: Path = ROOT_DIR) -> bool:
    if case_id not in NEGATIVE_CASES:
        raise ValueError(case_id)
    source_root = root_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="safenest-m-b10a-negative-") as temp:
        temp_out = Path(temp) / "out"
        shutil.copytree(source_root / OUT_DIR_REL, temp_out)
        target = temp_out / "candidate_pool.json"
        if case_id == "eligibility_gate_corruption":
            data = _load_json(target)
            data["candidates"][0]["eligibility"]["E11"]["passed"] = False
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif case_id == "ranking_winner_corruption":
            target = temp_out / "candidate_ranking.json"
            data = _load_json(target)
            data["selected_candidate_id"] = data["ordered_candidates"][1]["candidate_id"]
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif case_id == "identity_sha_corruption":
            target = temp_out / "input_identity.json"
            data = _load_json(target)
            data["inputs"][0]["sha256"] = "0" * 64
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif case_id == "baseline_registry_corruption":
            target = temp_out / "historical_baseline_registry.json"
            data = _load_json(target)
            data["baselines"][0]["pool_eligible"] = True
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif case_id == "locked_test_protocol_corruption":
            target = temp_out / "locked_test_access_audit.json"
            data = _load_json(target)
            data["prediction_access_attempts"] = 1
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif case_id == "checksum_corruption":
            target = temp_out / "candidate_ranking.json"
            data = target.read_text(encoding="utf-8").replace("0.224991", "0.224992", 1)
            target.write_text(data, encoding="utf-8")
        elif case_id == "forbidden_final_artifact":
            target = temp_out / "locked_test_predictions.json"
            target.write_text("{}\n", encoding="utf-8")
        try:
            validate_m_b10a_artifacts(source_root, output_dir=temp_out, run_upstream=False)
        except MB10AValidationError:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate M-B10A setup evidence")
    parser.add_argument("--skip-upstream", action="store_true", help="Skip the required upstream validator chain (unit-test helper only).")
    args = parser.parse_args()
    try:
        result = validate_m_b10a_artifacts(ROOT_DIR, run_upstream=not args.skip_upstream)
    except MB10AValidationError as exc:
        print(json.dumps({"validation_status": "FAIL", "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
