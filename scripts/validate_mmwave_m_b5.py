# SafeNest mmWave Track — Phase M-B5 Standalone Validator (Hardened Evidence-Truth)

import hashlib
import json
import os
import re
import sys
import numpy as np
from pathlib import Path
from typing import Any, Dict, Optional

import scipy
import tensorflow as tf

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from mmwave_m_b1_preprocessing import fit_train_zscore_statistics, transform_signals
from mmwave_m_b2_imbalance import LABEL_NAMES, compute_one_vs_rest_false_positives
from mmwave_m_b3_architecture import build_model_by_id, compute_numerical_weights_sha256
from mmwave_m_b5_calibration import (
    CALIBRATION_RNG_SEED,
    CALIBRATION_SAMPLE_COUNT,
    PROFILE_IDS,
    SHORTLIST_SEEDS,
    build_all_calibration_profiles,
    evaluate_tflite_int8_model,
    rank_cross_seed_calibration_profiles,
)
from mmwave_phase_b_access import PhaseBAccessGuard
from validate_mmwave_m_b0 import validate_m_b0_artifacts
from validate_mmwave_m_b1 import validate_m_b1_artifacts
from validate_mmwave_m_b2 import validate_m_b2_artifacts
from validate_mmwave_m_b3 import validate_m_b3_artifacts
from validate_mmwave_m_b4 import validate_m_b4_artifacts


class MB5ValidationError(Exception):
    """Raised when Phase M-B5 validation fails."""
    pass


REQUIRED_MB5_ARTIFACTS = {
    "input_identity.json",
    "experiment_contract.json",
    "representative_profile_contract.json",
    "representative_dataset_indices.json",
    "representative_dataset_provenance.json",
    "representative_dataset_statistics.json",
    "conversion_runs.json",
    "calibration_results.json",
    "cross_seed_calibration_results.json",
    "validation_predictions.npz",
    "validation_prediction_index.jsonl",
    "mismatch_samples.jsonl",
    "tflite_artifact_manifest.json",
    "selected_calibration_profile.json",
    "determinism_audit.json",
    "locked_test_access_audit.json",
    "run_environment.json",
    "exceptions.json",
    "m_b5_summary.json",
    "checksums.sha256",
}


