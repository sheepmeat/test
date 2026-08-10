# SafeNest mmWave Track — Phase M-B5 Calibration Profiles & Strict INT8 Evaluator

import hashlib
import json
import os
import sys
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple

import tensorflow as tf

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from mmwave_m_b1_preprocessing import fit_train_zscore_statistics, transform_signals
from mmwave_m_b2_imbalance import LABEL_NAMES, compute_one_vs_rest_false_positives, compute_subject_level_diagnostics
from mmwave_m_b3_architecture import build_model_by_id, compute_numerical_weights_sha256
from mmwave_phase_b_access import PhaseBAccessGuard

CALIBRATION_SAMPLE_COUNT = 120
CALIBRATION_RNG_SEED = 20260810
SHORTLIST_SEEDS = [42, 43, 44]

PROFILE_IDS = [
    "M-B5_CAL_TRAIN_ORDER_120",
    "M-B5_CAL_RANDOM_PROPORTIONAL_120",
    "M-B5_CAL_CLASS_BALANCED_120",
    "M-B5_CAL_DISTRIBUTION_AWARE_120",
]


def build_profile_a_train_order(train_windows: List[Dict[str, Any]], sample_count: int = CALIBRATION_SAMPLE_COUNT) -> List[int]:
    """Profile A: First sample_count pure-class TRAIN rows in canonical TRAIN order."""
    if len(train_windows) < sample_count:
        raise ValueError(f"TRAIN dataset has fewer than {sample_count} samples: {len(train_windows)}")
    return list(range(sample_count))


def build_profile_b_random_proportional(
    train_windows: List[Dict[str, Any]],
    sample_count: int = CALIBRATION_SAMPLE_COUNT,
    seed: int = CALIBRATION_RNG_SEED,
) -> List[int]:
    """Profile B: Proportional class random sample without replacement using pinned RNG."""
    total = len(train_windows)
    label_ids = [w["safenest_label_id"] for w in train_windows]
    class_counts = {c: label_ids.count(idx) for idx, c in enumerate(LABEL_NAMES)}

    # Largest-remainder allocation
    raw_alloc = {c: sample_count * class_counts[c] / total for c in LABEL_NAMES}
    int_alloc = {c: int(np.floor(raw_alloc[c])) for c in LABEL_NAMES}
    remainders = {c: raw_alloc[c] - int_alloc[c] for c in LABEL_NAMES}
    rem_needed = sample_count - sum(int_alloc.values())
    sorted_classes = sorted(LABEL_NAMES, key=lambda c: remainders[c], reverse=True)
    for i in range(rem_needed):
        int_alloc[sorted_classes[i]] += 1

    rng = np.random.RandomState(seed)
    selected_indices = []

    for idx, cname in enumerate(LABEL_NAMES):
        c_count_needed = int_alloc[cname]
        c_eligible = [i for i, w in enumerate(train_windows) if w["safenest_label_id"] == idx]
        if len(c_eligible) < c_count_needed:
            raise ValueError(f"Class '{cname}' has fewer eligible samples ({len(c_eligible)}) than needed ({c_count_needed})")
        sampled = rng.choice(c_eligible, size=c_count_needed, replace=False)
        selected_indices.extend(sampled.tolist())

    return sorted(selected_indices)


def build_profile_c_class_balanced(
    train_windows: List[Dict[str, Any]],
    sample_count: int = CALIBRATION_SAMPLE_COUNT,
    seed: int = CALIBRATION_RNG_SEED,
) -> List[int]:
    """Profile C: Equal class balanced sample (40 per class for 120 samples) without replacement."""
    target_per_class = sample_count // len(LABEL_NAMES)
    rng = np.random.RandomState(seed)
    selected_indices = []

    for idx, cname in enumerate(LABEL_NAMES):
        c_eligible = [i for i, w in enumerate(train_windows) if w["safenest_label_id"] == idx]
        if len(c_eligible) < target_per_class:
            raise ValueError(f"Balanced profile infeasible: class '{cname}' has only {len(c_eligible)} samples, need {target_per_class}")
        sampled = rng.choice(c_eligible, size=target_per_class, replace=False)
        selected_indices.extend(sampled.tolist())

    return sorted(selected_indices)


def build_profile_d_distribution_aware(
    train_windows: List[Dict[str, Any]],
    preprocessed_train_x: np.ndarray,
    sample_count: int = CALIBRATION_SAMPLE_COUNT,
) -> List[int]:
    """Profile D: Deterministic farthest-point coverage in robust-scaled feature space with subject diversity cap."""
    N = len(train_windows)
    features = []

    for i in range(N):
        sig = preprocessed_train_x[i]  # shape (250,) or (250, 1)
        sig_flat = sig.flatten()

        peak_abs = float(np.max(np.abs(sig_flat)))
        rms = float(np.sqrt(np.mean(sig_flat ** 2)))
        p01 = float(np.percentile(sig_flat, 1))
        p99 = float(np.percentile(sig_flat, 99))
        dyn_range = p99 - p01

        lbl_id = train_windows[i]["safenest_label_id"]
        class_onehot = [1.0 if lbl_id == idx else 0.0 for idx in range(3)]

        posture = train_windows[i].get("posture", "supine").lower()
        posture_map = {"supine": [1.0, 0.0, 0.0], "left": [0.0, 1.0, 0.0], "right": [0.0, 0.0, 1.0]}
        posture_onehot = posture_map.get(posture, [1.0, 0.0, 0.0])

        test_cond = train_windows[i].get("test_condition", "normal").lower()
        cond_map = {"normal": [1.0, 0.0, 0.0], "rapid": [0.0, 1.0, 0.0], "apnea_proxy": [0.0, 0.0, 1.0]}
        cond_onehot = cond_map.get(test_cond, [1.0, 0.0, 0.0])

        feat_row = [peak_abs, rms, p01, p99, dyn_range] + class_onehot + posture_onehot + cond_onehot
        features.append(feat_row)

    feat_matrix = np.array(features, dtype=np.float64)

    # Fit median & IQR on continuous features (cols 0..4)
    cont_feats = feat_matrix[:, :5]
    medians = np.median(cont_feats, axis=0)
    iqr = np.percentile(cont_feats, 75, axis=0) - np.percentile(cont_feats, 25, axis=0)
    iqr[iqr == 0] = 1.0

    norm_cont = (cont_feats - medians) / iqr
    norm_matrix = np.hstack([norm_cont, feat_matrix[:, 5:]])

    center = np.median(norm_matrix, axis=0)
    distances_from_center = np.linalg.norm(norm_matrix - center, axis=1)

    # First sample: farthest from center
    first_idx = int(np.argmax(distances_from_center))

    selected = [first_idx]
    selected_set = {first_idx}

    subject_counts = {w["subject_id"]: 0 for w in train_windows}
    subject_counts[train_windows[first_idx]["subject_id"]] += 1

    subject_cap = 2

    while len(selected) < sample_count:
        # Distance of remaining candidates to currently selected set
        cand_indices = [i for i in range(N) if i not in selected_set]

        # Filter by subject cap
        eligible_cands = [i for i in cand_indices if subject_counts[train_windows[i]["subject_id"]] < subject_cap]

        if not eligible_cands:
            # Relax subject cap
            subject_cap += 1
            continue

        selected_feats = norm_matrix[selected]  # shape (K, D)
        best_cand = None
        max_min_dist = -1.0

        for cand_i in eligible_cands:
            cand_f = norm_matrix[cand_i]
            dists = np.linalg.norm(selected_feats - cand_f, axis=1)
            min_d = np.min(dists)

            # Tie breaking: strictly larger min_d, or if tied (within 1e-9), choose smaller canonical index
            if min_d > max_min_dist + 1e-9:
                max_min_dist = min_d
                best_cand = cand_i
            elif abs(min_d - max_min_dist) <= 1e-9:
                if best_cand is None or cand_i < best_cand:
                    best_cand = cand_i

        selected.append(best_cand)
        selected_set.add(best_cand)
        subject_counts[train_windows[best_cand]["subject_id"]] += 1

    return sorted(selected)


def build_all_calibration_profiles(
    train_windows: List[Dict[str, Any]],
    preprocessed_train_x: np.ndarray,
    sample_count: int = CALIBRATION_SAMPLE_COUNT,
) -> Dict[str, List[int]]:
    """Build all 4 preregistered M-B5 calibration profiles."""
    prof_a = build_profile_a_train_order(train_windows, sample_count=sample_count)
    prof_b = build_profile_b_random_proportional(train_windows, sample_count=sample_count)
    prof_c = build_profile_c_class_balanced(train_windows, sample_count=sample_count)
    prof_d = build_profile_d_distribution_aware(train_windows, preprocessed_train_x, sample_count=sample_count)

    return {
        "M-B5_CAL_TRAIN_ORDER_120": prof_a,
        "M-B5_CAL_RANDOM_PROPORTIONAL_120": prof_b,
        "M-B5_CAL_CLASS_BALANCED_120": prof_c,
        "M-B5_CAL_DISTRIBUTION_AWARE_120": prof_d,
    }