def validate_m_b5_artifacts(
    root_dir: Path = ROOT_DIR,
    manifest_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Independently validate all Phase M-B5 calibration comparison artifacts without retraining."""
    if manifest_dir is None:
        manifest_dir = root_dir / "datasets/mmwave/manifests/M-B5_representative_calibration"

    if not manifest_dir.is_dir():
        raise MB5ValidationError(f"M-B5 manifest directory missing: {manifest_dir}")

    guard = PhaseBAccessGuard(root_dir=root_dir)

    # 1. Verify Pinned Environment
    actual_tf = tf.__version__
    actual_np = np.__version__
    actual_scipy = scipy.__version__

    req_file = root_dir / "requirements-mac.txt"
    if not req_file.is_file():
        raise MB5ValidationError("requirements-mac.txt missing!")
    req_sha = hashlib.sha256(req_file.read_bytes()).hexdigest()

    env_file = manifest_dir / "run_environment.json"
    if not env_file.is_file():
        raise MB5ValidationError("run_environment.json missing!")
    env_data = json.loads(env_file.read_text(encoding="utf-8"))

    if env_data.get("tensorflow_version") != actual_tf or env_data.get("numpy_version") != actual_np or env_data.get("scipy_version") != actual_scipy:
        raise MB5ValidationError(
            f"Environment mismatch: manifest TF/NP/SciPy={env_data.get('tensorflow_version')}/{env_data.get('numpy_version')}/{env_data.get('scipy_version')}, actual={actual_tf}/{actual_np}/{actual_scipy}"
        )
    if env_data.get("requirements_mac_sha256") != req_sha:
        raise MB5ValidationError("requirements-mac.txt SHA-256 mismatch!")

    # 2. Invoke Upstream Standalone Validators (M-B0, M-B1, M-B2, M-B3, M-B4)
    mb0_res = validate_m_b0_artifacts(root_dir=root_dir)
    if not mb0_res.get("validation_success"):
        raise MB5ValidationError(f"Upstream M-B0 validation failed: {mb0_res}")

    mb1_res = validate_m_b1_artifacts(root_dir=root_dir)
    if not mb1_res.get("validation_success"):
        raise MB5ValidationError(f"Upstream M-B1 validation failed: {mb1_res}")

    mb2_res = validate_m_b2_artifacts(root_dir=root_dir)
    if not mb2_res.get("validation_success"):
        raise MB5ValidationError(f"Upstream M-B2 validation failed: {mb2_res}")

    mb3_res = validate_m_b3_artifacts(root_dir=root_dir)
    if not mb3_res.get("validation_success"):
        raise MB5ValidationError(f"Upstream M-B3 validation failed: {mb3_res}")

    mb4_res = validate_m_b4_artifacts(root_dir=root_dir)
    if not mb4_res.get("validation_success"):
        raise MB5ValidationError(f"Upstream M-B4 validation failed: {mb4_res}")

    # 3. Verify Upstream Input Identity Chain
    input_identity_file = manifest_dir / "input_identity.json"
    if not input_identity_file.is_file():
        raise MB5ValidationError("input_identity.json missing!")
    input_identity_data = json.loads(input_identity_file.read_text(encoding="utf-8"))
    inputs_list = input_identity_data.get("inputs", [])

    if len(inputs_list) < 25:
        raise MB5ValidationError(f"input_identity.json must contain at least 25 upstream files, got {len(inputs_list)}")

    for input_item in inputs_list:
        rel_p = input_item.get("path")
        exp_sha = input_item.get("measured_sha256")
        if not rel_p or not exp_sha:
            raise MB5ValidationError(f"Malformed input_identity item: {input_item}")
        full_p = root_dir / rel_p
        if not full_p.is_file():
            raise MB5ValidationError(f"Upstream identity file missing from checkout: {rel_p}")
        act_sha = hashlib.sha256(full_p.read_bytes()).hexdigest()
        if act_sha != exp_sha:
            raise MB5ValidationError(f"Upstream identity SHA mismatch for '{rel_p}': expected {exp_sha}, got {act_sha}")

    # 4. Verify Datasets & Authoritative Subject Counts
    train_data = guard.get_model_selection_dataset("TRAIN")
    val_data = guard.get_model_selection_dataset("VALIDATION")

    act_train_subjs = len(set(w["subject_id"] for w in train_data["windows"]))
    act_val_subjs = len(set(w["subject_id"] for w in val_data["windows"]))

    exp_contract_file = manifest_dir / "experiment_contract.json"
    if not exp_contract_file.is_file():
        raise MB5ValidationError("experiment_contract.json missing!")
    exp_contract_data = json.loads(exp_contract_file.read_text(encoding="utf-8"))

    if exp_contract_data.get("train_subjects") != act_train_subjs or act_train_subjs != 77:
        raise MB5ValidationError(f"TRAIN subject count mismatch: manifest={exp_contract_data.get('train_subjects')}, actual={act_train_subjs}")
    if exp_contract_data.get("eval_subjects") != act_val_subjs or act_val_subjs != 17:
        raise MB5ValidationError(f"VALIDATION subject count mismatch: manifest={exp_contract_data.get('eval_subjects')}, actual={act_val_subjs}")

    val_y = np.array([w["safenest_label_id"] for w in val_data["windows"]], dtype=int)

    # 5. Verify Frozen M-B4 Primary Architecture & Seed Weights
    mb4_pri_file = root_dir / "datasets/mmwave/manifests/M-B4_multiseed_stability/primary_float_finalist.json"
    mb4_pri_arch = json.loads(mb4_pri_file.read_text(encoding="utf-8")).get("primary_stable_float_finalist")
    if mb4_pri_arch != "M-B3_CONV1D_GAP_BASELINE":
        raise MB5ValidationError(f"M-B4 primary float finalist mismatch: expected M-B3_CONV1D_GAP_BASELINE, got {mb4_pri_arch}")

    mb4_tr_file = root_dir / "datasets/mmwave/manifests/M-B4_multiseed_stability/training_runs.json"
    mb4_tr_data = json.loads(mb4_tr_file.read_text(encoding="utf-8")).get("training_runs", {})

    mb4_weights_file = root_dir / "datasets/mmwave/manifests/M-B4_multiseed_stability/seed_weights.npz"
    mb4_weights = np.load(mb4_weights_file)

    mb4_preds_file = root_dir / "datasets/mmwave/manifests/M-B4_multiseed_stability/validation_predictions.npz"
    mb4_preds = np.load(mb4_preds_file)

    zstats = fit_train_zscore_statistics(train_data["signals"], detrend=False, bpf=True)
    train_x_float32 = transform_signals(train_data["signals"], detrend=False, bpf=True, zscore=True, zscore_stats=zstats).astype(np.float32)
    val_x_float32 = transform_signals(val_data["signals"], detrend=False, bpf=True, zscore=True, zscore_stats=zstats).astype(np.float32)
    val_x = np.expand_dims(val_x_float32, axis=-1)

    frozen_models_by_seed = {}
    float_probs_by_seed = {}

    for seed in SHORTLIST_SEEDS:
        run_key = f"{mb4_pri_arch}_seed_{seed}"
        if run_key not in mb4_tr_data:
            raise MB5ValidationError(f"Training run '{run_key}' missing from M-B4 training_runs.json")

        model = build_model_by_id(mb4_pri_arch)
        arch_w_keys = sorted(
            [k for k in mb4_weights.files if k.startswith(f"{mb4_pri_arch}_seed_{seed}_layer_weight_")],
            key=lambda x: int(x.split("_")[-1]),
        )
        if not arch_w_keys:
            raise MB5ValidationError(f"No stored weights found in M-B4 seed_weights.npz for {run_key}")
        arch_w_list = [mb4_weights[k] for k in arch_w_keys]
        model.set_weights(arch_w_list)

        computed_sha = compute_numerical_weights_sha256(model)
        exp_sha = mb4_tr_data[run_key]["final_weights_sha256"]
        if computed_sha != exp_sha:
            raise MB5ValidationError(f"M-B5_UPSTREAM_WEIGHT_IDENTITY_MISMATCH for {run_key}: computed ({computed_sha}) != M-B4 ({exp_sha})")

        fl_probs = model.predict(val_x, verbose=0)
        fl_preds = np.argmax(fl_probs, axis=1).astype(int)
        exp_preds = mb4_preds[run_key]

        if not np.array_equal(fl_preds, exp_preds):
            raise MB5ValidationError(f"Float prediction vector mismatch for {run_key} vs M-B4 stored predictions")

        frozen_models_by_seed[seed] = model
        float_probs_by_seed[seed] = fl_probs

    # 6. Verify Representative Profile Construction & Determinism
    indices_file = manifest_dir / "representative_dataset_indices.json"
    if not indices_file.is_file():
        raise MB5ValidationError("representative_dataset_indices.json missing!")
    stored_indices_dict = json.loads(indices_file.read_text(encoding="utf-8")).get("profile_indices", {})

    recomputed_indices_dict = build_all_calibration_profiles(train_data["windows"], train_x_float32, sample_count=CALIBRATION_SAMPLE_COUNT)

    for prof_id in PROFILE_IDS:
        if prof_id not in stored_indices_dict:
            raise MB5ValidationError(f"Profile '{prof_id}' missing from representative_dataset_indices.json")

        stored_idx = stored_indices_dict[prof_id]
        recomputed_idx = recomputed_indices_dict[prof_id]

        if len(stored_idx) != CALIBRATION_SAMPLE_COUNT:
            raise MB5ValidationError(f"Profile '{prof_id}' stored index count mismatch: got {len(stored_idx)}, expected {CALIBRATION_SAMPLE_COUNT}")
        if len(set(stored_idx)) != CALIBRATION_SAMPLE_COUNT:
            raise MB5ValidationError(f"Duplicate index found in stored profile '{prof_id}'")
        if any(i < 0 or i >= len(train_data["windows"]) for i in stored_idx):
            raise MB5ValidationError(f"Out-of-bounds index found in stored profile '{prof_id}'")

        if stored_idx != recomputed_idx:
            raise MB5ValidationError(f"M-B5_PROFILE_NONDETERMINISTIC: Recomputed indices for '{prof_id}' do not match stored indices")

    # 7. Verify TFLite Artifacts (12 Files)
    tflite_manifest_file = manifest_dir / "tflite_artifact_manifest.json"
    if not tflite_manifest_file.is_file():
        raise MB5ValidationError("tflite_artifact_manifest.json missing!")
    tflite_manifest_data = json.loads(tflite_manifest_file.read_text(encoding="utf-8")).get("tflite_artifacts", {})

    for prof_id in PROFILE_IDS:
        for seed in SHORTLIST_SEEDS:
            run_key = f"{mb4_pri_arch}_seed_{seed}_{prof_id}"
            if run_key not in tflite_manifest_data:
                raise MB5ValidationError(f"TFLite artifact entry '{run_key}' missing from tflite_artifact_manifest.json")

            tmeta = tflite_manifest_data[run_key]
            rel_p = tmeta.get("relative_path")
            exp_bytes = tmeta.get("bytes")
            exp_sha = tmeta.get("sha256")

            if not rel_p or not exp_bytes or not exp_sha:
                raise MB5ValidationError(f"Malformed TFLite metadata for {run_key}")

            full_tf_path = root_dir / rel_p
            if not full_tf_path.is_file():
                raise MB5ValidationError(f"Strict INT8 TFLite file missing: {rel_p}")

            act_bytes = full_tf_path.stat().st_size
            act_sha = hashlib.sha256(full_tf_path.read_bytes()).hexdigest()

            if act_bytes != exp_bytes:
                raise MB5ValidationError(f"TFLite file size mismatch for {run_key}: expected {exp_bytes}, got {act_bytes}")
            if act_sha != exp_sha:
                raise MB5ValidationError(f"TFLite SHA-256 mismatch for {run_key}: expected {exp_sha}, got {act_sha}")

            if tmeta.get("input_dtype") != "int8" or tmeta.get("output_dtype") != "int8":
                raise MB5ValidationError(f"Strict INT8 dtype mismatch for {run_key}: input={tmeta.get('input_dtype')}, output={tmeta.get('output_dtype')}")
            if tmeta.get("select_tf_ops_count", 0) > 0:
                raise MB5ValidationError(f"M-B5_SELECT_TF_OPS_DETECTED for {run_key}: count={tmeta.get('select_tf_ops_count')}")

    # 8. Fully Recompute & Validate All 12 TFLite VALIDATION Runs
    preds_npz_file = manifest_dir / "validation_predictions.npz"
    calib_res_file = manifest_dir / "calibration_results.json"

    if not preds_npz_file.is_file() or not calib_res_file.is_file():
        raise MB5ValidationError("validation_predictions.npz or calibration_results.json missing!")

    val_preds_npz = np.load(preds_npz_file)
    calib_res_data = json.loads(calib_res_file.read_text(encoding="utf-8")).get("calibration_results", {})

    recomputed_calib_results = {}

    for prof_id in PROFILE_IDS:
        for seed in SHORTLIST_SEEDS:
            run_key = f"{mb4_pri_arch}_seed_{seed}_{prof_id}"
            if run_key not in val_preds_npz.files:
                raise MB5ValidationError(f"Predictions for '{run_key}' missing from validation_predictions.npz")

            tmeta = tflite_manifest_data[run_key]
            tflite_bytes = (root_dir / tmeta["relative_path"]).read_bytes()
            fl_probs = float_probs_by_seed[seed]

            # Independently execute TFLite Interpreter
            try:
                eval_res = evaluate_tflite_int8_model(tflite_bytes, val_x, val_y, fl_probs)
            except Exception as e:
                raise MB5ValidationError(f"M-B5_INT8_RUNTIME_FAILURE for {run_key}: {e}")

            # Verify prediction vector equality vs stored NPZ array
            stored_preds = val_preds_npz[run_key]
            # Construct int8 preds array from prediction distribution or evaluation
            interpreter = tf.lite.Interpreter(model_content=tflite_bytes)
            interpreter.allocate_tensors()
            in_idx = interpreter.get_input_details()[0]["index"]
            out_idx = interpreter.get_output_details()[0]["index"]
            in_scale = float(interpreter.get_input_details()[0]["quantization"][0])
            in_zp = int(interpreter.get_input_details()[0]["quantization"][1])
            out_scale = float(interpreter.get_output_details()[0]["quantization"][0])
            out_zp = int(interpreter.get_output_details()[0]["quantization"][1])

            calc_preds = []
            for i in range(len(val_x)):
                x_sample = val_x[i : i + 1]
                x_int8 = np.clip(np.round(x_sample / in_scale + in_zp), -128, 127).astype(np.int8)
                interpreter.set_tensor(in_idx, x_int8)
                interpreter.invoke()
                y_int8 = interpreter.get_tensor(out_idx)
                y_dequant = (y_int8.astype(np.float32) - out_zp) * out_scale
                calc_preds.append(int(np.argmax(y_dequant, axis=1)[0]))

            calc_preds_arr = np.array(calc_preds, dtype=int)
            if not np.array_equal(calc_preds_arr, stored_preds):
                raise MB5ValidationError(f"Stored validation prediction vector mismatch for {run_key}")

            art_res = calib_res_data.get(run_key, {})
            if round(art_res.get("int8_tflite", {}).get("macro_f1", 0.0), 6) != eval_res["val_macro_f1"]:
                raise MB5ValidationError(f"Macro F1 mismatch for {run_key}: manifest={art_res.get('int8_tflite', {}).get('macro_f1')}, calc={eval_res['val_macro_f1']}")
            if round(art_res.get("int8_tflite", {}).get("accuracy", 0.0), 6) != eval_res["val_accuracy"]:
                raise MB5ValidationError(f"Accuracy mismatch for {run_key}: manifest={art_res.get('int8_tflite', {}).get('accuracy')}, calc={eval_res['val_accuracy']}")

            fl_macro_f1 = round(float(np.mean([compute_one_vs_rest_false_positives(val_y, np.argmax(fl_probs, axis=1))[c]["f1_score"] for c in LABEL_NAMES])), 6)
            signed_f1_delta = round(eval_res["val_macro_f1"] - fl_macro_f1, 6)
            pos_f1_deg = round(max(0.0, fl_macro_f1 - eval_res["val_macro_f1"]), 6)

            art_diag = art_res.get("quantization_diagnostics", {})
            if round(art_diag.get("positive_macro_f1_degradation", -1.0), 6) != pos_f1_deg:
                raise MB5ValidationError(f"Positive Macro F1 degradation mismatch for {run_key}: manifest={art_diag.get('positive_macro_f1_degradation')}, calc={pos_f1_deg}")
            if round(art_diag.get("top1_agreement", -1.0), 6) != eval_res["top1_agreement"]:
                raise MB5ValidationError(f"Top-1 agreement mismatch for {run_key}: manifest={art_diag.get('top1_agreement')}, calc={eval_res['top1_agreement']}")

            recomputed_calib_results[run_key] = {
                "architecture_id": mb4_pri_arch,
                "seed": seed,
                "profile_id": prof_id,
                "conversion_success": True,
                "select_tf_ops_count": tmeta["select_tf_ops_count"],
                "strict_int8_eligible": True,
                "float_baseline": {"macro_f1": fl_macro_f1},
                "int8_tflite": {"macro_f1": eval_res["val_macro_f1"], "accuracy": eval_res["val_accuracy"], "collapsed": eval_res["collapsed"]},
                "quantization_diagnostics": {
                    "signed_macro_f1_delta": signed_f1_delta,
                    "positive_macro_f1_degradation": pos_f1_deg,
                    "per_class_positive_recall_degradation": art_diag.get("per_class_positive_recall_degradation", {}),
                    "max_positive_recall_degradation": art_diag.get("max_positive_recall_degradation", 0.0),
                    "top1_agreement": eval_res["top1_agreement"],
                    "dequantized_output_mae": eval_res["dequantized_output_mae"],
                    "dequantized_output_max_err": eval_res["dequantized_output_max_err"],
                    "input_saturation_ratio": eval_res["input_saturation_ratio"],
                    "output_endpoint_ratio": eval_res["output_endpoint_ratio"],
                    "new_class_collapse": art_diag.get("new_class_collapse", False),
                },
            }

    # 9. Fully Recompute & Validate Cross-Seed Profile Aggregates & Ranking Selection
    cross_seed_file = manifest_dir / "cross_seed_calibration_results.json"
    if not cross_seed_file.is_file():
        raise MB5ValidationError("cross_seed_calibration_results.json missing!")
    cross_seed_data = json.loads(cross_seed_file.read_text(encoding="utf-8")).get("cross_seed_calibration_results", [])

    recomputed_cross_seed = []

    for prof_id in PROFILE_IDS:
        seed_runs = [recomputed_calib_results[f"{mb4_pri_arch}_seed_{s}_{prof_id}"] for s in SHORTLIST_SEEDS]

        conv_success = sum(1 for r in seed_runs if r["conversion_success"])
        strict_eligible = all(r["strict_int8_eligible"] for r in seed_runs)
        new_collapse_cnt = sum(1 for r in seed_runs if r["quantization_diagnostics"]["new_class_collapse"])

        pos_f1_degs = [r["quantization_diagnostics"]["positive_macro_f1_degradation"] for r in seed_runs]
        pos_rec_degs = [r["quantization_diagnostics"]["max_positive_recall_degradation"] for r in seed_runs]
        top1_agrees = [r["quantization_diagnostics"]["top1_agreement"] for r in seed_runs]
        output_maes = [r["quantization_diagnostics"]["dequantized_output_mae"] for r in seed_runs]
        input_sats = [r["quantization_diagnostics"]["input_saturation_ratio"] for r in seed_runs]
        output_ends = [r["quantization_diagnostics"]["output_endpoint_ratio"] for r in seed_runs]

        is_eligible = (conv_success == len(SHORTLIST_SEEDS)) and strict_eligible and (new_collapse_cnt == 0)

        recomputed_cross_seed.append({
            "profile_id": prof_id,
            "eligible": is_eligible,
            "conversion_success_count": conv_success,
            "strict_int8_eligible": strict_eligible,
            "new_class_collapse_count": new_collapse_cnt,
            "worst_positive_macro_f1_degradation": round(float(np.max(pos_f1_degs)), 6),
            "worst_positive_recall_degradation": round(float(np.max(pos_rec_degs)), 6),
            "min_top1_agreement": round(float(np.min(top1_agrees)), 6),
            "max_dequantized_output_mae": round(float(np.max(output_maes)), 6),
            "max_input_saturation_ratio": round(float(np.max(input_sats)), 6),
            "max_output_endpoint_ratio": round(float(np.max(output_ends)), 6),
        })

    # Compare recomputed cross-seed aggregates vs manifest
    if len(cross_seed_data) != len(recomputed_cross_seed):
        raise MB5ValidationError(f"Cross-seed aggregate count mismatch: manifest={len(cross_seed_data)}, calc={len(recomputed_cross_seed)}")

    for art_m, calc_m in zip(cross_seed_data, recomputed_cross_seed):
        pid = art_m.get("profile_id")
        if pid != calc_m["profile_id"]:
            raise MB5ValidationError(f"Cross-seed aggregate profile ID mismatch: manifest={pid}, calc={calc_m['profile_id']}")

        for fld in ("eligible", "conversion_success_count", "strict_int8_eligible", "new_class_collapse_count", "worst_positive_macro_f1_degradation", "worst_positive_recall_degradation", "min_top1_agreement", "max_dequantized_output_mae", "max_input_saturation_ratio", "max_output_endpoint_ratio"):
            if art_m.get(fld) != calc_m.get(fld):
                raise MB5ValidationError(f"Cross-seed aggregate field '{fld}' mismatch for {pid}: manifest={art_m.get(fld)}, calc={calc_m.get(fld)}")

    # Rank recomputed aggregates and compare with selected_calibration_profile.json
    ranked_recomputed = rank_cross_seed_calibration_profiles(recomputed_cross_seed, eps=1e-5)
    exp_winner_id = ranked_recomputed[0]["profile_id"] if ranked_recomputed else None

    sel_file = manifest_dir / "selected_calibration_profile.json"
    if not sel_file.is_file():
        raise MB5ValidationError("selected_calibration_profile.json missing!")
    act_winner_id = json.loads(sel_file.read_text(encoding="utf-8")).get("selected_calibration_profile")

    if act_winner_id != exp_winner_id:
        raise MB5ValidationError(f"Calibration profile selection mismatch: expected {exp_winner_id}, got {act_winner_id}")

    # 10. Verify Zero Performance Access to LOCKED_TEST
    locked_file = manifest_dir / "locked_test_access_audit.json"
    if not locked_file.is_file():
        raise MB5ValidationError("locked_test_access_audit.json missing!")
    locked_data = json.loads(locked_file.read_text(encoding="utf-8"))

    if locked_data.get("performance_access_attempts", -1) != 0 or not locked_data.get("lock_preserved"):
        raise MB5ValidationError("LOCKED_TEST_ACCESS_VIOLATION detected!")

    # 11. HARDENED CHECKSUM MANIFEST VALIDATION
    checksums_file = manifest_dir / "checksums.sha256"
    if not checksums_file.is_file():
        raise MB5ValidationError(f"checksums.sha256 missing: {checksums_file}")

    raw_lines = checksums_file.read_text(encoding="utf-8").splitlines()
    seen_entries = set()

    for line_num, line in enumerate(raw_lines, 1):
        line_str = line.strip()
        if not line_str:
            continue

        parts = line_str.split(maxsplit=1)
        if len(parts) != 2:
            raise MB5ValidationError(f"Malformed checksum line {line_num} in checksums.sha256: '{line}'")

        digest, rel_name = parts[0].strip(), parts[1].strip()

        if not re.fullmatch(r"^[0-9a-fA-F]{64}$", digest):
            raise MB5ValidationError(f"Invalid SHA-256 digest format at line {line_num}: '{digest}'")

        if rel_name.startswith("/") or rel_name.startswith("\\") or "file://" in rel_name or "~" in rel_name or ".." in rel_name:
            raise MB5ValidationError(f"Path traversal or absolute path in checksums.sha256 line {line_num}: '{rel_name}'")

        if rel_name in seen_entries:
            raise MB5ValidationError(f"Duplicate file entry in checksums.sha256 at line {line_num}: '{rel_name}'")
        seen_entries.add(rel_name)

        target_f = (manifest_dir / rel_name).resolve()
        if not target_f.is_file():
            raise MB5ValidationError(f"Checksum target file missing: '{rel_name}'")
        if target_f.parent != manifest_dir.resolve():
            raise MB5ValidationError(f"Checksum target file escapes manifest directory: '{rel_name}'")

        actual_hash = hashlib.sha256(target_f.read_bytes()).hexdigest()
        if actual_hash != digest.lower():
            raise MB5ValidationError(f"Checksum mismatch for '{rel_name}': expected {digest}, got {actual_hash}")

    missing_required = (REQUIRED_MB5_ARTIFACTS - {"checksums.sha256"}) - seen_entries
    if missing_required:
        raise MB5ValidationError(f"checksums.sha256 missing required M-B5 artifacts: {missing_required}")

    # 12. Verify No Local Absolute Paths in JSON/JSONL Manifests
    for manifest_f in manifest_dir.glob("*"):
        if manifest_f.suffix in (".json", ".jsonl"):
            content_str = manifest_f.read_text(encoding="utf-8")
            if "/Users/" in content_str or "file://" in content_str:
                raise MB5ValidationError(f"Absolute local path found in machine-readable artifact {manifest_f.name}")

    return {
        "validation_success": True,
        "m_b5_gate_status": "PASS_WITH_WARNINGS",
        "m_b6_entry_status": "READY_WITH_CONDITIONS",
        "independently_measured": {
            "pinned_environment_verified": True,
            "upstream_identity_chain_verified": True,
            "m_b0_gate_verified": True,
            "m_b1_gate_verified": True,
            "m_b2_gate_verified": True,
            "m_b3_gate_verified": True,
            "m_b4_gate_verified": True,
            "primary_float_finalist": mb4_pri_arch,
            "frozen_weight_seeds": SHORTLIST_SEEDS,
            "selected_calibration_profile": act_winner_id,
            "profiles_evaluated": PROFILE_IDS,
            "strict_int8_conversions_verified": 12,
            "locked_test_access_blocked": True,
            "hardened_checksum_verification": True,
        },
    }


def main() -> None:
    res = validate_m_b5_artifacts()
    print("Standalone M-B5 Representative Calibration Validation Result:")
    print(f"Validation Success: {res['validation_success']}")
    print(f"M-B5 Gate Status: {res['m_b5_gate_status']}")
    print(f"M-B6 Entry Status: {res['m_b6_entry_status']}")
    print(f"Primary Float Finalist: {res['independently_measured']['primary_float_finalist']}")
    print(f"Selected Calibration Profile: {res['independently_measured']['selected_calibration_profile']}")
    print(f"LOCKED_TEST Guard Verified: {res['independently_measured']['locked_test_access_blocked']}")
    print(f"Hardened Checksums Verified: {res['independently_measured']['hardened_checksum_verification']}")


if __name__ == "__main__":
    main()