def compute_tensor_statistics(data_x: np.ndarray) -> Dict[str, float]:
    """Compute comprehensive tensor statistics over a preprocessed float dataset."""
    flat = data_x.flatten()
    return {
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
        "mean": float(np.mean(flat)),
        "std": float(np.std(flat)),
        "p01": float(np.percentile(flat, 1)),
        "p05": float(np.percentile(flat, 5)),
        "p25": float(np.percentile(flat, 25)),
        "p50": float(np.percentile(flat, 50)),
        "p75": float(np.percentile(flat, 75)),
        "p95": float(np.percentile(flat, 95)),
        "p99": float(np.percentile(flat, 99)),
        "peak_abs": float(np.max(np.abs(flat))),
        "rms": float(np.sqrt(np.mean(flat ** 2))),
    }


def convert_model_to_strict_int8_tflite(
    model: tf.keras.Model,
    calib_x_float32: np.ndarray,
) -> Tuple[bytes, Dict[str, Any]]:
    """Convert float Keras model to strict INT8 TFLite model using specified representative float32 samples."""
    def representative_dataset_gen():
        for i in range(len(calib_x_float32)):
            sample = calib_x_float32[i : i + 1]  # shape (1, 250, 1)
            yield [sample]

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    tflite_model_bytes = converter.convert()

    # Inspect TFLite model using Interpreter
    interpreter = tf.lite.Interpreter(model_content=tflite_model_bytes)
    interpreter.allocate_tensors()

    in_details = interpreter.get_input_details()[0]
    out_details = interpreter.get_output_details()[0]

    op_details = interpreter._get_ops_details()
    op_types = [op["op_name"] for op in op_details]

    metadata = {
        "bytes": len(tflite_model_bytes),
        "sha256": hashlib.sha256(tflite_model_bytes).hexdigest(),
        "input_dtype": str(in_details["dtype"].__name__),
        "output_dtype": str(out_details["dtype"].__name__),
        "input_shape": [int(x) for x in in_details["shape"]],
        "output_shape": [int(x) for x in out_details["shape"]],
        "input_scale": float(in_details["quantization"][0]),
        "input_zero_point": int(in_details["quantization"][1]),
        "output_scale": float(out_details["quantization"][0]),
        "output_zero_point": int(out_details["quantization"][1]),
        "op_types": op_types,
        "select_tf_ops_count": sum(1 for t in op_types if "Flex" in t or "Select" in t),
    }

    return tflite_model_bytes, metadata


def evaluate_tflite_int8_model(
    tflite_model_bytes: bytes,
    val_x_float32: np.ndarray,
    val_y: np.ndarray,
    float_probs: np.ndarray,
) -> Dict[str, Any]:
    """Execute strict INT8 TFLite model on VALIDATION set and compute quantization metrics."""
    interpreter = tf.lite.Interpreter(model_content=tflite_model_bytes)
    interpreter.allocate_tensors()

    in_details = interpreter.get_input_details()[0]
    out_details = interpreter.get_output_details()[0]

    in_idx = in_details["index"]
    out_idx = out_details["index"]

    in_scale = float(in_details["quantization"][0])
    in_zp = int(in_details["quantization"][1])
    out_scale = float(out_details["quantization"][0])
    out_zp = int(out_details["quantization"][1])

    N = len(val_x_float32)
    int8_preds = []
    dequant_probs = []

    total_input_elements = 0
    saturated_input_elements = 0
    saturated_sample_count = 0

    endpoint_occupancy_count = 0
    total_output_elements = 0

    mismatch_samples = []

    for i in range(N):
        x_sample = val_x_float32[i : i + 1]  # shape (1, 250, 1)

        # Pre-clamp quantization math for input saturation calculation
        q_raw = np.round(x_sample / in_scale + in_zp)
        sat_mask = (q_raw < -128) | (q_raw > 127)
        sat_cnt = int(np.sum(sat_mask))

        total_input_elements += q_raw.size
        saturated_input_elements += sat_cnt
        if sat_cnt > 0:
            saturated_sample_count += 1

        x_int8 = np.clip(q_raw, -128, 127).astype(np.int8)

        interpreter.set_tensor(in_idx, x_int8)
        interpreter.invoke()
        y_int8 = interpreter.get_tensor(out_idx)  # shape (1, 3)

        # Output endpoint occupancy (-128 or 127)
        endpoint_mask = (y_int8 == -128) | (y_int8 == 127)
        endpoint_occupancy_count += int(np.sum(endpoint_mask))
        total_output_elements += y_int8.size

        # Dequantize output probabilities
        y_dequant = (y_int8.astype(np.float32) - out_zp) * out_scale
        pred_class = int(np.argmax(y_dequant, axis=1)[0])

        int8_preds.append(pred_class)
        dequant_probs.append(y_dequant[0].tolist())

        float_pred_class = int(np.argmax(float_probs[i]))
        abs_err = np.mean(np.abs(y_dequant[0] - float_probs[i]))

        if pred_class != float_pred_class or sat_cnt > 0 or abs_err > 0.05:
            mismatch_samples.append({
                "validation_sample_index": i,
                "float_pred_class": float_pred_class,
                "int8_pred_class": pred_class,
                "true_class": int(val_y[i]),
                "float_probs": float_probs[i].tolist(),
                "dequant_probs": y_dequant[0].tolist(),
                "abs_output_error": float(abs_err),
                "input_saturation_count": sat_cnt,
            })

    int8_preds_arr = np.array(int8_preds, dtype=int)
    dequant_probs_arr = np.array(dequant_probs, dtype=np.float32)

    # One-vs-rest confusion & metrics
    cm = compute_one_vs_rest_false_positives(val_y, int8_preds_arr)
    macro_f1 = float(np.mean([cm[c]["f1_score"] for c in LABEL_NAMES]))
    accuracy = float(np.mean(int8_preds_arr == val_y))
    min_rec = float(min(cm[c]["recall"] for c in LABEL_NAMES))
    apnea_rec = cm["APNEA"]["recall"]
    rapid_rec = cm["RAPID_OR_ABNORMAL"]["recall"]

    collapsed = (apnea_rec == 0.0) or (rapid_rec == 0.0) or (len(np.unique(int8_preds_arr)) < 3)

    pred_dist = {c: int(np.sum(int8_preds_arr == idx)) for idx, c in enumerate(LABEL_NAMES)}

    # Quantization error metrics vs Float baseline
    float_preds_arr = np.argmax(float_probs, axis=1)
    top1_agreement = float(np.mean(int8_preds_arr == float_preds_arr))
    dequantized_output_mae = float(np.mean(np.abs(dequant_probs_arr - float_probs)))
    dequantized_output_max_err = float(np.max(np.abs(dequant_probs_arr - float_probs)))

    input_saturation_ratio = float(saturated_input_elements / total_input_elements) if total_input_elements > 0 else 0.0
    output_endpoint_ratio = float(endpoint_occupancy_count / total_output_elements) if total_output_elements > 0 else 0.0

    return {
        "val_macro_f1": round(macro_f1, 6),
        "val_accuracy": round(accuracy, 6),
        "min_per_class_recall": round(min_rec, 6),
        "apnea_recall": round(apnea_rec, 6),
        "rapid_recall": round(rapid_rec, 6),
        "collapsed": collapsed,
        "prediction_distribution": pred_dist,
        "class_metrics": cm,
        "top1_agreement": round(top1_agreement, 6),
        "dequantized_output_mae": round(dequantized_output_mae, 6),
        "dequantized_output_max_err": round(dequantized_output_max_err, 6),
        "input_saturation_ratio": round(input_saturation_ratio, 6),
        "saturated_sample_count": saturated_sample_count,
        "output_endpoint_ratio": round(output_endpoint_ratio, 6),
        "mismatch_samples": mismatch_samples,
    }


def rank_cross_seed_calibration_profiles(
    cross_seed_results: List[Dict[str, Any]],
    eps: float = 1e-5,
) -> List[Dict[str, Any]]:
    """Rank calibration profiles based on the preregistered 8-criterion rule aggregated across seeds 42, 43, 44."""
    eligible_profiles = [p for p in cross_seed_results if p["eligible"]]

    def sort_key(p: Dict[str, Any]):
        # Criterion 1: LOWER worst-seed positive Macro F1 degradation
        c1 = p["worst_positive_macro_f1_degradation"]
        # Criterion 2: LOWER worst-seed max positive per-class recall degradation
        c2 = p["worst_positive_recall_degradation"]
        # Criterion 3: HIGHER minimum Top-1 agreement (negate for min-sorting)
        c3 = -p["min_top1_agreement"]
        # Criterion 4: LOWER max dequantized output MAE
        c4 = p["max_dequantized_output_mae"]
        # Criterion 5: LOWER max input saturation ratio
        c5 = p["max_input_saturation_ratio"]
        # Criterion 6: LOWER max output endpoint ratio
        c6 = p["max_output_endpoint_ratio"]
        # Criterion 7: Simpler policy preference
        policy_order = {
            "M-B5_CAL_TRAIN_ORDER_120": 1,
            "M-B5_CAL_RANDOM_PROPORTIONAL_120": 2,
            "M-B5_CAL_CLASS_BALANCED_120": 3,
            "M-B5_CAL_DISTRIBUTION_AWARE_120": 4,
        }
        c7 = policy_order.get(p["profile_id"], 99)
        # Criterion 8: Lexicographic profile ID
        c8 = p["profile_id"]

        return (c1, c2, c3, c4, c5, c6, c7, c8)

    ranked = sorted(eligible_profiles, key=sort_key)
    return ranked
